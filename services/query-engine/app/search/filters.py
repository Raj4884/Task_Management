"""
LogSentry Query Engine - Search Filter Utilities.

Parsing and validation helpers for search query parameters.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("query-engine.filters")

# Fields allowed in ORDER BY clauses to prevent SQL injection
ALLOWED_SORT_FIELDS: set[str] = {
    "timestamp",
    "level",
    "service_name",
    "ingested_at",
    "id",
    "host",
    "environment",
}

VALID_LEVELS: set[str] = {"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}

VALID_INTERVALS: dict[str, str] = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "6h": "6 hours",
    "1d": "1 day",
}


def parse_time_range(
    start: str | None,
    end: str | None,
    default_hours: int = 24,
) -> tuple[datetime, datetime]:
    """Parse start/end time strings into UTC datetime objects.

    Args:
        start: ISO-format start time string, or None for default lookback.
        end: ISO-format end time string, or None for now.
        default_hours: Hours to look back when start is not specified.

    Returns:
        Tuple of (start_dt, end_dt) in UTC.

    Raises:
        ValueError: If the time strings are not valid ISO-format.
    """
    now = datetime.now(timezone.utc)

    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid end_time format: {end}") from exc
    else:
        end_dt = now

    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid start_time format: {start}") from exc
    else:
        start_dt = end_dt - timedelta(hours=default_hours)

    # Ensure start < end
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    return start_dt, end_dt


def parse_levels(levels_str: str | None) -> list[str]:
    """Parse a comma-separated levels string into a validated list.

    Args:
        levels_str: Comma-separated log levels, e.g. "ERROR,FATAL".

    Returns:
        List of validated uppercase level strings.

    Raises:
        ValueError: If any level is not recognized.
    """
    if not levels_str:
        return []

    parsed: list[str] = []
    for raw in levels_str.split(","):
        level = raw.strip().upper()
        if level and level not in VALID_LEVELS:
            raise ValueError(
                f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(VALID_LEVELS))}"
            )
        if level:
            parsed.append(level)

    return parsed


def validate_sort_field(field: str) -> str:
    """Validate and return a safe sort field name.

    Only fields from the allow-list are permitted to prevent SQL injection.

    Args:
        field: Requested sort field name.

    Returns:
        The validated field name.

    Raises:
        ValueError: If the field is not in the allow-list.
    """
    normalised = field.strip().lower()
    if normalised not in ALLOWED_SORT_FIELDS:
        raise ValueError(
            f"Invalid sort field '{field}'. Allowed: {', '.join(sorted(ALLOWED_SORT_FIELDS))}"
        )
    return normalised


def validate_sort_order(order: str) -> str:
    """Validate sort order is 'asc' or 'desc'.

    Args:
        order: Requested sort order.

    Returns:
        Validated lowercase sort order.

    Raises:
        ValueError: If the order is invalid.
    """
    normalised = order.strip().lower()
    if normalised not in ("asc", "desc"):
        raise ValueError("sort_order must be 'asc' or 'desc'")
    return normalised


def parse_metadata_filter(filter_str: str | None) -> dict | None:
    """Parse a metadata filter string into a JSONB-compatible dict.

    Supports two formats:
      - JSON string: '{"key": "value"}'
      - Simple key=value pairs: 'region=us-east-1,tier=premium'

    Args:
        filter_str: Raw metadata filter string from the query parameter.

    Returns:
        Dictionary suitable for JSONB @> containment queries, or None.
    """
    if not filter_str:
        return None

    stripped = filter_str.strip()

    # Attempt JSON parse first
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            logger.warning("Failed to parse metadata filter as JSON: %s", stripped)

    # Fall back to key=value parsing
    result: dict[str, str] = {}
    for pair in stripped.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value

    return result if result else None


def validate_interval(interval: str) -> str:
    """Validate a time interval shorthand and return a PostgreSQL interval string.

    Args:
        interval: Shorthand like '1m', '5m', '1h', '1d'.

    Returns:
        PostgreSQL-compatible interval string.

    Raises:
        ValueError: If the interval is not recognized.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval '{interval}'. Allowed: {', '.join(VALID_INTERVALS.keys())}"
        )
    return VALID_INTERVALS[interval]
