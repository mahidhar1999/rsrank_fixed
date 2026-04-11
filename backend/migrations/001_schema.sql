-- ============================================================
-- RSRank Complete Database Schema
-- Version 2.0 - Production Ready
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- 1. USERS & AUTH
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    plan                VARCHAR(20) NOT NULL DEFAULT 'free'
                            CHECK (plan IN ('free','pro','enterprise')),
    razorpay_order_id   VARCHAR(100),
    razorpay_payment_id VARCHAR(100),
    razorpay_sub_id     VARCHAR(100),
    status              VARCHAR(20) DEFAULT 'pending'
                            CHECK (status IN ('pending','active','cancelled','expired')),
    amount_paise        INT,
    valid_from          TIMESTAMPTZ,
    valid_until         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. MASTER TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS indices (
    id              SERIAL PRIMARY KEY,
    index_name      VARCHAR(100) UNIQUE NOT NULL,
    index_category  VARCHAR(20) NOT NULL
                        CHECK (index_category IN ('broad','sector')),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS stocks_master (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) UNIQUE NOT NULL,
    company_name    TEXT,
    isin            VARCHAR(20),
    instrument_type VARCHAR(20) DEFAULT 'EQUITY'
                        CHECK (instrument_type IN ('EQUITY','ETF','OTHER')),
    listing_date    DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Membership: stock belongs to indices.
-- effective_from enables time-aware membership queries.
CREATE TABLE IF NOT EXISTS stock_index_membership (
    stock_id        INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    index_id        INT REFERENCES indices(id) ON DELETE CASCADE,
    effective_from  DATE NOT NULL,
    effective_to    DATE,
    is_primary      BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (stock_id, index_id, effective_from)
);

-- ============================================================
-- 3. CORPORATE ACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS corporate_actions (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20) NOT NULL,
    action_type VARCHAR(20) NOT NULL
                    CHECK (action_type IN ('BONUS','SPLIT','DIVIDEND')),
    ratio_old   INT NOT NULL,
    ratio_new   INT NOT NULL,
    ex_date     DATE NOT NULL,
    processed   BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    UNIQUE (symbol, action_type, ex_date)
);

-- ============================================================
-- 4. PRICE TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    stock_id        INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    trade_date      DATE NOT NULL,
    open            NUMERIC,
    high            NUMERIC,
    low             NUMERIC,
    close           NUMERIC NOT NULL,
    volume          BIGINT,
    traded_value    NUMERIC,
    PRIMARY KEY (stock_id, trade_date)
);

CREATE TABLE IF NOT EXISTS index_prices (
    index_id        INT REFERENCES indices(id) ON DELETE CASCADE,
    trade_date      DATE NOT NULL,
    close           NUMERIC NOT NULL,
    PRIMARY KEY (index_id, trade_date)
);

-- ============================================================
-- 5. UNIVERSE (Top 750 by liquidity per day)
-- ============================================================
CREATE TABLE IF NOT EXISTS universe_daily (
    trade_date          DATE NOT NULL,
    stock_id            INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    liquidity_rank      INT,
    avg_traded_value_30 NUMERIC,
    PRIMARY KEY (trade_date, stock_id)
);

-- ============================================================
-- 6. RETURNS (Flexible lookback: 65D, 125D)
-- ============================================================
CREATE TABLE IF NOT EXISTS returns (
    entity_type     VARCHAR(10) NOT NULL
                        CHECK (entity_type IN ('stock','index')),
    entity_id       INT NOT NULL,
    lookback_days   INT NOT NULL,
    trade_date      DATE NOT NULL,
    return_value    NUMERIC,
    PRIMARY KEY (entity_type, entity_id, lookback_days, trade_date)
);

