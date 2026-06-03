"""
LogSentry API Gateway - Authentication Routes.

Endpoints:
    POST /auth/login    – Authenticate with username + password → JWT tokens
    POST /auth/register – Create a new user → JWT tokens
    POST /auth/refresh  – Exchange a refresh token for a new access token
    GET  /auth/me       – Return the authenticated user's profile
"""

import logging
import sys
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt

sys.path.insert(0, "/app")
from shared.database.connection import DatabasePool  # noqa: E402

from app.auth.jwt_handler import (  # noqa: E402
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.auth.middleware import get_current_user  # noqa: E402
from app.auth.models import (  # noqa: E402
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.config import settings  # noqa: E402
from jose import JWTError  # noqa: E402

logger = logging.getLogger("api-gateway.auth.routes")

# (passlib removed in favor of direct bcrypt)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Helpers ──────────────────────────────────────────────────────────────


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _build_token_response(user_id: str, username: str, role: str) -> TokenResponse:
    """Create an access + refresh token pair wrapped in TokenResponse."""
    access = create_access_token(user_id, username, role)
    refresh = create_refresh_token(user_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ─── POST /auth/login ────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate a user by username + password and return JWT tokens."""
    async with DatabasePool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, password_hash, role, is_active "
            "FROM users WHERE username = $1",
            body.username,
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if not _verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    logger.info("User '%s' logged in", row["username"])
    return _build_token_response(
        user_id=str(row["id"]),
        username=row["username"],
        role=row["role"],
    )


# ─── POST /auth/register ─────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(body: RegisterRequest):
    """Register a new user and return JWT tokens."""
    password_hash = _hash_password(body.password)
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    try:
        async with DatabasePool.transaction() as conn:
            await conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                uuid.UUID(user_id),
                body.username,
                body.email,
                password_hash,
                "viewer",       # default role
                True,
                now,
                now,
            )
    except Exception as exc:
        # asyncpg raises UniqueViolationError for duplicate username / email
        err_msg = str(exc).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists",
            )
        logger.exception("Registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )

    logger.info("New user registered: %s (%s)", body.username, user_id)
    return _build_token_response(
        user_id=user_id,
        username=body.username,
        role="viewer",
    )


# ─── POST /auth/refresh ──────────────────────────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str):
    """Exchange a valid refresh token for a fresh access token pair."""
    try:
        payload = verify_token(refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    user_id = payload["sub"]

    # Fetch latest user state from DB (role may have changed, account may be disabled)
    async with DatabasePool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, role, is_active FROM users WHERE id = $1",
            uuid.UUID(user_id),
        )

    if row is None or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    logger.info("Token refreshed for user '%s'", row["username"])
    return _build_token_response(
        user_id=str(row["id"]),
        username=row["username"],
        role=row["role"],
    )


# ─── GET /auth/me ─────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return profile information for the currently authenticated user."""
    async with DatabasePool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, role, is_active, created_at "
            "FROM users WHERE id = $1",
            uuid.UUID(current_user["user_id"]),
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=str(row["id"]),
        username=row["username"],
        email=row["email"],
        role=row["role"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )
