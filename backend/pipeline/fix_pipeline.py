"""
fix_pipeline.py — fixes all 4 issues in sequence:
  1. ETF tagging in stocks_master
  2. Index prices backfill from Jan 2024
  3. Stock-index membership rebuild
  4. RS computation for all dates

Run once:
  docker exec -it rsrank-api-1 python scripts/fix_pipeline.py
"""

import requests
import pandas as pd
from datetime import date, timedelta
from io import StringIO
from urllib.parse import quote
from sqlalchemy import text
import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from app.db import engine
except ModuleNotFoundError:
    from db import engine

BASELINE_DATE = date(2024, 1, 1)
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}


def _session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com", timeout=10)
    return s


def _refresh(session):
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass
    return session


def _fetch(session, url, retries=4):
    for i in range(retries):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                return r
        except Exception as e:
            print(f"    Retry {i+1}: {e}")
        time.sleep(4)
    return None


# ================================================================
# FIX 1 — ETF Tagging
# ================================================================

def fix_etf_tagging(session):
    print("\n" + "="*50)
    print("FIX 1 — ETF Tagging")
    print("="*50)

    # Check current state
    with engine.connect() as conn:
        counts = conn.execute(text("""
            SELECT instrument_type, COUNT(*) as cnt
            FROM stocks_master
            GROUP BY instrument_type
        """)).fetchall()
        print("  Current instrument_type distribution:")
        for r in counts:
            print(f"    {r.instrument_type or 'NULL'}: {r.cnt}")

    # Fetch ETF list from NSE
    print("  Fetching ETF list from NSE...")
    r = _fetch(session, "https://www.nseindia.com/api/etf")
    if r is None:
        print("  ETF API failed — trying alternative method")
        _fix_etf_from_equity_csv(session)
        return

    data = r.json().get("data", [])
    etf_symbols = [d["symbol"].strip() for d in data if d.get("symbol")]
    print(f"  NSE reports {len(etf_symbols)} ETF symbols")

    if not etf_symbols:
        print("  No ETF symbols returned — skipping")
        return

    # Check overlap with stocks_master
    with engine.connect() as conn:
        matched = conn.execute(text("""
            SELECT COUNT(*) FROM stocks_master
            WHERE symbol = ANY(:syms)
        """), {"syms": etf_symbols}).scalar()
        print(f"  {matched} ETF symbols found in stocks_master")

        if matched == 0:
            print("  No overlap — checking symbol format mismatch...")
            sample_etf = etf_symbols[:5]
            sample_db = conn.execute(text(
                "SELECT symbol FROM stocks_master LIMIT 10"
            )).fetchall()
            print(f"  ETF sample: {sample_etf}")
            print(f"  DB sample: {[r.symbol for r in sample_db]}")

        # Tag ETFs
        result = conn.execute(text("""
            UPDATE stocks_master
            SET instrument_type = 'ETF'
            WHERE symbol = ANY(:syms)
        """), {"syms": etf_symbols})
        print(f"  Tagged {result.rowcount} ETFs")

        # Reset non-ETFs back to EQUITY (in case of stale tags)
        result2 = conn.execute(text("""
            UPDATE stocks_master
            SET instrument_type = 'EQUITY'
            WHERE symbol != ALL(:syms)
              AND (instrument_type IS NULL OR instrument_type = 'ETF')
        """), {"syms": etf_symbols})
        print(f"  Reset {result2.rowcount} stocks back to EQUITY")

        conn.commit()

    # Final count
    with engine.connect() as conn:
        counts = conn.execute(text("""
            SELECT instrument_type, COUNT(*) as cnt
            FROM stocks_master
            GROUP BY instrument_type
        """)).fetchall()
        print("  Final distribution:")
        for r in counts:
            print(f"    {r.instrument_type}: {r.cnt}")

    print("  FIX 1 complete ✅")


