"""
Auth router — Google OAuth → JWT flow.

Flow:
  1. Frontend does Google sign-in (NextAuth), gets an id_token.
  2. Frontend sends id_token to POST /auth/google.
  3. We verify with Google, upsert user in DB, return access + refresh tokens.
  4. Refresh tokens are stored in Redis and rotated on each /auth/refresh call.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import httpx

from pydantic import EmailStr

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.redis import get_redis
from app.db.mongo import get_db
from app.models.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleAuthRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


async def _verify_google_token(id_token: str) -> dict:
    """Verify Google id_token and return user info."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": id_token})
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        data = resp.json()
        # Validate audience
        if data.get("aud") != settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
        return data


@router.post("/google", response_model=TokenResponse)
async def google_auth(payload: GoogleAuthRequest):
    """Exchange Google id_token for Rihla JWT."""
    google_data = await _verify_google_token(payload.id_token)

    google_id = google_data.get("sub")
    email = google_data.get("email")
    name = google_data.get("name", email)
    avatar_url = google_data.get("picture")

    if not google_id or not email:
        raise HTTPException(status_code=401, detail="Incomplete Google profile")

    db = await get_db()

    # Upsert user
    existing = await db.find_one("users", {"google_id": google_id})
    now = datetime.now(timezone.utc)

    if existing:
        await db.update_one(
            "users",
            {"google_id": google_id},
            {"name": name, "avatar_url": avatar_url, "updated_at": now},
        )
        user_doc = await db.find_one("users", {"google_id": google_id})
    else:
        user_data = {
            "google_id": google_id,
            "email": email,
            "name": name,
            "avatar_url": avatar_url,
            "theme": "sacred",
            "ai_model": "openai",
            "created_at": now,
            "updated_at": now,
        }
        inserted_id = await db.insert_one("users", user_data)
        user_doc = await db.find_one("users", {"_id": inserted_id})

    user = UserOut.from_doc(user_doc)

    # Issue tokens
    token_data = {"sub": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token in Redis (key: refresh:<token> → user_id, TTL = 30d)
    redis = await get_redis()
    await redis.setex(
        f"refresh:{refresh_token}",
        settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user.id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest):
    """Rotate refresh token → new access + refresh pair."""
    redis = await get_redis()
    user_id = await redis.get(f"refresh:{payload.refresh_token}")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    db = await get_db()
    user_doc = await db.find_one("users", {"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    user = UserOut.from_doc(user_doc)

    # Rotate: delete old, issue new
    await redis.delete(f"refresh:{payload.refresh_token}")
    token_data = {"sub": user.id, "email": user.email}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    await redis.setex(
        f"refresh:{new_refresh}",
        settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user.id,
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=user,
    )


# ── Email / Password auth ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


async def _issue_tokens(user: UserOut) -> TokenResponse:
    """Common: issue access + refresh tokens and store in Redis."""
    token_data = {"sub": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    redis = await get_redis()
    await redis.setex(
        f"refresh:{refresh_token}",
        settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user.id,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest):
    """Sign up with name, email, phone, password."""
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    db = await get_db()
    if await db.find_one("users", {"email": payload.email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    now = datetime.now(timezone.utc)
    user_data = {
        "google_id": None,
        "email": payload.email,
        "name": payload.name,
        "phone": payload.phone,
        "avatar_url": None,
        "password_hash": hash_password(payload.password),
        "theme": "sacred",
        "ai_model": "openai",
        "created_at": now,
        "updated_at": now,
    }
    inserted_id = await db.insert_one("users", user_data)
    user_doc = await db.find_one("users", {"_id": inserted_id})
    user = UserOut.from_doc(user_doc)
    return await _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """Sign in with email and password."""
    db = await get_db()
    user_doc = await db.find_one("users", {"email": payload.email})

    # Use a constant-time path to avoid timing attacks
    dummy_hash = "$2b$12$notavalidhash000000000000000000000000000"
    stored_hash = user_doc.get("password_hash") if user_doc else dummy_hash

    if not user_doc or not stored_hash or not verify_password(payload.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = UserOut.from_doc(user_doc)
    return await _issue_tokens(user)

