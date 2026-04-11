#!/usr/bin/env python3
"""
setup_db.py - Run once on a fresh database.
Creates all tables, functions, and seeds index data.

Usage:
    cd backend
    python scripts/setup_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import engine

SQL_FILES = [
    ("sql/001_schema.sql", "Schema (tables + indexes)"),
    ("sql/002_functions.sql", "Stored functions"),
    ("migrations/002_seed_indices.sql", "Seed 40 NSE indices"),
]


def _strip_psql_meta(sql: str) -> str:
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("\\")]
    return "\n".join(lines).strip()


def run():
    base = os.path.dirname(os.path.dirname(__file__))

    for rel_path, label in SQL_FILES:
        path = os.path.join(base, rel_path)
        if not os.path.exists(path):
            print(f"  Skipping {path} (not found)")
            continue

        print(f"  Running: {label}...", end=" ", flush=True)
        with open(path, encoding="utf-8") as f:
            sql = _strip_psql_meta(f.read())

        if not sql:
            print("OK")
            continue

        raw_conn = engine.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                cur.execute(sql)
            raw_conn.commit()
        except Exception as exc:
            raw_conn.rollback()
            print(f"\n    Failed: {exc}")
            raise
        finally:
            raw_conn.close()

        print("OK")

    print("\nDatabase setup complete!")
    print("Next: run the monthly pipeline to ingest historical data.")
    print("python pipeline/monthly.py\n")


if __name__ == "__main__":
    print("\nRSRank Database Setup\n")
    run()
