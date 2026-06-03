"""
LogSentry API Gateway - Proxy Routes.

Transparently forwards authenticated requests to internal micro-services
via ``httpx``.  Also exposes an SSE endpoint that subscribes to the Redis
Pub/Sub channel ``logs:realtime`` and streams log events to the client.

Service mapping:
    /api/ingest           → log-ingestion:8001
    /api/search           → query-engine:8004
    /api/analytics/*      → query-engine:8004
    /api/anomalies/*      → anomaly-detection:8003
    /api/alerts           → query-engine:8004
    /api/export/*         → query-engine:8004
    /api/logs/stream      → SSE from Redis pub/sub
"""

import asyncio
import json
import logging
import sys
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

sys.path.insert(0, "/app")
from shared.database.connection import RedisConnection  # noqa: E402

from app.auth.middleware import get_current_user  # noqa: E402
from app.config import settings  # noqa: E402

logger = logging.getLogger("api-gateway.proxy")

router = APIRouter(prefix="/api", tags=["proxy"])

# ── Shared httpx client (connection-pooled) ───────────────────────────────
# Created lazily to avoid issues when the module is imported at startup.
_http_client: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _http_client


async def _proxy_request(
    method: str,
    target_url: str,
    request: Request,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    """Forward an incoming request to an internal service and return its response.

    Args:
        method:     HTTP method (GET, POST, PUT, …).
        target_url: Fully-qualified URL of the downstream service endpoint.
        request:    The original incoming FastAPI request.
        params:     Optional query-string overrides.

    Returns:
        Parsed JSON from the downstream service.

    Raises:
        HTTPException: On connection errors or non-2xx responses.
    """
    client = await _get_http_client()

    # Preserve original query string unless overridden
    if params is None:
        params = dict(request.query_params)

    # Read body (empty for GET)
    body = await request.body()
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Accept": "application/json",
    }

    try:
        response = await client.request(
            method=method,
            url=target_url,
            content=body if body else None,
            params=params,
            headers=headers,
        )
    except httpx.ConnectError as exc:
        logger.error("Upstream connection failed: %s → %s", target_url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service unavailable: {target_url}",
        )
    except httpx.TimeoutException:
        logger.error("Upstream timed out: %s", target_url)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream service timed out: {target_url}",
        )

    if response.status_code >= 400:
        # Surface the upstream error to the caller
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


# ═══════════════════════════════════════════════════════════════════════════
#  Log Ingestion  →  log-ingestion:8001
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/ingest")
async def ingest_log(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy a single log entry to the ingestion service."""
    url = f"{settings.INGESTION_SERVICE_URL}/ingest"
    return await _proxy_request("POST", url, request)


@router.post("/ingest/batch")
async def ingest_batch(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy a batch of log entries to the ingestion service."""
    url = f"{settings.INGESTION_SERVICE_URL}/ingest/batch"
    return await _proxy_request("POST", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  Search  →  query-engine:8004
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/search")
async def search_logs(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy log search queries to the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/search"
    return await _proxy_request("GET", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  Analytics  →  query-engine:8004
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/analytics/dashboard-stats")
async def dashboard_stats(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Aggregate dashboard statistics from the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/analytics/dashboard-stats"
    return await _proxy_request("GET", url, request)


@router.get("/analytics/{path:path}")
async def proxy_analytics(
    path: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy any /analytics/* request to the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/analytics/{path}"
    return await _proxy_request("GET", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  Anomalies  →  anomaly-detection:8003
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/anomalies/{path:path}")
async def proxy_anomalies(
    path: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy any /anomalies/* request to the anomaly-detection service."""
    url = f"{settings.ANOMALY_SERVICE_URL}/anomalies/{path}"
    return await _proxy_request("GET", url, request)


@router.get("/anomalies")
async def list_anomalies(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """List anomalies from the anomaly-detection service."""
    url = f"{settings.ANOMALY_SERVICE_URL}/anomalies"
    return await _proxy_request("GET", url, request)


@router.post("/anomalies/{path:path}")
async def proxy_anomalies_post(
    path: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy POST /anomalies/* requests (train, etc.) to the anomaly-detection service."""
    url = f"{settings.ANOMALY_SERVICE_URL}/anomalies/{path}"
    return await _proxy_request("POST", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  Alerts  →  query-engine:8004
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/alerts")
async def list_alerts(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """List alerts from the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/alerts"
    return await _proxy_request("GET", url, request)


@router.post("/alerts")
async def create_alert(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Create an alert via the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/alerts"
    return await _proxy_request("POST", url, request)


@router.put("/alerts/{alert_id}/{action:path}")
async def update_alert_action(
    alert_id: str,
    action: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy PUT /alerts/{id}/* to the query engine (acknowledge, resolve, etc.)."""
    url = f"{settings.QUERY_ENGINE_URL}/alerts/{alert_id}/{action}"
    return await _proxy_request("PUT", url, request)


@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy PUT /alerts/{id} to the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/alerts/{alert_id}"
    return await _proxy_request("PUT", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  Export  →  query-engine:8004
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/export/{path:path}")
async def proxy_export(
    path: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Proxy export requests to the query engine."""
    url = f"{settings.QUERY_ENGINE_URL}/export/{path}"
    return await _proxy_request("GET", url, request)


# ═══════════════════════════════════════════════════════════════════════════
#  SSE – Real-time log stream via Redis Pub/Sub
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/logs/stream")
async def sse_log_stream(
    request: Request,
    _user: dict = Depends(get_current_user),
    channel: str = Query(default=None, description="Override the pub/sub channel"),
):
    """Server-Sent Events endpoint for real-time log streaming.

    Subscribes to the Redis Pub/Sub channel ``logs:realtime`` (or a custom
    channel) and pushes every published message to the connected client as
    an SSE ``data:`` frame.
    """
    pubsub_channel = channel or settings.REDIS_PUBSUB_CHANNEL

    async def _event_generator():
        redis = await RedisConnection.get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(pubsub_channel)
        logger.info("SSE client subscribed to '%s'", pubsub_channel)

        try:
            while True:
                # Check if the client has disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected")
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    # Ensure it's a string
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
                else:
                    # Send a keep-alive comment every ~1 s to detect disconnects
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled")
        finally:
            await pubsub.unsubscribe(pubsub_channel)
            await pubsub.close()
            logger.info("SSE pubsub cleaned up for '%s'", pubsub_channel)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
