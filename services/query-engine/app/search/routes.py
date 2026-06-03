"""
LogSentry Query Engine - Search Routes.

Provides full-text search with filtering, pagination, and autocomplete
suggestions against the log_entries table.
"""

import sys
import time
import math
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, "/app")
from shared.database.connection import DatabasePool
from shared.schemas.log_entry import (
    LogEntryResponse,
    LogSearchResponse,
)

from app.search.query_builder import build_search_query, build_count_query
from app.search.filters import parse_levels

logger = logging.getLogger("query-engine.search")

router = APIRouter()


@router.get("/search", response_model=LogSearchResponse)
async def search_logs(
    q: Optional[str] = Query(None, description="Full-text search query"),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    level: Optional[str] = Query(None, description="Filter by single log level"),
    levels: Optional[str] = Query(
        None, description="Comma-separated log levels, e.g. ERROR,FATAL"
    ),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    trace_id: Optional[str] = Query(None, description="Filter by trace ID"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    host: Optional[str] = Query(None, description="Filter by host"),
    metadata_filters: Optional[str] = Query(
        None,
        description="JSONB metadata filter (JSON string or key=value pairs)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """Full-text search across log entries with filtering, pagination, and ranking.

    When ``q`` is provided, results are ranked by PostgreSQL full-text search
    relevance.  All other parameters act as additive filters.
    """
    start_ts = time.perf_counter()

    # Validate levels if provided
    parsed_levels: list[str] | None = None
    if levels:
        try:
            parsed_levels = parse_levels(levels)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Build params dict
    params = {
        "q": q,
        "service_name": service_name,
        "level": level,
        "levels": parsed_levels,
        "environment": environment,
        "trace_id": trace_id,
        "start_time": start_time,
        "end_time": end_time,
        "host": host,
        "metadata_filters": metadata_filters,
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }

    try:
        search_sql, search_params = build_search_query(params)
        count_sql, count_params = build_count_query(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        async with DatabasePool.acquire() as conn:
            # Execute search and count concurrently
            rows = await conn.fetch(search_sql, *search_params)
            total = await conn.fetchval(count_sql, *count_params)
    except Exception as exc:
        logger.error("Search query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Search query execution failed")

    total = total or 0
    total_pages = max(1, math.ceil(total / page_size))
    elapsed_ms = round((time.perf_counter() - start_ts) * 1000, 2)

    logs = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)

        logs.append(
            LogEntryResponse(
                id=row["id"],
                timestamp=row["timestamp"],
                level=row["level"],
                service_name=row["service_name"],
                message=row["message"],
                trace_id=row["trace_id"],
                span_id=row["span_id"],
                environment=row["environment"],
                host=row["host"],
                metadata=metadata or {},
                error_fingerprint=row["error_fingerprint"],
                ingested_at=row["ingested_at"],
            )
        )

    logger.info(
        "Search completed: q=%s, results=%d/%d, time=%.2fms",
        q, len(logs), total, elapsed_ms,
    )

    return LogSearchResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query_time_ms=elapsed_ms,
    )


@router.get("/search/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(10, ge=1, le=50, description="Max suggestions"),
):
    """Autocomplete suggestions based on partial query text.

    Uses trigram similarity (``pg_trgm``) against recent log messages and
    service names to provide fast prefix-based suggestions.
    """
    if not q or not q.strip():
        return {"suggestions": []}

    term = q.strip()

    sql = """
        (
            SELECT DISTINCT service_name AS suggestion, 'service' AS type
            FROM log_entries
            WHERE service_name ILIKE $1
            LIMIT $2
        )
        UNION ALL
        (
            SELECT DISTINCT ON (left(message, 80))
                left(message, 120) AS suggestion, 'message' AS type
            FROM log_entries
            WHERE message ILIKE $1
            ORDER BY left(message, 80), timestamp DESC
            LIMIT $2
        )
        UNION ALL
        (
            SELECT DISTINCT host AS suggestion, 'host' AS type
            FROM log_entries
            WHERE host ILIKE $1 AND host IS NOT NULL
            LIMIT $2
        )
        ORDER BY type, suggestion
        LIMIT $2
    """

    pattern = f"%{term}%"

    try:
        async with DatabasePool.acquire() as conn:
            rows = await conn.fetch(sql, pattern, limit)
    except Exception as exc:
        logger.error("Suggest query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Suggestion query failed")

    suggestions = [
        {"text": row["suggestion"], "type": row["type"]}
        for row in rows
        if row["suggestion"]
    ]

    return {"suggestions": suggestions}
