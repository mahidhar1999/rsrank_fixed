"""
RSRank Monthly Pipeline — Production Ready v3
=============================================
Single entry point for ALL data setup and maintenance.
Run on 1st of each month via cron, or manually anytime.

Can also be used as the INITIAL SETUP script on a fresh database.

Steps (all idempotent — safe to re-run):
  1.  Fetch NSE equity list + listing dates from EQUITY_L.csv
  2.  Insert new stocks into stocks_master
  3.  Bulk backfill prices (one bhavcopy per day for ALL stocks)
  4.  Backfill index prices from BASELINE_DATE → today
  5.  Tag ETFs
  6.  Refresh stock-index membership
  7.  Fetch + apply corporate actions
  8.  Rebuild RS for any missing dates
  9.  Print full summary

Config at top — tune as needed.
All steps safe to re-run (ON CONFLICT DO NOTHING everywhere).
Session refreshed every N API calls to avoid NSE rate limits.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta, date
from io import StringIO
from urllib.parse import quote
from sqlalchemy import text
import time, sys, os, logging, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from app.db import engine
except ModuleNotFoundError:
    from db import engine

# ── Config ────────────────────────────────────────────────────────
BASELINE_DATE         = date(2024, 1, 1)
REQUEST_DELAY         = 0.35   # seconds between NSE quote API calls
BACKFILL_DELAY        = 0.25   # seconds between bhavcopy downloads
INDEX_DELAY           = 0.25   # seconds between index CSV downloads
SESSION_REFRESH_EVERY = 50     # refresh NSE cookies every N API calls
RETRY_COUNT           = 5
RETRY_DELAY           = 5      # seconds between retries

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept":          "text/html,application/json,*/*",
}

# ── Logging ───────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/monthly.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("monthly")


# ================================================================
# HTTP Helpers
# ================================================================

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)
        log.info("  NSE session initialised")
    except Exception as e:
        log.warning(f"  Session init warning: {e}")
    return s


def _refresh_session(session: requests.Session) -> requests.Session:
    try:
        session.get("https://www.nseindia.com", timeout=15)
    except Exception:
        pass
    return session


def _fetch(session: requests.Session, url: str,
           retries: int = RETRY_COUNT) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None  # weekend / holiday file missing
        except Exception as e:
            log.debug(f"    Retry {attempt + 1}/{retries}: {e}")
        time.sleep(RETRY_DELAY)
    return None


# ================================================================
# STEP 1 — Fetch NSE equity list with listing dates
# ================================================================

def fetch_nse_equities(session) -> pd.DataFrame:
    """
    Returns DataFrame: SYMBOL, LISTING_DATE
    Reads listing dates directly from EQUITY_L.csv — no per-stock API calls.
    """
    log.info("[1] Fetching NSE equity list...")

    r = _fetch(session,
               "https://archives.nseindia.com/content/equities/EQUITY_L.csv")
    if r is None:
        raise RuntimeError("Failed to fetch EQUITY_L.csv after retries")

    df = pd.read_csv(StringIO(r.text))
    df.columns = df.columns.str.strip().str.upper()
    df = df[df["SERIES"].str.strip().isin(["EQ", "BE"])].copy()
    df["SYMBOL"] = df["SYMBOL"].str.strip()

    # Locate listing date column (NSE occasionally renames it)
    date_col = next(
        (c for c in df.columns if "LISTING" in c),
        next((c for c in df.columns if "DATE" in c), None)
    )
    df["LISTING_DATE"] = (
        pd.to_datetime(df[date_col], dayfirst=True, errors="coerce").dt.date
        if date_col else None
    )

    result = df[["SYMBOL", "LISTING_DATE"]].drop_duplicates("SYMBOL")
    log.info(f"  {len(result)} symbols  |  "
             f"{result['LISTING_DATE'].notna().sum()} have listing dates")
    return result


# ================================================================
# STEP 2 — Insert / update stocks_master
# ================================================================

def insert_new_stocks(equity_df: pd.DataFrame) -> list[str]:
    """
    Bulk-inserts new symbols. Updates listing_date for NULLs.
    Returns list of NEW symbol strings (need backfill).
    """
    log.info("[2] Syncing stocks_master...")

    with engine.connect() as conn:
        existing = {r.symbol for r in
                    conn.execute(text("SELECT symbol FROM stocks_master")).fetchall()}

    new_df      = equity_df[~equity_df["SYMBOL"].isin(existing)]
    new_symbols = new_df["SYMBOL"].tolist()
    log.info(f"  {len(existing)} existing  |  {len(new_symbols)} new")

    if new_symbols:
        with engine.begin() as conn:
            for _, row in new_df.iterrows():
                conn.execute(text("""
                    INSERT INTO stocks_master (symbol, listing_date, instrument_type)
                    VALUES (:sym, :ld, 'EQUITY')
                    ON CONFLICT (symbol) DO NOTHING
                """), {"sym": row["SYMBOL"], "ld": row["LISTING_DATE"]})
        log.info(f"  Inserted {len(new_symbols)} new stocks")

    # Fill missing listing dates on existing rows
    with engine.begin() as conn:
        updated = 0
        for _, row in equity_df[equity_df["LISTING_DATE"].notna()].iterrows():
            res = conn.execute(text("""
                UPDATE stocks_master SET listing_date = :ld
                WHERE symbol = :sym AND listing_date IS NULL
            """), {"sym": row["SYMBOL"], "ld": row["LISTING_DATE"]})
            updated += res.rowcount
    if updated:
        log.info(f"  Filled listing dates for {updated} existing stocks")

    return new_symbols


# ================================================================
# STEP 3 — Bulk backfill stock prices
# ================================================================

def bulk_backfill_prices(new_symbols: list[str], session):
    """
    Downloads each bhavcopy CSV once and extracts the requested symbols.
    The default monthly run passes all equity symbols so historical gaps and
    stale rows are repaired for existing stocks as well.
    """
    if not new_symbols:
        log.info("[3] No new stocks — skipping stock price backfill")
        return

    log.info(f"[3] Bulk backfill for {len(new_symbols)} new stocks "
             f"({BASELINE_DATE} → today)...")

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, symbol FROM stocks_master WHERE symbol = ANY(:syms)"
        ), {"syms": new_symbols}).fetchall()
    stock_map    = {r.symbol: r.id for r in rows}
    new_syms_set = set(new_symbols)

    current       = BASELINE_DATE
    today         = date.today()
    trading_days  = 0
    rows_inserted = 0
    days_skipped  = 0

    while current <= today:
        url = (
            "https://archives.nseindia.com/products/content/"
            f"sec_bhavdata_full_{current.strftime('%d%m%Y')}.csv"
        )
        r = _fetch(session, url)

        if r:
            try:
                df = pd.read_csv(StringIO(r.text))
                df.columns = df.columns.str.strip().str.upper()
                df["SYMBOL"] = df["SYMBOL"].str.strip()

                df = df[
                    df["SYMBOL"].isin(new_syms_set) &
                    df["SERIES"].str.strip().str.upper().isin(["EQ", "BE"])
                ].copy()

                if not df.empty:
                    if "TTL_TRD_VAL" in df.columns:
                        df["TV"] = pd.to_numeric(
                            df["TTL_TRD_VAL"], errors="coerce").fillna(0)
                    elif "TURNOVER_LACS" in df.columns:
                        df["TV"] = pd.to_numeric(
                            df["TURNOVER_LACS"], errors="coerce").fillna(0) * 100_000
                    else:
                        df["TV"] = 0.0

                    batch = []
                    for _, row in df.iterrows():
                        sid = stock_map.get(row["SYMBOL"])
                        if not sid:
                            continue
                        try:
                            batch.append({
                                "sid": sid, "d": current,
                                "c":   float(row["CLOSE_PRICE"]),
                                "v":   int(row["TTL_TRD_QNTY"]),
                                "tv":  float(row["TV"]),
                            })
                        except (ValueError, TypeError):
                            continue

                    if batch:
                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO stock_prices
                                    (stock_id, trade_date, close, volume, traded_value)
                                VALUES (:sid, :d, :c, :v, :tv)
                                ON CONFLICT (stock_id, trade_date) DO UPDATE
                                SET close = EXCLUDED.close,
                                    volume = EXCLUDED.volume,
                                    traded_value = EXCLUDED.traded_value
                            """), batch)
                        rows_inserted += len(batch)

                trading_days += 1

            except Exception as e:
                log.warning(f"  Parse error {current}: {e}")
        else:
            days_skipped += 1

        current += timedelta(days=1)
        time.sleep(BACKFILL_DELAY)

        if trading_days > 0 and trading_days % 30 == 0:
            log.info(f"  {current} | {rows_inserted:,} rows inserted")

        if trading_days > 0 and trading_days % 100 == 0:
            session = _refresh_session(session)

    log.info(f"  Stock backfill done: {trading_days} days | "
             f"{rows_inserted:,} rows | {days_skipped} skipped")


