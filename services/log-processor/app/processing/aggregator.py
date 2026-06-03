"""
LogSentry - Real-time metrics aggregation using Redis.
Maintains rolling counters for log volume and error rates.
"""

import logging
from datetime import datetime

logger = logging.getLogger("aggregator")


async def update_counters(redis, entry: dict):
    """
    Update real-time metric counters in Redis for a processed log entry.
    
    Maintains per-service, per-minute counters with auto-expiry.
    """
    try:
        service = entry.get("service_name", "unknown")
        level = entry.get("level", "INFO")
        now = datetime.utcnow()
        minute_key = now.strftime("%Y%m%d%H%M")
        hour_key = now.strftime("%Y%m%d%H")

        pipe = redis.pipeline()

        # Per-service per-minute log count
        count_key = f"logs:count:{service}:{minute_key}"
        pipe.incr(count_key)
        pipe.expire(count_key, 3600)  # 1 hour TTL

        # Per-service per-minute error count
        if level in ("ERROR", "FATAL"):
            error_key = f"logs:errors:{service}:{minute_key}"
            pipe.incr(error_key)
            pipe.expire(error_key, 3600)

        # Per-service level distribution (hourly)
        level_key = f"logs:levels:{service}:{hour_key}"
        pipe.hincrby(level_key, level, 1)
        pipe.expire(level_key, 86400)  # 24 hour TTL

        # Global counters
        global_count_key = f"logs:count:_global:{minute_key}"
        pipe.incr(global_count_key)
        pipe.expire(global_count_key, 3600)

        if level in ("ERROR", "FATAL"):
            global_error_key = f"logs:errors:_global:{minute_key}"
            pipe.incr(global_error_key)
            pipe.expire(global_error_key, 3600)

        # Service last seen
        pipe.hset("services:last_seen", service, now.isoformat())

        # Active services set (hourly)
        active_key = f"services:active:{hour_key}"
        pipe.sadd(active_key, service)
        pipe.expire(active_key, 86400)

        await pipe.execute()

    except Exception as e:
        logger.debug(f"Error updating counters: {e}")


async def get_current_rate(redis, service: str = "_global") -> float:
    """Calculate current logs/sec rate from the last minute's counter."""
    try:
        now = datetime.utcnow()
        minute_key = now.strftime("%Y%m%d%H%M")
        count_key = f"logs:count:{service}:{minute_key}"
        count = await redis.get(count_key)
        if count:
            elapsed_seconds = now.second or 1
            return int(count) / elapsed_seconds
        return 0.0
    except Exception:
        return 0.0


async def get_error_rate(redis, service: str, minutes: int = 5) -> float:
    """Calculate error rate percentage over the last N minutes."""
    try:
        now = datetime.utcnow()
        total_logs = 0
        total_errors = 0

        for i in range(minutes):
            ts = datetime.utcfromtimestamp(now.timestamp() - i * 60)
            minute_key = ts.strftime("%Y%m%d%H%M")

            count = await redis.get(f"logs:count:{service}:{minute_key}")
            errors = await redis.get(f"logs:errors:{service}:{minute_key}")

            total_logs += int(count) if count else 0
            total_errors += int(errors) if errors else 0

        if total_logs == 0:
            return 0.0
        return round((total_errors / total_logs) * 100, 2)
    except Exception:
        return 0.0


async def get_level_distribution(redis, service: str) -> dict:
    """Get log level distribution for a service in the current hour."""
    try:
        now = datetime.utcnow()
        hour_key = now.strftime("%Y%m%d%H")
        level_key = f"logs:levels:{service}:{hour_key}"
        distribution = await redis.hgetall(level_key)
        return {k: int(v) for k, v in distribution.items()} if distribution else {}
    except Exception:
        return {}
