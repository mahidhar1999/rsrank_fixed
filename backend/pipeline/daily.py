"""
RSRank Daily Pipeline
Runs every trading day after market close.
Steps:
  1. Ingest stock bhavcopy
  2. Ingest index prices
  3. Fetch & apply corporate actions
  4. compute_daily_metrics() stored function (builds universe + RS)
"""

import requests
import pandas as pd
from datetime import datetime, date, timedelta
from io import StringIO
from sqlalchemy import text
from pipeline.mailer import send_email
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from app.db import engine
except ModuleNotFoundError:
    from db import engine  # standalone run

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com", timeout=10)
    return s


def _normalize_index_name(name: str) -> str:
    return name.upper().replace("&", "AND").replace("  ", " ").strip()


# ── Step 1: Stock Prices ──────────────────────────────────────────

def ingest_stock_data(trade_date: date, session: requests.Session) -> bool:
    print(f"[1] Ingesting stock bhavcopy for {trade_date}...")
    url = (
        "https://archives.nseindia.com/products/content/"
        f"sec_bhavdata_full_{trade_date.strftime('%d%m%Y')}.csv"
    )
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"    No bhavcopy available for {trade_date} (HTTP {resp.status_code})")
        return False

    df = pd.read_csv(StringIO(resp.text))
    df.columns = df.columns.str.strip().str.upper()

    df["SERIES"] = df["SERIES"].astype(str).str.strip().str.upper()
    df = df[df["SERIES"].isin(["EQ", "BE"])]
    if df.empty:
        print("    No EQ/BE stocks found.")
        return False

    df["TRADE_DATE"] = pd.to_datetime(df["DATE1"], dayfirst=True).dt.date

    if "TTL_TRD_VAL" in df.columns:
        df["TRADED_VALUE"] = df["TTL_TRD_VAL"]
    elif "TURNOVER_LACS" in df.columns:
        df["TRADED_VALUE"] = df["TURNOVER_LACS"] * 100_000
    else:
        print("    No traded value column found.")
        return False

    df = df[["SYMBOL", "CLOSE_PRICE", "TTL_TRD_QNTY", "TRADED_VALUE", "TRADE_DATE"]].copy()
    df.columns = ["symbol", "close", "volume", "traded_value", "trade_date"]
    df["symbol"] = df["symbol"].str.strip()
    df = df.dropna(subset=["close", "volume"])

    with engine.connect() as conn:
        # Upsert symbols into master
        symbols = df["symbol"].unique().tolist()
        for sym in symbols:
            conn.execute(text("""
                INSERT INTO stocks_master (symbol) VALUES (:s)
                ON CONFLICT (symbol) DO NOTHING
            """), {"s": sym})
        conn.commit()

        # Fetch ID map
        rows = conn.execute(text("SELECT id, symbol FROM stocks_master")).fetchall()
        stock_map = {r.symbol: r.id for r in rows}

        # Bulk insert prices
        price_rows = [
            {
                "stock_id":     stock_map[row.symbol],
                "trade_date":   row.trade_date,
                "close":        float(row.close),
                "volume":       int(row.volume),
                "traded_value": float(row.traded_value),
            }
            for row in df.itertuples()
            if row.symbol in stock_map
        ]
        if price_rows:
            conn.execute(text("""
                INSERT INTO stock_prices (stock_id, trade_date, close, volume, traded_value)
                VALUES (:stock_id, :trade_date, :close, :volume, :traded_value)
                ON CONFLICT (stock_id, trade_date) DO UPDATE
                SET close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    traded_value = EXCLUDED.traded_value
            """), price_rows)
        conn.commit()

    print(f"    Inserted {len(price_rows)} stock prices.")
    return True


# ── Step 2: Index Prices ──────────────────────────────────────────

def ingest_index_prices(trade_date: date, session: requests.Session):
    print(f"[2] Fetching NSE index prices...")
    archive_url = (
        "https://archives.nseindia.com/content/indices/"
        f"ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"
    )
    resp = session.get(archive_url, timeout=20)
    if resp.status_code != 200:
        # A live fallback is acceptable only for today's run.
        if trade_date != date.today():
            print(f"    No dated index file available for {trade_date} (HTTP {resp.status_code})")
            return False

        live_resp = session.get("https://www.nseindia.com/api/allIndices", timeout=15)
        if live_resp.status_code != 200:
            print(f"    Index API failed: {live_resp.status_code}")
            return False

        df = pd.DataFrame(live_resp.json()["data"])[["index", "last"]]
        df.columns = ["index_name", "close"]
    else:
        df = pd.read_csv(StringIO(resp.text))[["Index Name", "Closing Index Value"]]
        df.columns = ["index_name", "close"]

    df["index_name"] = df["index_name"].astype(str).str.strip()
    df["normalized"] = df["index_name"].apply(_normalize_index_name)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, index_name FROM indices")).fetchall()
        index_map = {_normalize_index_name(r.index_name): r.id for r in rows}

        inserted = 0
        for _, row in df.iterrows():
            idx_id = index_map.get(row.normalized)
            if not idx_id:
                continue
            conn.execute(text("""
                INSERT INTO index_prices (index_id, trade_date, close)
                VALUES (:iid, :d, :close)
                ON CONFLICT (index_id, trade_date) DO UPDATE
                SET close = EXCLUDED.close
            """), {"iid": idx_id, "d": trade_date, "close": float(row.close)})
            inserted += 1
        conn.commit()

    print(f"    Inserted {inserted} index prices.")
    return inserted > 0