# ================================================================
# STEP 4 — Backfill index prices (previously manual fix)
# ================================================================

def backfill_index_prices(session):
    """
    Downloads NSE index CSV for every trading day since BASELINE_DATE.
    Skips dates already loaded. Safe to re-run.
    This was previously only in fix_pipeline.py — now part of monthly.
    """
    log.info("[4] Syncing index prices...")

    with engine.connect() as conn:
        index_rows = conn.execute(text(
            "SELECT id, index_name FROM indices"
        )).fetchall()
        existing_count = conn.execute(text(
            "SELECT COUNT(*) FROM index_prices"
        )).scalar()

    def normalize(name: str) -> str:
        return name.upper().replace("&", "AND").replace("  ", " ").strip()

    index_map = {normalize(r.index_name): r.id for r in index_rows}

    current = BASELINE_DATE
    today   = date.today()
    all_dates = []
    while current <= today:
        all_dates.append(current)
        current += timedelta(days=1)

    log.info(f"  {existing_count:,} existing rows | "
             f"{len(all_dates)} dates to verify")

    inserted_total = 0
    trading_days   = 0
    days_skipped   = 0

    for d in all_dates:
        url = (
            "https://archives.nseindia.com/content/indices/"
            f"ind_close_all_{d.strftime('%d%m%Y')}.csv"
        )
        r = _fetch(session, url)

        if r:
            try:
                df = pd.read_csv(StringIO(r.text))

                if "Index Name" not in df.columns:
                    days_skipped += 1
                    time.sleep(INDEX_DELAY)
                    continue

                df = df[["Index Name", "Closing Index Value"]].copy()
                df.columns = ["index_name", "close"]
                df["normalized"] = df["index_name"].apply(normalize)
                df = df[df["normalized"].isin(index_map)]

                if not df.empty:
                    batch = [
                        {"iid": index_map[row["normalized"]],
                         "d": d, "close": float(row["close"])}
                        for _, row in df.iterrows()
                    ]
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO index_prices (index_id, trade_date, close)
                            VALUES (:iid, :d, :close)
                            ON CONFLICT (index_id, trade_date) DO UPDATE
                            SET close = EXCLUDED.close
                        """), batch)
                    inserted_total += len(batch)

                trading_days += 1

            except Exception as e:
                log.warning(f"  Parse error {d}: {e}")
        else:
            days_skipped += 1

        time.sleep(INDEX_DELAY)

        if trading_days > 0 and trading_days % 60 == 0:
            log.info(f"  {d} | {inserted_total:,} rows inserted")

        if trading_days > 0 and trading_days % 200 == 0:
            session = _refresh_session(session)

    log.info(f"  Index backfill done: {trading_days} days | "
             f"{inserted_total:,} rows | {days_skipped} skipped")


# ================================================================
# STEP 5 — Tag ETFs
# ================================================================

def tag_etfs(session):
    log.info("[5] Updating ETF classification...")

    r = _fetch(session, "https://www.nseindia.com/api/etf")
    if r is None:
        log.warning("  ETF API unavailable — skipping")
        return

    try:
        etf_symbols = [
            d["symbol"].strip() for d in r.json().get("data", [])
            if d.get("symbol")
        ]
    except Exception as e:
        log.warning(f"  ETF parse error: {e}")
        return

    if not etf_symbols:
        log.warning("  No ETF symbols returned")
        return

    with engine.begin() as conn:
        tagged = conn.execute(text("""
            UPDATE stocks_master SET instrument_type = 'ETF'
            WHERE symbol = ANY(:syms)
        """), {"syms": etf_symbols})
        conn.execute(text("""
            UPDATE stocks_master SET instrument_type = 'EQUITY'
            WHERE symbol != ALL(:syms) AND instrument_type = 'ETF'
        """), {"syms": etf_symbols})

    log.info(f"  NSE reports {len(etf_symbols)} ETFs | "
             f"{tagged.rowcount} tagged in stocks_master")


# ================================================================
# STEP 6 — Refresh stock-index membership
# ================================================================

def refresh_membership(session):
    """
    Builds stock → sector mapping using NSE quote API.
    Replaces what was previously a manual fix step.
    """
    log.info("[6] Refreshing stock-index membership...")

    with engine.connect() as conn:
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

    total   = len(stocks)
    mapped  = 0
    failed  = 0
    no_idx  = 0
    counter = 0

    log.info(f"  Processing {total} equity stocks...")

    for stock in stocks:
        counter += 1

        if counter % SESSION_REFRESH_EVERY == 0:
            session = _refresh_session(session)
            log.info(f"  {counter}/{total} | mapped: {mapped} | "
                     f"failed: {failed} | no_index: {no_idx}")

        try:
            r = _fetch(
                session,
                f"https://www.nseindia.com/api/quote-equity"
                f"?symbol={quote(stock.symbol)}"
            )
            if r is None:
                failed += 1
                continue

            api_indices = r.json().get("metadata", {}).get("pdSectorIndAll", [])
            if not api_indices:
                no_idx += 1
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
                            (stock_id, index_id, effective_from,
                             effective_to, is_primary)
                        VALUES (:sid, :iid, :ef, NULL, :ip)
                        ON CONFLICT (stock_id, index_id, effective_from)
                        DO UPDATE SET is_primary = EXCLUDED.is_primary
                    """), {
                        "sid": stock.id, "iid": idx_id,
                        "ef":  eff_from, "ip":  is_primary,
                    })

            mapped += 1
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            failed += 1
            if failed <= 3:
                log.warning(f"  Error {stock.symbol}: {e}")

    with engine.connect() as conn:
        total_rows = conn.execute(text(
            "SELECT COUNT(*) FROM stock_index_membership"
        )).scalar()

    log.info(f"  Done: {mapped} mapped | {failed} failed | "
             f"{no_idx} no index | {total_rows:,} total rows")