-- ============================================================
-- 7. RS VALUES (raw ratios, 3 layers)
-- ============================================================
CREATE TABLE IF NOT EXISTS rs_values (
    stock_id            INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    lookback_days       INT NOT NULL,
    trade_date          DATE NOT NULL,
    rs_vs_market        NUMERIC,   -- Stock / Nifty50
    rs_vs_sector        NUMERIC,   -- Stock / Primary Sector
    sector_rs_vs_market NUMERIC,   -- Primary Sector / Nifty50
    rs_combined         NUMERIC,   -- 0.75*rs65 + 0.25*rs125
    PRIMARY KEY (stock_id, lookback_days, trade_date)
);

-- ============================================================
-- 8. RS RANKINGS (percentiles 0-100)
-- ============================================================
CREATE TABLE IF NOT EXISTS rs_rankings (
    stock_id                INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    lookback_days           INT NOT NULL,
    trade_date              DATE NOT NULL,
    pct_vs_market           NUMERIC,
    pct_vs_sector           NUMERIC,
    sector_pct_vs_market    NUMERIC,
    pct_combined            NUMERIC,
    PRIMARY KEY (stock_id, lookback_days, trade_date)
);

-- ============================================================
-- 9. RS ACCELERATION (10-day delta)
-- ============================================================
CREATE TABLE IF NOT EXISTS rs_acceleration (
    stock_id        INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    lookback_days   INT NOT NULL,
    trade_date      DATE NOT NULL,
    delta_rs_market NUMERIC,
    delta_rs_sector NUMERIC,
    delta_combined  NUMERIC,
    PRIMARY KEY (stock_id, lookback_days, trade_date)
);

-- ============================================================
-- 10. LEADERSHIP STABILITY (30-day window)
-- ============================================================
CREATE TABLE IF NOT EXISTS leadership_stability_30d (
    stock_id        INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    lookback_days   INT NOT NULL,
    trade_date      DATE NOT NULL,
    stability_score NUMERIC,
    days_in_top_pct INT,
    PRIMARY KEY (stock_id, lookback_days, trade_date)
);

-- ============================================================
-- 11. MODEL PORTFOLIO (monthly rebalance)
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              SERIAL PRIMARY KEY,
    rebalance_date  DATE NOT NULL,
    stock_id        INT REFERENCES stocks_master(id),
    symbol          VARCHAR(20) NOT NULL,
    rs_combined     NUMERIC,
    rank_in_port    INT,
    weight          NUMERIC DEFAULT 0.02,  -- equal weight 1/50
    UNIQUE (rebalance_date, stock_id)
);

CREATE TABLE IF NOT EXISTS portfolio_performance (
    trade_date          DATE PRIMARY KEY,
    portfolio_value     NUMERIC,     -- indexed to 100 at start
    nifty_value         NUMERIC,     -- indexed to 100 at start
    portfolio_return    NUMERIC,     -- daily return %
    nifty_return        NUMERIC,     -- daily return %
    alpha               NUMERIC,
    portfolio_cum_return NUMERIC,    -- cumulative from inception
    nifty_cum_return    NUMERIC
);

-- ============================================================
-- 12. PIPELINE LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          SERIAL PRIMARY KEY,
    run_type    VARCHAR(20) CHECK (run_type IN ('daily','monthly','manual')),
    trade_date  DATE,
    status      VARCHAR(20) DEFAULT 'running'
                    CHECK (status IN ('running','success','failed')),
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_msg   TEXT,
    rows_inserted INT
);

