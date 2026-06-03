"""
LogSentry Anomaly Detection - Configuration.

Loads database, Redis, and ML-specific settings from environment variables.
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
class MLConfig:
    """Machine learning model configuration."""

    # Isolation Forest
    contamination: float = field(
        default_factory=lambda: float(os.getenv("ANOMALY_CONTAMINATION", "0.05"))
    )
    n_estimators: int = 100
    random_state: int = 42

    # Training schedule
    retrain_interval_hours: int = field(
        default_factory=lambda: int(os.getenv("ANOMALY_RETRAIN_INTERVAL_HOURS", "6"))
    )
    training_lookback_days: int = 7
    min_training_samples: int = 50

    # Scoring
    anomaly_window_minutes: int = field(
        default_factory=lambda: int(os.getenv("ANOMALY_WINDOW_MINUTES", "5"))
    )
    scoring_interval_seconds: int = 60

    # Statistical detection thresholds
    z_score_threshold: float = 3.0
    ewma_span: int = 10
    ewma_threshold: float = 2.5
    spike_multiplier: float = 3.0

    # Score combination weights
    isolation_forest_weight: float = 0.5
    statistical_weight: float = 0.3
    pattern_weight: float = 0.2

    # Model persistence
    models_dir: str = "/app/models"


@dataclass(frozen=True)
class ServiceConfig:
    """Anomaly Detection service configuration."""

    service_name: str = "anomaly-detection"
    port: int = 8003
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Singleton instances
db_config = DatabaseConfig()
redis_config = RedisConfig()
ml_config = MLConfig()
service_config = ServiceConfig()