# ================================================================
# STEP 7 — Corporate actions
# ================================================================

def process_corporate_actions(session):
    """
    Fetches BONUS/SPLIT events from NSE and adjusts historical prices.
    Must run BEFORE RS computation so RS uses adjusted prices.
    Returns the earliest ex-date affected in this run so downstream metrics
    can be recomputed from the right point in history.
    """
    log.info("[7] Processing corporate actions...")

    from pipeline.corporate_actions import fetch_and_store_actions
    inserted = fetch_and_store_actions(session)
    log.info(f"  {inserted} new action(s) fetched from NSE")

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE corporate_actions ca
            SET processed = TRUE, processed_at = NOW()
            WHERE ca.processed = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM stocks_master sm WHERE sm.symbol = ca.symbol
              )
        """))

    with engine.connect() as conn:
        earliest_ex_date = conn.execute(text("""
            SELECT MIN(ex_date) FROM corporate_actions WHERE processed = FALSE
        """)).scalar()
        pending = conn.execute(text(
            "SELECT COUNT(*) FROM corporate_actions WHERE processed = FALSE"
        )).scalar()

    if pending == 0:
        log.info("  No pending corporate actions")
        return None

    log.info(f"  Applying {pending} pending action(s)...")
    with engine.begin() as conn:
        conn.execute(text("CALL apply_corporate_actions()"))
    log.info("  Corporate actions applied ✅")
    return earliest_ex_date


def reset_derived_metrics(from_date: date):
    log.info(f"  Resetting derived metrics from {from_date}...")
    with engine.begin() as conn:
        for table in (
            "leadership_stability_30d",
            "rs_acceleration",
            "rs_rankings",
            "rs_values",
            "returns",
            "universe_daily",
        ):
            conn.execute(text(f"DELETE FROM {table} WHERE trade_date >= :d"), {"d": from_date})


def prune_stock_only_dates(from_date: date = BASELINE_DATE):
    log.info(f"  Removing stock-only dates from {from_date}...")
    with engine.begin() as conn:
        for table in (
            "leadership_stability_30d",
            "rs_acceleration",
            "rs_rankings",
            "rs_values",
            "returns",
            "universe_daily",
        ):
            conn.execute(text("""
                DELETE FROM {table}
                WHERE trade_date IN (
                    SELECT DISTINCT trade_date
                    FROM stock_prices
                    WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM index_prices)
                      AND trade_date >= :d
                )
            """.replace('{table}', table)), {"d": from_date})

        conn.execute(text("""
            DELETE FROM stock_prices
            WHERE trade_date NOT IN (SELECT DISTINCT trade_date FROM index_prices)
              AND trade_date >= :d
        """), {"d": from_date})


# ================================================================
# STEP 8 — Rebuild RS for all missing dates
# ================================================================

def rebuild_missing_rs(from_date: date = BASELINE_DATE, recompute_existing: bool = False):
    """
    Computes the RS pipeline for overlapping stock/index dates.
    When recompute_existing is True, all derived rows from from_date onward are
    rebuilt. Otherwise only dates missing rs_rankings are filled in.
    """
    log.info("[8] Computing RS for missing dates...")

    with engine.connect() as conn:
        if recompute_existing:
            missing = conn.execute(text("""
                SELECT DISTINCT sp.trade_date
                FROM stock_prices sp
                WHERE sp.trade_date >= :baseline
                  AND sp.trade_date IN (
                      SELECT DISTINCT trade_date FROM index_prices
                  )
                ORDER BY sp.trade_date
            """), {"baseline": from_date}).fetchall()
        else:
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
            """), {"baseline": from_date}).fetchall()

    total = len(missing)
    log.info(f"  {total} dates need computation")

    if total == 0:
        log.info("  All dates up to date ✅")
        return

    computed = 0
    errors   = 0

    for row in missing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("SELECT compute_daily_metrics(:d)"),
                    {"d": row.trade_date}
                )
            computed += 1
            if computed % 20 == 0:
                log.info(f"  {computed}/{total} | latest: {row.trade_date}")

        except Exception as e:
            errors += 1
            log.warning(f"  Error {row.trade_date}: {e}")

    log.info(f"  Done: {computed} computed | {errors} errors")


