from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from app.db import get_db
from app.schemas import MarketSummary, TopSector

router = APIRouter()


@router.get("/summary", response_model=MarketSummary)
def market_summary(
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to latest"),
    db: Connection = Depends(get_db),
):
    # Resolve trade date
    if trade_date:
        d = trade_date
    else:
        row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_rankings")).first()
        d = row.d if row and row.d else None

    if not d:
        return MarketSummary(
            trade_date="2024-01-01", nifty50_close=None, nifty50_change_pct=None,
            universe_size=0, leaders=0, laggards=0, neutral=0,
            top_sector=None, advancing_sectors=0, declining_sectors=0,
        )

    # Universe size
    size_row = db.execute(
        text("SELECT COUNT(*) as cnt FROM universe_daily WHERE trade_date = :d"),
        {"d": d}
    ).first()
    universe_size = size_row.cnt if size_row else 0

    # Leaders / laggards from rs_values
    dist = db.execute(text("""
        SELECT
            SUM(CASE WHEN rs_combined >= 1.2 THEN 1 ELSE 0 END) as leaders,
            SUM(CASE WHEN rs_combined <= 0.8 THEN 1 ELSE 0 END) as laggards,
            SUM(CASE WHEN rs_combined > 0.8 AND rs_combined < 1.2 THEN 1 ELSE 0 END) as neutral
        FROM rs_values
        WHERE trade_date = :d AND lookback_days = 65
    """), {"d": d}).first()

    leaders  = int(dist.leaders  or 0)
    laggards = int(dist.laggards or 0)
    neutral  = int(dist.neutral  or 0)

    # Nifty 50 close + daily change
    nifty_row = db.execute(text("""
        SELECT curr.close,
               CASE WHEN prev.close > 0
                    THEN ROUND(((curr.close - prev.close) / prev.close) * 100, 2)
                    ELSE NULL END as chg_pct
        FROM index_prices curr
        JOIN indices i ON i.id = curr.index_id AND i.index_name = 'Nifty 50'
        LEFT JOIN LATERAL (
            SELECT close FROM index_prices
            WHERE index_id = curr.index_id AND trade_date < :d
            ORDER BY trade_date DESC LIMIT 1
        ) prev ON TRUE
        WHERE curr.trade_date = :d
    """), {"d": d}).first()

    nifty_close = float(nifty_row.close) if nifty_row and nifty_row.close else None
    nifty_chg   = float(nifty_row.chg_pct) if nifty_row and nifty_row.chg_pct else None

    # Top sector by RS vs market
    top_sector_row = db.execute(text("""
        WITH nifty AS (
            SELECT return_value
            FROM returns
            WHERE entity_type = 'index'
              AND lookback_days = 65
              AND trade_date = :d
              AND entity_id = (SELECT id FROM indices WHERE index_name = 'Nifty 50')
        ),
        sector_pct AS (
            SELECT
                sim.index_id,
                MAX(rr.sector_pct_vs_market) AS pct_vs_market
            FROM rs_rankings rr
            JOIN stock_index_membership sim
              ON sim.stock_id = rr.stock_id
             AND sim.is_primary = TRUE
             AND sim.effective_from <= :d
             AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
            WHERE rr.trade_date = :d
            GROUP BY sim.index_id
        )
        SELECT
            i.index_name,
            ROUND(((1 + r.return_value) / (1 + nifty.return_value))::NUMERIC, 3) AS rs,
            sp.pct_vs_market AS pct
        FROM returns r
        JOIN indices i ON i.id = r.entity_id AND i.index_category = 'sector'
        JOIN nifty ON nifty.return_value IS NOT NULL AND nifty.return_value > -1
        LEFT JOIN sector_pct sp ON sp.index_id = r.entity_id
        WHERE r.entity_type = 'index'
          AND r.lookback_days = 65
          AND r.trade_date = :d
          AND r.return_value IS NOT NULL
        ORDER BY rs DESC
        LIMIT 1
    """), {"d": d}).first()

    top_sector = None
    if top_sector_row:
        top_sector = TopSector(
            name=top_sector_row.index_name,
            rs=float(top_sector_row.rs),
            pct=float(top_sector_row.pct or 0),
        )

    # Advancing / declining sectors
    sector_trend = db.execute(text("""
        SELECT
            SUM(CASE WHEN r65.return_value > r_prev.return_value THEN 1 ELSE 0 END) as advancing,
            SUM(CASE WHEN r65.return_value < r_prev.return_value THEN 1 ELSE 0 END) as declining
        FROM returns r65
        JOIN indices i ON i.id = r65.entity_id AND i.index_category = 'sector'
        LEFT JOIN LATERAL (
            SELECT return_value FROM returns
            WHERE entity_type = 'index' AND entity_id = r65.entity_id
              AND lookback_days = 65 AND trade_date < :d
            ORDER BY trade_date DESC LIMIT 1
        ) r_prev ON TRUE
        WHERE r65.entity_type = 'index' AND r65.lookback_days = 65 AND r65.trade_date = :d
    """), {"d": d}).first()

    return MarketSummary(
        trade_date=d,
        nifty50_close=nifty_close,
        nifty50_change_pct=nifty_chg,
        universe_size=universe_size,
        leaders=leaders,
        laggards=laggards,
        neutral=neutral,
        top_sector=top_sector,
        advancing_sectors=int(sector_trend.advancing or 0) if sector_trend else 0,
        declining_sectors=int(sector_trend.declining or 0) if sector_trend else 0,
    )


@router.get("/latest-date")
def latest_date(db: Connection = Depends(get_db)):
    row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_rankings")).first()
    return {"latest_date": str(row.d) if row and row.d else None}


@router.get("/available-dates")
def available_dates(db: Connection = Depends(get_db)):
    rows = db.execute(text("""
        SELECT DISTINCT trade_date FROM rs_rankings
        ORDER BY trade_date DESC LIMIT 90
    """)).fetchall()
    return {"dates": [str(r.trade_date) for r in rows]}