# ── Step 3: Corporate Actions ─────────────────────────────────────

def process_corporate_actions(session: requests.Session):
    print("[3] Processing corporate actions...")
    # Fetch new actions
    from pipeline.corporate_actions import fetch_and_store_actions
    fetch_and_store_actions(session)

    # Apply pending
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE corporate_actions ca
            SET processed = TRUE, processed_at = NOW()
            WHERE ca.processed = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM stocks_master sm WHERE sm.symbol = ca.symbol
              )
        """))
        conn.commit()

        earliest_ex_date = conn.execute(text("""
            SELECT MIN(ex_date) FROM corporate_actions WHERE processed = FALSE
        """)).scalar()
        count = conn.execute(text(
            "SELECT COUNT(*) FROM corporate_actions WHERE processed = FALSE"
        )).scalar()
        if count:
            print(f"    Applying {count} pending corporate action(s)...")
            conn.execute(text("CALL apply_corporate_actions()"))
            conn.commit()
            return earliest_ex_date
        else:
            print("    No pending corporate actions.")
            return None


def reset_derived_metrics(from_date: date):
    print(f"    Resetting derived metrics from {from_date}...")
    with engine.connect() as conn:
        for table in (
            "leadership_stability_30d",
            "rs_acceleration",
            "rs_rankings",
            "rs_values",
            "returns",
            "universe_daily",
        ):
            conn.execute(text(f"DELETE FROM {table} WHERE trade_date >= :d"), {"d": from_date})
        conn.commit()


def prune_stock_only_dates(from_date: date | None = None):
    predicate = "AND trade_date >= :d" if from_date else ""
    params = {"d": from_date} if from_date else {}
    with engine.connect() as conn:
        orphan_dates = conn.execute(text(f"""
            SELECT DISTINCT trade_date
            FROM stock_prices
            WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM index_prices)
            {predicate}
        """), params).fetchall()
        if not orphan_dates:
            return

        for table in (
            "leadership_stability_30d",
            "rs_acceleration",
            "rs_rankings",
            "rs_values",
            "returns",
            "universe_daily",
        ):
            conn.execute(text(f"""
                DELETE FROM {table}
                WHERE trade_date IN (
                    SELECT DISTINCT trade_date
                    FROM stock_prices
                    WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM index_prices)
                    {predicate}
                )
            """), params)

        conn.execute(text(f"""
            DELETE FROM stock_prices
            WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM index_prices)
            {predicate}
        """), params)
        conn.commit()


def rebuild_metrics_from(from_date: date):
    print(f"    Recomputing derived metrics from {from_date}...")
    with engine.connect() as conn:
        dates = [
            row.trade_date for row in conn.execute(text("""
                SELECT DISTINCT sp.trade_date
                FROM stock_prices sp
                WHERE sp.trade_date >= :d
                  AND sp.trade_date IN (SELECT DISTINCT trade_date FROM index_prices)
                ORDER BY sp.trade_date
            """), {"d": from_date}).fetchall()
        ]

    for d in dates:
        compute_metrics(d)


# ── Step 4: Compute RS Metrics ────────────────────────────────────

def compute_metrics(trade_date: date):
    print(f"[4] Computing RS metrics for {trade_date}...")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT compute_daily_metrics(:d)"),
            {"d": trade_date}
        ).scalar()
        conn.commit()
    print(f"    {result}")


# ── Main ──────────────────────────────────────────────────────────

def run_pipeline(trade_date: date = None):
    if trade_date is None:
        trade_date = date.today()

    print(f"\n{'='*50}")
    print(f"  RSRank Daily Pipeline — {trade_date}")
    print(f"{'='*50}\n")

    session = _make_session()

    try:
        success = ingest_stock_data(trade_date, session)
        if not success:
            print("Pipeline stopped — no stock data for this date.")
            return

        has_index_data = ingest_index_prices(trade_date, session)
        if not has_index_data:
            print("Pipeline stopped - no index data for this date.")
            return

        earliest_ex_date = process_corporate_actions(session)
        if earliest_ex_date:
            reset_derived_metrics(earliest_ex_date)
            rebuild_metrics_from(earliest_ex_date)
        else:
            compute_metrics(trade_date)

        msg = f"RSRank pipeline completed successfully for {trade_date}"
        print(msg)
        send_email("✅ RSRank Pipeline Success", msg)
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    d = None
    if len(sys.argv) > 1:
        d = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    run_pipeline(d)



