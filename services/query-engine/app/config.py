"""
LogSentry Query Engine - Configuration.

Loads database, Redis, and service-specific settings from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "postgres"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "logsentry"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "logsentry"))
    password: str = field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "logsentry_secret_2024")
    )


@dataclass(frozen=True)
class RedisConfig:
    """Redis connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    password: str | None = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD", None) or None
    )


@dataclass(frozen=True)
class ServiceConfig:
    """Query Engine service configuration."""

    service_name: str = "query-engine"
    port: int = 8004
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Search defaults
    default_page_size: int = 50
    max_page_size: int = 500
    max_export_rows: int = 10000

    # Cache TTLs (seconds)
    timeseries_cache_ttl: int = 60
    dashboard_cache_ttl: int = 30
    service_health_cache_ttl: int = 120


# Singleton instances
db_config = DatabaseConfig()
redis_config = RedisConfig()
service_config = ServiceConfig()
