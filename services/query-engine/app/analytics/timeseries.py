"""
LogSentry Query Engine - Time Series Analytics.

Provides bucketed log volume and error rate calculations with Redis caching.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone

from app.search.filters import validate_interval

logger = logging.getLogger("query-engine.timeseries")

# Cache TTL in seconds
CACHE_TTL = 60


def _cache_key(prefix: str, **kwargs) -> str:
    """Generate a deterministic Redis cache key from parameters."""
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"qe:cache:{prefix}:{digest}"


async def get_log_volume(
    pool,
    redis,
    service: str | None,
    level: str | None,
    interval: str,
    start: datetime,
    end: datetime,
) -> dict:
    """Get log volume bucketed by time interval.

    Uses ``date_trunc`` and GROUP BY for efficient bucketed counts.
    Results are cached in Redis with a 60-second TTL.

    Args:
        pool: asyncpg connection pool.
        redis: Redis connection for caching.
        service: Optional service name filter.
        level: Optional log level filter.
        interval: Time bucket interval (e.g. '1m', '5m', '1h', '1d').
        start: Start of the time range.
        end: End of the time range.

    Returns:
        Dictionary with metric name, interval, data points, total, and average.
    """
    pg_interval = validate_interval(interval)

    # Check cache
    cache_params = dict(
        service=service, level=level, interval=interval,
        start=str(start), end=str(end),
    )
    ck = _cache_key("volume", **cache_params)

    if redis:
        try:
            cached = await redis.get(ck)
            if cached:
                logger.debug("Cache hit for log volume: %s", ck)
                return json.loads(cached)
        except Exception:
            pass

    # Build query
    conditions = ["timestamp >= $1", "timestamp <= $2"]
    params: list = [start, end]
    idx = 3

    if service:
        conditions.append(f"service_name = ${idx}")
        params.append(service)
        idx += 1

    if level:
        conditions.append(f"level = ${idx}")
        params.append(level.upper())
        idx += 1

    where = " AND ".join(conditions)

    sql = f"""
        SELECT
            date_trunc('{pg_interval.split()[1] if ' ' in pg_interval else pg_interval}', timestamp) AS bucket,
            COUNT(*) AS count
        FROM log_entries
        WHERE {where}
        GROUP BY bucket
        ORDER BY bucket ASC
    """

    # date_trunc needs a valid field – extract it properly
    # Map interval to PostgreSQL date_trunc precision
    trunc_map = {
        "1m": "minute", "5m": "minute", "15m": "minute",
        "1h": "hour", "6h": "hour", "1d": "day",
    }
    precision = trunc_map.get(interval, "hour")

    # For non-1-unit intervals, use date_bin instead (PG 14+)
    if interval in ("5m", "15m", "6h"):
        sql = f"""
            SELECT
                date_bin('{pg_interval}'::interval, timestamp, $1) AS bucket,
                COUNT(*) AS count
            FROM log_entries
            WHERE {where}
            GROUP BY bucket
            ORDER BY bucket ASC
        """
    else:
        sql = f"""
            SELECT
                date_trunc('{precision}', timestamp) AS bucket,
                COUNT(*) AS count
            FROM log_entries
            WHERE {where}
            GROUP BY bucket
            ORDER BY bucket ASC
        """

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception as exc:
        logger.error("Log volume query failed: %s", exc)
        raise

    data = [
        {"timestamp": row["bucket"].isoformat(), "value": float(row["count"]), "label": None}
        for row in rows
    ]
    total = sum(point["value"] for point in data)
    average = total / len(data) if data else 0.0

    result = {
        "metric": "log_volume",
        "interval": interval,
        "data": data,
        "total": total,
        "average": round(average, 2),
    }

    # Cache result
    if redis:
        try:
            await redis.setex(ck, CACHE_TTL, json.dumps(result, default=str))
        except Exception:
            pass

    return result


async def get_error_rate(
    pool,
    redis,
    service: str | None,
    interval: str,
    start: datetime,
    end: datetime,
) -> dict:
    """Get error rate percentage bucketed by time interval.

    Calculates ``error_count / total_count * 100`` per time bucket.

    Args:
        pool: asyncpg connection pool.
        redis: Redis connection for caching.
        service: Optional service name filter.
        interval: Time bucket interval.
        start: Start of the time range.
        end: End of the time range.

    Returns:
        Dictionary with metric name, interval, data points, total, and average.
    """
    pg_interval = validate_interval(interval)

    cache_params = dict(service=service, interval=interval, start=str(start), end=str(end))
    ck = _cache_key("error_rate", **cache_params)

    if redis:
        try:
            cached = await redis.get(ck)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    conditions = ["timestamp >= $1", "timestamp <= $2"]
    params: list = [start, end]
    idx = 3

    if service:
        conditions.append(f"service_name = ${idx}")
        params.append(service)
        idx += 1

    where = " AND ".join(conditions)

    trunc_map = {
        "1m": "minute", "5m": "minute", "15m": "minute",
        "1h": "hour", "6h": "hour", "1d": "day",
    }
    precision = trunc_map.get(interval, "hour")

    if interval in ("5m", "15m", "6h"):
        bucket_expr = f"date_bin('{pg_interval}'::interval, timestamp, $1)"
    else:
        bucket_expr = f"date_trunc('{precision}', timestamp)"

    sql = f"""
        SELECT
            {bucket_expr} AS bucket,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL')) AS errors
        FROM log_entries
        WHERE {where}
        GROUP BY bucket
        ORDER BY bucket ASC
    """

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception as exc:
        logger.error("Error rate query failed: %s", exc)
        raise

    data = []
    total_errors = 0.0
    for row in rows:
        total_count = row["total"]
        error_count = row["errors"]
        rate = (error_count / total_count * 100) if total_count > 0 else 0.0
        total_errors += rate
        data.append({
            "timestamp": row["bucket"].isoformat(),
            "value": round(rate, 2),
            "label": f"{error_count}/{total_count}",
        })

    average = total_errors / len(data) if data else 0.0

    result = {
        "metric": "error_rate",
        "interval": interval,
        "data": data,
        "total": round(total_errors, 2),
        "average": round(average, 2),
    }

    if redis:
        try:
            await redis.setex(ck, CACHE_TTL, json.dumps(result, default=str))
        except Exception:
            pass

    return result
