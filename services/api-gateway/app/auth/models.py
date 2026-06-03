"""
LogSentry API Gateway - Auth Request / Response Models.

Defines gateway-specific Pydantic models for login and registration.
Shared models (UserResponse, TokenResponse) are imported from the
shared schemas package.
"""

import sys

from pydantic import BaseModel, Field

sys.path.insert(0, "/app")
from shared.schemas.log_entry import TokenResponse, UserResponse  # noqa: E402, F401


class LoginRequest(BaseModel):
    """Credentials for user authentication."""

    username: str = Field(..., min_length=1, max_length=100, description="Username or login name")
    password: str = Field(..., min_length=1, description="Plain-text password")


class RegisterRequest(BaseModel):
    """Payload for new user registration."""

    username: str = Field(..., min_length=3, max_length=100, description="Desired username")
    email: str = Field(..., max_length=255, description="Valid email address")
    password: str = Field(..., min_length=6, description="Password (≥ 6 chars)")
