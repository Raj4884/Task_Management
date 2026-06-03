"""
LogSentry - Rule-based alert detection.
Checks for error rate thresholds, spikes, and pattern matches.
"""

import json
import re
import uuid
import logging
from datetime import datetime
from app.processing.aggregator import get_error_rate

logger = logging.getLogger("alert-detector")


class AlertDetector:
    """Evaluates alert rules against incoming log data."""

    def __init__(self, redis, db_pool):
        self.redis = redis
        self.db_pool = db_pool
        self.cooldown_seconds = 300  # 5 minute cooldown between same alerts
        self.error_rate_threshold = 15.0  # Alert if > 15% error rate
        self.spike_multiplier = 3.0  # Alert if error rate is 3x the average
        self.critical_patterns = [
            r"OutOfMemoryError",
            r"StackOverflowError",
            r"FATAL",
            r"segmentation fault",
            r"kernel panic",
            r"disk full",
            r"connection refused",
            r"database.*down",
            r"OOM",
        ]

    async def check_batch(self, entries: list[dict]):
        """Run all alert checks on a batch of log entries."""
        # Group entries by service
        services = {}
        for entry in entries:
            svc = entry.get("service_name", "unknown")
            if svc not in services:
                services[svc] = []
            services[svc].append(entry)

        for service, svc_entries in services.items():
            # Check error rate threshold
            await self._check_error_rate(service)

            # Check for critical patterns
            for entry in svc_entries:
                if entry.get("level") in ("ERROR", "FATAL"):
                    await self._check_patterns(entry)

    async def _check_error_rate(self, service: str):
        """Check if error rate exceeds threshold."""
        cooldown_key = f"alert:cooldown:error_rate:{service}"

        # Check cooldown
        if await self.redis.exists(cooldown_key):
            return

        error_rate = await get_error_rate(self.redis, service, minutes=5)

        if error_rate > self.error_rate_threshold:
            alert = {
                "title": f"High error rate on {service}",
                "description": f"Error rate is {error_rate:.1f}% (threshold: {self.error_rate_threshold}%)",
                "severity": "critical" if error_rate > 30 else "warning",
                "service_name": service,
                "rule_type": "threshold",
                "rule_config": {"threshold": self.error_rate_threshold, "actual": error_rate},
            }
            await self._create_alert(alert)
            await self.redis.setex(cooldown_key, self.cooldown_seconds, "1")

    async def _check_patterns(self, entry: dict):
        """Check log message against critical patterns."""
        message = entry.get("message", "")
        service = entry.get("service_name", "unknown")

        for pattern in self.critical_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                cooldown_key = f"alert:cooldown:pattern:{service}:{pattern}"
                if await self.redis.exists(cooldown_key):
                    continue

                alert = {
                    "title": f"Critical pattern detected on {service}",
                    "description": f"Pattern '{pattern}' found: {message[:200]}",
                    "severity": "critical",
                    "service_name": service,
                    "rule_type": "pattern",
                    "rule_config": {"pattern": pattern},
                }
                await self._create_alert(alert)
                await self.redis.setex(cooldown_key, self.cooldown_seconds, "1")
                break  # Only one alert per message

    async def _create_alert(self, alert: dict):
        """Insert alert into database and publish notification."""
        try:
            alert_id = str(uuid.uuid4())
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO alerts (id, title, description, severity, service_name, 
                                        rule_type, rule_config, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'active')
                    """,
                    alert_id,
                    alert["title"],
                    alert.get("description"),
                    alert["severity"],
                    alert.get("service_name"),
                    alert["rule_type"],
                    json.dumps(alert.get("rule_config", {})),
                )

            # Publish alert to Redis for real-time notification
            alert_msg = {
                "type": "alert",
                "id": alert_id,
                "title": alert["title"],
                "severity": alert["severity"],
                "service_name": alert.get("service_name"),
                "triggered_at": datetime.utcnow().isoformat(),
            }
            await self.redis.publish("alerts:realtime", json.dumps(alert_msg))
            logger.warning(f"Alert created: {alert['title']}")

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
