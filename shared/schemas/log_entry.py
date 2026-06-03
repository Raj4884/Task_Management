"""
LogSentry - Shared Pydantic schemas for log entries.
Used across all microservices for consistent data contracts.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class LogLevel(str, Enum):
    """Standard log levels."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogEntryCreate(BaseModel):
    """Schema for creating a new log entry (ingestion input)."""
    timestamp: Optional[datetime] = None
    level: LogLevel = LogLevel.INFO
    service_name: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    trace_id: Optional[str] = Field(None, max_length=64)
    span_id: Optional[str] = Field(None, max_length=32)
    environment: Optional[str] = Field("production", max_length=50)
    host: Optional[str] = Field(None, max_length=255)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def set_timestamp(cls, v):
        return v or datetime.utcnow()


class LogEntryBatchCreate(BaseModel):
    """Schema for batch log ingestion."""
    logs: list[LogEntryCreate] = Field(..., min_length=1, max_length=1000)


class LogEntryResponse(BaseModel):
    """Schema for log entry API response."""
    id: int
    timestamp: datetime
    level: LogLevel
    service_name: str
    message: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    environment: Optional[str] = None
    host: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_fingerprint: Optional[str] = None
    ingested_at: datetime

    class Config:
        from_attributes = True


class LogSearchQuery(BaseModel):
    """Schema for search queries."""
    q: Optional[str] = None
    service_name: Optional[str] = None
    level: Optional[LogLevel] = None
    levels: Optional[list[LogLevel]] = None
    environment: Optional[str] = None
    trace_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    host: Optional[str] = None
    metadata_filters: Optional[dict[str, Any]] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)
    sort_by: str = Field("timestamp")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class LogSearchResponse(BaseModel):
    """Paginated search response."""
    logs: list[LogEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    query_time_ms: float


class ServiceInfo(BaseModel):
    """Service registry entry."""
    id: str
    name: str
    description: Optional[str] = None
    environment: str = "production"
    status: str = "active"
    first_seen_at: datetime
    last_seen_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ServiceHealthResponse(BaseModel):
    """Service health metrics."""
    service_name: str
    total_logs_24h: int = 0
    errors_24h: int = 0
    fatals_24h: int = 0
    warns_24h: int = 0
    error_rate_pct: float = 0.0
    first_log: Optional[datetime] = None
    last_log: Optional[datetime] = None
    unique_errors: int = 0
    status: str = "active"


class AlertCreate(BaseModel):
    """Schema for creating an alert."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    severity: str = Field(..., pattern="^(info|warning|critical|emergency)$")
    service_name: Optional[str] = None
    rule_type: str = Field(..., pattern="^(threshold|pattern|anomaly|absence)$")
    rule_config: dict[str, Any] = Field(default_factory=dict)


class AlertResponse(BaseModel):
    """Alert API response."""
    id: str
    title: str
    description: Optional[str] = None
    severity: str
    service_name: Optional[str] = None
    rule_type: str
    rule_config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class AnomalyResponse(BaseModel):
    """ML anomaly detection result."""
    id: str
    detected_at: datetime
    anomaly_type: str
    service_name: Optional[str] = None
    severity_score: float
    description: Optional[str] = None
    features: dict[str, Any] = Field(default_factory=dict)
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    is_acknowledged: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class TimeseriesPoint(BaseModel):
    """Single point in a time series."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


class TimeseriesResponse(BaseModel):
    """Time series analytics response."""
    metric: str
    interval: str
    data: list[TimeseriesPoint]
    total: float
    average: float


class IngestionResponse(BaseModel):
    """Response from log ingestion endpoints."""
    status: str = "accepted"
    count: int = 0
    message: str = "Logs queued for processing"


class UserCreate(BaseModel):
    """User registration schema."""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    """User API response (no password)."""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class DashboardStats(BaseModel):
    """Overview dashboard statistics."""
    total_logs_24h: int = 0
    total_errors_24h: int = 0
    error_rate_pct: float = 0.0
    active_services: int = 0
    active_alerts: int = 0
    anomalies_detected: int = 0
    logs_per_second: float = 0.0
    top_error_services: list[dict[str, Any]] = Field(default_factory=list)
