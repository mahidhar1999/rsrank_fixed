-- ================================================================
-- RSRank Stored Functions v2.0
-- Run after schema: psql -f 002_functions.sql
-- ================================================================

-- ----------------------------------------------------------------
-- HELPER: Get Nifty 50 index ID (cached)
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_nifty50_id()
RETURNS INT LANGUAGE SQL STABLE AS $$
    SELECT id FROM indices WHERE index_name = 'Nifty 50' LIMIT 1;
$$;

-- ----------------------------------------------------------------
-- FUNCTION: build_universe(p_date DATE)
-- Selects Top 750 equity stocks by 30-day avg traded value
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION build_universe(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO universe_daily (trade_date, stock_id, liquidity_rank, avg_traded_value_30)
    SELECT
        p_date,
        ranked.stock_id,
        ROW_NUMBER() OVER (ORDER BY ranked.avg_tv DESC),
        ROUND(ranked.avg_tv, 0)
    FROM (
        SELECT
            sp.stock_id,
            AVG(sp.traded_value) AS avg_tv
        FROM stock_prices sp
        JOIN stocks_master sm ON sm.id = sp.stock_id
        WHERE sp.trade_date <= p_date
          AND sp.trade_date > p_date - INTERVAL '35 days'
          AND sm.instrument_type = 'EQUITY'
          AND sm.is_active = TRUE
        GROUP BY sp.stock_id
        HAVING COUNT(DISTINCT sp.trade_date) >= 12
    ) ranked
    WHERE ranked.avg_tv IS NOT NULL
    ORDER BY ranked.avg_tv DESC
    LIMIT 750
    ON CONFLICT (trade_date, stock_id) DO NOTHING;
END;
$$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_daily_returns(p_date DATE)
-- Computes 65D and 125D returns for universe stocks + all indices
-- Uses LATERAL JOIN to get price from exactly N trading days ago
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_daily_returns(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE lookback INT;
BEGIN
  FOREACH lookback IN ARRAY ARRAY[65, 125] LOOP
    INSERT INTO returns (entity_type, entity_id, lookback_days, trade_date, return_value)
    SELECT 'stock', curr.stock_id, lookback, p_date,
      CASE WHEN past.close IS NOT NULL AND past.close > 0
           THEN ROUND(((curr.close / past.close) - 1)::NUMERIC, 6) ELSE NULL END
    FROM stock_prices curr
    JOIN LATERAL (
      SELECT sp2.close FROM stock_prices sp2
      WHERE sp2.stock_id = curr.stock_id AND sp2.trade_date < p_date
      ORDER BY sp2.trade_date DESC OFFSET (lookback - 1) LIMIT 1
    ) past ON TRUE
    WHERE curr.trade_date = p_date
      AND curr.stock_id IN (SELECT stock_id FROM universe_daily WHERE trade_date = p_date)
    ON CONFLICT (entity_type, entity_id, lookback_days, trade_date)
    DO UPDATE SET return_value = EXCLUDED.return_value;

    INSERT INTO returns (entity_type, entity_id, lookback_days, trade_date, return_value)
    SELECT 'index', curr.index_id, lookback, p_date,
      CASE WHEN past.close IS NOT NULL AND past.close > 0
           THEN ROUND(((curr.close / past.close) - 1)::NUMERIC, 6) ELSE NULL END
    FROM index_prices curr
    JOIN LATERAL (
      SELECT ip2.close FROM index_prices ip2
      WHERE ip2.index_id = curr.index_id AND ip2.trade_date < p_date
      ORDER BY ip2.trade_date DESC OFFSET (lookback - 1) LIMIT 1
    ) past ON TRUE
    WHERE curr.trade_date = p_date
    ON CONFLICT (entity_type, entity_id, lookback_days, trade_date)
    DO UPDATE SET return_value = EXCLUDED.return_value;
  END LOOP;
END; $$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_daily_rs(p_date DATE)
-- 3-Layer RS computation:
--   A) rs_vs_market       = (1 + stock_ret) / (1 + nifty_ret)
--   B) sector_rs_vs_market = (1 + sector_ret) / (1 + nifty_ret)
--   C) rs_vs_sector       = (1 + stock_ret) / (1 + sector_ret)
-- rs_combined = 0.75 * rs65 + 0.25 * rs125
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_daily_rs(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_nifty_id INT;
BEGIN
  v_nifty_id := get_nifty50_id();
  INSERT INTO rs_values (stock_id, lookback_days, trade_date, rs_vs_market, rs_vs_sector, sector_rs_vs_market)
  SELECT u.stock_id, r_stock.lookback_days, p_date,
    CASE WHEN r_nifty.return_value IS NOT NULL AND r_nifty.return_value > -1
         THEN ROUND(((1 + r_stock.return_value) / (1 + r_nifty.return_value))::NUMERIC, 6) ELSE NULL END,
    CASE WHEN r_sector.return_value IS NOT NULL AND r_sector.return_value > -1
         THEN ROUND(((1 + r_stock.return_value) / (1 + r_sector.return_value))::NUMERIC, 6) ELSE NULL END,
    CASE WHEN r_nifty.return_value IS NOT NULL AND r_nifty.return_value > -1
          AND r_sector.return_value IS NOT NULL
         THEN ROUND(((1 + r_sector.return_value) / (1 + r_nifty.return_value))::NUMERIC, 6) ELSE NULL END
  FROM universe_daily u
  JOIN returns r_stock ON r_stock.entity_type = 'stock' AND r_stock.entity_id = u.stock_id AND r_stock.trade_date = p_date
  JOIN returns r_nifty ON r_nifty.entity_type = 'index' AND r_nifty.entity_id = v_nifty_id
                       AND r_nifty.lookback_days = r_stock.lookback_days AND r_nifty.trade_date = p_date
  LEFT JOIN stock_index_membership sim ON sim.stock_id = u.stock_id AND sim.is_primary = TRUE
    AND sim.effective_from <= p_date AND (sim.effective_to IS NULL OR sim.effective_to >= p_date)
  LEFT JOIN returns r_sector ON r_sector.entity_type = 'index' AND r_sector.entity_id = sim.index_id
    AND r_sector.lookback_days = r_stock.lookback_days AND r_sector.trade_date = p_date
  WHERE u.trade_date = p_date AND r_stock.return_value IS NOT NULL
  ON CONFLICT (stock_id, lookback_days, trade_date)
  DO UPDATE SET rs_vs_market = EXCLUDED.rs_vs_market,
                rs_vs_sector = EXCLUDED.rs_vs_sector,
                sector_rs_vs_market = EXCLUDED.sector_rs_vs_market;

  UPDATE rs_values v65
  SET rs_combined = ROUND((0.75 * v65.rs_vs_market + 0.25 * v125.rs_vs_market)::NUMERIC, 6)
  FROM rs_values v125
  WHERE v65.stock_id = v125.stock_id AND v65.trade_date = p_date AND v125.trade_date = p_date
    AND v65.lookback_days = 65 AND v125.lookback_days = 125
    AND v65.rs_vs_market IS NOT NULL AND v125.rs_vs_market IS NOT NULL;
END; $$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_rs_rankings(p_date DATE)
-- Converts RS ratios to percentile ranks 0-100
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_rs_rankings(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO rs_rankings (stock_id, trade_date, pct_vs_market, pct_vs_sector, sector_pct_vs_market, pct_combined)
  SELECT stock_id, p_date,
    ROUND((PERCENT_RANK() OVER (ORDER BY rs_vs_market        NULLS FIRST) * 100)::NUMERIC, 1),
    ROUND((PERCENT_RANK() OVER (ORDER BY rs_vs_sector        NULLS FIRST) * 100)::NUMERIC, 1),
    ROUND((PERCENT_RANK() OVER (ORDER BY sector_rs_vs_market NULLS FIRST) * 100)::NUMERIC, 1),
    ROUND((PERCENT_RANK() OVER (ORDER BY rs_combined         NULLS FIRST) * 100)::NUMERIC, 1)
  FROM rs_values WHERE trade_date = p_date AND lookback_days = 65
  ON CONFLICT (stock_id, trade_date)
  DO UPDATE SET pct_vs_market = EXCLUDED.pct_vs_market,
                pct_vs_sector = EXCLUDED.pct_vs_sector,
                sector_pct_vs_market = EXCLUDED.sector_pct_vs_market,
                pct_combined = EXCLUDED.pct_combined;
END; $$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_rs_acceleration(p_date DATE)
-- ΔRS = RS_today - RS_10_trading_days_ago
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_rs_acceleration(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO rs_acceleration (stock_id, trade_date, delta_rs_market, delta_rs_sector, delta_combined)
  SELECT curr.stock_id, p_date,
    ROUND((curr.rs_vs_market - past.rs_vs_market)::NUMERIC, 4),
    ROUND((curr.rs_vs_sector - past.rs_vs_sector)::NUMERIC, 4),
    ROUND((curr.rs_combined  - past.rs_combined )::NUMERIC, 4)
  FROM rs_values curr
  JOIN LATERAL (
    SELECT rs2.rs_vs_market, rs2.rs_vs_sector, rs2.rs_combined
    FROM rs_values rs2
    WHERE rs2.stock_id = curr.stock_id AND rs2.lookback_days = 65
      AND rs2.trade_date < p_date AND rs2.rs_combined IS NOT NULL
    ORDER BY rs2.trade_date DESC OFFSET 9 LIMIT 1
  ) past ON TRUE
  WHERE curr.trade_date = p_date AND curr.lookback_days = 65 AND curr.rs_combined IS NOT NULL
  ON CONFLICT (stock_id, trade_date)
  DO UPDATE SET delta_rs_market = EXCLUDED.delta_rs_market,
                delta_rs_sector = EXCLUDED.delta_rs_sector,
                delta_combined  = EXCLUDED.delta_combined;
END; $$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_leadership_stability(p_date DATE)
-- % of last 30 trading days the stock ranked in top 30th pct
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_leadership_stability(p_date DATE)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO leadership_stability_30d (stock_id, trade_date, stability_score)
  SELECT u.stock_id, p_date,
    ROUND((100.0 * SUM(CASE WHEN rr.pct_combined >= 70 THEN 1 ELSE 0 END)::NUMERIC
               / NULLIF(COUNT(*), 0)), 1)
  FROM universe_daily u
  JOIN LATERAL (
    SELECT pct_combined FROM rs_rankings
    WHERE stock_id = u.stock_id AND trade_date <= p_date
    ORDER BY trade_date DESC LIMIT 30
  ) rr ON TRUE
  WHERE u.trade_date = p_date
  GROUP BY u.stock_id
  ON CONFLICT (stock_id, trade_date)
  DO UPDATE SET stability_score = EXCLUDED.stability_score;
END; $$;

-- ----------------------------------------------------------------
-- FUNCTION: compute_daily_metrics(p_date DATE)
-- Master orchestrator — call this from Python pipeline
-- ----------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_daily_metrics(p_date DATE)
RETURNS TEXT LANGUAGE plpgsql AS $$
BEGIN
    PERFORM build_universe(p_date);
    PERFORM compute_daily_returns(p_date);
    PERFORM compute_daily_rs(p_date);
    PERFORM compute_rs_rankings(p_date);
    PERFORM compute_rs_acceleration(p_date);
    PERFORM compute_leadership_stability(p_date);
    RETURN 'OK: computed metrics for ' || p_date::TEXT;
END;
$$;

-- ----------------------------------------------------------------
-- PROCEDURE: apply_corporate_actions()
-- Adjusts historical prices for BONUS and SPLIT events
--   BONUS A:B  → adjustment = A / (A + B)  [price goes down]
--   SPLIT 1:N  → adjustment = 1 / N        [price goes down]
-- ----------------------------------------------------------------
CREATE OR REPLACE PROCEDURE apply_corporate_actions()
LANGUAGE plpgsql AS $$
DECLARE
    rec           RECORD;
    v_stock_id    INT;
    v_adjustment  NUMERIC;
BEGIN
    FOR rec IN
        SELECT ca.id, ca.symbol, ca.action_type,
               ca.ratio_old, ca.ratio_new, ca.ex_date,
               sm.id AS stock_id
        FROM   corporate_actions ca
        JOIN   stocks_master sm ON sm.symbol = ca.symbol
        WHERE  ca.processed = FALSE
        ORDER  BY ca.ex_date ASC
    LOOP
        v_stock_id := rec.stock_id;

        IF rec.action_type = 'BONUS' THEN
            v_adjustment := rec.ratio_old::NUMERIC
                          / (rec.ratio_old + rec.ratio_new)::NUMERIC;
        ELSIF rec.action_type = 'SPLIT' THEN
            v_adjustment := rec.ratio_old::NUMERIC / rec.ratio_new::NUMERIC;
        ELSE
            CONTINUE;
        END IF;

        -- Adjust all prices BEFORE ex_date
        UPDATE stock_prices
        SET    close = ROUND(close * v_adjustment, 4)
        WHERE  stock_id   = v_stock_id
          AND  trade_date < rec.ex_date;

        UPDATE corporate_actions
        SET    processed    = TRUE,
               processed_at = NOW()
        WHERE  id = rec.id;

        RAISE NOTICE 'Applied % for % (factor: %)', rec.action_type, rec.symbol, v_adjustment;
    END LOOP;
END;
$$;

\echo '✅ Functions created successfully'
