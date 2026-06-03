"""
LogSentry - Feature engineering for anomaly detection.
"""

import numpy as np
import logging

logger = logging.getLogger("feature-extractor")


class FeatureExtractor:
    """Extracts numerical features from log data for ML models."""

    FEATURE_NAMES = [
        "log_count",
        "error_count",
        "fatal_count",
        "warn_count",
        "error_rate",
        "unique_errors",
        "avg_msg_length",
        "unique_hosts",
    ]

    def extract_from_rows(self, rows) -> tuple[np.ndarray, list[str]]:
        """
        Extract features from database query rows.
        Each row is an hourly aggregation per service.
        Returns (features_array, feature_names).
        """
        features = []

        for row in rows:
            log_count = row["log_count"] or 0
            error_count = row["error_count"] or 0
            fatal_count = row["fatal_count"] or 0
            warn_count = row["warn_count"] or 0
            error_rate = (error_count + fatal_count) / max(log_count, 1) * 100
            unique_errors = row["unique_errors"] or 0
            avg_msg_length = row["avg_msg_length"] or 0
            unique_hosts = row["unique_hosts"] or 0

            features.append([
                log_count,
                error_count,
                fatal_count,
                warn_count,
                error_rate,
                unique_errors,
                float(avg_msg_length),
                unique_hosts,
            ])

        return np.array(features, dtype=np.float64), self.FEATURE_NAMES

    def extract_realtime_features(self, metrics: dict) -> np.ndarray:
        """
        Extract features from real-time Redis metrics.
        Returns a single feature vector.
        """
        log_count = metrics.get("log_count", 0)
        error_count = metrics.get("error_count", 0)
        fatal_count = metrics.get("fatal_count", 0)
        warn_count = metrics.get("warn_count", 0)
        error_rate = (error_count + fatal_count) / max(log_count, 1) * 100

        return np.array([[
            log_count,
            error_count,
            fatal_count,
            warn_count,
            error_rate,
            metrics.get("unique_errors", 0),
            metrics.get("avg_msg_length", 100),
            metrics.get("unique_hosts", 1),
        ]], dtype=np.float64)

    def normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Simple min-max normalization."""
        mins = features.min(axis=0)
        maxs = features.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1
        return (features - mins) / ranges
