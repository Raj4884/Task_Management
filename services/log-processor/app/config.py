"""
LogSentry - Log Processor Service Configuration.

Loads settings from environment variables with sensible defaults
for PostgreSQL, Redis, and stream consumer configuration.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Immutable application settings sourced from environment variables."""

    # PostgreSQL
    postgres_host: str = field(
        default_factory=lambda: os.getenv("POSTGRES_HOST", "postgres")
    )
    postgres_port: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432"))
    )
    postgres_db: str = field(
        default_factory=lambda: os.getenv("POSTGRES_DB", "logsentry")
    )
    postgres_user: str = field(
        default_factory=lambda: os.getenv("POSTGRES_USER", "logsentry")
    )
    postgres_password: str = field(
        default_factory=lambda: os.getenv(
            "POSTGRES_PASSWORD", "logsentry_secret_2024"
        )
    )

    # Redis
    redis_host: str = field(
        default_factory=lambda: os.getenv("REDIS_HOST", "redis")
    )
    redis_port: int = field(
        default_factory=lambda: int(os.getenv("REDIS_PORT", "6379"))
    )
    redis_password: str | None = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD") or None
    )

    # Redis Streams
    redis_stream_name: str = field(
        default_factory=lambda: os.getenv("REDIS_STREAM_NAME", "logs:raw")
    )
    redis_consumer_group: str = field(
        default_factory=lambda: os.getenv("REDIS_CONSUMER_GROUP", "log-processors")
    )
    redis_dead_letter_stream: str = field(
        default_factory=lambda: os.getenv("REDIS_DEAD_LETTER_STREAM", "logs:dead-letter")
    )

    # Consumer tuning
    consumer_batch_size: int = field(
        default_factory=lambda: int(os.getenv("CONSUMER_BATCH_SIZE", "100"))
    )
    consumer_block_ms: int = field(
        default_factory=lambda: int(os.getenv("CONSUMER_BLOCK_MS", "5000"))
    )
    consumer_max_retries: int = field(
        default_factory=lambda: int(os.getenv("CONSUMER_MAX_RETRIES", "3"))
    )

    # Real-time pub/sub
    realtime_channel: str = field(
        default_factory=lambda: os.getenv("REALTIME_CHANNEL", "logs:realtime")
    )

    # Application
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    service_name: str = "log-processor"
    service_version: str = "1.0.0"

    # Views refresh
    views_refresh_interval_batches: int = field(
        default_factory=lambda: int(
            os.getenv("VIEWS_REFRESH_INTERVAL_BATCHES", "100")
        )
    )
    views_refresh_interval_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("VIEWS_REFRESH_INTERVAL_SECONDS", "300")
        )
    )


# Singleton settings instance
settings = Settings()
