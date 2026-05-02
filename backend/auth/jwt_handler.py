# backend/auth/jwt_handler.py
"""
JWT token creation / validation and FastAPI dependency for extracting current user.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-dev-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

_security = HTTPBearer()


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    """Create a signed JWT containing user_id and username."""
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT.  Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> int:
    """
    Dependency — extracts user_id from the Authorization Bearer token.
    Use this when you only need the user id (avoids a DB lookup).
    """
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return int(user_id)


def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[int]:
    """
    Like get_current_user_id but returns None when no token is present
    instead of raising 401.  Useful for endpoints that work for both
    authenticated and anonymous users (e.g. summarize with optional caching).
    """
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return int(payload["sub"])
    except Exception:
        return None
