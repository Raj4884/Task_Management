"""
LogSentry - WebSocket handler for live log tailing.
Subscribes to Redis Pub/Sub and forwards to connected clients.
"""

import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.auth.jwt_handler import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, token: str = Query(default=None)):
    """
    WebSocket endpoint for live log tailing.
    Authenticate via query param: ws://host/ws/logs?token=JWT_TOKEN
    """
    # Authenticate
    if token:
        try:
            payload = verify_token(token)
            if not payload:
                await websocket.close(code=4001, reason="Invalid token")
                return
        except Exception:
            await websocket.close(code=4001, reason="Authentication failed")
            return

    await manager.connect(websocket)

    # Import Redis here to avoid circular imports
    import redis.asyncio as aioredis
    import os

    redis_client = aioredis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("logs:realtime")

    try:
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(_heartbeat(websocket))

        # Start Redis listener task
        redis_task = asyncio.create_task(_redis_listener(pubsub, websocket))

        # Listen for client messages (filters, commands)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    elif msg.get("type") == "filter":
                        # Client can send filter preferences
                        logger.info(f"Client filter update: {msg.get('filters')}")
                except json.JSONDecodeError:
                    pass
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        heartbeat_task.cancel()
        redis_task.cancel()
        await pubsub.unsubscribe("logs:realtime")
        await pubsub.close()
        await redis_client.close()


async def _heartbeat(websocket: WebSocket):
    """Send periodic heartbeats to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "heartbeat", "status": "ok"}))
    except Exception:
        pass


async def _redis_listener(pubsub, websocket: WebSocket):
    """Listen for messages from Redis Pub/Sub and forward to WebSocket."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    break
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
