# backend/auth/main.py
"""
Authentication sub-application — mounted at /api/auth
Endpoints: register, login, profile
"""

from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import (
    UserDB,
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)
from auth.password import hash_password, verify_password
from auth.jwt_handler import create_access_token, get_current_user_id


def _log(msg: str):
    print(f"INFO: [AUTH] {msg}", flush=True)


app = FastAPI(title="Auth Module", root_path="/api/auth")


# ── Register ──────────────────────────────────────────────────────────────────

@app.post("/register", response_model=TokenResponse)
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        _log(f"Registration attempt: {data.email}")

        # Validate input
        if not data.username or len(data.username.strip()) < 2:
            raise HTTPException(400, "Username must be at least 2 characters")
        if not data.email or "@" not in data.email:
            raise HTTPException(400, "Invalid email address")
        if not data.password or len(data.password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")

        # Check duplicates
        if db.query(UserDB).filter(UserDB.email == data.email).first():
            _log(f"Registration failed — email already exists: {data.email}")
            raise HTTPException(409, "Email already registered")
        if db.query(UserDB).filter(UserDB.username == data.username).first():
            _log(f"Registration failed — username taken: {data.username}")
            raise HTTPException(409, "Username already taken")

        user = UserDB(
            username=data.username.strip(),
            email=data.email.strip().lower(),
            password_hash=hash_password(data.password),
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id, user.username)
        _log(f"User registered successfully: {user.username} (id={user.id})")

        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as e:
        _log(f"Registration exception: {str(e)}")
        raise HTTPException(500, f"Server error: {str(e)}")


# ── Login ─────────────────────────────────────────────────────────────────────

@app.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    _log(f"Login attempt: {data.email}")

    user = db.query(UserDB).filter(UserDB.email == data.email.strip().lower()).first()

    if not user or not verify_password(data.password, user.password_hash):
        _log(f"Login failed — bad credentials: {data.email}")
        raise HTTPException(401, "Invalid email or password")

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id, user.username)
    _log(f"User logged in successfully: {user.username}")

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ── Profile ───────────────────────────────────────────────────────────────────

@app.get("/profile", response_model=UserResponse)
def get_profile(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return UserResponse.model_validate(user)


@app.put("/profile", response_model=UserResponse)
def update_profile(
    updates: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    allowed = {"username", "email", "profile_image"}
    for key, val in updates.items():
        if key in allowed and val is not None:
            setattr(user, key, val)

    db.commit()
    db.refresh(user)
    _log(f"Profile updated: {user.username}")
    return UserResponse.model_validate(user)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "module": "auth"}
