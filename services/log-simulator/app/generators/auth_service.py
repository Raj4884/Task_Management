"""Auth-service log generator.

Produces realistic authentication / authorisation log messages covering
login attempts, token lifecycle, password management, OAuth flows, and
session management.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from faker import Faker

from app.generators.base import BaseLogGenerator

fake = Faker()

# ---------------------------------------------------------------------------
# Domain-specific message pools
# ---------------------------------------------------------------------------

_INFO_MESSAGES: list[str] = [
    "User '{user}' authenticated successfully via {auth_method}",
    "Access token issued for user '{user}' (ttl={ttl}s)",
    "Refresh token rotated for session {session}",
    "Password reset email sent to {email}",
    "OAuth2 authorization code exchanged for token (provider={provider})",
    "Session {session} created for user '{user}' from {ip}",
    "MFA challenge completed successfully for user '{user}'",
    "API key validated for service account '{sa}'",
    "User '{user}' logged out – session {session} invalidated",
    "SSO callback processed for provider '{provider}'",
    "Role '{role}' granted to user '{user}' by admin",
    "SAML assertion validated for org '{org}'",
]

_DEBUG_MESSAGES: list[str] = [
    "JWT signature verified (alg=RS256, kid={kid})",
    "Looking up user by email: {email}",
    "Bcrypt hash comparison completed in {ms}ms",
    "Session store read for key {session}: {result}",
    "CORS pre-flight check passed for origin {origin}",
    "Rate-limit bucket check: {bucket} – remaining={remaining}",
    "OIDC discovery document fetched from {provider}",
]

_WARN_MESSAGES: list[str] = [
    "Failed login attempt #{n} for user '{user}' from {ip}",
    "Token nearing expiry for user '{user}' (remaining={remaining}s)",
    "Unusual login location detected: {ip} ({country})",
    "Password strength below policy threshold for user '{user}'",
    "MFA device not registered – falling back to email OTP for '{user}'",
    "Session {session} idle for {minutes} minutes – will expire soon",
    "Deprecated OAuth grant type 'implicit' used by client '{client}'",
]

_ERROR_MESSAGES: list[str] = [
    "Authentication failed: invalid credentials for user '{user}' from {ip}",
    "Token validation error: {reason}",
    "Account locked after {n} failed attempts: user '{user}'",
    "OAuth token exchange failed: {reason} (provider={provider})",
    "Session store write failed: {reason}",
    "Brute-force detection triggered for IP {ip} – {n} attempts in {seconds}s",
    "MFA verification failed for user '{user}': code mismatch",
    "LDAP bind error: {reason}",
    "SAML response signature invalid for provider '{provider}'",
]

_FATAL_MESSAGES: list[str] = [
    "FATAL: Auth database connection pool exhausted – cannot process logins",
    "FATAL: JWT signing key missing from vault – refusing to issue tokens",
    "FATAL: Redis session store unreachable – all sessions invalidated",
]

_TRACE_MESSAGES: list[str] = [
    "TRACE: Entering auth middleware for path {path}",
    "TRACE: Cookie jar contents: {cookies}",
    "TRACE: PKCE code_verifier generated ({bytes} bytes)",
]


class AuthServiceGenerator(BaseLogGenerator):
    """Generates realistic log entries for an authentication service."""

    service_name: str = "auth-service"

    # -- message overrides ------------------------------------------------

    def _service_messages(self, level: str) -> list[str]:
        return {
            "INFO": _INFO_MESSAGES,
            "DEBUG": _DEBUG_MESSAGES,
            "WARN": _WARN_MESSAGES,
            "ERROR": _ERROR_MESSAGES,
            "FATAL": _FATAL_MESSAGES,
            "TRACE": _TRACE_MESSAGES,
        }.get(level, _INFO_MESSAGES)

    # -- metadata overrides -----------------------------------------------

    def _service_metadata(self, level: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "user_id": fake.uuid4()[:8],
            "ip_address": fake.ipv4_public(),
            "auth_method": random.choice(["password", "oauth2", "api_key", "sso", "mfa"]),
            "mfa_enabled": random.choice([True, True, False]),
        }
        if level in ("ERROR", "FATAL"):
            meta["error_code"] = random.choice([
                "INVALID_CREDENTIALS", "TOKEN_EXPIRED", "ACCOUNT_LOCKED",
                "BRUTE_FORCE", "MFA_FAILED", "SESSION_STORE_ERROR",
            ])
        return meta

    # -- template rendering extension -------------------------------------

    def _render_template(self, template: str) -> str:  # noqa: D401
        """Extend base rendering with auth-specific placeholders."""
        auth_replacements: dict[str, str] = {
            "{user}": fake.user_name(),
            "{email}": fake.email(),
            "{ip}": fake.ipv4_public(),
            "{session}": uuid.uuid4().hex[:12],
            "{provider}": random.choice(["google", "github", "okta", "azure-ad", "auth0"]),
            "{auth_method}": random.choice(["password", "oauth2", "api_key", "sso"]),
            "{ttl}": str(random.choice([900, 1800, 3600, 7200])),
            "{sa}": f"svc-{fake.lexify('???')}-{random.randint(1, 99):02d}",
            "{kid}": uuid.uuid4().hex[:8],
            "{origin}": fake.url(),
            "{bucket}": f"auth:rate:{fake.ipv4_public()}",
            "{remaining}": str(random.randint(0, 100)),
            "{country}": fake.country_code(),
            "{minutes}": str(random.randint(15, 60)),
            "{seconds}": str(random.randint(5, 60)),
            "{client}": f"client-{fake.lexify('????')}",
            "{role}": random.choice(["admin", "editor", "viewer", "billing"]),
            "{org}": fake.company(),
            "{path}": random.choice(["/api/v1/login", "/api/v1/token", "/api/v1/users/me"]),
            "{cookies}": f"sid={uuid.uuid4().hex[:8]}; csrftoken={uuid.uuid4().hex[:8]}",
            "{reason}": random.choice([
                "connection refused", "invalid_grant", "token_revoked",
                "signature mismatch", "timeout", "invalid_scope",
            ]),
        }
        result = template
        for ph, val in auth_replacements.items():
            if ph in result:
                result = result.replace(ph, val, 1)
        return super()._render_template(result)
