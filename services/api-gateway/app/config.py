"""
LogSentry API Gateway - Configuration.

Loads all settings from environment variables with sensible defaults
for local development. In production, all secrets MUST be overridden.
"""

import os


class Settings:
    """Application settings loaded from environment variables."""

    # ── JWT ───────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )

    # ── Internal service URLs ─────────────────────────────────────────
    INGESTION_SERVICE_URL: str = os.getenv(
        "INGESTION_SERVICE_URL", "http://log-ingestion:8001"
    )
    QUERY_ENGINE_URL: str = os.getenv(
        "QUERY_ENGINE_URL", "http://query-engine:8004"
    )
    ANOMALY_SERVICE_URL: str = os.getenv(
        "ANOMALY_SERVICE_URL", "http://anomaly-detection:8003"
    )

    # ── PostgreSQL ────────────────────────────────────────────────────
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "logsentry")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "logsentry")
    POSTGRES_PASSWORD: str = os.getenv(
        "POSTGRES_PASSWORD", "logsentry_secret_2024"
    )

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD", None) or None
    REDIS_PUBSUB_CHANNEL: str = os.getenv(
        "REDIS_PUBSUB_CHANNEL", "logs:realtime"
    )

    # ── General ───────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = "api-gateway"
    API_VERSION: str = "1.0.0"


settings = Settings()
