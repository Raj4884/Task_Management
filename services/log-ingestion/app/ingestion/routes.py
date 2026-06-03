"""
LogSentry - Log Ingestion Routes.

API endpoints for ingesting logs:

* ``POST /ingest``       — single structured log entry
* ``POST /ingest/batch`` — batch of up to 1000 structured entries
* ``POST /ingest/raw``   — raw plain-text log (auto-detected format)
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from app.ingestion.normalizer import normalize_entry
from app.ingestion.parser import auto_detect_and_parse
from app.schemas import (
    IngestionResponse,
    LogEntryBatchCreate,
    LogEntryCreate,
    RawLogEntry,
)

logger = logging.getLogger("log-ingestion.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_publisher(request: Request):
    """Retrieve the ``StreamPublisher`` from application state."""
    from app.main import app_state

    if app_state.publisher is None:
        raise HTTPException(
            status_code=503,
            detail="Service not ready — Redis publisher is not initialised",
        )
    return app_state.publisher


def _entry_to_dict(entry: LogEntryCreate) -> dict[str, Any]:
    """Convert a Pydantic model to a plain dict for normalisation."""
    return entry.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=IngestionResponse,
    summary="Ingest a single log entry",
    status_code=202,
)
async def ingest_single(entry: LogEntryCreate, request: Request):
    """Accept a single structured log entry.

    The entry is normalized and published to the Redis Stream for
    downstream processing.
    """
    publisher = _get_publisher(request)
    start = time.monotonic()

    try:
        raw_dict = _entry_to_dict(entry)
        normalized = normalize_entry(raw_dict)
        message_id = await publisher.publish_single(normalized)
        elapsed_ms = (time.monotonic() - start) * 1000

        logger.debug(
            "Ingested single log [%s] in %.1fms",
            message_id,
            elapsed_ms,
        )
        return IngestionResponse(
            status="accepted",
            count=1,
            message=f"Log queued for processing (id={message_id})",
        )

    except Exception as exc:
        logger.exception("Failed to ingest single log entry")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {exc}",
        ) from exc


@router.post(
    "/batch",
    response_model=IngestionResponse,
    summary="Ingest a batch of log entries",
    status_code=202,
)
async def ingest_batch(batch: LogEntryBatchCreate, request: Request):
    """Accept a batch of up to 1000 structured log entries.

    All entries are normalized in-memory, then published to Redis in a
    single pipelined operation for maximum throughput.
    """
    publisher = _get_publisher(request)
    start = time.monotonic()

    try:
        normalized_entries = []
        for entry in batch.logs:
            raw_dict = _entry_to_dict(entry)
            normalized = normalize_entry(raw_dict)
            normalized_entries.append(normalized)

        message_ids = await publisher.publish_batch(normalized_entries)
        elapsed_ms = (time.monotonic() - start) * 1000
        count = len(message_ids)

        logger.info(
            "Ingested batch of %d logs in %.1fms (%.0f logs/sec)",
            count,
            elapsed_ms,
            count / (elapsed_ms / 1000) if elapsed_ms > 0 else 0,
        )
        return IngestionResponse(
            status="accepted",
            count=count,
            message=f"{count} logs queued for processing",
        )

    except Exception as exc:
        logger.exception("Failed to ingest batch of %d logs", len(batch.logs))
        raise HTTPException(
            status_code=500,
            detail=f"Batch ingestion failed: {exc}",
        ) from exc


@router.post(
    "/raw",
    response_model=IngestionResponse,
    summary="Ingest a raw text log",
    status_code=202,
)
async def ingest_raw(
    request: Request,
    body: str = Body(
        ...,
        media_type="text/plain",
        description="Raw log text — the service will auto-detect the format",
    ),
):
    """Accept a raw plain-text log line or multi-line block.

    The service auto-detects the format (JSON, syslog, Apache combined,
    or plain-text), parses it, normalizes it, and publishes to Redis.
    Multi-line input is split on newlines and each non-empty line is
    treated as a separate log entry.
    """
    publisher = _get_publisher(request)
    start = time.monotonic()

    try:
        lines = [l for l in body.splitlines() if l.strip()]
        if not lines:
            raise HTTPException(status_code=400, detail="Empty log body")

        normalized_entries = []
        for line in lines:
            parsed = auto_detect_and_parse(line)
            normalized = normalize_entry(parsed)
            normalized_entries.append(normalized)

        if len(normalized_entries) == 1:
            message_ids = [await publisher.publish_single(normalized_entries[0])]
        else:
            message_ids = await publisher.publish_batch(normalized_entries)

        elapsed_ms = (time.monotonic() - start) * 1000
        count = len(message_ids)

        logger.info(
            "Ingested %d raw log line(s) in %.1fms",
            count,
            elapsed_ms,
        )
        return IngestionResponse(
            status="accepted",
            count=count,
            message=f"{count} raw log(s) parsed and queued for processing",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to ingest raw log")
        raise HTTPException(
            status_code=500,
            detail=f"Raw ingestion failed: {exc}",
        ) from exc
