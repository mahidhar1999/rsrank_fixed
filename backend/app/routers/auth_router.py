from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection
from datetime import datetime, timezone
from app.db import get_db
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.schemas import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.dependencies import get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Connection = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email}
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    pw_hash = body.password #hash_password(body.password)
    try:
        print("Registering user:", body.email)

        row = db.execute(
            text("""
                INSERT INTO users (email, password_hash, full_name)
                VALUES (:email, :pw, :name)
                RETURNING id, email, full_name, plan, subscription_status, is_admin
            """),
            {"email": body.email, "pw": pw_hash, "name": body.full_name},
        ).mappings().first()

        print("DB row:", row)

        db.commit()

    except Exception as e:
        print("REGISTER ERROR:", e)
        raise HTTPException(status_code=400, detail=str(e))

    user = dict(row)
    tokens = _issue_tokens(user)
    return TokenResponse(**tokens, user=_safe_user(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT id, email, full_name, password_hash, plan, subscription_status, is_admin FROM users WHERE email = :email"),
        {"email": body.email},
    ).mappings().first()

    #if not row or not verify_password(body.password, row["password_hash"]):
    if not row or body.password != row["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = dict(row)
    tokens = _issue_tokens(user)
    return TokenResponse(**tokens, user=_safe_user(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Connection = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    row = db.execute(
        text("SELECT id, email, full_name, plan, subscription_status, is_admin FROM users WHERE id = :id"),
        {"id": int(user_id)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    user = dict(row)
    tokens = _issue_tokens(user)
    return TokenResponse(**tokens, user=_safe_user(user))


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return _safe_user(current_user)


# ── Helpers ──────────────────────────────────────────────────────

def _issue_tokens(user: dict) -> dict:
    subject = str(user["id"])
    return {
        "access_token":  create_access_token({"sub": subject}),
        "refresh_token": create_refresh_token({"sub": subject}),
        "token_type":    "bearer",
    }

def _safe_user(user: dict) -> dict:
    return {
        "id":                  user["id"],
        "email":               user["email"],
        "full_name":           user.get("full_name"),
        "plan":                user.get("plan", "free"),
        "subscription_status": user.get("subscription_status", "inactive"),
        "is_admin":            user.get("is_admin", False),
    }
