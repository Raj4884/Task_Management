"""Notification-service log generator.

Produces realistic notification-delivery log messages covering email,
SMS, push notifications, in-app messaging, and template rendering.
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
    "Email sent to {email}: subject='{subject}' via {provider}",
    "SMS delivered to {phone}: template={template} ({chars} chars)",
    "Push notification sent to device {device_id} (platform={platform})",
    "In-app notification created for user {user}: type={notif_type}",
    "Template '{template}' rendered in {ms}ms ({size} bytes)",
    "Notification batch {batch} dispatched: {count} messages",
    "Webhook notification delivered to {url}: HTTP {status}",
    "User {user} notification preferences updated: {channels}",
    "Digest email compiled for {user}: {count} unread notifications",
    "Campaign '{campaign}' started: {total} recipients",
]

_DEBUG_MESSAGES: list[str] = [
    "SMTP connection established to {smtp_host}:{port}",
    "Template cache hit for '{template}' (version={version})",
    "FCM token validation for device {device_id}: valid={valid}",
    "SMS provider rate: {remaining}/{limit} messages this minute",
    "Email DKIM signature generated for domain {domain}",
    "Notification deduplication check: key={dedup_key} – {result}",
    "Rendering Handlebars template with {vars} variables",
]

_WARN_MESSAGES: list[str] = [
    "Email bounce detected: {email} – type={bounce_type}",
    "SMS delivery rate limited by provider: {remaining}/{limit} remaining",
    "Push notification token expired for device {device_id}",
    "Template '{template}' rendering slow: {ms}ms > {threshold}ms",
    "Notification queue depth high: {depth} pending messages",
    "Invalid recipient phone number: {phone} – skipping SMS",
    "Email open tracking pixel blocked for {email}",
]

_ERROR_MESSAGES: list[str] = [
    "Email delivery failed: {reason} for {email}",
    "SMS sending error: provider returned {status} for {phone}",
    "Push notification failed: {reason} (device={device_id})",
    "Template rendering error: {detail} in '{template}'",
    "Invalid recipient: {recipient} – notification {notif_id} dropped",
    "SMTP authentication failed: {reason}",
    "Rate limit exceeded: {count} notifications in {seconds}s (limit={limit})",
    "Webhook delivery failed after {n} retries: {url}",
]

_FATAL_MESSAGES: list[str] = [
    "FATAL: Email provider credentials revoked – all email delivery halted",
    "FATAL: Notification queue consumer crashed – messages accumulating",
    "FATAL: Template storage unreachable – cannot render any notifications",
]

_TRACE_MESSAGES: list[str] = [
    "TRACE: Raw SMTP dialog: EHLO → 250 ({ms}ms)",
    "TRACE: FCM payload: {bytes} bytes, priority={priority}",
    "TRACE: Template AST parsed: {nodes} nodes",
]


class NotificationServiceGenerator(BaseLogGenerator):
    """Generates realistic log entries for a notification delivery service."""

    service_name: str = "notification-service"

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
            "notification_id": uuid.uuid4().hex[:12],
            "channel": random.choice(["email", "sms", "push", "in_app", "webhook"]),
            "template": random.choice([
                "welcome", "password_reset", "order_confirmation",
                "payment_receipt", "shipping_update", "promotional",
                "alert", "digest", "verification",
            ]),
            "provider": random.choice([
                "sendgrid", "ses", "twilio", "firebase", "mailgun", "sns",
            ]),
        }
        if level in ("ERROR", "FATAL"):
            meta["error_code"] = random.choice([
                "DELIVERY_FAILED", "RATE_LIMITED", "INVALID_RECIPIENT",
                "TEMPLATE_ERROR", "PROVIDER_ERROR", "AUTH_FAILED",
            ])
        return meta

    def _render_template(self, template: str) -> str:
        notif_replacements: dict[str, str] = {
            "{email}": fake.email(),
            "{subject}": random.choice([
                "Your order has shipped!", "Password reset request",
                "Welcome to the platform", "Payment receipt",
                "Action required: verify your email", "Weekly digest",
            ]),
            "{provider}": random.choice(["sendgrid", "ses", "mailgun"]),
            "{phone}": fake.phone_number(),
            "{template}": random.choice([
                "welcome_v2", "order_shipped", "payment_receipt",
                "password_reset", "promo_summer", "alert_critical",
            ]),
            "{chars}": str(random.randint(60, 160)),
            "{device_id}": f"dev_{uuid.uuid4().hex[:10]}",
            "{platform}": random.choice(["ios", "android", "web"]),
            "{user}": fake.user_name(),
            "{notif_type}": random.choice([
                "alert", "info", "promotion", "system", "social",
            ]),
            "{size}": str(random.randint(500, 50000)),
            "{batch}": f"batch_{random.randint(1000, 9999)}",
            "{count}": str(random.randint(10, 10000)),
            "{url}": fake.url(),
            "{channels}": ", ".join(random.sample(["email", "sms", "push", "in_app"], k=random.randint(1, 3))),
            "{campaign}": random.choice([
                "summer_sale", "welcome_series", "reengagement",
                "product_launch", "black_friday",
            ]),
            "{total}": str(random.randint(100, 100000)),
            "{smtp_host}": f"smtp.{fake.domain_name()}",
            "{port}": str(random.choice([25, 465, 587, 2525])),
            "{version}": f"v{random.randint(1, 5)}",
            "{valid}": random.choice(["true", "false"]),
            "{remaining}": str(random.randint(0, 500)),
            "{limit}": str(random.choice([100, 500, 1000])),
            "{domain}": fake.domain_name(),
            "{dedup_key}": uuid.uuid4().hex[:12],
            "{result}": random.choice(["new", "duplicate"]),
            "{vars}": str(random.randint(3, 20)),
            "{bounce_type}": random.choice(["hard", "soft", "complaint"]),
            "{threshold}": str(random.choice([100, 200, 500])),
            "{depth}": str(random.randint(100, 50000)),
            "{recipient}": fake.email(),
            "{notif_id}": f"notif_{uuid.uuid4().hex[:8]}",
            "{seconds}": str(random.randint(10, 120)),
            "{priority}": random.choice(["high", "normal", "low"]),
            "{nodes}": str(random.randint(5, 50)),
            "{reason}": random.choice([
                "mailbox_full", "invalid_address", "blocked_by_provider",
                "token_expired", "network_timeout", "quota_exceeded",
            ]),
            "{detail}": random.choice([
                "missing variable 'user_name'", "syntax error at line 12",
                "partial not found: 'footer'", "loop exceeded max iterations",
            ]),
        }
        result = template
        for ph, val in notif_replacements.items():
            if ph in result:
                result = result.replace(ph, val, 1)
        return super()._render_template(result)
