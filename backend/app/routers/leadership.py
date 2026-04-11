from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from app.db import get_db

router = APIRouter()


@router.get("")
def leadership(
    trade_date: Optional[str] = Query(None),
    min_stability: float = Query(60, description="Min stability score 0-100"),
    limit: int = Query(50, ge=5, le=200),
    db: Connection = Depends(get_db),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) as d FROM leadership_stability_30d")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    rows = db.execute(text("""
        SELECT
            sm.symbol, sm.company_name,
            (SELECT i.index_name FROM stock_index_membership sim
             JOIN indices i ON i.id = sim.index_id
             WHERE sim.stock_id = sm.id AND sim.is_primary = TRUE
               AND sim.effective_from <= :d AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
             ORDER BY sim.effective_from DESC LIMIT 1) AS sector,
            ls.stability_score,
            rv.rs_combined,
            rr.pct_combined
        FROM leadership_stability_30d ls
        JOIN stocks_master sm ON sm.id = ls.stock_id
        LEFT JOIN rs_rankings rr ON rr.stock_id = ls.stock_id AND rr.trade_date = :d
        LEFT JOIN rs_values rv ON rv.stock_id = ls.stock_id AND rv.trade_date = :d AND rv.lookback_days = 65
        WHERE ls.trade_date = :d
          AND ls.stability_score >= :min_s
        ORDER BY ls.stability_score DESC, rr.pct_combined DESC NULLS LAST
        LIMIT :lim
    """), {"d": trade_date, "min_s": min_stability, "lim": limit}).mappings().fetchall()

    return {
        "trade_date": trade_date,
        "min_stability": min_stability,
        "stocks": [
            {
                "symbol": r["symbol"],
                "company_name": r["company_name"],
                "sector": r["sector"],
                "stability_score": float(r["stability_score"]) if r["stability_score"] else None,
                "rs_combined": float(r["rs_combined"]) if r["rs_combined"] else None,
                "pct_combined": float(r["pct_combined"]) if r["pct_combined"] else None,
            }
            for r in rows
        ],
    }
