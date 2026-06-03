"""
LogSentry - Log Format Parser.

Detects and parses common log formats into a dict compatible with
``LogEntryCreate`` fields.  Supported formats:

* JSON structured logs
* Syslog RFC 3164 / RFC 5424
* Apache / Nginx combined access log
* Generic plain-text with heuristic pattern matching
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("log-ingestion.parser")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Syslog RFC 3164:  <PRI>Mon DD HH:MM:SS hostname app[pid]: message
_SYSLOG_3164_RE = re.compile(
    r"^(?:<(\d{1,3})>)?"
    r"\s*([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
    r"\s+(\S+)"
    r"\s+(\S+?)(?:\[(\d+)\])?:\s+"
    r"(.+)$",
    re.DOTALL,
)

# Syslog RFC 5424:  <PRI>VER TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG
_SYSLOG_5424_RE = re.compile(
    r"^<(\d{1,3})>(\d+)\s+"
    r"(\S+)\s+"   # timestamp
    r"(\S+)\s+"   # hostname
    r"(\S+)\s+"   # app-name
    r"(\S+)\s+"   # procid
    r"(\S+)\s*"   # msgid
    r"(?:\[.*?\]\s*)?"  # structured data (skip for now)
    r"(.*)$",
    re.DOTALL,
)

# Apache/Nginx combined:  host ident user [datetime] "request" status bytes "referer" "ua"
_APACHE_COMBINED_RE = re.compile(
    r'^(\S+)\s+(\S+)\s+(\S+)\s+'
    r'\[([^\]]+)\]\s+'
    r'"([^"]*?)"\s+'
    r'(\d{3})\s+'
    r'(\d+|-)\s*'
    r'(?:"([^"]*?)"\s*)?'
    r'(?:"([^"]*?)")?'
)

# Common plain-text pattern: TIMESTAMP LEVEL [optional context] message
_PLAIN_TEXT_RE = re.compile(
    r"^(\d{4}[-/]\d{2}[-/]\d{2}[T\s]\d{2}:\d{2}:\d{2}[.,]?\d*(?:Z|[+-]\d{2}:?\d{2})?)"
    r"\s+(\w+)"
    r"(?:\s+\[([^\]]+)\])?"
    r"\s+(.+)$",
    re.DOTALL,
)

# Fallback: just a level keyword at the beginning
_LEVEL_PREFIX_RE = re.compile(
    r"^\[?(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|ERR|FATAL|CRITICAL|SEVERE)\]?\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# Priority → syslog severity mapping
_SYSLOG_SEVERITY_MAP = {
    0: "FATAL",   # Emergency
    1: "FATAL",   # Alert
    2: "FATAL",   # Critical
    3: "ERROR",   # Error
    4: "WARN",    # Warning
    5: "INFO",    # Notice
    6: "INFO",    # Informational
    7: "DEBUG",   # Debug
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_json_log(raw: str) -> Optional[dict]:
    """Parse a JSON-formatted log entry.

    Handles common JSON log schemas produced by structured logging libraries
    (Python ``logging``, Go ``zap``/``zerolog``, Node ``pino``/``winston``).

    Returns
    -------
    dict | None
        Fields compatible with ``LogEntryCreate``, or ``None`` on failure.
    """
    try:
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    # Try common field names for each LogEntryCreate attribute
    message = (
        data.get("message")
        or data.get("msg")
        or data.get("log")
        or data.get("text")
        or data.get("body")
        or ""
    )
    if not message:
        return None

    level = (
        data.get("level")
        or data.get("severity")
        or data.get("log_level")
        or data.get("loglevel")
        or "INFO"
    )

    timestamp = (
        data.get("timestamp")
        or data.get("time")
        or data.get("ts")
        or data.get("@timestamp")
        or data.get("datetime")
    )

    service_name = (
        data.get("service_name")
        or data.get("service")
        or data.get("app")
        or data.get("application")
        or data.get("logger")
        or data.get("name")
        or "unknown"
    )

    # Build metadata from remaining keys
    known_keys = {
        "message", "msg", "log", "text", "body",
        "level", "severity", "log_level", "loglevel",
        "timestamp", "time", "ts", "@timestamp", "datetime",
        "service_name", "service", "app", "application", "logger", "name",
        "trace_id", "traceId", "traceID", "span_id", "spanId", "spanID",
        "environment", "env", "host", "hostname", "server",
    }
    metadata = {k: v for k, v in data.items() if k not in known_keys}

    return {
        "timestamp": timestamp,
        "level": str(level),
        "service_name": str(service_name),
        "message": str(message),
        "trace_id": data.get("trace_id") or data.get("traceId") or data.get("traceID"),
        "span_id": data.get("span_id") or data.get("spanId") or data.get("spanID"),
        "environment": data.get("environment") or data.get("env"),
        "host": data.get("host") or data.get("hostname") or data.get("server"),
        "metadata": metadata if metadata else {},
    }


def parse_syslog(raw: str) -> Optional[dict]:
    """Parse syslog format (RFC 3164 and RFC 5424).

    Returns
    -------
    dict | None
        Fields compatible with ``LogEntryCreate``, or ``None`` on failure.
    """
    line = raw.strip()

    # Try RFC 5424 first (has version number)
    m = _SYSLOG_5424_RE.match(line)
    if m:
        pri = int(m.group(1))
        severity = pri & 0x07
        facility = pri >> 3
        return {
            "timestamp": m.group(3),
            "level": _SYSLOG_SEVERITY_MAP.get(severity, "INFO"),
            "service_name": m.group(5) if m.group(5) != "-" else "unknown",
            "message": m.group(8) or "",
            "host": m.group(4) if m.group(4) != "-" else None,
            "trace_id": None,
            "span_id": None,
            "environment": None,
            "metadata": {
                "syslog_facility": facility,
                "syslog_severity": severity,
                "syslog_version": int(m.group(2)),
                "syslog_procid": m.group(6) if m.group(6) != "-" else None,
                "syslog_msgid": m.group(7) if m.group(7) != "-" else None,
            },
        }

    # Try RFC 3164
    m = _SYSLOG_3164_RE.match(line)
    if m:
        pri_str = m.group(1)
        level = "INFO"
        metadata: dict = {}
        if pri_str:
            pri = int(pri_str)
            severity = pri & 0x07
            facility = pri >> 3
            level = _SYSLOG_SEVERITY_MAP.get(severity, "INFO")
            metadata["syslog_facility"] = facility
            metadata["syslog_severity"] = severity

        proc_id = m.group(5)
        if proc_id:
            metadata["pid"] = proc_id

        return {
            "timestamp": m.group(2),
            "level": level,
            "service_name": m.group(4) or "unknown",
            "message": m.group(6) or "",
            "host": m.group(3) if m.group(3) != "-" else None,
            "trace_id": None,
            "span_id": None,
            "environment": None,
            "metadata": metadata,
        }

    return None


def parse_apache_combined(raw: str) -> Optional[dict]:
    """Parse Apache/Nginx combined access-log format.

    Returns
    -------
    dict | None
        Fields compatible with ``LogEntryCreate``, or ``None`` on failure.
    """
    m = _APACHE_COMBINED_RE.match(raw.strip())
    if not m:
        return None

    client_ip = m.group(1)
    timestamp_str = m.group(4)
    request_line = m.group(5)
    status_code = int(m.group(6))
    bytes_sent_str = m.group(7)
    referer = m.group(8) if m.group(8) else None
    user_agent = m.group(9) if m.group(9) else None

    bytes_sent = int(bytes_sent_str) if bytes_sent_str != "-" else 0

    # Determine log level from HTTP status code
    if status_code >= 500:
        level = "ERROR"
    elif status_code >= 400:
        level = "WARN"
    else:
        level = "INFO"

    return {
        "timestamp": timestamp_str,
        "level": level,
        "service_name": "httpd",
        "message": f"{request_line} → {status_code}",
        "host": client_ip,
        "trace_id": None,
        "span_id": None,
        "environment": None,
        "metadata": {
            "http_method": request_line.split()[0] if request_line else None,
            "http_path": request_line.split()[1] if len(request_line.split()) > 1 else None,
            "http_status": status_code,
            "bytes_sent": bytes_sent,
            "referer": referer,
            "user_agent": user_agent,
            "client_ip": client_ip,
        },
    }


def parse_plain_text(raw: str) -> Optional[dict]:
    """Parse plain-text log lines using heuristic regex patterns.

    Handles formats like::

        2024-01-15T10:30:00Z ERROR [service] Some message
        2024-01-15 10:30:00 WARN  Some message

    Returns
    -------
    dict | None
        Fields compatible with ``LogEntryCreate``, or ``None`` on failure.
    """
    line = raw.strip()
    if not line:
        return None

    # Try structured plain-text: TIMESTAMP LEVEL [context] message
    m = _PLAIN_TEXT_RE.match(line)
    if m:
        context = m.group(3)
        service = context if context else "unknown"
        return {
            "timestamp": m.group(1),
            "level": m.group(2).upper(),
            "service_name": service,
            "message": m.group(4),
            "host": None,
            "trace_id": None,
            "span_id": None,
            "environment": None,
            "metadata": {},
        }

    # Fallback: starts with a level keyword
    m = _LEVEL_PREFIX_RE.match(line)
    if m:
        return {
            "timestamp": None,
            "level": m.group(1).upper(),
            "service_name": "unknown",
            "message": m.group(2),
            "host": None,
            "trace_id": None,
            "span_id": None,
            "environment": None,
            "metadata": {},
        }

    return None


def auto_detect_and_parse(raw: str) -> dict:
    """Try each parser in priority order and return the first success.

    Priority:
    1. JSON (most unambiguous)
    2. Syslog (RFC 5424 / 3164)
    3. Apache/Nginx combined
    4. Structured plain-text
    5. Fallback — wrap entire line as message

    Returns
    -------
    dict
        Always returns a dict; worst case wraps the raw text as the message.
    """
    if not raw or not raw.strip():
        return {
            "timestamp": None,
            "level": "INFO",
            "service_name": "unknown",
            "message": raw or "",
            "host": None,
            "trace_id": None,
            "span_id": None,
            "environment": None,
            "metadata": {},
        }

    parsers = [
        ("json", parse_json_log),
        ("syslog", parse_syslog),
        ("apache_combined", parse_apache_combined),
        ("plain_text", parse_plain_text),
    ]

    for name, parser in parsers:
        try:
            result = parser(raw)
            if result:
                result.setdefault("metadata", {})
                result["metadata"]["_parsed_format"] = name
                logger.debug("Parsed with %s parser", name)
                return result
        except Exception:
            logger.debug("Parser %s raised an exception", name, exc_info=True)
            continue

    # Ultimate fallback — wrap raw text as the message
    logger.debug("No parser matched; using raw fallback")
    return {
        "timestamp": None,
        "level": "INFO",
        "service_name": "unknown",
        "message": raw.strip(),
        "host": None,
        "trace_id": None,
        "span_id": None,
        "environment": None,
        "metadata": {"_parsed_format": "raw_fallback"},
    }
