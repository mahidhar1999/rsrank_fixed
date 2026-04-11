from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from app.db import get_db
from app.schemas import StockRankingsResponse, StockRanking, HeatmapResponse, HeatmapStock, StockHistoryResponse, RSPoint

router = APIRouter()

COLOR_BUCKETS = [
    (90, "h5"), (75, "h4"), (60, "h3"), (50, "h2"),
    (45, "h1"), (40, "n"),  (30, "l1"), (20, "l2"),
    (10, "l3"), (5,  "l4"), (0,  "l5"),
]

def _color_bucket(pct: Optional[float]) -> str:
    if pct is None:
        return "n"
    for threshold, label in COLOR_BUCKETS:
        if pct >= threshold:
            return label
    return "l5"


def _latest_date(db: Connection, provided: Optional[str]) -> str:
    if provided:
        return provided
    row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_rankings")).first()
    return str(row.d) if row and row.d else "2024-01-01"


@router.get("/rankings", response_model=StockRankingsResponse)
def stock_rankings(
    trade_date: Optional[str] = Query(None),
    sector: Optional[str] = Query(None, description="Filter by sector index name"),
    min_pct: Optional[float] = Query(None, description="Min RS percentile 0-100"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Connection = Depends(get_db),
):
    d = _latest_date(db, trade_date)
    offset = (page - 1) * limit

    sector_filter = ""
    params: dict = {"d": d, "limit": limit, "offset": offset}

    if sector:
        sector_filter = """
            AND u.stock_id IN (
                SELECT sim.stock_id FROM stock_index_membership sim
                JOIN indices i ON i.id = sim.index_id
                WHERE i.index_name = :sector
                  AND sim.effective_from <= :d
                  AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
            )
        """
        params["sector"] = sector

    if min_pct is not None:
        sector_filter += " AND rr.pct_combined >= :min_pct"
        params["min_pct"] = min_pct

    rows = db.execute(text(f"""
        SELECT
            ROW_NUMBER() OVER (ORDER BY rr.pct_combined DESC NULLS LAST) AS rank,
            sm.symbol,
            sm.company_name,
            (SELECT i.index_name FROM stock_index_membership sim
             JOIN indices i ON i.id = sim.index_id
             WHERE sim.stock_id = sm.id AND sim.is_primary = TRUE
               AND sim.effective_from <= :d
               AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
             ORDER BY sim.effective_from DESC LIMIT 1) AS sector,
            sp.close,
            rv65.rs_vs_market   AS rs_65d,
            rv125.rs_vs_market  AS rs_125d,
            rv65.rs_combined,
            rr.pct_combined,
            rr.pct_vs_market,
            rr.pct_vs_sector,
            ls.stability_score,
            ra.delta_combined
        FROM universe_daily u
        JOIN stocks_master sm ON sm.id = u.stock_id
        JOIN rs_rankings rr ON rr.stock_id = u.stock_id AND rr.trade_date = :d
        LEFT JOIN rs_values rv65  ON rv65.stock_id  = u.stock_id AND rv65.trade_date  = :d AND rv65.lookback_days  = 65
        LEFT JOIN rs_values rv125 ON rv125.stock_id = u.stock_id AND rv125.trade_date = :d AND rv125.lookback_days = 125
        LEFT JOIN stock_prices sp ON sp.stock_id = u.stock_id AND sp.trade_date = :d
        LEFT JOIN leadership_stability_30d ls ON ls.stock_id = u.stock_id AND ls.trade_date = :d
        LEFT JOIN rs_acceleration ra ON ra.stock_id = u.stock_id AND ra.trade_date = :d
        WHERE u.trade_date = :d
        {sector_filter}
        ORDER BY rr.pct_combined DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).mappings().fetchall()

    count_row = db.execute(text(f"""
        SELECT COUNT(*) as cnt
        FROM universe_daily u
        JOIN rs_rankings rr ON rr.stock_id = u.stock_id AND rr.trade_date = :d
        WHERE u.trade_date = :d {sector_filter}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).first()

    stocks = [
        StockRanking(
            rank=int(r["rank"]),
            symbol=r["symbol"],
            company_name=r["company_name"],
            sector=r["sector"],
            close=float(r["close"]) if r["close"] else None,
            rs_65d=float(r["rs_65d"]) if r["rs_65d"] else None,
            rs_125d=float(r["rs_125d"]) if r["rs_125d"] else None,
            rs_combined=float(r["rs_combined"]) if r["rs_combined"] else None,
            pct_combined=float(r["pct_combined"]) if r["pct_combined"] else None,
            pct_vs_market=float(r["pct_vs_market"]) if r["pct_vs_market"] else None,
            pct_vs_sector=float(r["pct_vs_sector"]) if r["pct_vs_sector"] else None,
            stability_score=float(r["stability_score"]) if r["stability_score"] else None,
            delta_combined=float(r["delta_combined"]) if r["delta_combined"] else None,
        )
        for r in rows
    ]

    return StockRankingsResponse(
        trade_date=d, total=count_row.cnt if count_row else 0,
        page=page, limit=limit, stocks=stocks,
    )


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    trade_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=10, le=750),
    db: Connection = Depends(get_db),
):
    d = _latest_date(db, trade_date)

    rows = db.execute(text("""
        SELECT
            sm.symbol,
            rv.rs_combined,
            rr.pct_combined,
            (SELECT i.index_name FROM stock_index_membership sim
             JOIN indices i ON i.id = sim.index_id
             WHERE sim.stock_id = sm.id AND sim.is_primary = TRUE
               AND sim.effective_from <= :d
               AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
             ORDER BY sim.effective_from DESC LIMIT 1) AS sector
        FROM universe_daily u
        JOIN stocks_master sm ON sm.id = u.stock_id
        JOIN rs_rankings rr ON rr.stock_id = u.stock_id AND rr.trade_date = :d
        LEFT JOIN rs_values rv ON rv.stock_id = u.stock_id AND rv.trade_date = :d AND rv.lookback_days = 65
        WHERE u.trade_date = :d
        ORDER BY rr.pct_combined DESC NULLS LAST
        LIMIT :limit
    """), {"d": d, "limit": limit}).mappings().fetchall()

    stocks = [
        HeatmapStock(
            symbol=r["symbol"],
            rs_combined=float(r["rs_combined"]) if r["rs_combined"] else None,
            pct_combined=float(r["pct_combined"]) if r["pct_combined"] else None,
            color_bucket=_color_bucket(float(r["pct_combined"]) if r["pct_combined"] else None),
            sector=r["sector"],
        )
        for r in rows
    ]
    return HeatmapResponse(trade_date=d, stocks=stocks)


@router.get("/{symbol}/rs-history", response_model=StockHistoryResponse)
def rs_history(
    symbol: str,
    lookback_days: int = Query(90, description="Number of trading days of history"),
    db: Connection = Depends(get_db),
):
    stock = db.execute(
        text("SELECT id FROM stocks_master WHERE symbol = :s"), {"s": symbol.upper()}
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    rows = db.execute(text("""
        SELECT rv.trade_date, rv.rs_combined, rr.pct_combined
        FROM rs_values rv
        LEFT JOIN rs_rankings rr ON rr.stock_id = rv.stock_id AND rr.trade_date = rv.trade_date
        WHERE rv.stock_id = :sid AND rv.lookback_days = 65
        ORDER BY rv.trade_date DESC
        LIMIT :n
    """), {"sid": stock.id, "n": lookback_days}).mappings().fetchall()

    history = [
        RSPoint(
            trade_date=r["trade_date"],
            rs_combined=float(r["rs_combined"]) if r["rs_combined"] else None,
            pct_combined=float(r["pct_combined"]) if r["pct_combined"] else None,
        )
        for r in reversed(rows)
    ]
    return StockHistoryResponse(symbol=symbol.upper(), history=history)
