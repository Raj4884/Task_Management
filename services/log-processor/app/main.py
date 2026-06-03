"""
LogSentry - Log Processor main application.
FastAPI app that also runs the Redis Streams consumer as a background task.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

sys.path.insert(0, "/app")

from shared.database.connection import DatabasePool, RedisConnection
from app.config import settings
from app.consumer import StreamConsumer

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("log-processor")

consumer_instance: StreamConsumer = None
consumer_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown."""
    global consumer_instance, consumer_task
    logger.info("Starting Log Processor service...")

    # Initialize connections
    pool = await DatabasePool.get_pool()
    redis = await RedisConnection.get_redis()

    # Ensure consumer group exists
    try:
        await redis.xgroup_create(
            settings.redis_stream_name,
            settings.redis_consumer_group,
            id="0",
            mkstream=True,
        )
        logger.info(f"Created consumer group '{settings.redis_consumer_group}'")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"Consumer group '{settings.redis_consumer_group}' already exists")
        else:
            logger.error(f"Error creating consumer group: {e}")

    # Start the stream consumer
    consumer_instance = StreamConsumer(pool, redis)
    consumer_task = asyncio.create_task(consumer_instance.run())
    logger.info("Stream consumer started")

    yield

    # Shutdown
    logger.info("Shutting down Log Processor...")
    if consumer_instance:
        consumer_instance.stop()
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    await DatabasePool.close()
    await RedisConnection.close()
    logger.info("Log Processor shut down complete")


app = FastAPI(
    title="LogSentry Log Processor",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "log-processor",
        "consumer_running": consumer_task is not None and not consumer_task.done() if consumer_task else False,
    }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    if consumer_instance:
        return {
            "processed_total": consumer_instance.processed_count,
            "errors_total": consumer_instance.error_count,
            "batch_count": consumer_instance.batch_count,
        }
    return {"status": "consumer not initialized"}
