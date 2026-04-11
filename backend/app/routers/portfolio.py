from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from app.db import get_db
from app.dependencies import require_pro

router = APIRouter()
TOP_N = 50
BENCHMARK_INDEX = "Nifty 500"


@router.get("/current")
def current_portfolio(
    trade_date: Optional[str] = Query(None),
    db: Connection = Depends(get_db),
    current_user: dict = Depends(require_pro),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) AS d FROM rs_rankings")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    rows = db.execute(text("""
        SELECT
            ROW_NUMBER() OVER (ORDER BY rr.pct_combined DESC NULLS LAST) AS rank,
            sm.symbol,
            sm.company_name,
            (
                SELECT i.index_name
                FROM stock_index_membership sim
                JOIN indices i ON i.id = sim.index_id
                WHERE sim.stock_id = sm.id
                  AND sim.is_primary = TRUE
                  AND sim.effective_from <= :d
                  AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
                ORDER BY sim.effective_from DESC
                LIMIT 1
            ) AS sector,
            rv.rs_combined,
            rr.pct_combined,
            sp.close
        FROM universe_daily u
        JOIN stocks_master sm
          ON sm.id = u.stock_id
        JOIN rs_rankings rr
          ON rr.stock_id = u.stock_id
         AND rr.trade_date = :d
        LEFT JOIN rs_values rv
          ON rv.stock_id = u.stock_id
         AND rv.trade_date = :d
         AND rv.lookback_days = 65
        LEFT JOIN stock_prices sp
          ON sp.stock_id = u.stock_id
         AND sp.trade_date = :d
        WHERE u.trade_date = :d
          AND EXISTS (
              SELECT 1
              FROM stock_index_membership sim
              JOIN indices i ON i.id = sim.index_id
              WHERE sim.stock_id = u.stock_id
                AND i.index_name = :benchmark
                AND sim.effective_from <= :d
                AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
          )
        ORDER BY rr.pct_combined DESC NULLS LAST
        LIMIT :n
    """), {"d": trade_date, "n": TOP_N, "benchmark": BENCHMARK_INDEX}).mappings().fetchall()

    return {
        "trade_date": trade_date,
        "rebalance_on": "First trading day of each month",
        "weight_per_stock": round(100.0 / TOP_N, 2),
        "holdings": [
            {
                "rank": int(r["rank"]),
                "symbol": r["symbol"],
                "company_name": r["company_name"],
                "sector": r["sector"],
                "rs_combined": float(r["rs_combined"]) if r["rs_combined"] else None,
                "pct_combined": float(r["pct_combined"]) if r["pct_combined"] else None,
                "close": float(r["close"]) if r["close"] else None,
                "weight_pct": round(100.0 / TOP_N, 2),
            }
            for r in rows
        ],
    }


@router.get("/performance")
def portfolio_performance(
    db: Connection = Depends(get_db),
    current_user: dict = Depends(require_pro),
):
    """
    Monthly portfolio returns vs Nifty 500.

    Methodology:
    - Rebalance date = first trading day of each month
    - Portfolio = Top 50 Nifty 500 stocks by RS Combined on rebalance date
    - Return = average of individual stock returns from rebalance date to month-end
    - Summary values are compounded across all returned months
    """

    monthly_rows = db.execute(text("""
        WITH benchmark AS (
            SELECT id
            FROM indices
            WHERE index_name = :benchmark
            LIMIT 1
        ),
        monthly AS (
            SELECT
                DATE_TRUNC('month', rr.trade_date)::DATE AS month_start,
                MIN(rr.trade_date) AS first_day,
                MAX(rr.trade_date) AS last_day
            FROM rs_rankings rr
            GROUP BY DATE_TRUNC('month', rr.trade_date)
        ),
        complete_months AS (
            SELECT month_start, first_day, last_day
            FROM monthly
            WHERE first_day <> last_day
        ),
        ranked_members AS (
            SELECT
                cm.month_start,
                cm.first_day,
                cm.last_day,
                u.stock_id,
                ROW_NUMBER() OVER (
                    PARTITION BY cm.month_start
                    ORDER BY rr.pct_combined DESC NULLS LAST
                ) AS rank
            FROM complete_months cm
            JOIN universe_daily u
              ON u.trade_date = cm.first_day
            JOIN rs_rankings rr
              ON rr.stock_id = u.stock_id
             AND rr.trade_date = cm.first_day
            WHERE EXISTS (
                SELECT 1
                FROM stock_index_membership sim
                JOIN indices i ON i.id = sim.index_id
                WHERE sim.stock_id = u.stock_id
                  AND i.index_name = :benchmark
                  AND sim.effective_from <= cm.first_day
                  AND (sim.effective_to IS NULL OR sim.effective_to >= cm.first_day)
            )
        ),
        top_members AS (
            SELECT month_start, first_day, last_day, stock_id
            FROM ranked_members
            WHERE rank <= :top_n
        ),
        portfolio_monthly AS (
            SELECT
                t.month_start,
                t.first_day,
                t.last_day,
                COUNT(*) FILTER (WHERE p_end.close IS NOT NULL) AS stocks_counted,
                AVG(
                    CASE
                        WHEN p_start.close > 0 AND p_end.close IS NOT NULL
                        THEN (p_end.close / p_start.close) - 1
                        ELSE NULL
                    END
                ) AS portfolio_ret
            FROM top_members t
            JOIN stock_prices p_start
              ON p_start.stock_id = t.stock_id
             AND p_start.trade_date = t.first_day
            LEFT JOIN stock_prices p_end
              ON p_end.stock_id = t.stock_id
             AND p_end.trade_date = t.last_day
            GROUP BY t.month_start, t.first_day, t.last_day
        ),
        benchmark_monthly AS (
            SELECT
                cm.month_start,
                CASE
                    WHEN p_start.close > 0
                    THEN (p_end.close / p_start.close) - 1
                    ELSE NULL
                END AS benchmark_ret
            FROM complete_months cm
            JOIN benchmark b ON TRUE
            JOIN index_prices p_start
              ON p_start.index_id = b.id
             AND p_start.trade_date = cm.first_day
            JOIN index_prices p_end
              ON p_end.index_id = b.id
             AND p_end.trade_date = cm.last_day
        )
        SELECT
            pm.month_start,
            pm.first_day,
            pm.last_day,
            pm.stocks_counted,
            pm.portfolio_ret,
            bm.benchmark_ret
        FROM portfolio_monthly pm
        LEFT JOIN benchmark_monthly bm
          ON bm.month_start = pm.month_start
        ORDER BY pm.month_start
    """), {"benchmark": BENCHMARK_INDEX, "top_n": TOP_N}).mappings().fetchall()

    if not monthly_rows:
        return {"monthly_returns": [], "ytd_portfolio": 0, "ytd_nifty": 0, "ytd_alpha": 0}

    monthly_returns = []
    for row in monthly_rows:
        port_ret = round(float(row["portfolio_ret"]) * 100, 2) if row["portfolio_ret"] else 0.0
        nifty_ret = round(float(row["benchmark_ret"]) * 100, 2) if row["benchmark_ret"] else 0.0

        monthly_returns.append({
            "month": str(row["month_start"])[:7],
            "start_date": str(row["first_day"]),
            "end_date": str(row["last_day"]),
            "portfolio_return": port_ret,
            "nifty_return": nifty_ret,
            "alpha": round(port_ret - nifty_ret, 2),
            "stocks_counted": int(row["stocks_counted"] or 0),
        })

    port_mult = 1.0
    nifty_mult = 1.0
    for month in monthly_returns:
        port_mult *= (1 + month["portfolio_return"] / 100)
        nifty_mult *= (1 + month["nifty_return"] / 100)

    ytd_port = round((port_mult - 1) * 100, 2)
    ytd_nifty = round((nifty_mult - 1) * 100, 2)

    return {
        "ytd_portfolio": ytd_port,
        "ytd_nifty": ytd_nifty,
        "ytd_alpha": round(ytd_port - ytd_nifty, 2),
        "monthly_returns": monthly_returns,
    }


@router.get("/preview")
def portfolio_preview(
    trade_date: Optional[str] = Query(None),
    db: Connection = Depends(get_db),
):
    if not trade_date:
        row = db.execute(text("SELECT MAX(trade_date) AS d FROM rs_rankings")).first()
        trade_date = str(row.d) if row and row.d else "2024-01-01"

    rows = db.execute(text("""
        SELECT sm.symbol, rr.pct_combined
        FROM universe_daily u
        JOIN stocks_master sm
          ON sm.id = u.stock_id
        JOIN rs_rankings rr
          ON rr.stock_id = u.stock_id
         AND rr.trade_date = :d
        WHERE u.trade_date = :d
          AND EXISTS (
              SELECT 1
              FROM stock_index_membership sim
              JOIN indices i ON i.id = sim.index_id
              WHERE sim.stock_id = u.stock_id
                AND i.index_name = :benchmark
                AND sim.effective_from <= :d
                AND (sim.effective_to IS NULL OR sim.effective_to >= :d)
          )
        ORDER BY rr.pct_combined DESC NULLS LAST
        LIMIT 5
    """), {"d": trade_date, "benchmark": BENCHMARK_INDEX}).mappings().fetchall()

    return {
        "trade_date": trade_date,
        "preview": [
            {
                "symbol": r["symbol"],
                "pct_combined": float(r["pct_combined"]) if r["pct_combined"] else None,
            }
            for r in rows
        ],
        "total_holdings": TOP_N,
        "message": "Sign up to view all 50 Nifty 500 holdings and performance analytics",
    }
