"""
clean_holidays.py
Removes non-trading days from stock_prices and index_prices.
A date is a trading day only if NSE published a bhavcopy for it.
We verify by checking which dates have data for the most liquid stocks.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from app.db import engine
except ModuleNotFoundError:
    from db import engine

from sqlalchemy import text
from datetime import date, timedelta

def clean_holidays():
    print("\n=== Holiday / Non-Trading Day Cleaner ===\n")

    # ── Step 1: Find all dates in stock_prices
    with engine.connect() as conn:
        all_dates = [r.trade_date for r in conn.execute(text("""
            SELECT DISTINCT trade_date
            FROM stock_prices
            ORDER BY trade_date
        """)).fetchall()]

    print(f"Total distinct dates in stock_prices: {len(all_dates)}")

    # ── Step 2: A real trading day has data for many stocks
    # If fewer than 100 stocks traded on a day, it's a holiday/error
    MIN_STOCKS_THRESHOLD = 100

    with engine.connect() as conn:
        stock_counts = {
            r.trade_date: r.cnt for r in conn.execute(text("""
                SELECT trade_date, COUNT(DISTINCT stock_id) as cnt
                FROM stock_prices
                GROUP BY trade_date
                ORDER BY trade_date
            """)).fetchall()
        }

    # ── Step 3: Identify bad dates
    holiday_dates = [
        d for d, cnt in stock_counts.items()
        if cnt < MIN_STOCKS_THRESHOLD
    ]

    # Also flag weekends explicitly
    weekend_dates = [
        d for d in all_dates
        if d.weekday() in (5, 6)  # Saturday=5, Sunday=6
    ]

    bad_dates = sorted(set(holiday_dates + weekend_dates))

    print(f"\nDates with < {MIN_STOCKS_THRESHOLD} stocks (likely holidays/errors):")
    for d in bad_dates:
        cnt = stock_counts.get(d, 0)
        day = d.strftime("%A")
        print(f"  {d}  ({day})  stocks: {cnt}")

    if not bad_dates:
        print("  None found — data looks clean!")
        return

    print(f"\nTotal bad dates to remove: {len(bad_dates)}")
    confirm = input("\nDelete these dates from stock_prices and index_prices? (yes/no): ")

    if confirm.strip().lower() != "yes":
        print("Aborted — nothing deleted.")
        return

    # ── Step 4: Delete bad dates
    with engine.begin() as conn:
        sp_deleted = conn.execute(text("""
            DELETE FROM stock_prices
            WHERE trade_date = ANY(:dates)
        """), {"dates": bad_dates}).rowcount

        ip_deleted = conn.execute(text("""
            DELETE FROM index_prices
            WHERE trade_date = ANY(:dates)
        """), {"dates": bad_dates}).rowcount

    print(f"\nDeleted:")
    print(f"  stock_prices:  {sp_deleted:,} rows")
    print(f"  index_prices:  {ip_deleted:,} rows")

    # ── Step 5: Verify result
    with engine.connect() as conn:
        sp_stats = conn.execute(text("""
            SELECT COUNT(*) as rows, MIN(trade_date) as from_d, MAX(trade_date) as to_d
            FROM stock_prices
        """)).first()
        ip_stats = conn.execute(text("""
            SELECT COUNT(*) as rows, MIN(trade_date) as from_d, MAX(trade_date) as to_d
            FROM index_prices
        """)).first()

    print(f"\nAfter cleanup:")
    print(f"  stock_prices: {sp_stats.rows:,} rows  ({sp_stats.from_d} → {sp_stats.to_d})")
    print(f"  index_prices: {ip_stats.rows:,} rows  ({ip_stats.from_d} → {ip_stats.to_d})")
    print("\n✅ Holiday cleanup complete")


if __name__ == "__main__":
    clean_holidays()