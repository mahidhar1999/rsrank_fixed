# RSRank — Relative Strength Intelligence Platform

A production-ready momentum analytics platform for NSE stocks.
Tracks RS across 3 layers (stock vs market, stock vs sector, sector vs market),
runs a rules-based Top-50 model portfolio, and gates premium features behind Razorpay.

---

## Architecture

```
rsrank/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── config.py         # Env-based configuration
│   │   ├── db.py             # SQLAlchemy engine
│   │   ├── auth.py           # JWT utilities
│   │   ├── dependencies.py   # FastAPI auth middleware
│   │   ├── schemas.py        # Pydantic request/response models
│   │   └── routers/
│   │       ├── auth_router.py
│   │       ├── market.py
│   │       ├── stocks.py
│   │       ├── sectors.py
│   │       ├── portfolio.py
│   │       ├── acceleration.py
│   │       ├── leadership.py
│   │       ├── payments.py
│   │       └── pipeline.py
│   ├── pipeline/
│   │   ├── daily.py          # Runs every trading day
│   │   ├── monthly.py        # Runs 1st of each month
│   │   └── corporate_actions.py
│   ├── sql/
│   │   ├── 001_schema.sql    # All tables + indexes
│   │   └── 002_functions.sql # RS computation stored functions
│   ├── migrations/
│   │   └── 002_seed_indices.sql  # 40 NSE indices
│   └── scripts/
│       ├── setup_db.py       # One-time DB setup
│       └── setup_cron.sh     # Install cron jobs
└── frontend/
    └── src/
        ├── api/client.js     # All API calls (axios)
        ├── context/AuthContext.jsx
        ├── components/       # Sidebar, Topbar, PaywallGate
        └── pages/            # Overview, Heatmap, Sectors,
                              # Portfolio, Acceleration, Leadership,
                              # Login, Register, Pricing
```

---

## RS Engine

**3-Layer Computation (all run as PostgreSQL stored functions):**

```
A)  RS_stock_market   = (1 + Stock Return) / (1 + Nifty 50 Return)
B)  RS_sector_market  = (1 + Sector Return) / (1 + Nifty 50 Return)
C)  RS_stock_sector   = (1 + Stock Return) / (1 + Sector Return)

RS_combined = 0.75 × RS_65D + 0.25 × RS_125D

Identity check: RS_stock_market ≈ RS_stock_sector × RS_sector_market
```

**Daily computation order:**
1. `build_universe(date)` — Top 750 by 30D avg traded value
2. `compute_daily_returns(date)` — 65D and 125D for all stocks + indices
3. `compute_daily_rs(date)` — 3-layer RS values + rs_combined
4. `compute_rs_rankings(date)` — PERCENT_RANK → 0-100 percentiles
5. `compute_rs_acceleration(date)` — ΔRS vs 10 trading days ago
6. `compute_leadership_stability(date)` — % of last 30D in top tier

All 6 steps are wrapped in `compute_daily_metrics(date)` — call once from Python.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node 20+
- PostgreSQL 15+
- A Razorpay account (test keys work fine)

### 1. Clone and configure

```bash
git clone <your-repo>
cd rsrank

# Backend env
cp backend/.env.example backend/.env
# Edit backend/.env with your DB credentials and keys

# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Set up the database

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE rsrank;"

# Set up backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run schema + functions + seed
python scripts/setup_db.py
```

### 3. Load historical data

```bash
# Monthly pipeline — fetches NSE equity list, inserts stocks,
# backfills prices from Jan 2024, tags ETFs, builds membership.
# Takes 2-4 hours on first run (NSE rate limits).
python pipeline/monthly.py

# Once stock data is loaded, run for today's date:
python pipeline/daily.py
```

### 4. Start the API server

```bash
# From backend/
uvicorn app.main:app --reload --port 8000

# API docs available at: http://localhost:8000/docs
```

### 5. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
# App at: http://localhost:5173
```

### 6. Create your first admin user

```bash
# Register via the UI or directly via API:
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yoursite.com","password":"strongpassword","full_name":"Admin"}'

# Then manually set is_admin = TRUE in DB:
psql -d rsrank -c "UPDATE users SET is_admin = TRUE WHERE email = 'admin@yoursite.com';"
```

---

## Production Deployment (Docker)

```bash
# 1. Copy and fill env
cp .env.example .env
nano .env

