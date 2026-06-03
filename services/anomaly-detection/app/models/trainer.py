"""
LogSentry - Model training pipeline.
Orchestrates fetching data, extracting features, and training all ML models.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.models.isolation_forest import IsolationForestModel
from app.models.statistical import StatisticalDetector
from app.models.pattern_detector import PatternDetector
from app.features.extractor import FeatureExtractor

logger = logging.getLogger("trainer")


class ModelTrainer:
    """Orchestrates the ML model training pipeline."""

    def __init__(self, db_pool, redis):
        self.db_pool = db_pool
        self.redis = redis
        self.isolation_model = IsolationForestModel(contamination=0.05)
        self.statistical_detector = StatisticalDetector()
        self.pattern_detector = PatternDetector()
        self.feature_extractor = FeatureExtractor()
        self.last_trained = None

    def load_models(self):
        """Load pre-trained models from disk."""
        self.isolation_model.load()
        self.pattern_detector.load()

    async def train_all_models(self) -> dict:
        """
        Full training pipeline:
        1. Fetch last 7 days of log data
        2. Extract features
        3. Train Isolation Forest
        4. Train Pattern Detector
        5. Save models
        """
        logger.info("Starting model training pipeline...")
        results = {"status": "started", "models": {}}

        try:
            # Fetch aggregated log data
            async with self.db_pool.acquire() as conn:
                # Get windowed features for Isolation Forest
                rows = await conn.fetch("""
                    SELECT 
                        date_trunc('hour', timestamp) AS window,
                        service_name,
                        COUNT(*) AS log_count,
                        COUNT(*) FILTER (WHERE level = 'ERROR') AS error_count,
                        COUNT(*) FILTER (WHERE level = 'FATAL') AS fatal_count,
                        COUNT(*) FILTER (WHERE level = 'WARN') AS warn_count,
                        COUNT(DISTINCT error_fingerprint) AS unique_errors,
                        AVG(LENGTH(message)) AS avg_msg_length,
                        COUNT(DISTINCT host) AS unique_hosts
                    FROM log_entries
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    GROUP BY date_trunc('hour', timestamp), service_name
                    ORDER BY window
                """)

                if len(rows) >= 10:
                    features, feature_names = self.feature_extractor.extract_from_rows(rows)
                    self.isolation_model.train(features, feature_names)
                    self.isolation_model.save()
                    results["models"]["isolation_forest"] = {
                        "status": "trained",
                        "samples": len(features),
                        "features": feature_names,
                    }
                else:
                    results["models"]["isolation_forest"] = {
                        "status": "skipped",
                        "reason": f"Not enough data ({len(rows)} samples, need 10+)",
                    }

                # Get log messages for Pattern Detector
                messages = await conn.fetch("""
                    SELECT message FROM log_entries
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    AND level IN ('ERROR', 'FATAL', 'WARN')
                    ORDER BY RANDOM()
                    LIMIT 5000
                """)

                if len(messages) >= 10:
                    msg_list = [r["message"] for r in messages]
                    self.pattern_detector.fit(msg_list)
                    self.pattern_detector.save()
                    clusters = self.pattern_detector.get_clusters()
                    results["models"]["pattern_detector"] = {
                        "status": "trained",
                        "messages_analyzed": len(msg_list),
                        "clusters_found": len(clusters),
                    }
                else:
                    results["models"]["pattern_detector"] = {
                        "status": "skipped",
                        "reason": f"Not enough messages ({len(messages)})",
                    }

            self.last_trained = datetime.utcnow().isoformat()
            results["status"] = "completed"
            results["trained_at"] = self.last_trained

            # Cache training status in Redis
            import json
            await self.redis.setex(
                "anomaly:training:status",
                86400,
                json.dumps(results, default=str),
            )
            logger.info(f"Training pipeline completed: {results}")

        except Exception as e:
            logger.error(f"Training pipeline error: {e}")
            results["status"] = "error"
            results["error"] = str(e)

        return results

    async def schedule_periodic_training(self, interval_hours: int = 6):
        """Background task that retrains models periodically."""
        # Initial delay to let data accumulate
        await asyncio.sleep(120)  # Wait 2 minutes before first training

        while True:
            try:
                logger.info("Periodic model retraining triggered")
                await self.train_all_models()
            except Exception as e:
                logger.error(f"Periodic training error: {e}")

            await asyncio.sleep(interval_hours * 3600)
