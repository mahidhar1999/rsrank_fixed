from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional, List
from app.db import get_db
from app.schemas import SectorRotationResponse, SectorRS, SectorStock

router = APIRouter()


@router.get("/rotation", response_model=SectorRotationResponse)
def sector_rotation(
    trade_date: Optional[str] = Query(None),
    db: Connection = Depends(get_db),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_rankings")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    # Get Nifty 50 returns for RS computation
    nifty_ret = {}
    for lb in [65, 125]:
        r = db.execute(text("""
            SELECT return_value FROM returns
            WHERE entity_type = 'index' AND lookback_days = :lb AND trade_date = :d
              AND entity_id = (SELECT id FROM indices WHERE index_name = 'Nifty 50' LIMIT 1)
        """), {"d": trade_date, "lb": lb}).scalar()
        nifty_ret[lb] = float(r) if r is not None else None

    rows = db.execute(text("""
        SELECT
            i.index_name,
            r65.return_value AS ret_65,
            r125.return_value AS ret_125,
            -- trend: compare current 65D return vs 65D return 10 trading days ago
            prev_ret.return_value AS ret_65_prev,
            COUNT(DISTINCT sim.stock_id) AS stock_count
        FROM indices i
        LEFT JOIN returns r65  ON r65.entity_id  = i.id AND r65.entity_type  = 'index' AND r65.lookback_days  = 65  AND r65.trade_date  = :d
        LEFT JOIN returns r125 ON r125.entity_id = i.id AND r125.entity_type = 'index' AND r125.lookback_days = 125 AND r125.trade_date = :d
        LEFT JOIN LATERAL (
            SELECT return_value FROM returns
            WHERE entity_id = i.id AND entity_type = 'index' AND lookback_days = 65 AND trade_date < :d
            ORDER BY trade_date DESC OFFSET 9 LIMIT 1
        ) prev_ret ON TRUE
        LEFT JOIN stock_index_membership sim
            ON sim.index_id = i.id AND sim.is_primary = TRUE
            AND sim.effective_from <= :d AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
        WHERE i.index_category = 'sector' AND i.is_active = TRUE
        GROUP BY i.id, i.index_name, r65.return_value, r125.return_value, prev_ret.return_value
        ORDER BY r65.return_value DESC NULLS LAST
    """), {"d": trade_date}).mappings().fetchall()

    sectors = []
    for r in rows:
        n65  = nifty_ret.get(65)
        n125 = nifty_ret.get(125)

        rs_65  = None
        rs_125 = None
        pct_mkt = None

        if r["ret_65"] is not None and n65 is not None and n65 > -1:
            rs_65 = round((1 + float(r["ret_65"])) / (1 + float(n65)), 4)
        if r["ret_125"] is not None and n125 is not None and n125 > -1:
            rs_125 = round((1 + float(r["ret_125"])) / (1 + float(n125)), 4)

        # Trend based on current vs 10D-ago return
        trend = "flat"
        if r["ret_65"] is not None and r["ret_65_prev"] is not None:
            diff = float(r["ret_65"]) - float(r["ret_65_prev"])
            if diff > 0.005:
                trend = "up"
            elif diff < -0.005:
                trend = "down"

        sectors.append(SectorRS(
            index_name=r["index_name"],
            rs_65d=rs_65,
            rs_125d=rs_125,
            pct_vs_market=pct_mkt,
            trend=trend,
            stock_count=int(r["stock_count"] or 0),
        ))

    return SectorRotationResponse(trade_date=trade_date, sectors=sectors)


@router.get("/{sector_name}/stocks")
def sector_stocks(
    sector_name: str,
    trade_date: Optional[str] = Query(None),
    db: Connection = Depends(get_db),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) as d FROM rs_rankings")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    index_row = db.execute(
        text("SELECT id FROM indices WHERE index_name = :n"), {"n": sector_name}
    ).first()
    if not index_row:
        raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' not found")

    rows = db.execute(text("""
        SELECT
            sm.symbol, sm.company_name,
            rv.rs_combined,
            rr.pct_combined,
            rr.pct_vs_sector
        FROM stock_index_membership sim
        JOIN stocks_master sm ON sm.id = sim.stock_id
        LEFT JOIN rs_rankings rr ON rr.stock_id = sim.stock_id AND rr.trade_date = :d
        LEFT JOIN rs_values rv  ON rv.stock_id  = sim.stock_id AND rv.trade_date  = :d AND rv.lookback_days = 65
        WHERE sim.index_id = :iid
          AND sim.effective_from <= :d
          AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
        ORDER BY rr.pct_combined DESC NULLS LAST
    """), {"d": trade_date, "iid": index_row.id}).mappings().fetchall()

    return {
        "sector": sector_name,
        "trade_date": trade_date,
        "stocks": [
            {
                "symbol": r["symbol"],
                "company_name": r["company_name"],
                "rs_combined": float(r["rs_combined"]) if r["rs_combined"] else None,
                "pct_combined": float(r["pct_combined"]) if r["pct_combined"] else None,
                "pct_vs_sector": float(r["pct_vs_sector"]) if r["pct_vs_sector"] else None,
            }
            for r in rows
        ],
    }
