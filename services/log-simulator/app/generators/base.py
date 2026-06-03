"""Base log generator that all service-specific generators extend.

Provides realistic log generation with:
- Weighted log-level distribution
- Correlated trace / span IDs
- Multiple host instances per service
- Rich, realistic metadata
- Override hooks for failure-scenario injection
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone
from typing import Any

from faker import Faker

fake = Faker()

# ---------------------------------------------------------------------------
# Weighted log-level distribution (sums to 1000 for integer sampling)
# INFO 60%, DEBUG 20%, WARN 12%, ERROR 7%, FATAL 0.5%, TRACE 0.5%
# ---------------------------------------------------------------------------
_LEVEL_WEIGHTS: list[tuple[str, int]] = [
    ("INFO", 600),
    ("DEBUG", 200),
    ("WARN", 120),
    ("ERROR", 70),
    ("FATAL", 5),
    ("TRACE", 5),
]
_LEVELS, _WEIGHTS = zip(*_LEVEL_WEIGHTS)

# ---------------------------------------------------------------------------
# Common generic log messages (used as fallback by the base class)
# ---------------------------------------------------------------------------
_GENERIC_INFO_MESSAGES: list[str] = [
    "Request processed successfully",
    "Health check passed",
    "Configuration reloaded",
    "Cache refreshed for key group '{group}'",
    "Scheduled job '{job}' completed in {ms}ms",
    "Connection pool stats: active={active}, idle={idle}",
    "Metrics flushed to collector",
    "Graceful shutdown initiated",
    "Worker thread started: {thread}",
    "Rate limiter bucket refilled",
]

_GENERIC_DEBUG_MESSAGES: list[str] = [
    "Entering handler: {handler}",
    "SQL query executed in {ms}ms",
    "Cache lookup for key '{key}': {result}",
    "Serialising response payload ({bytes} bytes)",
    "Retry attempt {n} for operation '{op}'",
    "Deserialised request body in {ms}ms",
    "Thread pool utilisation: {pct}%",
    "DNS resolution for {host} took {ms}ms",
]

_GENERIC_WARN_MESSAGES: list[str] = [
    "Response time exceeded threshold: {ms}ms > {threshold}ms",
    "Connection pool nearing capacity: {pct}% used",
    "Deprecated API version called: {version}",
    "Disk usage at {pct}% on {volume}",
    "Retry {n}/{max} for downstream call to {service}",
    "Request payload size {kb}KB exceeds recommendation",
    "Certificate expires in {days} days",
]

_GENERIC_ERROR_MESSAGES: list[str] = [
    "Unhandled exception in request handler: {exc}",
    "Database connection timed out after {ms}ms",
    "Downstream service '{service}' returned HTTP {status}",
    "Failed to write to cache: {reason}",
    "Circuit breaker OPEN for {service}",
    "Request validation failed: {detail}",
    "Out of memory: heap usage {mb}MB",
]

_GENERIC_FATAL_MESSAGES: list[str] = [
    "FATAL: Unable to connect to database after {n} retries – shutting down",
    "FATAL: Corrupted WAL segment detected – manual intervention required",
    "FATAL: TLS certificate invalid – refusing to serve traffic",
    "FATAL: Out of file descriptors (limit={limit})",
]

_GENERIC_TRACE_MESSAGES: list[str] = [
    "TRACE: Middleware chain entry: {mw}",
    "TRACE: Raw socket read {bytes} bytes",
    "TRACE: GC pause {ms}ms (generation {gen})",
    "TRACE: Header parsing complete for request {req_id}",
]


def _random_hex(length: int = 16) -> str:
    """Return a random lowercase hex string of *length* characters."""
    return "".join(random.choices(string.hexdigits[:16], k=length))


class BaseLogGenerator:
    """Generates realistic log entries for a single simulated microservice.

    Subclasses override ``_service_messages()`` and ``_service_metadata()``
    to add domain-specific messages and metadata.  The base class provides
    all the structural plumbing (levels, timestamps, trace propagation,
    host selection, override hooks).
    """

    # Subclasses should set these as class-level defaults.
    service_name: str = "generic-service"
    _environments: list[str] = ["production"]
    _host_count: int = 3  # number of simulated instances

    def __init__(
        self,
        service_name: str | None = None,
        environment: str = "production",
    ) -> None:
        if service_name is not None:
            self.service_name = service_name
        self.environment = environment

        # Build stable host names for this service
        self.hosts: list[str] = [
            f"{self.service_name}-{i:02d}.internal"
            for i in range(1, self._host_count + 1)
        ]

        # Trace-ID pool – reuse a small pool so some logs are correlated
        self._trace_pool: list[str] = [uuid.uuid4().hex for _ in range(8)]
        self._trace_pool_cursor: int = 0

        # Override knobs (modified by scenarios)
        self._error_rate_override: float | None = None
        self._latency_factor: float = 1.0
        self._extra_messages: list[tuple[str, str]] = []  # (level, message)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_log(self) -> dict[str, Any]:
        """Generate a single realistic log entry as a plain dict."""
        level = self._pick_level()
        message = self._pick_message(level)
        trace_id, span_id = self._pick_trace()
        host = random.choice(self.hosts)
        duration_ms = self._pick_duration(level)
        status_code = self._pick_status_code(level)

        metadata: dict[str, Any] = {
            "request_id": uuid.uuid4().hex[:12],
            "duration_ms": duration_ms,
            "status_code": status_code,
        }
        # Merge in service-specific metadata
        metadata.update(self._service_metadata(level))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service_name": self.service_name,
            "message": message,
            "trace_id": trace_id,
            "span_id": span_id,
            "environment": self.environment,
            "host": host,
            "metadata": metadata,
        }

    def generate_batch(self, count: int) -> list[dict[str, Any]]:
        """Generate *count* log entries."""
        return [self.generate_log() for _ in range(count)]

    # -- Override hooks for scenarios ------------------------------------

    def set_error_rate(self, rate: float) -> None:
        """Override error probability (0.0 – 1.0). Pass *None* to reset."""
        self._error_rate_override = max(0.0, min(rate, 1.0))

    def set_latency_factor(self, factor: float) -> None:
        """Multiply all generated latency values by *factor*."""
        self._latency_factor = max(0.1, factor)

    def inject_messages(self, messages: list[tuple[str, str]]) -> None:
        """Inject extra ``(level, message)`` pairs to be emitted."""
        self._extra_messages.extend(messages)

    def reset(self) -> None:
        """Reset to normal behaviour after a scenario ends."""
        self._error_rate_override = None
        self._latency_factor = 1.0
        self._extra_messages.clear()

    # ------------------------------------------------------------------
    # Internal helpers (override in subclasses)
    # ------------------------------------------------------------------

    def _service_messages(self, level: str) -> list[str]:
        """Return service-specific message templates for *level*.

        Subclasses **should** override this to provide domain-relevant
        messages.  The base implementation falls back to generic messages.
        """
        return []

    def _service_metadata(self, level: str) -> dict[str, Any]:
        """Return additional service-specific metadata fields.

        Subclasses **should** override this to add domain-specific
        metadata (e.g. ``user_id``, ``order_id``).
        """
        return {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pick_level(self) -> str:
        """Choose a log level respecting optional error-rate override."""
        if self._error_rate_override is not None:
            if random.random() < self._error_rate_override:
                return random.choices(["ERROR", "FATAL"], weights=[9, 1])[0]
            # Remaining traffic is mostly INFO/DEBUG
            return random.choices(
                ["INFO", "DEBUG", "WARN", "TRACE"],
                weights=[55, 25, 15, 5],
            )[0]
        return random.choices(_LEVELS, weights=_WEIGHTS, k=1)[0]

    def _pick_message(self, level: str) -> str:
        """Select a realistic message for the given level."""
        # Drain injected messages first (FIFO)
        if self._extra_messages:
            inj_level, inj_msg = self._extra_messages.pop(0)
            if inj_level == level or random.random() < 0.3:
                return inj_msg

        # Try service-specific messages first
        pool = self._service_messages(level)
        if not pool:
            pool = self._generic_messages(level)
        template = random.choice(pool)
        return self._render_template(template)

    @staticmethod
    def _generic_messages(level: str) -> list[str]:
        """Fallback generic messages by level."""
        return {
            "INFO": _GENERIC_INFO_MESSAGES,
            "DEBUG": _GENERIC_DEBUG_MESSAGES,
            "WARN": _GENERIC_WARN_MESSAGES,
            "ERROR": _GENERIC_ERROR_MESSAGES,
            "FATAL": _GENERIC_FATAL_MESSAGES,
            "TRACE": _GENERIC_TRACE_MESSAGES,
        }.get(level, _GENERIC_INFO_MESSAGES)

    def _render_template(self, template: str) -> str:
        """Fill placeholders in a message template with realistic data."""
        replacements: dict[str, str] = {
            "{ms}": str(random.randint(1, 5000)),
            "{bytes}": str(random.randint(64, 65536)),
            "{kb}": str(random.randint(1, 2048)),
            "{mb}": str(random.randint(64, 4096)),
            "{pct}": str(random.randint(50, 99)),
            "{n}": str(random.randint(1, 10)),
            "{max}": str(random.randint(3, 10)),
            "{limit}": str(random.choice([1024, 4096, 65536])),
            "{days}": str(random.randint(1, 30)),
            "{gen}": str(random.randint(0, 2)),
            "{active}": str(random.randint(5, 50)),
            "{idle}": str(random.randint(0, 20)),
            "{status}": str(random.choice([400, 401, 403, 404, 429, 500, 502, 503, 504])),
            "{version}": random.choice(["v1", "v2-beta", "v1.1-deprecated"]),
            "{volume}": random.choice(["/data", "/var/log", "/tmp"]),
            "{service}": random.choice([
                "auth-service", "payment-service", "order-service",
                "user-service", "notification-service", "inventory-service",
            ]),
            "{handler}": random.choice([
                "POST /api/v1/orders", "GET /api/v1/users/{id}",
                "PUT /api/v1/settings", "DELETE /api/v1/sessions",
            ]),
            "{key}": f"cache:{fake.lexify('???')}:{random.randint(1, 9999)}",
            "{result}": random.choice(["HIT", "MISS"]),
            "{op}": random.choice(["db_write", "api_call", "cache_set", "s3_upload"]),
            "{thread}": f"worker-{random.randint(1, 16)}",
            "{host}": fake.hostname(),
            "{job}": random.choice(["cleanup", "reindex", "aggregate", "sync"]),
            "{group}": random.choice(["users", "products", "sessions", "analytics"]),
            "{exc}": random.choice([
                "NullPointerException", "ConnectionResetError",
                "TimeoutError", "ValueError", "KeyError",
                "PermissionError", "IOError",
            ]),
            "{reason}": random.choice([
                "connection refused", "timeout", "disk full",
                "serialisation error", "key too large",
            ]),
            "{detail}": random.choice([
                "missing required field 'email'",
                "invalid UUID format for 'id'",
                "value out of range for 'quantity'",
                "unknown enum variant 'XLARGE'",
            ]),
            "{mw}": random.choice([
                "AuthMiddleware", "RateLimiter", "RequestLogger",
                "CORSHandler", "CompressionMiddleware",
            ]),
            "{req_id}": uuid.uuid4().hex[:12],
        }
        result = template
        for placeholder, value in replacements.items():
            if placeholder in result:
                result = result.replace(placeholder, value, 1)
        return result

    def _pick_trace(self) -> tuple[str, str]:
        """Select a trace ID (sometimes reused) and a fresh span ID."""
        # 30% chance of reusing a recent trace ID to simulate correlation
        if random.random() < 0.3:
            trace_id = self._trace_pool[
                self._trace_pool_cursor % len(self._trace_pool)
            ]
        else:
            trace_id = uuid.uuid4().hex
            # Rotate into the pool
            self._trace_pool[
                self._trace_pool_cursor % len(self._trace_pool)
            ] = trace_id
            self._trace_pool_cursor += 1
        span_id = _random_hex(16)
        return trace_id, span_id

    def _pick_duration(self, level: str) -> int:
        """Generate a realistic response duration in ms.

        Errors tend to have higher durations (timeouts). The value is
        then multiplied by the latency factor set by scenarios.
        """
        if level in ("ERROR", "FATAL"):
            base = random.choices(
                [random.randint(500, 5000), random.randint(10, 300)],
                weights=[7, 3],
            )[0]
        elif level == "WARN":
            base = random.randint(100, 1500)
        else:
            base = random.randint(10, 200)
        return int(base * self._latency_factor)

    @staticmethod
    def _pick_status_code(level: str) -> int:
        """Choose an HTTP status code consistent with the log level."""
        if level in ("ERROR", "FATAL"):
            return random.choice([400, 401, 403, 404, 408, 429, 500, 502, 503, 504])
        if level == "WARN":
            return random.choice([200, 201, 301, 400, 408, 429])
        return random.choice([200, 200, 200, 201, 204])
