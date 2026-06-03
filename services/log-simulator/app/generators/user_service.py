"""User-service log generator.

Produces realistic user-management log messages covering registration,
profile updates, preferences, notification preferences, and account
lifecycle events.
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
    "User {user} registered successfully (source={source})",
    "Profile updated for user {user}: fields=[{fields}]",
    "Email verification link sent to {email}",
    "User {user} preferences saved: locale={locale}, timezone={tz}",
    "Avatar uploaded for user {user}: {size}KB, {format}",
    "User {user} account deactivated by {actor}",
    "Notification preferences updated for user {user}: {channels}",
    "User {user} accepted Terms of Service v{version}",
    "Password changed for user {user}",
    "User export request completed for {user}: {records} records",
]

_DEBUG_MESSAGES: list[str] = [
    "Querying user by ID: {user_id}",
    "Gravatar hash computed for {email} in {ms}ms",
    "Image resize: {original_w}x{original_h} → {target_w}x{target_h}",
    "User search index updated: {count} documents",
    "Cache invalidation for user:{user_id} across {nodes} nodes",
    "Rate limiter check for registration: {ip} – allowed={allowed}",
    "Merge duplicate profiles: {user_a} ← {user_b}",
]

_WARN_MESSAGES: list[str] = [
    "Duplicate email registration attempt: {email} from {ip}",
    "Profile picture upload exceeds size limit: {size}MB > {limit}MB",
    "User {user} has not verified email after {days} days",
    "Slow query in user search: {ms}ms (threshold: {threshold}ms)",
    "User {user} approaching API rate limit: {remaining}/{max} remaining",
    "Deprecated field '{field}' used in profile update request",
    "Unusual registration spike from IP range {ip_range}",
]

_ERROR_MESSAGES: list[str] = [
    "Validation error during registration: {detail}",
    "Duplicate email constraint violation: {email}",
    "Profile picture upload failed: {reason}",
    "User search index sync failed: {reason}",
    "Email delivery failed for verification: {email} – {reason}",
    "Database connection error during user lookup: {reason}",
    "GDPR data export failed for user {user}: {reason}",
    "Account merge conflict: incompatible profiles {user_a} / {user_b}",
]

_FATAL_MESSAGES: list[str] = [
    "FATAL: User database primary unreachable – read-only mode activated",
    "FATAL: Search index corrupted – full reindex required",
    "FATAL: S3 bucket credentials expired – avatar uploads disabled",
]

_TRACE_MESSAGES: list[str] = [
    "TRACE: User payload validation: {bytes} bytes, {fields_count} fields",
    "TRACE: Password hash rounds: {rounds}",
    "TRACE: Entering profile update transaction for {user_id}",
]


class UserServiceGenerator(BaseLogGenerator):
    """Generates realistic log entries for a user management service."""

    service_name: str = "user-service"

    def _service_messages(self, level: str) -> list[str]:
        return {
            "INFO": _INFO_MESSAGES,
            "DEBUG": _DEBUG_MESSAGES,
            "WARN": _WARN_MESSAGES,
            "ERROR": _ERROR_MESSAGES,
            "FATAL": _FATAL_MESSAGES,
            "TRACE": _TRACE_MESSAGES,
        }.get(level, _INFO_MESSAGES)

    def _service_metadata(self, level: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "user_id": fake.uuid4()[:8],
            "email": fake.email(),
            "registration_source": random.choice([
                "web", "mobile_ios", "mobile_android", "api", "admin_portal",
            ]),
        }
        if level in ("ERROR", "FATAL"):
            meta["error_code"] = random.choice([
                "VALIDATION_ERROR", "DUPLICATE_EMAIL", "UPLOAD_FAILED",
                "INDEX_SYNC_FAILED", "DB_CONNECTION_ERROR", "EXPORT_FAILED",
            ])
        return meta

    def _render_template(self, template: str) -> str:
        user_replacements: dict[str, str] = {
            "{user}": fake.user_name(),
            "{user_id}": fake.uuid4()[:8],
            "{email}": fake.email(),
            "{ip}": fake.ipv4_public(),
            "{source}": random.choice(["web", "mobile", "api", "oauth"]),
            "{fields}": ", ".join(random.sample(
                ["display_name", "bio", "avatar_url", "locale", "phone", "address"],
                k=random.randint(1, 3),
            )),
            "{locale}": random.choice(["en-US", "de-DE", "fr-FR", "ja-JP", "es-ES"]),
            "{tz}": random.choice(["UTC", "America/New_York", "Europe/Berlin", "Asia/Tokyo"]),
            "{size}": str(random.randint(50, 5000)),
            "{format}": random.choice(["jpeg", "png", "webp"]),
            "{actor}": random.choice(["self", "admin", "system"]),
            "{channels}": ", ".join(random.sample(["email", "sms", "push", "in_app"], k=random.randint(1, 3))),
            "{version}": f"{random.randint(1, 5)}.{random.randint(0, 9)}",
            "{records}": str(random.randint(10, 50000)),
            "{original_w}": str(random.choice([1920, 3840, 4032])),
            "{original_h}": str(random.choice([1080, 2160, 3024])),
            "{target_w}": str(random.choice([128, 256, 512])),
            "{target_h}": str(random.choice([128, 256, 512])),
            "{count}": str(random.randint(1, 10000)),
            "{nodes}": str(random.randint(2, 8)),
            "{allowed}": random.choice(["true", "false"]),
            "{user_a}": f"usr_{uuid.uuid4().hex[:6]}",
            "{user_b}": f"usr_{uuid.uuid4().hex[:6]}",
            "{limit}": str(random.choice([5, 10, 20])),
            "{days}": str(random.randint(1, 30)),
            "{remaining}": str(random.randint(0, 100)),
            "{max}": str(random.choice([100, 500, 1000])),
            "{field}": random.choice(["nickname", "legacy_id", "fax_number"]),
            "{ip_range}": f"{fake.ipv4_public()}/24",
            "{detail}": random.choice([
                "email format invalid", "username too short",
                "password does not meet policy", "missing required field 'name'",
            ]),
            "{reason}": random.choice([
                "connection_timeout", "file_corrupt", "s3_error",
                "smtp_refused", "index_locked",
            ]),
            "{fields_count}": str(random.randint(3, 20)),
            "{rounds}": str(random.choice([10, 12, 14])),
        }
        result = template
        for ph, val in user_replacements.items():
            if ph in result:
                result = result.replace(ph, val, 1)
        return super()._render_template(result)
