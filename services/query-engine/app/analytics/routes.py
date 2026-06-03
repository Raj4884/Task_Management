"""
LogSentry - Analytics API routes.
Dashboard stats, time-series, service health, and alert management.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Query

logger = logging.getLogger("analytics-routes")

router = APIRouter(prefix="/analytics")


@router.get("/dashboard-stats")
async def dashboard_stats(request: Request):
    """Aggregated stats for the overview dashboard."""
    pool = request.app.state.db_pool
    redis = request.app.state.redis

    async with pool.acquire() as conn:
        # Total logs and errors in 24h
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) AS total_logs,
                COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL')) AS total_errors,
                ROUND(
                    (COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL'))::numeric / 
                    GREATEST(COUNT(*), 1) * 100), 2
                ) AS error_rate
            FROM log_entries 
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)

        # Active services count
        svc_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT service_name) 
            FROM log_entries 
            WHERE timestamp > NOW() - INTERVAL '1 hour'
        """)

        # Active alerts
        alert_count = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts WHERE status = 'active'"
        )

        # Anomalies in 24h
        anomaly_count = await conn.fetchval("""
            SELECT COUNT(*) FROM anomalies 
            WHERE detected_at > NOW() - INTERVAL '24 hours'
        """)

        # Top error services
        top_errors = await conn.fetch("""
            SELECT service_name, COUNT(*) AS error_count
            FROM log_entries
            WHERE level IN ('ERROR', 'FATAL') 
            AND timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY service_name
            ORDER BY error_count DESC
            LIMIT 5
        """)

    # Logs per second from Redis
    logs_per_sec = 0.0
    try:
        now = datetime.utcnow()
        minute_key = now.strftime("%Y%m%d%H%M")
        count = await redis.get(f"logs:count:_global:{minute_key}")
        if count:
            elapsed = now.second or 1
            logs_per_sec = round(int(count) / elapsed, 1)
    except Exception:
        pass

    return {
        "total_logs_24h": stats["total_logs"] if stats else 0,
        "total_errors_24h": stats["total_errors"] if stats else 0,
        "error_rate_pct": float(stats["error_rate"]) if stats else 0.0,
        "active_services": svc_count or 0,
        "active_alerts": alert_count or 0,
        "anomalies_detected": anomaly_count or 0,
        "logs_per_second": logs_per_sec,
        "top_error_services": [
            {"service_name": r["service_name"], "error_count": r["error_count"]}
            for r in (top_errors or [])
        ],
    }


