-- ================================================================
-- RSRank Database Schema v2.0
-- Run this once on a fresh database: psql -f 001_schema.sql
-- ================================================================

-- ================================================================
-- USERS & AUTH
-- ================================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(200),
    plan VARCHAR(20) DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    razorpay_customer_id VARCHAR(100),
    subscription_id VARCHAR(100),
    subscription_status VARCHAR(20) DEFAULT 'inactive'
        CHECK (subscription_status IN ('active', 'inactive', 'cancelled', 'expired')),
    valid_until TIMESTAMPTZ,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    razorpay_order_id VARCHAR(100) UNIQUE,
    razorpay_payment_id VARCHAR(100),
    razorpay_signature VARCHAR(400),
    amount NUMERIC NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    plan VARCHAR(20),
    status VARCHAR(20) DEFAULT 'created'
        CHECK (status IN ('created', 'paid', 'failed', 'refunded')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- MASTER TABLES
-- ================================================================

CREATE TABLE IF NOT EXISTS indices (
    id SERIAL PRIMARY KEY,
    index_name VARCHAR(100) UNIQUE NOT NULL,
    index_category VARCHAR(20) NOT NULL CHECK (index_category IN ('broad', 'sector')),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS stocks_master (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    company_name TEXT,
    isin VARCHAR(20),
    instrument_type VARCHAR(20) DEFAULT 'EQUITY'
        CHECK (instrument_type IN ('EQUITY', 'ETF', 'OTHER')),
    listing_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATE DEFAULT CURRENT_DATE
);

-- Point-in-time membership: PK includes effective_from
CREATE TABLE IF NOT EXISTS stock_index_membership (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    index_id INT REFERENCES indices(id) ON DELETE CASCADE,
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_primary BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (stock_id, index_id, effective_from)
);

-- ================================================================
-- PRICE STORAGE
-- ================================================================

CREATE TABLE IF NOT EXISTS stock_prices (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    close NUMERIC NOT NULL,
    volume BIGINT,
    traded_value NUMERIC,
    PRIMARY KEY (stock_id, trade_date)
);

CREATE TABLE IF NOT EXISTS index_prices (
    index_id INT REFERENCES indices(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    close NUMERIC NOT NULL,
    PRIMARY KEY (index_id, trade_date)
);

-- ================================================================
-- DAILY UNIVERSE — Top 750 by liquidity (prevents survivorship bias)
-- ================================================================

CREATE TABLE IF NOT EXISTS universe_daily (
    trade_date DATE NOT NULL,
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    liquidity_rank INT,
    avg_traded_value_30 NUMERIC,
    PRIMARY KEY (trade_date, stock_id)
);

-- ================================================================
-- CORPORATE ACTIONS
-- ================================================================

CREATE TABLE IF NOT EXISTS corporate_actions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('BONUS', 'SPLIT', 'DIVIDEND')),
    ratio_old INT,
    ratio_new INT,
    ex_date DATE NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    UNIQUE (symbol, action_type, ex_date)
);

-- ================================================================
-- RS ENGINE TABLES
-- ================================================================

-- Rolling returns for stocks and indices
CREATE TABLE IF NOT EXISTS returns (
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('stock', 'index')),
    entity_id INT NOT NULL,
    lookback_days INT NOT NULL,
    trade_date DATE NOT NULL,
    return_value NUMERIC,
    PRIMARY KEY (entity_type, entity_id, lookback_days, trade_date)
);

-- 3-layer RS values (raw ratios, not percentiles)
CREATE TABLE IF NOT EXISTS rs_values (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    lookback_days INT NOT NULL,
    trade_date DATE NOT NULL,
    rs_vs_market NUMERIC,           -- A: Stock / Nifty 50
    rs_vs_sector NUMERIC,           -- C: Stock / Primary Sector
    sector_rs_vs_market NUMERIC,    -- B: Primary Sector / Nifty 50
    rs_combined NUMERIC,            -- 0.75 * rs65 + 0.25 * rs125
    PRIMARY KEY (stock_id, lookback_days, trade_date)
);

-- Percentile rankings (0-100 scale)
CREATE TABLE IF NOT EXISTS rs_rankings (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    pct_vs_market NUMERIC,
    pct_vs_sector NUMERIC,
    sector_pct_vs_market NUMERIC,
    pct_combined NUMERIC,
    PRIMARY KEY (stock_id, trade_date)
);

-- 10-day RS delta (acceleration/deceleration)
CREATE TABLE IF NOT EXISTS rs_acceleration (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    delta_rs_market NUMERIC,
    delta_rs_sector NUMERIC,
    delta_combined NUMERIC,
    PRIMARY KEY (stock_id, trade_date)
);

-- 30-day leadership persistence
CREATE TABLE IF NOT EXISTS leadership_stability_30d (
    stock_id INT REFERENCES stocks_master(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    stability_score NUMERIC,        -- % of last 30D in top percentile
    PRIMARY KEY (stock_id, trade_date)
);

-- ================================================================
-- PERFORMANCE INDEXES
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_stock_prices_date        ON stock_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_date  ON stock_prices(stock_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_index_prices_date        ON index_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_returns_entity           ON returns(entity_type, entity_id, lookback_days, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_returns_date             ON returns(trade_date);
CREATE INDEX IF NOT EXISTS idx_rs_values_date           ON rs_values(trade_date);
CREATE INDEX IF NOT EXISTS idx_rs_values_combined       ON rs_values(trade_date, lookback_days, rs_combined DESC);
CREATE INDEX IF NOT EXISTS idx_rs_rankings_date         ON rs_rankings(trade_date);
CREATE INDEX IF NOT EXISTS idx_rs_rankings_pct          ON rs_rankings(trade_date, pct_combined DESC);
CREATE INDEX IF NOT EXISTS idx_acceleration_date        ON rs_acceleration(trade_date);
CREATE INDEX IF NOT EXISTS idx_stability_date           ON leadership_stability_30d(trade_date);
CREATE INDEX IF NOT EXISTS idx_universe_date            ON universe_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_membership_primary       ON stock_index_membership(stock_id, is_primary, effective_from);
CREATE INDEX IF NOT EXISTS idx_corp_actions_unprocessed ON corporate_actions(processed, ex_date);

\echo '✅ Schema created successfully'
