"""
LogSentry - PostgreSQL batch writer for processed logs.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("storage")


class LogStorage:
    """Handles batch insertion of log entries into PostgreSQL."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def store_batch(self, entries: list[dict]) -> int:
        """
        Batch insert log entries into PostgreSQL.
        Returns the number of entries stored.
        """
        if not entries:
            return 0

        rows = []
        for entry in entries:
            ts = entry.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    ts = datetime.utcnow()
            elif not ts:
                ts = datetime.utcnow()

            metadata = entry.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            rows.append((
                ts,
                entry.get("level", "INFO"),
                entry.get("service_name", "unknown"),
                entry.get("message", ""),
                entry.get("trace_id"),
                entry.get("span_id"),
                entry.get("environment", "production"),
                entry.get("host"),
                json.dumps(metadata),
                entry.get("error_fingerprint"),
            ))

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.executemany(
                    """
                    INSERT INTO log_entries 
                        (timestamp, level, service_name, message, trace_id, 
                         span_id, environment, host, metadata, error_fingerprint)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
                    """,
                    rows,
                )
                return len(rows)
        except Exception as e:
            logger.error(f"Error storing batch of {len(rows)} entries: {e}")
            # Try individual inserts as fallback
            stored = 0
            async with self.db_pool.acquire() as conn:
                for row in rows:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO log_entries 
                                (timestamp, level, service_name, message, trace_id, 
                                 span_id, environment, host, metadata, error_fingerprint)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
                            """,
                            *row,
                        )
                        stored += 1
                    except Exception as inner_e:
                        logger.debug(f"Failed to store individual entry: {inner_e}")
            return stored
