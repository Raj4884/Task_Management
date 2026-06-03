"""
LogSentry - Real-time anomaly scoring.
Periodically reads metrics from Redis, runs models, and stores results.
"""

import json
import uuid
import asyncio
import logging
from datetime import datetime

from app.features.extractor import FeatureExtractor

logger = logging.getLogger("realtime-scorer")


class RealtimeScorer:
    """Runs periodic anomaly scoring on live service metrics."""

    def __init__(self, trainer, redis, db_pool):
        self.trainer = trainer
        self.redis = redis
        self.db_pool = db_pool
        self.feature_extractor = FeatureExtractor()

    async def run_periodic_scoring(self, interval_seconds: int = 60):
        """Background task: periodically score all services."""
        # Wait for initial data
        await asyncio.sleep(30)

        while True:
            try:
                await self._score_all_services()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Scoring cycle error: {e}")

            await asyncio.sleep(interval_seconds)

    async def _score_all_services(self):
        """Score all active services using current metrics."""
        # Get active services from Redis
        services = await self.redis.hkeys("services:last_seen")
        if not services:
            return

        all_scores = {}
        now = datetime.utcnow()
        minute_key = now.strftime("%Y%m%d%H%M")

        for service in services:
            try:
                metrics = await self._get_service_metrics(service, minute_key)
                score_result = self._score_service(service, metrics)
                all_scores[service] = score_result

                # If anomaly detected, record it
                if score_result.get("is_anomaly"):
                    await self._record_anomaly(service, score_result)

            except Exception as e:
                logger.debug(f"Error scoring {service}: {e}")

        # Cache all scores in Redis
        if all_scores:
            await self.redis.setex(
                "anomaly:realtime:scores",
                120,
                json.dumps(all_scores, default=str),
            )

    async def _get_service_metrics(self, service: str, minute_key: str) -> dict:
        """Gather current metrics for a service from Redis counters."""
        pipe = self.redis.pipeline()
        pipe.get(f"logs:count:{service}:{minute_key}")
        pipe.get(f"logs:errors:{service}:{minute_key}")
        results = await pipe.execute()

        return {
            "log_count": int(results[0]) if results[0] else 0,
            "error_count": int(results[1]) if results[1] else 0,
            "fatal_count": 0,
            "warn_count": 0,
            "unique_errors": 0,
            "avg_msg_length": 100,
            "unique_hosts": 1,
        }

    def _score_service(self, service: str, metrics: dict) -> dict:
        """Run all models on a service's metrics."""
        result = {
            "service": service,
            "timestamp": datetime.utcnow().isoformat(),
            "is_anomaly": False,
            "combined_score": 0.0,
            "scores": {},
        }

        # Isolation Forest scoring
        if self.trainer.isolation_model.is_trained:
            features = self.feature_extractor.extract_realtime_features(metrics)
            if_scores = self.trainer.isolation_model.score(features)
            if_score = float(if_scores[0])
            # Convert to 0-1 (lower decision function = more anomalous)
            normalized_if = max(0, min(1, 0.5 - if_score))
            result["scores"]["isolation_forest"] = normalized_if

            if if_scores[0] < -0.1:
                result["is_anomaly"] = True

        # Statistical scoring
        stat = self.trainer.statistical_detector
        if metrics["log_count"] > 0:
            error_rate = metrics["error_count"] / max(metrics["log_count"], 1) * 100
            is_spike = stat.detect_spike(error_rate, [5.0, 8.0, 3.0, 6.0, 4.0])
            if is_spike:
                result["scores"]["statistical_spike"] = 0.8
                result["is_anomaly"] = True
            else:
                result["scores"]["statistical_spike"] = 0.1

        # Combine scores
        scores = list(result["scores"].values())
        if scores:
            result["combined_score"] = round(sum(scores) / len(scores), 3)

        return result

    async def _record_anomaly(self, service: str, score_result: dict):
        """Insert a detected anomaly into the database."""
        try:
            # Check cooldown
            cooldown_key = f"anomaly:cooldown:{service}"
            if await self.redis.exists(cooldown_key):
                return

            # Determine type
            anomaly_type = "volume_anomaly"
            if score_result["scores"].get("statistical_spike", 0) > 0.5:
                anomaly_type = "error_spike"

            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO anomalies 
                        (id, anomaly_type, service_name, severity_score, description, 
                         features, model_name, model_version)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                    """,
                    str(uuid.uuid4()),
                    anomaly_type,
                    service,
                    score_result["combined_score"],
                    f"Anomaly detected on {service}: combined score {score_result['combined_score']:.3f}",
                    json.dumps(score_result["scores"]),
                    "ensemble",
                    "1.0",
                )

            # Set cooldown (5 minutes)
            await self.redis.setex(cooldown_key, 300, "1")

            # Publish alert
            await self.redis.publish("alerts:realtime", json.dumps({
                "type": "anomaly",
                "service": service,
                "score": score_result["combined_score"],
                "anomaly_type": anomaly_type,
            }))

            logger.warning(f"Anomaly recorded for {service}: score={score_result['combined_score']:.3f}")

        except Exception as e:
            logger.error(f"Error recording anomaly: {e}")
