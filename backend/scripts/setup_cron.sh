#!/bin/bash
# setup_cron.sh — Install cron jobs for RSRank pipelines
# Run once on your server: bash scripts/setup_cron.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
LOG_DIR="$REPO_DIR/logs"

mkdir -p "$LOG_DIR"

echo "Setting up RSRank cron jobs..."
echo "Repo: $REPO_DIR"
echo "Python: $PYTHON"

# Write crontab
(crontab -l 2>/dev/null; cat <<EOF

# RSRank Daily Pipeline — runs at 6:30 PM IST (13:00 UTC) on weekdays
# NSE closes at 3:30 PM IST; 6:30 gives time for bhavcopy to publish
30 13 * * 1-5 cd $REPO_DIR && $PYTHON pipeline/daily.py >> $LOG_DIR/daily.log 2>&1

# RSRank Monthly Pipeline — runs at 8:00 AM IST on 1st of each month
30 2 1 * * cd $REPO_DIR && $PYTHON pipeline/monthly.py >> $LOG_DIR/monthly.log 2>&1

EOF
) | crontab -

echo "✅ Cron jobs installed:"
crontab -l | grep -A1 "RSRank"
echo ""
echo "Logs will be written to: $LOG_DIR/"
