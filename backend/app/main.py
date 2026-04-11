from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, DEBUG
from app.routers import auth_router
from app.routers import market, stocks, sectors, portfolio
from app.routers import acceleration, leadership, payments, pipeline

app = FastAPI(
    title="RSRank API",
    description="Relative Strength Analytics Platform for NSE Stocks",
    version="2.0.0",
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth_router.router,   prefix="/api/auth",      tags=["Auth"])
app.include_router(market.router,        prefix="/api/market",    tags=["Market"])
app.include_router(stocks.router,        prefix="/api/stocks",    tags=["Stocks"])
app.include_router(sectors.router,       prefix="/api/sectors",   tags=["Sectors"])
app.include_router(portfolio.router,     prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(acceleration.router,  prefix="/api/acceleration", tags=["Acceleration"])
app.include_router(leadership.router,    prefix="/api/leadership",tags=["Leadership"])
app.include_router(payments.router,      prefix="/api/payments",  tags=["Payments"])
app.include_router(pipeline.router,      prefix="/api/pipeline",  tags=["Pipeline"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
