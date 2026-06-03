"""
LogSentry - Log Ingestion Service Main Application.

FastAPI application for high-throughput log intake. Manages Redis connections
via lifespan context and exposes ingestion routes with health checks.
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.ingestion.routes import router as ingestion_router
from app.queue.publisher import StreamPublisher

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("log-ingestion")


# ---------------------------------------------------------------------------
# Application state helpers
# ---------------------------------------------------------------------------
class AppState:
    """Mutable holder for objects attached during lifespan."""

    redis: aioredis.Redis | None = None
    publisher: StreamPublisher | None = None
    started_at: datetime | None = None


app_state = AppState()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Redis connection lifecycle."""
    logger.info(
        "Starting Log Ingestion Service v%s — connecting to Redis at %s:%d",
        settings.service_version,
        settings.redis_host,
        settings.redis_port,
    )

    # Connect to Redis
    app_state.redis = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=10,
        socket_keepalive=True,
        retry_on_timeout=True,
    )

    # Verify connectivity
    try:
        await app_state.redis.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.error("Failed to connect to Redis: %s", exc)
        raise

    # Create publisher
    app_state.publisher = StreamPublisher(
        redis=app_state.redis,
        stream_name=settings.redis_stream_name,
        maxlen=settings.redis_stream_maxlen,
    )
    app_state.started_at = datetime.now(timezone.utc)

    yield

    # Shutdown
    logger.info("Shutting down — closing Redis connection")
    if app_state.redis:
        await app_state.redis.close()
        app_state.redis = None
    app_state.publisher = None
    logger.info("Log Ingestion Service stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="LogSentry — Log Ingestion Service",
    description="High-throughput log intake with parsing, normalization, and Redis Streams publishing.",
    version=settings.service_version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc) if settings.log_level == "DEBUG" else None,
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(ingestion_router, prefix="/ingest", tags=["ingestion"])


@app.get("/health", tags=["health"])
async def health_check():
    """Service health check — verifies Redis is reachable."""
    redis_ok = False
    try:
        if app_state.redis:
            await app_state.redis.ping()
            redis_ok = True
    except Exception:
        logger.warning("Redis health-check ping failed")

    status = "healthy" if redis_ok else "degraded"
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": status,
        "redis": "connected" if redis_ok else "disconnected",
        "started_at": app_state.started_at.isoformat() if app_state.started_at else None,
        "uptime_seconds": (
            (datetime.now(timezone.utc) - app_state.started_at).total_seconds()
            if app_state.started_at
            else 0
        ),
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "docs": "/docs",
    }
