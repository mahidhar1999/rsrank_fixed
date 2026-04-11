from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.db import get_db
from app.auth import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Connection = Depends(get_db),
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise exc

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise exc

    user_id = payload.get("sub")
    if not user_id:
        raise exc

    row = db.execute(
        text("SELECT id, email, full_name, plan, subscription_status, valid_until, is_admin FROM users WHERE id = :id"),
        {"id": int(user_id)},
    ).mappings().first()

    if not row:
        raise exc

    return dict(row)


def require_pro(current_user: dict = Depends(get_current_user)):
    return current_user


def require_admin(current_user: dict = Depends(get_current_user)):
    if not current_user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Connection = Depends(get_db),
):
    """Returns user dict if authenticated, else None."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    row = db.execute(
        text("SELECT id, email, plan, subscription_status, is_admin FROM users WHERE id = :id"),
        {"id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None
