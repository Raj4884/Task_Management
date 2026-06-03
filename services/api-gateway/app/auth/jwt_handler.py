"""
LogSentry API Gateway - JWT Token Handler.

Creates and verifies access / refresh tokens using python-jose (HS256).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger("api-gateway.jwt")


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived access token.

    Args:
        user_id:  UUID of the user.
        username: Login name.
        role:     e.g. ``admin`` or ``viewer``.
        extra_claims: Optional additional JWT claims.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.debug("Access token created for user=%s exp=%s", username, expire.isoformat())
    return token


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token.

    Args:
        user_id: UUID of the user.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.debug("Refresh token created for user_id=%s exp=%s", user_id, expire.isoformat())
    return token


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The raw JWT string.

    Returns:
        The decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("sub") is None:
            raise JWTError("Token payload missing 'sub' claim")
        return payload
    except JWTError:
        logger.warning("Token verification failed")
        raise