def _fix_etf_from_equity_csv(session):
    """
    Fallback: EQUITY_L.csv has a SERIES column.
    Symbols with series not in EQ/BE are likely ETFs.
    """
    print("  Using EQUITY_L.csv series column as fallback...")
    r = _fetch(session, "https://archives.nseindia.com/content/equities/EQUITY_L.csv")
    if r is None:
        print("  Could not fetch EQUITY_L.csv either — ETF fix skipped")
        return

    df = pd.read_csv(StringIO(r.text))
    df.columns = df.columns.str.strip().str.upper()
    df["SYMBOL"] = df["SYMBOL"].str.strip()

    # Non EQ/BE series are ETFs/other instruments
    etf_df = df[~df["SERIES"].isin(["EQ", "BE"])]
    etf_symbols = etf_df["SYMBOL"].tolist()
    print(f"  Found {len(etf_symbols)} non-EQ/BE symbols")

    with engine.begin() as conn:
        r = conn.execute(text("""
            UPDATE stocks_master SET instrument_type = 'ETF'
            WHERE symbol = ANY(:syms)
        """), {"syms": etf_symbols})
        print(f"  Tagged {r.rowcount} ETFs via series fallback")


# ================================================================
# FIX 2 — Index Prices Backfill from 2024
# ================================================================

def fix_index_prices(session):
    print("\n" + "="*50)
    print("FIX 2 — Index Prices Backfill (Jan 2024 → today)")
    print("="*50)

    # Load index map
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, index_name FROM indices")).fetchall()
        # Check existing coverage
        existing = conn.execute(text("""
            SELECT MIN(trade_date) as min_d, MAX(trade_date) as max_d, COUNT(*) as cnt
            FROM index_prices
        """)).first()

    print(f"  {len(rows)} indices tracked in DB")
    print(f"  Existing index_prices: {existing.cnt} rows | "
          f"{existing.min_d} → {existing.max_d}")

    def normalize(name):
        return name.upper().replace("&", "AND").replace("  ", " ").strip()

    index_map = {normalize(r.index_name): r.id for r in rows}

    # Find dates already fully loaded
    with engine.connect() as conn:
        loaded_dates = {
            r.trade_date for r in
            conn.execute(text(
                "SELECT DISTINCT trade_date FROM index_prices"
            )).fetchall()
        }

    current = BASELINE_DATE
    today   = date.today()
    inserted_total = 0
    days_processed = 0
    days_skipped   = 0

    print(f"  Downloading daily index CSVs from {BASELINE_DATE} to {today}...")

    while current <= today:
        if current in loaded_dates:
            current += timedelta(days=1)
            continue

        url = (
            "https://archives.nseindia.com/content/indices/"
            f"ind_close_all_{current.strftime('%d%m%Y')}.csv"
        )

        r = _fetch(session, url)

        if r and r.status_code == 200:
            try:
                df = pd.read_csv(StringIO(r.text))

                if "Index Name" not in df.columns:
                    days_skipped += 1
                    current += timedelta(days=1)
                    continue

                df = df[["Index Name", "Closing Index Value"]].copy()
                df.columns = ["index_name", "close"]
                df["normalized"] = df["index_name"].apply(normalize)
                df = df[df["normalized"].isin(index_map)]

                if not df.empty:
                    batch = [
                        {
                            "iid":   index_map[row["normalized"]],
                            "d":     current,
                            "close": float(row["close"]),
                        }
                        for _, row in df.iterrows()
                    ]
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO index_prices (index_id, trade_date, close)
                            VALUES (:iid, :d, :close)
                            ON CONFLICT (index_id, trade_date) DO NOTHING
                        """), batch)
                    inserted_total += len(batch)

                days_processed += 1

            except Exception as e:
                print(f"    Parse error {current}: {e}")
        else:
            days_skipped += 1  # weekend / holiday

        current += timedelta(days=1)
        time.sleep(0.25)

        # Progress report every 60 days
        if days_processed % 60 == 0 and days_processed > 0:
            print(f"    {current} | {inserted_total} rows inserted")

        # Refresh session every 200 days
        if days_processed % 200 == 0 and days_processed > 0:
            session = _refresh(session)

    print(f"  Done: {days_processed} trading days | "
          f"{inserted_total} rows | {days_skipped} non-trading days")
    print("  FIX 2 complete ✅")


# ================================================================
# FIX 3 — Stock-Index Membership
# ================================================================

def fix_membership(session):
    print("\n" + "="*50)
    print("FIX 3 — Stock-Index Membership")
    print("="*50)

    # Check current state
    with engine.connect() as conn:
        current_count = conn.execute(text(
            "SELECT COUNT(*) FROM stock_index_membership"
        )).scalar()
        print(f"  Current membership rows: {current_count}")

    with engine.connect() as conn:
        # Only EQUITY stocks, only those with price data
        stocks = conn.execute(text("""
            SELECT sm.id, sm.symbol
            FROM stocks_master sm
            WHERE sm.instrument_type = 'EQUITY'
              AND sm.is_active = TRUE
              AND EXISTS (
                  SELECT 1 FROM stock_prices sp
                  WHERE sp.stock_id = sm.id LIMIT 1
              )
            ORDER BY sm.symbol
        """)).fetchall()

        indices = conn.execute(text(
            "SELECT id, index_name, index_category FROM indices"
        )).fetchall()

        stock_starts = {
            r.stock_id: r.start_date for r in conn.execute(text("""
                SELECT stock_id, MIN(trade_date) AS start_date
                FROM stock_prices GROUP BY stock_id
            """)).fetchall()
        }

        index_starts = {
            r.index_id: r.start_date for r in conn.execute(text("""
                SELECT index_id, MIN(trade_date) AS start_date
                FROM index_prices GROUP BY index_id
            """)).fetchall()
        }

    index_lookup = {
        i.index_name.strip().upper(): {"id": i.id, "cat": i.index_category}
        for i in indices
    }

    print(f"  Processing {len(stocks)} EQUITY stocks with price data...")

    mapped    = 0
    failed    = 0
    counter   = 0
    no_data   = 0

    for stock in stocks:
        counter += 1

        # Refresh session every 50 stocks
        if counter % 50 == 0:
            session = _refresh(session)
            print(f"    {counter}/{len(stocks)} | mapped: {mapped} | failed: {failed}")

        try:
            r = _fetch(
                session,
                f"https://www.nseindia.com/api/quote-equity?symbol={quote(stock.symbol)}"
            )

            if r is None:
                failed += 1
                continue

            data = r.json()
            api_indices = data.get("metadata", {}).get("pdSectorIndAll", [])

            if not api_indices:
                no_data += 1
                continue

            primary_set = False
            s_start     = stock_starts.get(stock.id)

            with engine.begin() as conn:
                for api_idx in api_indices:
                    norm     = api_idx.strip().upper()
                    idx_data = index_lookup.get(norm)
                    if not idx_data:
                        continue

                    idx_id    = idx_data["id"]
                    is_sector = idx_data["cat"] == "sector"
                    i_start   = index_starts.get(idx_id)

                    if not i_start or not s_start:
                        continue

                    eff_from   = max(i_start, s_start)
                    is_primary = is_sector and not primary_set
                    if is_primary:
                        primary_set = True

                    conn.execute(text("""
                        INSERT INTO stock_index_membership
                            (stock_id, index_id, effective_from, effective_to, is_primary)
                        VALUES (:sid, :iid, :ef, NULL, :ip)
                        ON CONFLICT (stock_id, index_id, effective_from)
                        DO UPDATE SET is_primary = EXCLUDED.is_primary
                    """), {
                        "sid": stock.id, "iid": idx_id,
                        "ef":  eff_from, "ip":  is_primary,
                    })

            mapped += 1
            time.sleep(0.4)

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"    Error {stock.symbol}: {e}")

    with engine.connect() as conn:
        final_count = conn.execute(text(
            "SELECT COUNT(*) FROM stock_index_membership"
        )).scalar()

    print(f"  Done: {mapped} mapped | {failed} failed | {no_data} no index data")
    print(f"  Total membership rows: {final_count}")
    print("  FIX 3 complete ✅")


# ================================================================
# FIX 4 — RS Computation for all dates
# ================================================================

def fix_rs_computation():
    print("\n" + "="*50)
    print("FIX 4 — RS Computation for all trading dates")
    print("="*50)

    with engine.connect() as conn:
        # Dates that have stock prices but no RS rankings
        missing = conn.execute(text("""
            SELECT DISTINCT sp.trade_date
            FROM stock_prices sp
            WHERE sp.trade_date NOT IN (
                SELECT DISTINCT trade_date FROM rs_rankings
            )
            AND sp.trade_date >= :baseline
            AND sp.trade_date IN (
                SELECT DISTINCT trade_date FROM index_prices
            )
            ORDER BY sp.trade_date
        """), {"baseline": BASELINE_DATE}).fetchall()

    total = len(missing)
    print(f"  {total} dates need RS computation")

    if total == 0:
        print("  All dates already computed — nothing to do")
        print("  FIX 4 complete ✅")
        return

    computed = 0
    errors   = 0

    for row in missing:
        try:
            with engine.begin() as conn:
                result = conn.execute(
                    text("SELECT compute_daily_metrics(:d)"),
                    {"d": row.trade_date}
                ).scalar()
            computed += 1

            if computed % 20 == 0:
                print(f"    {computed}/{total} dates computed | latest: {row.trade_date}")

        except Exception as e:
            errors += 1
            print(f"    Error on {row.trade_date}: {e}")

    print(f"  Done: {computed} dates computed | {errors} errors")

    # Final verification
    with engine.connect() as conn:
        stats = conn.execute(text("""
            SELECT
                COUNT(DISTINCT trade_date) as dates,
                COUNT(*) as total_rows,
                MIN(trade_date) as from_date,
                MAX(trade_date) as to_date
            FROM rs_rankings
        """)).first()

    print(f"\n  RS Rankings: {stats.total_rows} rows across "
          f"{stats.dates} dates ({stats.from_date} → {stats.to_date})")
    print("  FIX 4 complete ✅")


# ================================================================
# Summary check
# ================================================================

def print_summary():
    print("\n" + "="*50)
    print("DATABASE SUMMARY")
    print("="*50)

    with engine.connect() as conn:
        tables = [
            ("stocks_master",           "SELECT COUNT(*), SUM(CASE WHEN instrument_type='EQUITY' THEN 1 ELSE 0 END), SUM(CASE WHEN instrument_type='ETF' THEN 1 ELSE 0 END) FROM stocks_master"),
            ("stock_prices",            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_prices"),
            ("index_prices",            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM index_prices"),
            ("stock_index_membership",  "SELECT COUNT(*), SUM(CASE WHEN is_primary THEN 1 ELSE 0 END) FROM stock_index_membership"),
            ("universe_daily",          "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM universe_daily"),
            ("rs_rankings",             "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM rs_rankings"),
            ("rs_values",               "SELECT COUNT(*) FROM rs_values"),
            ("rs_acceleration",         "SELECT COUNT(*) FROM rs_acceleration"),
            ("leadership_stability_30d","SELECT COUNT(*) FROM leadership_stability_30d"),
        ]

        for name, query in tables:
            try:
                r = conn.execute(text(query)).first()
                print(f"  {name:<30} {[v for v in r]}")
            except Exception as e:
                print(f"  {name:<30} ERROR: {e}")


# ================================================================
# Main
# ================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only",
        choices=["etf", "index", "membership", "rs", "summary"],
        help="Run only one specific fix"
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  RSRank Fix Pipeline — {date.today()}")
    print(f"{'='*50}")

    session = _session()

    if args.only == "etf":
        fix_etf_tagging(session)
    elif args.only == "index":
        fix_index_prices(session)
    elif args.only == "membership":
        fix_membership(session)
    elif args.only == "rs":
        fix_rs_computation()
    elif args.only == "summary":
        print_summary()
    else:
        # Run all in correct order
        fix_etf_tagging(session)
        fix_index_prices(session)
        fix_membership(session)
        fix_rs_computation()

    print_summary()
    print(f"\n{'='*50}")
    print("  All fixes complete!")
    print(f"{'='*50}\n")