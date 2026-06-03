"""
LogSentry - Log Entry Normalizer.

Normalizes parsed log entries so they conform to the ``LogEntryCreate``
contract regardless of source format:

* Timestamps → UTC ``datetime``
* Levels → standard ``LogLevel`` enum values
* Missing fields → sensible defaults
* Trace IDs → auto-generated when absent
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dateutil_parser

logger = logging.getLogger("log-ingestion.normalizer")

# ---------------------------------------------------------------------------
# Level normalisation look-up
# ---------------------------------------------------------------------------
_LEVEL_MAP: dict[str, str] = {
    # Standard
    "trace": "TRACE",
    "debug": "DEBUG",
    "info": "INFO",
    "informational": "INFO",
    "notice": "INFO",
    "warn": "WARN",
    "warning": "WARN",
    "error": "ERROR",
    "err": "ERROR",
    "fatal": "FATAL",
    "critical": "FATAL",
    "crit": "FATAL",
    "alert": "FATAL",
    "emergency": "FATAL",
    "emerg": "FATAL",
    "panic": "FATAL",
    "severe": "ERROR",
    # Numeric syslog severities (as strings)
    "0": "FATAL",
    "1": "FATAL",
    "2": "FATAL",
    "3": "ERROR",
    "4": "WARN",
    "5": "INFO",
    "6": "INFO",
    "7": "DEBUG",
}

_VALID_LEVELS = {"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}

# Apache-style timestamp: 15/Jan/2024:10:30:00 +0000
_APACHE_TS_RE = re.compile(
    r"^(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}:\d{2}:\d{2})\s*([+-]\d{4})$"
)

# Syslog 3164 timestamp: Jan 15 10:30:00 (no year)
_SYSLOG_3164_TS_RE = re.compile(
    r"^([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_timestamp(ts: Any) -> datetime:
    """Convert various timestamp representations to a UTC-aware ``datetime``.

    Supported inputs
    ----------------
    * ``datetime`` objects (made tz-aware if naive)
    * ISO 8601 strings (``2024-01-15T10:30:00Z``)
    * Unix epoch seconds / milliseconds (``float`` or numeric ``str``)
    * Apache access-log format (``15/Jan/2024:10:30:00 +0000``)
    * Syslog RFC 3164 (``Jan 15 10:30:00`` — current year assumed)
    * Any other string parseable by ``dateutil``

    Returns
    -------
    datetime
        Always tz-aware in UTC.
    """
    if ts is None:
        return datetime.now(timezone.utc)

    # Already a datetime
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    # Numeric epoch
    if isinstance(ts, (int, float)):
        return _epoch_to_utc(ts)

    # String handling
    if not isinstance(ts, str):
        ts = str(ts)

    ts = ts.strip()
    if not ts:
        return datetime.now(timezone.utc)

    # Try numeric string (epoch)
    try:
        epoch = float(ts)
        return _epoch_to_utc(epoch)
    except ValueError:
        pass

    # Apache combined format
    m = _APACHE_TS_RE.match(ts)
    if m:
        reformed = f"{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)} {m.group(5)}"
        try:
            return dateutil_parser.parse(reformed).astimezone(timezone.utc)
        except Exception:
            pass

    # Syslog 3164 (no year)
    m = _SYSLOG_3164_TS_RE.match(ts)
    if m:
        year = datetime.now(timezone.utc).year
        reformed = f"{m.group(1)} {m.group(2)} {year} {m.group(3)}"
        try:
            return dateutil_parser.parse(reformed).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Generic dateutil parse
    try:
        dt = dateutil_parser.parse(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        logger.warning("Unable to parse timestamp '%s'; using current time", ts)
        return datetime.now(timezone.utc)


def normalize_level(level: str) -> str:
    """Map a log-level string to a standard ``LogLevel`` value.

    Examples
    --------
    >>> normalize_level("warning")
    'WARN'
    >>> normalize_level("err")
    'ERROR'
    >>> normalize_level("critical")
    'FATAL'

    Returns
    -------
    str
        One of TRACE, DEBUG, INFO, WARN, ERROR, FATAL.
    """
    if not level:
        return "INFO"

    upper = level.strip().upper()
    if upper in _VALID_LEVELS:
        return upper

    return _LEVEL_MAP.get(level.strip().lower(), "INFO")


def normalize_entry(entry: dict) -> dict:
    """Apply all normalizations and fill in required defaults.

    Parameters
    ----------
    entry : dict
        Parsed (but not yet normalized) log entry dict.

    Returns
    -------
    dict
        Fully normalized dict ready for ``LogEntryCreate`` validation.
    """
    normalized = dict(entry)  # shallow copy

    # Timestamp
    normalized["timestamp"] = normalize_timestamp(
        normalized.get("timestamp")
    ).isoformat()

    # Level
    normalized["level"] = normalize_level(str(normalized.get("level", "INFO")))

    # Service name — must be non-empty
    svc = normalized.get("service_name")
    if not svc or not str(svc).strip():
        normalized["service_name"] = "unknown"
    else:
        normalized["service_name"] = str(svc).strip()

    # Message — must be non-empty
    msg = normalized.get("message")
    if not msg or not str(msg).strip():
        normalized["message"] = "(empty)"
    else:
        normalized["message"] = str(msg).strip()

    # Trace ID — generate if missing
    if not normalized.get("trace_id"):
        normalized["trace_id"] = uuid.uuid4().hex

    # Span ID — leave None if not present (optional)
    normalized.setdefault("span_id", None)

    # Environment
    normalized.setdefault("environment", "production")

    # Host
    normalized.setdefault("host", None)

    # Metadata
    meta = normalized.get("metadata")
    if meta is None or not isinstance(meta, dict):
        normalized["metadata"] = {}

    return normalized


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _epoch_to_utc(epoch: float) -> datetime:
    """Convert a Unix epoch to UTC datetime.

    Handles both seconds and milliseconds by checking magnitude.
    """
    # Milliseconds threshold: anything > year 2100 in seconds ≈ 4.1e9
    if epoch > 1e12:
        epoch = epoch / 1000.0
    return datetime.fromtimestamp(epoch, tz=timezone.utc)
