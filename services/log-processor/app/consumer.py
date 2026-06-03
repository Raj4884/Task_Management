"""
LogSentry - Redis Streams consumer for log processing.
Two-phase startup: recover pending messages, then read new ones.
"""

import os
import json
import asyncio
import socket
import logging
from datetime import datetime

from app.config import settings
from app.processing.enricher import enrich_log_entry, generate_error_fingerprint
from app.processing.aggregator import update_counters
from app.processing.storage import LogStorage
from app.alerts.detector import AlertDetector

logger = logging.getLogger("consumer")


class StreamConsumer:
    """Redis Streams consumer with consumer group support."""

    def __init__(self, db_pool, redis):
        self.db_pool = db_pool
        self.redis = redis
        self.storage = LogStorage(db_pool)
        self.alert_detector = AlertDetector(redis, db_pool)
        self.stream_name = settings.redis_stream_name
        self.group_name = settings.redis_consumer_group
        self.consumer_name = f"{socket.gethostname()}-{os.getpid()}"
        self.dead_letter_stream = settings.redis_dead_letter_stream
        self.running = True
        self.processed_count = 0
        self.error_count = 0
        self.batch_count = 0
        self.max_retries = 3
        self.batch_size = 100
        self.block_ms = 5000
        self._views_refresh_counter = 0

    def stop(self):
        """Signal the consumer to stop."""
        self.running = False

    async def run(self):
        """Main consumer loop with two-phase startup."""
        logger.info(f"Consumer '{self.consumer_name}' starting...")

        # Phase 1: Recover pending (unacknowledged) messages
        logger.info("Phase 1: Recovering pending messages...")
        await self._recover_pending()

        # Phase 2: Read new messages
        logger.info("Phase 2: Reading new messages...")
        await self._read_new()

    async def _recover_pending(self):
        """Read and process unacknowledged messages from PEL."""
        last_id = "0"
        while self.running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: last_id},
                    count=self.batch_size,
                    block=1000,
                )

                if not messages:
                    break

                for stream, entries in messages:
                    if not entries:
                        break
                    for msg_id, data in entries:
                        last_id = msg_id
                    await self._process_batch(entries)

                # If we got fewer messages than batch size, we're done
                for stream, entries in messages:
                    if len(entries) < self.batch_size:
                        return
            except Exception as e:
                logger.error(f"Error recovering pending messages: {e}")
                await asyncio.sleep(1)
                return

    async def _read_new(self):
        """Read new messages from the stream."""
        while self.running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=self.batch_size,
                    block=self.block_ms,
                )

                if not messages:
                    continue

                for stream, entries in messages:
                    if entries:
                        await self._process_batch(entries)

            except asyncio.CancelledError:
                logger.info("Consumer cancelled, finishing up...")
                return
            except Exception as e:
                logger.error(f"Error reading messages: {e}")
                self.error_count += 1
                await asyncio.sleep(2)

    async def _process_batch(self, entries: list):
        """Process a batch of stream entries."""
        processed_entries = []
        ack_ids = []

        for msg_id, data in entries:
            try:
                log_data = json.loads(data.get("data", "{}"))
                enriched = enrich_log_entry(log_data)

                if enriched.get("level") in ("ERROR", "FATAL"):
                    enriched["error_fingerprint"] = generate_error_fingerprint(
                        enriched.get("message", ""),
                        enriched.get("service_name", ""),
                    )

                processed_entries.append(enriched)
                ack_ids.append(msg_id)

            except Exception as e:
                logger.error(f"Error processing message {msg_id}: {e}")
                self.error_count += 1
                # Check retry count
                retry_count = int(data.get("retries", 0))
                if retry_count >= self.max_retries:
                    await self._send_to_dead_letter(msg_id, data, str(e))
                    ack_ids.append(msg_id)
                else:
                    # Will be retried on next PEL recovery
                    pass

        # Batch store to PostgreSQL
        if processed_entries:
            try:
                count = await self.storage.store_batch(processed_entries)
                self.processed_count += count
                self.batch_count += 1
                logger.debug(f"Stored batch of {count} logs")

                # Update real-time counters in Redis
                for entry in processed_entries:
                    await update_counters(self.redis, entry)

                # Publish to Pub/Sub for live tailing
                for entry in processed_entries[-10:]:  # Last 10 for real-time
                    await self._publish_realtime(entry)

                # Check alerts
                await self.alert_detector.check_batch(processed_entries)

                # Periodically refresh materialized views
                self._views_refresh_counter += 1
                if self._views_refresh_counter >= 50:
                    await self._refresh_views()
                    self._views_refresh_counter = 0

            except Exception as e:
                logger.error(f"Error storing batch: {e}")
                self.error_count += 1
                return  # Don't ack if storage failed

        # Acknowledge processed messages
        if ack_ids:
            try:
                await self.redis.xack(self.stream_name, self.group_name, *ack_ids)
            except Exception as e:
                logger.error(f"Error acknowledging messages: {e}")

    async def _publish_realtime(self, entry: dict):
        """Publish processed log to Redis Pub/Sub for real-time streaming."""
        try:
            safe_entry = {
                "id": entry.get("id"),
                "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
                "level": entry.get("level", "INFO"),
                "service_name": entry.get("service_name", "unknown"),
                "message": entry.get("message", ""),
                "host": entry.get("host"),
                "trace_id": entry.get("trace_id"),
                "metadata": entry.get("metadata", {}),
            }
            await self.redis.publish("logs:realtime", json.dumps(safe_entry, default=str))
        except Exception as e:
            logger.debug(f"Error publishing to realtime channel: {e}")

    async def _send_to_dead_letter(self, msg_id: str, data: dict, error: str):
        """Move failed message to dead letter stream."""
        try:
            await self.redis.xadd(
                self.dead_letter_stream,
                {
                    "original_id": msg_id,
                    "data": json.dumps(data),
                    "error": error,
                    "failed_at": datetime.utcnow().isoformat(),
                },
                maxlen=10000,
            )
            logger.warning(f"Message {msg_id} moved to dead letter stream: {error}")
        except Exception as e:
            logger.error(f"Error sending to dead letter: {e}")

    async def _refresh_views(self):
        """Refresh materialized views for analytics."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("SELECT refresh_analytics_views()")
            logger.info("Refreshed analytics views")
        except Exception as e:
            logger.debug(f"Error refreshing views (may not exist yet): {e}")