# ================================================================
# STEP 9 — Summary
# ================================================================

def print_summary():
    log.info("\n" + "="*50)
    log.info("DATABASE SUMMARY")
    log.info("="*50)

    queries = [
        ("stocks_master",
         "SELECT COUNT(*) as total, "
         "SUM(CASE WHEN instrument_type='EQUITY' THEN 1 ELSE 0 END) as equity, "
         "SUM(CASE WHEN instrument_type='ETF'    THEN 1 ELSE 0 END) as etf "
         "FROM stocks_master"),
        ("stock_prices",
         "SELECT COUNT(*) as rows, MIN(trade_date) as from_d, "
         "MAX(trade_date) as to_d FROM stock_prices"),
        ("index_prices",
         "SELECT COUNT(*) as rows, MIN(trade_date) as from_d, "
         "MAX(trade_date) as to_d FROM index_prices"),
        ("stock_index_membership",
         "SELECT COUNT(*) as rows, "
         "SUM(CASE WHEN is_primary THEN 1 ELSE 0 END) as primary_rows "
         "FROM stock_index_membership"),
        ("corporate_actions",
         "SELECT COUNT(*) as total, "
         "SUM(CASE WHEN processed THEN 1 ELSE 0 END) as processed "
         "FROM corporate_actions"),
        ("universe_daily",
         "SELECT COUNT(*) as rows, MIN(trade_date) as from_d, "
         "MAX(trade_date) as to_d FROM universe_daily"),
        ("rs_rankings",
         "SELECT COUNT(*) as rows, MIN(trade_date) as from_d, "
         "MAX(trade_date) as to_d FROM rs_rankings"),
        ("rs_values",        "SELECT COUNT(*) as rows FROM rs_values"),
        ("rs_acceleration",  "SELECT COUNT(*) as rows FROM rs_acceleration"),
        ("leadership_stability_30d",
         "SELECT COUNT(*) as rows FROM leadership_stability_30d"),
    ]

    with engine.connect() as conn:
        for name, q in queries:
            try:
                row  = conn.execute(text(q)).first()
                vals = " | ".join(
                    f"{k}: {v:,}" if isinstance(v, int)
                    else f"{k}: {v}"
                    for k, v in zip(row._fields, row)
                    if v is not None
                )
                log.info(f"  {name:<30} {vals}")
            except Exception as e:
                log.warning(f"  {name:<30} ERROR: {e}")


