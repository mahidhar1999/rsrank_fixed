import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from pathlib import Path

# Load .env — checks backend/, then root folder
_backend_env = Path(__file__).parent.parent / ".env"
_root_env    = Path(__file__).parent.parent.parent / ".env"

if _backend_env.exists():
    load_dotenv(_backend_env)
elif _root_env.exists():
    load_dotenv(_root_env)
else:
    load_dotenv()

# ── Database
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", "password"))
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "rsrank_in")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── JWT
SECRET_KEY                  = os.getenv("SECRET_KEY", "CHANGE_ME_32_CHARS_MINIMUM_HERE_X")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ── Razorpay
RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

PLAN_AMOUNT_INR = {
    "pro":        49900,
    "enterprise": 199900,
}

# ── App
APP_ENV      = os.getenv("APP_ENV", "development")
DEBUG        = APP_ENV == "development"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
