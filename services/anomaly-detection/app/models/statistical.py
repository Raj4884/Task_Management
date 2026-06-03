"""
LogSentry - Statistical anomaly detection methods.
Z-score, moving average, EWMA, and spike detection.
"""

import numpy as np
import logging

logger = logging.getLogger("statistical")


class StatisticalDetector:
    """Statistical methods for time-series anomaly detection."""

    def z_score_detect(self, values: np.ndarray, threshold: float = 3.0) -> np.ndarray:
        """
        Z-score based anomaly detection.
        Returns boolean array: True where anomaly detected.
        """
        if len(values) < 3:
            return np.zeros(len(values), dtype=bool)

        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return np.zeros(len(values), dtype=bool)

        z_scores = np.abs((values - mean) / std)
        return z_scores > threshold

    def moving_average_detect(
        self, values: np.ndarray, window: int = 10, threshold: float = 2.0
    ) -> np.ndarray:
        """
        Moving average anomaly detection.
        Flags values outside moving_avg ± threshold * moving_std.
        """
        if len(values) < window:
            return np.zeros(len(values), dtype=bool)

        anomalies = np.zeros(len(values), dtype=bool)

        for i in range(window, len(values)):
            window_data = values[i - window : i]
            avg = np.mean(window_data)
            std = np.std(window_data)

            if std > 0 and abs(values[i] - avg) > threshold * std:
                anomalies[i] = True

        return anomalies

    def ewma_detect(
        self, values: np.ndarray, span: int = 10, threshold: float = 2.5
    ) -> np.ndarray:
        """
        Exponential Weighted Moving Average anomaly detection.
        More responsive to recent changes than simple moving average.
        """
        if len(values) < 3:
            return np.zeros(len(values), dtype=bool)

        alpha = 2.0 / (span + 1)
        anomalies = np.zeros(len(values), dtype=bool)

        ewma = values[0]
        ewma_var = 0.0

        for i in range(1, len(values)):
            diff = values[i] - ewma
            ewma = alpha * values[i] + (1 - alpha) * ewma
            ewma_var = alpha * diff**2 + (1 - alpha) * ewma_var
            ewma_std = np.sqrt(ewma_var)

            if ewma_std > 0 and abs(diff) > threshold * ewma_std:
                anomalies[i] = True

        return anomalies

    def detect_spike(
        self, current: float, historical: list[float], multiplier: float = 3.0
    ) -> bool:
        """
        Simple spike detection: is current value > multiplier * historical average?
        """
        if not historical:
            return False

        avg = np.mean(historical)
        std = np.std(historical) if len(historical) > 1 else avg * 0.1

        if std == 0:
            return current > avg * multiplier

        return current > avg + multiplier * std

    def detect_drop(
        self, current: float, historical: list[float], multiplier: float = 3.0
    ) -> bool:
        """Detect sudden drops (inverse of spike)."""
        if not historical:
            return False

        avg = np.mean(historical)
        std = np.std(historical) if len(historical) > 1 else avg * 0.1

        if std == 0:
            return current < avg / max(multiplier, 1)

        return current < avg - multiplier * std

    def compute_anomaly_score(self, current: float, historical: list[float]) -> float:
        """
        Compute a normalized anomaly score (0 = normal, 1 = highly anomalous).
        """
        if not historical or len(historical) < 2:
            return 0.0

        mean = np.mean(historical)
        std = np.std(historical)

        if std == 0:
            return 0.0 if current == mean else min(abs(current - mean) / max(mean, 1), 1.0)

        z = abs(current - mean) / std
        # Sigmoid-like mapping: z=3 -> ~0.95, z=1 -> ~0.26
        score = 1.0 - 1.0 / (1.0 + 0.1 * z**2)
        return min(score, 1.0)
