"""
LogSentry - Isolation Forest anomaly detection model.
"""

import logging
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
import os

logger = logging.getLogger("isolation-forest")

MODEL_DIR = "/app/models"


class IsolationForestModel:
    """Isolation Forest for multivariate anomaly detection on service metrics."""

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.model = None
        self.feature_names = []
        self.trained_at = None
        self.version = "1.0"

    @property
    def is_trained(self) -> bool:
        return self.model is not None

    def train(self, features: np.ndarray, feature_names: list[str]):
        """
        Train the Isolation Forest model.
        
        Args:
            features: 2D array of shape (n_samples, n_features)
            feature_names: List of feature names
        """
        if len(features) < 10:
            logger.warning("Not enough data to train (need at least 10 samples)")
            return

        self.feature_names = feature_names
        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(features)
        
        from datetime import datetime
        self.trained_at = datetime.utcnow().isoformat()
        logger.info(f"Trained Isolation Forest on {len(features)} samples with {len(feature_names)} features")

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        Predict anomalies. Returns array of -1 (anomaly) or 1 (normal).
        """
        if not self.is_trained:
            return np.ones(len(features))
        return self.model.predict(features)

    def score(self, features: np.ndarray) -> np.ndarray:
        """
        Return continuous anomaly scores (lower = more anomalous).
        Scores are typically between -0.5 (anomaly) and 0.5 (normal).
        """
        if not self.is_trained:
            return np.zeros(len(features))
        return self.model.decision_function(features)

    def save(self, name: str = "isolation_forest"):
        """Save model to disk."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"{name}.joblib")
        data = {
            "model": self.model,
            "feature_names": self.feature_names,
            "trained_at": self.trained_at,
            "version": self.version,
            "contamination": self.contamination,
        }
        joblib.dump(data, path)
        logger.info(f"Model saved to {path}")

    def load(self, name: str = "isolation_forest"):
        """Load model from disk."""
        path = os.path.join(MODEL_DIR, f"{name}.joblib")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}")
        data = joblib.load(path)
        self.model = data["model"]
        self.feature_names = data["feature_names"]
        self.trained_at = data["trained_at"]
        self.version = data.get("version", "1.0")
        logger.info(f"Model loaded from {path}")

    def get_info(self) -> dict:
        """Return model metadata."""
        return {
            "model_name": "isolation_forest",
            "is_trained": self.is_trained,
            "trained_at": self.trained_at,
            "version": self.version,
            "contamination": self.contamination,
            "feature_names": self.feature_names,
            "n_estimators": 100,
        }
