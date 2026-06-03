"""
LogSentry - Ingestion Schemas.

Re-exports shared schemas and adds ingestion-specific models for raw/syslog
log input that needs auto-detection and parsing.
"""

import sys
sys.path.insert(0, "/app")

from shared.schemas.log_entry import (  # noqa: F401 — re-exports
    AlertCreate,
    AlertResponse,
    DashboardStats,
    IngestionResponse,
    LogEntryBatchCreate,
    LogEntryCreate,
    LogEntryResponse,
    LogLevel,
    LogSearchQuery,
    LogSearchResponse,
    ServiceHealthResponse,
    TimeseriesPoint,
    TimeseriesResponse,
)

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RawLogEntry(BaseModel):
    """A raw, unparsed log entry submitted as plain text.

    The ingestion service will auto-detect the format and parse it into
    a structured ``LogEntryCreate``.
    """

    raw: str = Field(
        ...,
        min_length=1,
        max_length=1_048_576,
        description="Raw log line or multiline log text",
    )
    source: Optional[str] = Field(
        None,
        max_length=255,
        description="Hint about the origin (e.g. 'syslog', 'file', 'agent')",
    )
    service_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Override service name when the parser cannot detect one",
    )
    environment: Optional[str] = Field(
        None,
        max_length=50,
        description="Override environment when the parser cannot detect one",
    )
    host: Optional[str] = Field(
        None,
        max_length=255,
        description="Override hostname",
    )


class SyslogEntry(BaseModel):
    """Pre-parsed syslog payload fields (RFC 5424)."""

    priority: Optional[int] = Field(None, ge=0, le=191)
    version: Optional[int] = None
    timestamp: Optional[datetime] = None
    hostname: Optional[str] = None
    app_name: Optional[str] = None
    proc_id: Optional[str] = None
    msg_id: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    facility: Optional[int] = None
    severity: Optional[int] = None


class IngestionMetrics(BaseModel):
    """Snapshot of ingestion throughput counters."""

    total_ingested: int = 0
    total_failed: int = 0
    total_parsed_raw: int = 0
    uptime_seconds: float = 0.0
    avg_rate_per_second: float = 0.0
