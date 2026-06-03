"""
LogSentry - Log Ingestion Service Configuration.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Immutable application settings sourced from environment variables."""

    # Redis connection
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
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
    redis_stream_maxlen: int = field(
        default_factory=lambda: int(os.getenv("REDIS_STREAM_MAXLEN", "100000"))
    )

    # Application
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    service_name: str = "log-ingestion"
    service_version: str = "1.0.0"

    # Ingestion limits
    max_batch_size: int = field(
        default_factory=lambda: int(os.getenv("MAX_BATCH_SIZE", "1000"))
    )
    max_message_size_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_MESSAGE_SIZE_BYTES", "1048576"))  # 1MB
    )


# Singleton settings instance
settings = Settings()