-- ============================================================
-- 13. PERFORMANCE INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_date ON stock_prices(stock_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_index_prices_date ON index_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_returns_date ON returns(trade_date);
CREATE INDEX IF NOT EXISTS idx_returns_entity ON returns(entity_type, entity_id, lookback_days, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_rs_values_date ON rs_values(trade_date);
CREATE INDEX IF NOT EXISTS idx_rs_rankings_date ON rs_rankings(trade_date);
CREATE INDEX IF NOT EXISTS idx_rs_rankings_combined ON rs_rankings(trade_date, pct_combined DESC);
CREATE INDEX IF NOT EXISTS idx_universe_daily_date ON universe_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_corp_actions_unprocessed ON corporate_actions(processed, ex_date) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_membership_stock ON stock_index_membership(stock_id, is_primary);
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks_master USING gin(symbol gin_trgm_ops);

-- ============================================================
-- 14. STORED PROCEDURES
-- ============================================================

-- Compute rolling returns for a given date
CREATE OR REPLACE FUNCTION compute_daily_returns(p_date DATE)
RETURNS VOID AS $$
DECLARE
    lb INT;
BEGIN
    FOREACH lb IN ARRAY ARRAY[65, 125] LOOP
        -- Stock returns
        INSERT INTO returns (entity_type, entity_id, lookback_days, trade_date, return_value)
        SELECT
            'stock',
            sp_now.stock_id,
            lb,
            p_date,
            CASE WHEN sp_past.close > 0
                 THEN (sp_now.close - sp_past.close) / sp_past.close
                 ELSE NULL END
        FROM stock_prices sp_now
        JOIN stock_prices sp_past
            ON sp_past.stock_id = sp_now.stock_id
            AND sp_past.trade_date = (
                SELECT trade_date FROM stock_prices
                WHERE stock_id = sp_now.stock_id
                  AND trade_date <= p_date - lb
                ORDER BY trade_date DESC LIMIT 1
            )
        WHERE sp_now.trade_date = p_date
        ON CONFLICT (entity_type, entity_id, lookback_days, trade_date)
        DO UPDATE SET return_value = EXCLUDED.return_value;

        -- Index returns
        INSERT INTO returns (entity_type, entity_id, lookback_days, trade_date, return_value)
        SELECT
            'index',
            ip_now.index_id,
            lb,
            p_date,
            CASE WHEN ip_past.close > 0
                 THEN (ip_now.close - ip_past.close) / ip_past.close
                 ELSE NULL END
        FROM index_prices ip_now
        JOIN index_prices ip_past
            ON ip_past.index_id = ip_now.index_id
            AND ip_past.trade_date = (
                SELECT trade_date FROM index_prices
                WHERE index_id = ip_now.index_id
                  AND trade_date <= p_date - lb
                ORDER BY trade_date DESC LIMIT 1
            )
        WHERE ip_now.trade_date = p_date
        ON CONFLICT (entity_type, entity_id, lookback_days, trade_date)
        DO UPDATE SET return_value = EXCLUDED.return_value;
    END LOOP;
END;
$$ LANGUAGE plpgsql;


-- Compute RS values and rankings for a given date
CREATE OR REPLACE FUNCTION compute_daily_rs(p_date DATE)
RETURNS VOID AS $$
DECLARE
    nifty50_id INT;
BEGIN
    SELECT id INTO nifty50_id FROM indices WHERE index_name = 'Nifty 50';
    IF nifty50_id IS NULL THEN RETURN; END IF;

    -- RS Values for each lookback
    INSERT INTO rs_values (stock_id, lookback_days, trade_date,
                           rs_vs_market, rs_vs_sector, sector_rs_vs_market, rs_combined)
    SELECT
        sr.entity_id                                        AS stock_id,
        sr.lookback_days,
        p_date,
        CASE WHEN mr.return_value != 0 AND mr.return_value IS NOT NULL
             THEN (1 + sr.return_value) / (1 + mr.return_value)
             ELSE NULL END                                  AS rs_vs_market,
        CASE WHEN secr.return_value != 0 AND secr.return_value IS NOT NULL
             THEN (1 + sr.return_value) / (1 + secr.return_value)
             ELSE NULL END                                  AS rs_vs_sector,
        CASE WHEN mr.return_value != 0 AND mr.return_value IS NOT NULL
             THEN (1 + secr.return_value) / (1 + mr.return_value)
             ELSE NULL END                                  AS sector_rs_vs_market,
        NULL                                                AS rs_combined
    FROM returns sr
    -- market return
    JOIN returns mr
        ON mr.entity_type = 'index'
        AND mr.entity_id = nifty50_id
        AND mr.lookback_days = sr.lookback_days
        AND mr.trade_date = p_date
    -- primary sector return
    JOIN stock_index_membership sim
        ON sim.stock_id = sr.entity_id
        AND sim.is_primary = TRUE
        AND sim.effective_from <= p_date
        AND (sim.effective_to IS NULL OR sim.effective_to >= p_date)
    JOIN returns secr
        ON secr.entity_type = 'index'
        AND secr.entity_id = sim.index_id
        AND secr.lookback_days = sr.lookback_days
        AND secr.trade_date = p_date
    WHERE sr.entity_type = 'stock'
      AND sr.trade_date = p_date
    ON CONFLICT (stock_id, lookback_days, trade_date)
    DO UPDATE SET
        rs_vs_market        = EXCLUDED.rs_vs_market,
        rs_vs_sector        = EXCLUDED.rs_vs_sector,
        sector_rs_vs_market = EXCLUDED.sector_rs_vs_market;

    -- RS Combined: 0.75 * RS65 + 0.25 * RS125
    UPDATE rs_values rv65
    SET rs_combined = 0.75 * rv65.rs_vs_market + 0.25 * COALESCE(rv125.rs_vs_market, rv65.rs_vs_market)
    FROM rs_values rv125
    WHERE rv65.stock_id = rv125.stock_id
      AND rv65.trade_date = p_date
      AND rv125.trade_date = p_date
      AND rv65.lookback_days = 65
      AND rv125.lookback_days = 125;

    -- Percentile Rankings
    INSERT INTO rs_rankings (stock_id, lookback_days, trade_date,
                             pct_vs_market, pct_vs_sector, sector_pct_vs_market, pct_combined)
    SELECT
        stock_id,
        lookback_days,
        p_date,
        ROUND(PERCENT_RANK() OVER (PARTITION BY lookback_days ORDER BY rs_vs_market NULLS FIRST) * 100, 2),
        ROUND(PERCENT_RANK() OVER (PARTITION BY lookback_days ORDER BY rs_vs_sector NULLS FIRST) * 100, 2),
        ROUND(PERCENT_RANK() OVER (PARTITION BY lookback_days ORDER BY sector_rs_vs_market NULLS FIRST) * 100, 2),
        ROUND(PERCENT_RANK() OVER (PARTITION BY lookback_days ORDER BY rs_combined NULLS FIRST) * 100, 2)
    FROM rs_values
    WHERE trade_date = p_date
    ON CONFLICT (stock_id, lookback_days, trade_date)
    DO UPDATE SET
        pct_vs_market        = EXCLUDED.pct_vs_market,
        pct_vs_sector        = EXCLUDED.pct_vs_sector,
        sector_pct_vs_market = EXCLUDED.sector_pct_vs_market,
        pct_combined         = EXCLUDED.pct_combined;

    -- Acceleration (10-day delta)
    INSERT INTO rs_acceleration (stock_id, lookback_days, trade_date,
                                 delta_rs_market, delta_rs_sector, delta_combined)
    SELECT
        rv.stock_id,
        rv.lookback_days,
        p_date,
        rv.rs_vs_market - rv_old.rs_vs_market,
        rv.rs_vs_sector - rv_old.rs_vs_sector,
        rv.rs_combined  - rv_old.rs_combined
    FROM rs_values rv
    JOIN rs_values rv_old
        ON rv_old.stock_id = rv.stock_id
        AND rv_old.lookback_days = rv.lookback_days
        AND rv_old.trade_date = (
            SELECT trade_date FROM rs_values
            WHERE stock_id = rv.stock_id
              AND lookback_days = rv.lookback_days
              AND trade_date < p_date
            ORDER BY trade_date DESC
            OFFSET 9 LIMIT 1
        )
    WHERE rv.trade_date = p_date
    ON CONFLICT (stock_id, lookback_days, trade_date)
    DO UPDATE SET
        delta_rs_market = EXCLUDED.delta_rs_market,
        delta_rs_sector = EXCLUDED.delta_rs_sector,
        delta_combined  = EXCLUDED.delta_combined;

    -- Leadership Stability (30-day)
    INSERT INTO leadership_stability_30d (stock_id, lookback_days, trade_date,
                                          stability_score, days_in_top_pct)
    SELECT
        rr.stock_id,
        rr.lookback_days,
        p_date,
        ROUND(AVG(CASE WHEN rr2.pct_combined >= 80 THEN 1.0 ELSE 0.0 END) * 100, 2),
        SUM(CASE WHEN rr2.pct_combined >= 80 THEN 1 ELSE 0 END)
    FROM rs_rankings rr
    JOIN rs_rankings rr2
        ON rr2.stock_id = rr.stock_id
        AND rr2.lookback_days = rr.lookback_days
        AND rr2.trade_date >= p_date - INTERVAL '30 days'
        AND rr2.trade_date <= p_date
    WHERE rr.trade_date = p_date
    GROUP BY rr.stock_id, rr.lookback_days
    ON CONFLICT (stock_id, lookback_days, trade_date)
    DO UPDATE SET
        stability_score = EXCLUDED.stability_score,
        days_in_top_pct = EXCLUDED.days_in_top_pct;
END;
$$ LANGUAGE plpgsql;


-- Build daily universe (Top 750 by traded value, equity only)
CREATE OR REPLACE FUNCTION build_daily_universe(p_date DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO universe_daily (trade_date, stock_id, liquidity_rank, avg_traded_value_30)
    SELECT
        p_date,
        sub.stock_id,
        sub.rn,
        sub.avg_tv
    FROM (
        SELECT
            sp.stock_id,
            ROW_NUMBER() OVER (ORDER BY AVG(sp.traded_value) DESC NULLS LAST) AS rn,
            AVG(sp.traded_value) AS avg_tv
        FROM stock_prices sp
        JOIN stocks_master sm ON sm.id = sp.stock_id
        WHERE sp.trade_date BETWEEN p_date - 30 AND p_date
          AND sm.instrument_type = 'EQUITY'
          AND sm.is_active = TRUE
        GROUP BY sp.stock_id
    ) sub
    WHERE sub.rn <= 750
    ON CONFLICT (trade_date, stock_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;


-- Apply corporate actions (bonus/split) to historical prices
CREATE OR REPLACE PROCEDURE apply_corporate_actions()
LANGUAGE plpgsql AS $$
DECLARE
    ca RECORD;
    adj_factor NUMERIC;
BEGIN
    FOR ca IN
        SELECT ca.*, sm.id AS stock_master_id
        FROM corporate_actions ca
        JOIN stocks_master sm ON sm.symbol = ca.symbol
        WHERE ca.processed = FALSE
        ORDER BY ca.ex_date ASC
    LOOP
        IF ca.action_type IN ('BONUS', 'SPLIT') THEN
            adj_factor := (ca.ratio_old + ca.ratio_new)::NUMERIC / ca.ratio_old;
            IF ca.action_type = 'SPLIT' THEN
                adj_factor := ca.ratio_new::NUMERIC / ca.ratio_old;
            END IF;

            -- Adjust all prices BEFORE ex_date
            UPDATE stock_prices
            SET close = ROUND(close / adj_factor, 4)
            WHERE stock_id = ca.stock_master_id
              AND trade_date < ca.ex_date;
        END IF;

        UPDATE corporate_actions
        SET processed = TRUE, processed_at = NOW()
        WHERE id = ca.id;
    END LOOP;
END;
$$;


-- Compute full daily metrics (orchestrator)
CREATE OR REPLACE FUNCTION compute_daily_metrics(p_date DATE)
RETURNS VOID AS $$
BEGIN
    PERFORM compute_daily_returns(p_date);
    PERFORM build_daily_universe(p_date);
    PERFORM compute_daily_rs(p_date);
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 15. TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
