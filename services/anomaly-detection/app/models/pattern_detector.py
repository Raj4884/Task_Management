"""
LogSentry - Log pattern analysis using TF-IDF and DBSCAN clustering.
Detects novel log patterns that don't match known clusters.
"""

import logging
import os
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
import joblib

logger = logging.getLogger("pattern-detector")

MODEL_DIR = "/app/models"


class PatternDetector:
    """TF-IDF + DBSCAN based log pattern analysis."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
        )
        self.cluster_model = None
        self.cluster_centers = None
        self.cluster_labels = None
        self.fitted_vectors = None
        self.representative_messages = {}
        self.trained = False

    def _preprocess(self, message: str) -> str:
        """Normalize log message for vectorization."""
        msg = message.lower()
        msg = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', msg)
        msg = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<ip>', msg)
        msg = re.sub(r'\b\d{4,}\b', '<num>', msg)
        msg = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<ts>', msg)
        msg = re.sub(r'[0-9a-f]{8,}', '<hex>', msg)
        return msg.strip()

    def fit(self, messages: list[str]):
        """Fit TF-IDF vectorizer and DBSCAN clustering on log messages."""
        if len(messages) < 10:
            logger.warning("Not enough messages to train pattern detector")
            return

        processed = [self._preprocess(m) for m in messages]

        # Fit TF-IDF
        self.fitted_vectors = self.vectorizer.fit_transform(processed)

        # Cluster with DBSCAN
        self.cluster_model = DBSCAN(
            eps=0.5, min_samples=3, metric="cosine", n_jobs=-1
        )
        self.cluster_labels = self.cluster_model.fit_predict(self.fitted_vectors)

        # Compute cluster centers and representative messages
        unique_labels = set(self.cluster_labels)
        self.cluster_centers = {}
        self.representative_messages = {}

        for label in unique_labels:
            if label == -1:
                continue
            mask = self.cluster_labels == label
            cluster_vectors = self.fitted_vectors[mask]
            center = cluster_vectors.mean(axis=0)
            self.cluster_centers[label] = np.asarray(center)

            # Find most representative message
            indices = np.where(mask)[0]
            similarities = cosine_similarity(cluster_vectors, center.reshape(1, -1)).flatten()
            best_idx = indices[np.argmax(similarities)]
            self.representative_messages[label] = messages[best_idx][:200]

        self.trained = True
        n_clusters = len([l for l in unique_labels if l != -1])
        n_noise = np.sum(self.cluster_labels == -1)
        logger.info(f"Pattern detector: {n_clusters} clusters, {n_noise} noise points from {len(messages)} messages")

    def detect_novel(self, message: str) -> tuple[bool, float]:
        """
        Check if a message is novel (doesn't match known clusters).
        Returns (is_novel, max_similarity_score).
        """
        if not self.trained or not self.cluster_centers:
            return False, 0.0

        processed = self._preprocess(message)
        try:
            vector = self.vectorizer.transform([processed])
        except Exception:
            return False, 0.0

        max_similarity = 0.0
        for label, center in self.cluster_centers.items():
            sim = cosine_similarity(vector, center.reshape(1, -1))[0][0]
            max_similarity = max(max_similarity, sim)

        # Novel if max similarity is below threshold
        is_novel = max_similarity < 0.3
        return is_novel, float(max_similarity)

    def get_clusters(self) -> list[dict]:
        """Return discovered log pattern clusters."""
        clusters = []
        for label, rep_msg in self.representative_messages.items():
            count = int(np.sum(self.cluster_labels == label)) if self.cluster_labels is not None else 0
            clusters.append({
                "cluster_id": int(label),
                "representative_message": rep_msg,
                "count": count,
            })
        return sorted(clusters, key=lambda x: x["count"], reverse=True)

    def save(self, name: str = "pattern_detector"):
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"{name}.joblib")
        joblib.dump({
            "vectorizer": self.vectorizer,
            "cluster_model": self.cluster_model,
            "cluster_centers": self.cluster_centers,
            "cluster_labels": self.cluster_labels,
            "representative_messages": self.representative_messages,
            "trained": self.trained,
        }, path)

    def load(self, name: str = "pattern_detector"):
        path = os.path.join(MODEL_DIR, f"{name}.joblib")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}")
        data = joblib.load(path)
        self.vectorizer = data["vectorizer"]
        self.cluster_model = data["cluster_model"]
        self.cluster_centers = data["cluster_centers"]
        self.cluster_labels = data["cluster_labels"]
        self.representative_messages = data["representative_messages"]
        self.trained = data["trained"]
