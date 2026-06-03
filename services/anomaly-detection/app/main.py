"""
LogSentry - Anomaly Detection main application.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

sys.path.insert(0, "/app")

from shared.database.connection import DatabasePool, RedisConnection
from app.config import service_config, ml_config

logging.basicConfig(
    level=getattr(logging, service_config.log_level.upper()),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("anomaly-detection")

scorer_task = None
retrain_task_ref = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scorer_task, retrain_task_ref
    logger.info("Starting Anomaly Detection service...")

    pool = await DatabasePool.get_pool()
    redis = await RedisConnection.get_redis()

    # Load existing models
    from app.models.trainer import ModelTrainer
    from app.inference.realtime import RealtimeScorer

    trainer = ModelTrainer(pool, redis)
    app.state.trainer = trainer
    app.state.db_pool = pool
    app.state.redis = redis

    # Try to load pre-trained models
    try:
        trainer.load_models()
        logger.info("Loaded pre-trained models")
    except Exception:
        logger.info("No pre-trained models found, will train on first request or scheduled run")

    # Start real-time scorer
    scorer = RealtimeScorer(trainer, redis, pool)
    app.state.scorer = scorer
    scorer_task = asyncio.create_task(scorer.run_periodic_scoring(interval_seconds=ml_config.scoring_interval_seconds))

    # Schedule periodic retraining
    retrain_task_ref = asyncio.create_task(
        trainer.schedule_periodic_training(interval_hours=ml_config.retrain_interval_hours)
    )
    app.state.retrain_task = retrain_task_ref

    yield

    logger.info("Shutting down Anomaly Detection...")
    if scorer_task:
        scorer_task.cancel()
    if retrain_task_ref:
        retrain_task_ref.cancel()
    await DatabasePool.close()
    await RedisConnection.close()


app = FastAPI(title="LogSentry Anomaly Detection", version="1.0.0", lifespan=lifespan)

from app.inference.routes import router as inference_router
app.include_router(inference_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "anomaly-detection"}
