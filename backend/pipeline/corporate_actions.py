"""
Corporate actions fetcher — BONUS and SPLIT detection from NSE API.
Bug fixed: fetch_actions() no longer executes at import time.
"""

import re
import requests
from datetime import datetime
from sqlalchemy import text
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from app.db import engine
except ModuleNotFoundError:
    from db import engine


def fetch_and_store_actions(session: requests.Session = None) -> int:
    if session is None:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/corporates/corporateActions",
        })
        session.get("https://www.nseindia.com", timeout=10)

    START_DATE = "01-01-2024"
    url = "https://www.nseindia.com/api/corporates-corporateActions"
    params = {
        "index":     "equities",
        "from_date": START_DATE,
        "to_date":   datetime.today().strftime("%d-%m-%Y"),
    }

    resp = session.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"    Corporate actions API failed: {resp.status_code}")
        return 0

    try:
        data = resp.json()
    except Exception:
        print("    Response not JSON")
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in data:
            if row.get("series") != "EQ":
                continue

            symbol  = row.get("symbol", "").strip()
            subject = row.get("subject", "")
            ex_str  = row.get("exDate")

            if not symbol or not subject or not ex_str:
                continue

            try:
                ex_date = datetime.strptime(ex_str, "%d-%b-%Y").date()
            except ValueError:
                continue

            subject_upper = subject.upper()
            action_type = ratio_old = ratio_new = None

            if "BONUS" in subject_upper:
                m = re.search(r"(\d+)\s*:\s*(\d+)", subject)
                if not m:
                    continue
                action_type = "BONUS"
                ratio_old, ratio_new = int(m.group(1)), int(m.group(2))

            elif "SPLIT" in subject_upper or "SUBDIVISION" in subject_upper:
                m = re.search(r"(\d+)\D+(\d+)", subject)
                if not m:
                    continue
                old_face = int(m.group(1))
                new_face = int(m.group(2))
                if new_face == 0:
                    continue
                action_type = "SPLIT"
                ratio_old = 1
                ratio_new = old_face // new_face
            else:
                continue

            result = conn.execute(text("""
                INSERT INTO corporate_actions
                    (symbol, action_type, ratio_old, ratio_new, ex_date)
                VALUES
                    (:symbol, :action_type, :ratio_old, :ratio_new, :ex_date)
                ON CONFLICT (symbol, action_type, ex_date) DO NOTHING
                RETURNING id
            """), {
                "symbol": symbol, "action_type": action_type,
                "ratio_old": ratio_old, "ratio_new": ratio_new, "ex_date": ex_date,
            })
            if result.rowcount:
                inserted += 1

    print(f"    Corporate actions: {inserted} new record(s) inserted.")
    return inserted


# ── Standalone run ────────────────────────────────────────────────
if __name__ == "__main__":
    fetch_and_store_actions()
