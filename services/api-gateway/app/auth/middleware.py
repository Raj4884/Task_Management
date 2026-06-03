"""
LogSentry API Gateway - Auth Middleware / Dependencies.

Provides FastAPI dependency functions for JWT-based authentication:
  • get_current_user – mandatory Bearer token → user dict
  • optional_auth    – same but returns None when token is absent
  • require_role     – factory that restricts access to a specific role
"""

import logging
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import verify_token
from jose import JWTError

logger = logging.getLogger("api-gateway.auth")

# HTTPBearer extracts "Authorization: Bearer <token>" for us.
_bearer_scheme = HTTPBearer(auto_error=True)
_bearer_scheme_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """Validate the Bearer token and return the decoded user payload.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    try:
        payload = verify_token(credentials.credentials)
    except JWTError as exc:
        logger.warning("Authentication failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type – access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload["sub"],
        "username": payload.get("username"),
        "role": payload.get("role", "viewer"),
    }


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme_optional),
) -> Optional[dict[str, Any]]:
    """Attempt to authenticate but return ``None`` when no token is provided.

    Useful for endpoints that offer extended features to authenticated users
    but also work anonymously.
    """
    if credentials is None:
        return None

    try:
        payload = verify_token(credentials.credentials)
    except JWTError:
        return None

    if payload.get("type") != "access":
        return None

    return {
        "user_id": payload["sub"],
        "username": payload.get("username"),
        "role": payload.get("role", "viewer"),
    }


def require_role(required_role: str) -> Callable:
    """Factory that returns a dependency enforcing a minimum role.

    Usage::

        @router.delete("/admin/users/{uid}", dependencies=[Depends(require_role("admin"))])
        async def delete_user(uid: str): ...
    """

    async def _role_checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        # Simple role hierarchy: admin > editor > viewer
        role_hierarchy = {"viewer": 0, "editor": 1, "admin": 2}

        user_level = role_hierarchy.get(current_user.get("role", "viewer"), 0)
        required_level = role_hierarchy.get(required_role, 0)

        if user_level < required_level:
            logger.warning(
                "RBAC denied: user=%s role=%s required=%s",
                current_user.get("username"),
                current_user.get("role"),
                required_role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' or higher is required",
            )
        return current_user

    return _role_checker