# 2. Build and start all services
docker compose up -d --build

# 3. Check logs
docker compose logs -f api

# Services:
#   PostgreSQL  → localhost:5432
#   FastAPI     → localhost:8000
#   React/nginx → localhost:80
```

### Set up cron jobs on the server

```bash
cd backend
chmod +x scripts/setup_cron.sh
bash scripts/setup_cron.sh

# Daily at 6:30 PM IST (after NSE bhavcopy is published)
# Monthly on 1st of each month
```

---

## API Reference

### Public Endpoints (no auth required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/market/summary` | Universe size, leaders/laggards, top sector |
| GET | `/api/market/latest-date` | Latest available trade date |
| GET | `/api/stocks/rankings` | Paginated RS rankings with filters |
| GET | `/api/stocks/heatmap` | Color-bucketed heatmap data |
| GET | `/api/stocks/{symbol}/rs-history` | RS time series for a stock |
| GET | `/api/sectors/rotation` | All sectors RS + trend |
| GET | `/api/sectors/{name}/stocks` | Stocks in a sector |
| GET | `/api/acceleration` | Top emerging + fading by 10D delta |
| GET | `/api/leadership` | 30D stability scores |
| GET | `/api/portfolio/preview` | Top 5 holdings preview (free) |

### Auth Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user info |

### Premium Endpoints (Pro subscription required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/current` | Full 50 holdings |
| GET | `/api/portfolio/performance` | Monthly returns vs Nifty |

### Payment Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/payments/create-order` | Create Razorpay order |
| POST | `/api/payments/verify` | Verify payment + activate plan |
| POST | `/api/payments/webhook` | Razorpay server webhook |

### Admin Endpoints (admin users only)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/pipeline/run-daily` | Trigger daily pipeline |
| POST | `/api/pipeline/run-monthly` | Trigger monthly pipeline |
| GET | `/api/pipeline/status` | Pipeline run status |

---

## Razorpay Setup

1. Create account at [razorpay.com](https://razorpay.com)
2. Get Test keys from Dashboard → Settings → API Keys
3. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env`
4. For production: add your domain to Razorpay's whitelist
5. Set webhook URL in Razorpay Dashboard:
   `https://yourdomain.com/api/payments/webhook`
   Events to listen: `payment.captured`, `subscription.cancelled`

---

## Key Design Decisions

**Why stored functions for RS computation?**
Computing percentile ranks with `PERCENT_RANK()` across 750 stocks × 2 lookbacks
in Python would require fetching all data to memory. In PostgreSQL it runs as a
single `INSERT ... SELECT` — 10x faster and zero network overhead.

**Why `effective_from` in membership PK?**
Sector compositions change (stocks enter/leave indices). Point-in-time membership
prevents future data leaking into historical RS calculations — critical for
backtesting accuracy.

**Why equal-weight portfolio?**
Simplicity + auditability. Equal weight at 2% each means the portfolio is
fully reproducible from just the RS ranking — no optimization, no look-ahead.

**Why ₹499/month?**
Filters out non-serious users. At this price point, someone who subscribes
is genuinely using the data for trading decisions, which means they'll
renew if performance is good.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_USER` | Yes | PostgreSQL username |
| `DB_PASSWORD` | Yes | PostgreSQL password |
| `DB_HOST` | Yes | DB host (use `db` for Docker) |
| `DB_PORT` | No | Default 5432 |
| `DB_NAME` | No | Default `rsrank` |
| `SECRET_KEY` | Yes | JWT signing key (min 32 chars) |
| `RAZORPAY_KEY_ID` | Yes | Razorpay key ID |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay secret |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `APP_ENV` | No | `development` or `production` |

---

## Database Schema Overview

```
users                   → auth, subscription, Razorpay IDs
payments                → order/payment audit trail
indices                 → 40 NSE indices (broad + sector)
stocks_master           → all NSE equity symbols
stock_index_membership  → point-in-time stock↔sector mapping
stock_prices            → daily OHLCV from bhavcopy
index_prices            → daily index closing values
universe_daily          → Top 750 liquid stocks per day
corporate_actions       → BONUS/SPLIT events (price adjusted)
returns                 → 65D + 125D rolling returns
rs_values               → 3-layer RS ratios
rs_rankings             → PERCENT_RANK percentiles 0-100
rs_acceleration         → 10D RS delta
leadership_stability_30d→ % of 30D in top percentile
```
