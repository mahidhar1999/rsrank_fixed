from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from app.db import get_db

router = APIRouter()


@router.get("")
def acceleration(
    trade_date: Optional[str] = Query(None),
    limit: int = Query(20, ge=5, le=100),
    db: Connection = Depends(get_db),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_acceleration")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    def fetch(direction: str, lim: int):
        order = "DESC" if direction == "up" else "ASC"
        rows = db.execute(text(f"""
            SELECT
                sm.symbol, sm.company_name,
                (SELECT i.index_name FROM stock_index_membership sim
                 JOIN indices i ON i.id = sim.index_id
                 WHERE sim.stock_id = sm.id AND sim.is_primary = TRUE
                   AND sim.effective_from <= :d AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
                 ORDER BY sim.effective_from DESC LIMIT 1) AS sector,
                rv.rs_combined,
                rr.pct_combined,
                ra.delta_combined,
                ra.delta_rs_market
            FROM rs_acceleration ra
            JOIN stocks_master sm ON sm.id = ra.stock_id
            JOIN rs_rankings rr ON rr.stock_id = ra.stock_id AND rr.trade_date = :d
            LEFT JOIN rs_values rv ON rv.stock_id = ra.stock_id AND rv.trade_date = :d AND rv.lookback_days = 65
            WHERE ra.trade_date = :d AND ra.delta_combined IS NOT NULL
            ORDER BY ra.delta_combined {order} NULLS LAST
            LIMIT :lim
        """), {"d": trade_date, "lim": lim}).mappings().fetchall()

        return [
            {
                "symbol": r["symbol"],
                "company_name": r["company_name"],
                "sector": r["sector"],
                "rs_combined": float(r["rs_combined"]) if r["rs_combined"] else None,
                "pct_combined": float(r["pct_combined"]) if r["pct_combined"] else None,
                "delta_combined": float(r["delta_combined"]) if r["delta_combined"] else None,
                "delta_rs_market": float(r["delta_rs_market"]) if r["delta_rs_market"] else None,
            }
            for r in rows
        ]

    return {
        "trade_date": trade_date,
        "emerging": fetch("up", limit),
        "fading":   fetch("down", limit),
    }