# ================================================================
# Main — supports --only flag for running single steps
# ================================================================

STEPS = {
    "equities":    "Step 1+2: Fetch equity list + insert stocks",
    "stock_prices":"Step 3:   Bulk backfill stock prices",
    "index_prices":"Step 4:   Backfill index prices",
    "etf":         "Step 5:   Tag ETFs",
    "membership":  "Step 6:   Refresh stock-index membership",
    "corp_actions":"Step 7:   Fetch + apply corporate actions",
    "rs":          "Step 8:   Rebuild missing RS dates",
    "summary":     "Step 9:   Print summary only",
}


def run_monthly_pipeline(only: str = None):
    start_time = datetime.now()

    log.info("\n" + "="*50)
    log.info(f"  RSRank Monthly Pipeline v3 — {date.today()}")
    if only:
        log.info(f"  Running: {STEPS.get(only, only)}")
    log.info("="*50 + "\n")

    session = _make_session()

    try:
        if only == "summary":
            print_summary()
            return

        if only == "equities" or only is None:
            equity_df   = fetch_nse_equities(session)
            new_symbols = insert_new_stocks(equity_df)
        else:
            equity_df   = None
            new_symbols = []

        if only == "stock_prices" or only is None:
            if only is None and equity_df is not None:
                symbols_to_backfill = equity_df["SYMBOL"].tolist()
            else:
                with engine.connect() as conn:
                    symbols_to_backfill = [
                        r.symbol for r in conn.execute(text(
                            "SELECT symbol FROM stocks_master "
                            "WHERE instrument_type = 'EQUITY'"
                        )).fetchall()
                    ]
            bulk_backfill_prices(symbols_to_backfill, session)

        if only == "index_prices" or only is None:
            backfill_index_prices(session)

        if only == "etf" or only is None:
            tag_etfs(session)

        if only == "membership" or only is None:
            refresh_membership(session)

        if only == "corp_actions" or only is None:
            earliest_ex_date = process_corporate_actions(session)
        else:
            earliest_ex_date = None

        if only == "rs" or only is None:
            if only is None:
                rebuild_from = earliest_ex_date or BASELINE_DATE
                reset_derived_metrics(rebuild_from)
                rebuild_missing_rs(from_date=rebuild_from, recompute_existing=True)
            elif earliest_ex_date:
                reset_derived_metrics(earliest_ex_date)
                rebuild_missing_rs(from_date=earliest_ex_date, recompute_existing=True)
            else:
                rebuild_missing_rs()

    except Exception as e:
        log.error(f"\n❌ Pipeline failed: {e}")
        raise

    print_summary()

    elapsed = datetime.now() - start_time
    log.info(f"\n  Total time: {str(elapsed).split('.')[0]}")
    log.info("="*50)
    log.info("  Pipeline complete ✅")
    log.info("="*50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RSRank Monthly Pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--only",
        choices=list(STEPS.keys()),
        help="\n".join(f"  {k:<15} {v}" for k, v in STEPS.items()),
    )
    args = parser.parse_args()
    run_monthly_pipeline(only=args.only)











