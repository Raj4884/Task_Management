"""
LogSentry API Gateway - FastAPI Application Entry Point.

Central entry point for the LogSentry platform.  Handles:
  • JWT-based authentication (login / register / refresh / me)
  • Transparent reverse-proxy to internal micro-services
  • WebSocket endpoint for live log tailing
  • SSE endpoint for real-time log streaming
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Shared modules (mounted at /app/shared in Docker)
# ---------------------------------------------------------------------------
sys.path.insert(0, "/app")
from shared.database.connection import DatabasePool, RedisConnection  # noqa: E402

from app.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api-gateway")


# ---------------------------------------------------------------------------
# Lifespan – startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup, tear them down on shutdown."""
    logger.info("Starting API Gateway …")

    # Warm up the database connection pool
    pool = await DatabasePool.get_pool()
    logger.info("PostgreSQL pool ready  (min=%s, max=%s)", pool.get_min_size(), pool.get_max_size())

    # Warm up the Redis connection
    redis = await RedisConnection.get_redis()
    pong = await redis.ping()
    logger.info("Redis connected  (ping=%s)", pong)

    yield  # ← application runs here

    logger.info("Shutting down API Gateway …")
    await RedisConnection.close()
    await DatabasePool.close()
    logger.info("All connections closed.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="LogSentry API Gateway",
    description="Central entry point for the LogSentry distributed log-analysis platform.",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# ── CORS (allow all for development) ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ────────────────────────────────────────────────────
from app.auth.routes import router as auth_router          # noqa: E402
from app.proxy.routes import router as proxy_router        # noqa: E402
from app.websocket.handler import router as ws_router      # noqa: E402

app.include_router(auth_router)    # /auth/*
app.include_router(proxy_router)   # /api/*
app.include_router(ws_router)      # /ws/*


# ── Root & health ─────────────────────────────────────────────────────────
@app.get("/", tags=["info"])
async def root():
    """Return basic API information."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["info"])
async def health():
    """Liveness / readiness probe."""
    checks: dict = {"service": "healthy"}

    # Postgres check
    try:
        async with DatabasePool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["postgres"] = "healthy"
    except Exception as exc:
        logger.warning("Postgres health-check failed: %s", exc)
        checks["postgres"] = "unhealthy"

    # Redis check
    try:
        redis = await RedisConnection.get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as exc:
        logger.warning("Redis health-check failed: %s", exc)
        checks["redis"] = "unhealthy"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
