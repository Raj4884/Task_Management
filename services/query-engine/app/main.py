"""
LogSentry Query Engine - Main Application.

FastAPI service providing full-text search, analytics, alerting, and data export.
Runs on port 8004 with lifespan-managed DB pool and Redis connections.
"""

import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Shared module imports
sys.path.insert(0, "/app")
from shared.database.connection import DatabasePool, RedisConnection

from app.search.routes import router as search_router
from app.analytics.routes import router as analytics_router
from app.export.routes import router as export_router

logger = logging.getLogger("query-engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of database pool and Redis connection."""
    # Startup
    logger.info("Starting Query Engine service...")
    try:
        pool = await DatabasePool.get_pool()
        logger.info("PostgreSQL connection pool initialized (min=5, max=20)")

        redis = await RedisConnection.get_redis()
        await redis.ping()
        logger.info("Redis connection established")

        # Store references on app state for access in route handlers
        app.state.db_pool = pool
        app.state.redis = redis

    except Exception as exc:
        logger.error("Failed to initialise connections: %s", exc)
        raise

    yield

    # Shutdown
    logger.info("Shutting down Query Engine service...")
    await DatabasePool.close()
    await RedisConnection.close()
    logger.info("All connections closed")


app = FastAPI(
    title="LogSentry Query Engine",
    description="Full-text search, analytics, alerting, and export service for LogSentry.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount routers
app.include_router(search_router, tags=["Search"])
app.include_router(analytics_router, tags=["Analytics"])
app.include_router(export_router, tags=["Export"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health check – verifies DB and Redis connectivity."""
    status = {"service": "query-engine", "status": "healthy"}

    try:
        async with DatabasePool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        status["postgres"] = "connected"
    except Exception as exc:
        status["postgres"] = f"error: {exc}"
        status["status"] = "degraded"

    try:
        redis = await RedisConnection.get_redis()
        await redis.ping()
        status["redis"] = "connected"
    except Exception as exc:
        status["redis"] = f"error: {exc}"
        status["status"] = "degraded"

    return status


# Configure logging on module load
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
