"""
LogSentry - Anomaly detection API routes.
"""

import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Query
from typing import Optional

logger = logging.getLogger("anomaly-routes")

router = APIRouter(prefix="/anomalies")


@router.get("/")
async def list_anomalies(
    request: Request,
    service_name: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List detected anomalies from the database."""
    pool = request.app.state.db_pool

    query = "SELECT * FROM anomalies WHERE 1=1"
    params = []
    idx = 1

    if service_name:
        query += f" AND service_name = ${idx}"
        params.append(service_name)
        idx += 1

    if anomaly_type:
        query += f" AND anomaly_type = ${idx}"
        params.append(anomaly_type)
        idx += 1

    if start_time:
        query += f" AND detected_at >= ${idx}"
        params.append(datetime.fromisoformat(start_time))
        idx += 1

    if end_time:
        query += f" AND detected_at <= ${idx}"
        params.append(datetime.fromisoformat(end_time))
        idx += 1

    query += f" ORDER BY detected_at DESC LIMIT ${idx}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [
        {
            "id": str(r["id"]),
            "detected_at": r["detected_at"].isoformat(),
            "anomaly_type": r["anomaly_type"],
            "service_name": r["service_name"],
            "severity_score": r["severity_score"],
            "description": r["description"],
            "features": json.loads(r["features"]) if isinstance(r["features"], str) else r["features"],
            "model_name": r["model_name"],
            "model_version": r["model_version"],
            "is_acknowledged": r["is_acknowledged"],
            "metadata": json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"],
        }
        for r in rows
    ]


@router.get("/realtime")
async def realtime_scores(request: Request):
    """Get current anomaly scores for all services from Redis cache."""
    redis = request.app.state.redis

    cached = await redis.get("anomaly:realtime:scores")
    if cached:
        return json.loads(cached)

    return {"message": "No real-time scores available yet", "scores": {}}


@router.post("/train")
async def trigger_training(request: Request):
    """Trigger model retraining."""
    trainer = request.app.state.trainer
    result = await trainer.train_all_models()
    return result


@router.get("/models/status")
async def model_status(request: Request):
    """Return model info and training status."""
    trainer = request.app.state.trainer
    redis = request.app.state.redis

    cached_status = await redis.get("anomaly:training:status")

    return {
        "isolation_forest": trainer.isolation_model.get_info(),
        "pattern_detector": {
            "trained": trainer.pattern_detector.trained,
            "clusters": len(trainer.pattern_detector.representative_messages),
        },
        "last_trained": trainer.last_trained,
        "training_history": json.loads(cached_status) if cached_status else None,
    }


@router.put("/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(anomaly_id: str, request: Request):
    """Acknowledge a detected anomaly."""
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE anomalies SET is_acknowledged = TRUE WHERE id = $1",
            anomaly_id,
        )

    return {"status": "acknowledged", "id": anomaly_id}
