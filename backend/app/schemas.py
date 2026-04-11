from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date, datetime


# ── Auth ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Market ───────────────────────────────────────────────────────

class TopSector(BaseModel):
    name: str
    rs: float
    pct: float

class MarketSummary(BaseModel):
    trade_date: date
    nifty50_close: Optional[float]
    nifty50_change_pct: Optional[float]
    universe_size: int
    leaders: int
    laggards: int
    neutral: int
    top_sector: Optional[TopSector]
    advancing_sectors: int
    declining_sectors: int


# ── Stocks ───────────────────────────────────────────────────────

class StockRanking(BaseModel):
    rank: int
    symbol: str
    company_name: Optional[str]
    sector: Optional[str]
    close: Optional[float]
    rs_65d: Optional[float]
    rs_125d: Optional[float]
    rs_combined: Optional[float]
    pct_combined: Optional[float]
    pct_vs_market: Optional[float]
    pct_vs_sector: Optional[float]
    stability_score: Optional[float]
    delta_combined: Optional[float]

class StockRankingsResponse(BaseModel):
    trade_date: date
    total: int
    page: int
    limit: int
    stocks: List[StockRanking]

class HeatmapStock(BaseModel):
    symbol: str
    rs_combined: Optional[float]
    pct_combined: Optional[float]
    color_bucket: str
    sector: Optional[str]

class HeatmapResponse(BaseModel):
    trade_date: date
    stocks: List[HeatmapStock]

class RSPoint(BaseModel):
    trade_date: date
    rs_combined: Optional[float]
    pct_combined: Optional[float]

class StockHistoryResponse(BaseModel):
    symbol: str
    history: List[RSPoint]


# ── Sectors ──────────────────────────────────────────────────────

class SectorRS(BaseModel):
    index_name: str
    rs_65d: Optional[float]
    rs_125d: Optional[float]
    pct_vs_market: Optional[float]
    trend: str          # "up" | "down" | "flat"
    stock_count: int

class SectorRotationResponse(BaseModel):
    trade_date: date
    sectors: List[SectorRS]

class SectorStock(BaseModel):
    symbol: str
    company_name: Optional[str]
    rs_combined: Optional[float]
    pct_combined: Optional[float]
    pct_vs_sector: Optional[float]


# ── Portfolio ────────────────────────────────────────────────────

class PortfolioHolding(BaseModel):
    rank: int
    symbol: str
    company_name: Optional[str]
    sector: Optional[str]
    rs_combined: Optional[float]
    pct_combined: Optional[float]
    weight_pct: float = 2.0

class MonthlyReturn(BaseModel):
    month: str
    portfolio_return: float
    nifty_return: float
    alpha: float

class PortfolioPerformance(BaseModel):
    ytd_portfolio: float
    ytd_nifty: float
    ytd_alpha: float
    monthly_returns: List[MonthlyReturn]


# ── Acceleration ─────────────────────────────────────────────────

class AccelerationStock(BaseModel):
    symbol: str
    company_name: Optional[str]
    sector: Optional[str]
    rs_combined: Optional[float]
    pct_combined: Optional[float]
    delta_combined: Optional[float]
    delta_rs_market: Optional[float]

class AccelerationResponse(BaseModel):
    trade_date: date
    emerging: List[AccelerationStock]
    fading: List[AccelerationStock]


# ── Leadership ───────────────────────────────────────────────────

class LeadershipStock(BaseModel):
    symbol: str
    company_name: Optional[str]
    sector: Optional[str]
    stability_score: Optional[float]
    rs_combined: Optional[float]
    pct_combined: Optional[float]

class LeadershipResponse(BaseModel):
    trade_date: date
    stocks: List[LeadershipStock]


# ── Payments ─────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan: str   # "pro" | "enterprise"

class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan: str
