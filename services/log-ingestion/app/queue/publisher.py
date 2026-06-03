"""
LogSentry - Redis Streams Publisher.

Publishes normalized log entries to a Redis Stream using ``XADD``.
Supports single and batch (pipelined) publishing with approximate
stream trimming via ``MAXLEN ~``.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger("log-ingestion.publisher")


class StreamPublisher:
    """Publishes log entries to a Redis Stream.

    Parameters
    ----------
    redis : aioredis.Redis
        An active ``redis.asyncio`` connection.
    stream_name : str
        Redis Stream key (e.g. ``logs:raw``).
    maxlen : int
        Approximate max entries kept in the stream (``MAXLEN ~``).
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        stream_name: str = "logs:raw",
        maxlen: int = 100_000,
    ) -> None:
        self._redis = redis
        self._stream_name = stream_name
        self._maxlen = maxlen

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish_single(self, entry: dict[str, Any]) -> str:
        """Publish a single log entry to the Redis Stream.

        The entry dict is JSON-serialized and stored in a ``data`` field
        inside the stream message.

        Parameters
        ----------
        entry : dict
            Normalized log entry.

        Returns
        -------
        str
            The Redis Stream message ID (e.g. ``1706000000000-0``).
        """
        payload = self._serialize(entry)
        message_id: str = await self._redis.xadd(
            name=self._stream_name,
            fields={"data": payload},
            maxlen=self._maxlen,
            approximate=True,
        )
        logger.debug(
            "Published message %s to stream %s", message_id, self._stream_name
        )
        return message_id

    async def publish_batch(
        self, entries: list[dict[str, Any]]
    ) -> list[str]:
        """Publish a batch of log entries using a Redis pipeline.

        All ``XADD`` commands are queued in a pipeline and executed in a
        single round-trip for maximum throughput.

        Parameters
        ----------
        entries : list[dict]
            List of normalized log entries.

        Returns
        -------
        list[str]
            List of Redis Stream message IDs, one per entry.
        """
        if not entries:
            return []

        pipe = self._redis.pipeline(transaction=False)
        for entry in entries:
            payload = self._serialize(entry)
            pipe.xadd(
                name=self._stream_name,
                fields={"data": payload},
                maxlen=self._maxlen,
                approximate=True,
            )

        results = await pipe.execute()
        message_ids = [str(r) for r in results]
        logger.info(
            "Published batch of %d messages to stream %s",
            len(message_ids),
            self._stream_name,
        )
        return message_ids

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize(entry: dict[str, Any]) -> str:
        """JSON-serialize a log entry, handling datetime objects."""
        return json.dumps(entry, default=_json_default, ensure_ascii=False)


def _json_default(obj: Any) -> Any:
    """``json.dumps`` default handler for non-serializable types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
