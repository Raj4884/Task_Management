"""
LogSentry Query Engine - Service Health Analytics.

Queries the mv_service_health materialized view and provides detailed
per-service diagnostics.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("query-engine.service_health")


def calculate_health_status(error_rate_pct: float, total_logs: int) -> str:
    """Determine service health status based on error rate thresholds.

    Args:
        error_rate_pct: Error rate as a percentage.
        total_logs: Total log count in the window.

    Returns:
        Status string: 'active', 'degraded', or 'down'.
    """
    if total_logs == 0:
        return "down"
    if error_rate_pct >= 25.0:
        return "down"
    if error_rate_pct >= 5.0:
        return "degraded"
    return "active"


async def get_all_services_health(pool) -> list[dict]:
    """Query mv_service_health for all services.

    Args:
        pool: asyncpg connection pool.

    Returns:
        List of ServiceHealthResponse-compatible dictionaries.
    """
    sql = """
        SELECT
            service_name,
            total_logs_24h,
            errors_24h,
            fatals_24h,
            warns_24h,
            error_rate_pct,
            first_log,
            last_log,
            unique_errors
        FROM mv_service_health
        ORDER BY error_rate_pct DESC
    """

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
    except Exception as exc:
        logger.error("Service health query failed: %s", exc)
        raise

    results = []
    for row in rows:
        error_rate = float(row["error_rate_pct"] or 0)
        total = int(row["total_logs_24h"] or 0)
        status = calculate_health_status(error_rate, total)

        results.append({
            "service_name": row["service_name"],
            "total_logs_24h": total,
            "errors_24h": int(row["errors_24h"] or 0),
            "fatals_24h": int(row["fatals_24h"] or 0),
            "warns_24h": int(row["warns_24h"] or 0),
            "error_rate_pct": error_rate,
            "first_log": row["first_log"].isoformat() if row["first_log"] else None,
            "last_log": row["last_log"].isoformat() if row["last_log"] else None,
            "unique_errors": int(row["unique_errors"] or 0),
            "status": status,
        })

    return results


async def get_service_detail(pool, name: str) -> dict:
    """Get detailed diagnostics for a single service.

    Includes recent errors, log volume trend, and top error patterns.

    Args:
        pool: asyncpg connection pool.
        name: Service name.

    Returns:
        Dictionary with service details, recent errors, volume trend, and
        top error messages.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    # Fetch health summary
    health_sql = """
        SELECT
            service_name,
            total_logs_24h,
            errors_24h,
            fatals_24h,
            warns_24h,
            error_rate_pct,
            first_log,
            last_log,
            unique_errors
        FROM mv_service_health
        WHERE service_name = $1
    """

    # Recent errors (last 50)
    errors_sql = """
        SELECT id, timestamp, level, message, error_fingerprint, trace_id
        FROM log_entries
        WHERE service_name = $1
          AND level IN ('ERROR', 'FATAL')
          AND timestamp >= $2
        ORDER BY timestamp DESC
        LIMIT 50
    """

    # Hourly volume trend
    volume_sql = """
        SELECT
            date_trunc('hour', timestamp) AS hour,
            COUNT(*) AS count
        FROM log_entries
        WHERE service_name = $1
          AND timestamp >= $2
        GROUP BY hour
        ORDER BY hour ASC
    """

    # Top error messages
    top_errors_sql = """
        SELECT
            COALESCE(error_fingerprint, left(message, 100)) AS pattern,
            COUNT(*) AS occurrences,
            MAX(timestamp) AS last_seen,
            MIN(timestamp) AS first_seen
        FROM log_entries
        WHERE service_name = $1
          AND level IN ('ERROR', 'FATAL')
          AND timestamp >= $2
        GROUP BY pattern
        ORDER BY occurrences DESC
        LIMIT 10
    """

    try:
        async with pool.acquire() as conn:
            health_row = await conn.fetchrow(health_sql, name)
            error_rows = await conn.fetch(errors_sql, name, day_ago)
            volume_rows = await conn.fetch(volume_sql, name, day_ago)
            top_error_rows = await conn.fetch(top_errors_sql, name, day_ago)
    except Exception as exc:
        logger.error("Service detail query for '%s' failed: %s", name, exc)
        raise

    if not health_row:
        return {"service_name": name, "status": "unknown", "message": "Service not found"}

    error_rate = float(health_row["error_rate_pct"] or 0)
    total = int(health_row["total_logs_24h"] or 0)
    status = calculate_health_status(error_rate, total)

    recent_errors = [
        {
            "id": row["id"],
            "timestamp": row["timestamp"].isoformat(),
            "level": row["level"],
            "message": row["message"],
            "error_fingerprint": row["error_fingerprint"],
            "trace_id": row["trace_id"],
        }
        for row in error_rows
    ]

    volume_trend = [
        {"timestamp": row["hour"].isoformat(), "count": row["count"]}
        for row in volume_rows
    ]

    top_errors = [
        {
            "pattern": row["pattern"],
            "occurrences": row["occurrences"],
            "last_seen": row["last_seen"].isoformat(),
            "first_seen": row["first_seen"].isoformat(),
        }
        for row in top_error_rows
    ]

    return {
        "service_name": name,
        "status": status,
        "total_logs_24h": total,
        "errors_24h": int(health_row["errors_24h"] or 0),
        "fatals_24h": int(health_row["fatals_24h"] or 0),
        "warns_24h": int(health_row["warns_24h"] or 0),
        "error_rate_pct": error_rate,
        "unique_errors": int(health_row["unique_errors"] or 0),
        "recent_errors": recent_errors,
        "volume_trend": volume_trend,
        "top_errors": top_errors,
    }