@router.get("/timeseries")
async def timeseries(
    request: Request,
    service_name: Optional[str] = None,
    level: Optional[str] = None,
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|6h|1d)$"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """Log volume over time with configurable intervals."""
    pool = request.app.state.db_pool

    interval_map = {"1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes", "1h": "1 hour", "6h": "6 hours", "1d": "1 day"}
    pg_interval = interval_map[interval]

    # Default time range
    if not end_time:
        end = datetime.utcnow()
    else:
        end = datetime.fromisoformat(end_time)

    if not start_time:
        range_map = {"1m": 1, "5m": 6, "15m": 12, "1h": 24, "6h": 72, "1d": 168}
        start = end - timedelta(hours=range_map.get(interval, 24))
    else:
        start = datetime.fromisoformat(start_time)

    query = f"""
        SELECT date_trunc('{pg_interval.split()[1] if ' ' in pg_interval else pg_interval}', timestamp) AS bucket,
               COUNT(*) AS count
        FROM log_entries
        WHERE timestamp BETWEEN $1 AND $2
    """
    params = [start, end]
    idx = 3

    if service_name:
        query += f" AND service_name = ${idx}"
        params.append(service_name)
        idx += 1

    if level:
        query += f" AND level = ${idx}"
        params.append(level)
        idx += 1

    query += " GROUP BY bucket ORDER BY bucket ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    data = [{"timestamp": r["bucket"].isoformat(), "value": r["count"]} for r in rows]
    total = sum(r["count"] for r in rows)
    avg = total / max(len(rows), 1)

    return {
        "metric": "log_volume",
        "interval": interval,
        "data": data,
        "total": total,
        "average": round(avg, 2),
    }


@router.get("/error-rate")
async def error_rate_timeseries(
    request: Request,
    service_name: Optional[str] = None,
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|6h|1d)$"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """Error rate percentage over time."""
    pool = request.app.state.db_pool

    interval_map = {"1m": "minute", "5m": "minute", "15m": "minute", "1h": "hour", "6h": "hour", "1d": "day"}
    trunc_unit = interval_map[interval]

    end = datetime.fromisoformat(end_time) if end_time else datetime.utcnow()
    start = datetime.fromisoformat(start_time) if start_time else end - timedelta(hours=24)

    query = f"""
        SELECT date_trunc('{trunc_unit}', timestamp) AS bucket,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL')) AS errors,
               ROUND(
                   (COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL'))::numeric / 
                   GREATEST(COUNT(*), 1) * 100), 2
               ) AS error_rate
        FROM log_entries
        WHERE timestamp BETWEEN $1 AND $2
    """
    params = [start, end]
    idx = 3

    if service_name:
        query += f" AND service_name = ${idx}"
        params.append(service_name)
        idx += 1

    query += " GROUP BY bucket ORDER BY bucket ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    data = [{"timestamp": r["bucket"].isoformat(), "value": float(r["error_rate"]), "label": f"{r['errors']}/{r['total']}"} for r in rows]
    rates = [float(r["error_rate"]) for r in rows]

    return {
        "metric": "error_rate",
        "interval": interval,
        "data": data,
        "total": round(sum(rates), 2),
        "average": round(sum(rates) / max(len(rates), 1), 2),
    }


@router.get("/services")
async def list_services(request: Request):
    """List all services with health metrics."""
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        # Try materialized view first, fall back to direct query
        try:
            rows = await conn.fetch("SELECT * FROM mv_service_health ORDER BY error_rate_pct DESC")
        except Exception:
            rows = await conn.fetch("""
                SELECT service_name,
                    COUNT(*) AS total_logs_24h,
                    COUNT(*) FILTER (WHERE level = 'ERROR') AS errors_24h,
                    COUNT(*) FILTER (WHERE level = 'FATAL') AS fatals_24h,
                    COUNT(*) FILTER (WHERE level = 'WARN') AS warns_24h,
                    ROUND((COUNT(*) FILTER (WHERE level IN ('ERROR','FATAL'))::numeric / GREATEST(COUNT(*),1) * 100), 2) AS error_rate_pct,
                    MIN(timestamp) AS first_log,
                    MAX(timestamp) AS last_log,
                    COUNT(DISTINCT error_fingerprint) AS unique_errors
                FROM log_entries
                WHERE timestamp > NOW() - INTERVAL '24 hours'
                GROUP BY service_name
                ORDER BY error_rate_pct DESC
            """)

    return [
        {
            "service_name": r["service_name"],
            "total_logs_24h": r["total_logs_24h"],
            "errors_24h": r["errors_24h"],
            "fatals_24h": r["fatals_24h"],
            "warns_24h": r["warns_24h"],
            "error_rate_pct": float(r["error_rate_pct"]),
            "first_log": r["first_log"].isoformat() if r["first_log"] else None,
            "last_log": r["last_log"].isoformat() if r["last_log"] else None,
            "unique_errors": r["unique_errors"],
            "status": "down" if float(r["error_rate_pct"]) > 30 else "degraded" if float(r["error_rate_pct"]) > 10 else "active",
        }
        for r in rows
    ]


@router.get("/services/{name}")
async def service_detail(name: str, request: Request):
    """Detailed view of a specific service."""
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        # Recent errors
        errors = await conn.fetch("""
            SELECT timestamp, message, error_fingerprint, metadata
            FROM log_entries
            WHERE service_name = $1 AND level IN ('ERROR', 'FATAL')
            AND timestamp > NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC LIMIT 20
        """, name)

        # Hourly volume trend
        volume = await conn.fetch("""
            SELECT date_trunc('hour', timestamp) AS hour, 
                   COUNT(*) AS count,
                   COUNT(*) FILTER (WHERE level IN ('ERROR','FATAL')) AS errors
            FROM log_entries
            WHERE service_name = $1 AND timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY hour ORDER BY hour ASC
        """, name)

        # Top error patterns
        patterns = await conn.fetch("""
            SELECT error_fingerprint, 
                   MIN(message) AS sample_message,
                   COUNT(*) AS occurrences,
                   MAX(timestamp) AS last_seen
            FROM log_entries
            WHERE service_name = $1 AND error_fingerprint IS NOT NULL
            AND timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY error_fingerprint
            ORDER BY occurrences DESC LIMIT 10
        """, name)

    return {
        "service_name": name,
        "recent_errors": [
            {"timestamp": r["timestamp"].isoformat(), "message": r["message"][:300],
             "fingerprint": r["error_fingerprint"]}
            for r in errors
        ],
        "volume_trend": [
            {"hour": r["hour"].isoformat(), "count": r["count"], "errors": r["errors"]}
            for r in volume
        ],
        "top_error_patterns": [
            {"fingerprint": r["error_fingerprint"], "message": r["sample_message"][:200],
             "count": r["occurrences"], "last_seen": r["last_seen"].isoformat()}
            for r in patterns
        ],
    }


# ============================================
# Alert management routes
# ============================================

@router.get("/alerts")
async def list_alerts(
    request: Request,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    service_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List alerts with optional filtering."""
    pool = request.app.state.db_pool
    
    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    idx = 1

    if status:
        query += f" AND status = ${idx}"
        params.append(status)
        idx += 1
    if severity:
        query += f" AND severity = ${idx}"
        params.append(severity)
        idx += 1
    if service_name:
        query += f" AND service_name = ${idx}"
        params.append(service_name)
        idx += 1

    query += f" ORDER BY triggered_at DESC LIMIT ${idx}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [
        {
            "id": str(r["id"]),
            "title": r["title"],
            "description": r["description"],
            "severity": r["severity"],
            "service_name": r["service_name"],
            "rule_type": r["rule_type"],
            "rule_config": json.loads(r["rule_config"]) if isinstance(r["rule_config"], str) else (r["rule_config"] or {}),
            "status": r["status"],
            "triggered_at": r["triggered_at"].isoformat(),
            "acknowledged_at": r["acknowledged_at"].isoformat() if r["acknowledged_at"] else None,
            "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
        }
        for r in rows
    ]


@router.post("/alerts")
async def create_alert(request: Request):
    """Create a new alert."""
    pool = request.app.state.db_pool
    body = await request.json()
    import uuid

    alert_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO alerts (id, title, description, severity, service_name, rule_type, rule_config)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """,
            alert_id,
            body["title"],
            body.get("description"),
            body["severity"],
            body.get("service_name"),
            body["rule_type"],
            json.dumps(body.get("rule_config", {})),
        )

    return {"id": alert_id, "status": "created"}


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: Request):
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE alerts SET status = 'acknowledged', acknowledged_at = NOW() WHERE id = $1",
            alert_id,
        )
    return {"id": alert_id, "status": "acknowledged"}


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: Request):
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE alerts SET status = 'resolved', resolved_at = NOW() WHERE id = $1",
            alert_id,
        )
    return {"id": alert_id, "status": "resolved"}
