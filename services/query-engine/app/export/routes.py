"""
LogSentry - Export routes for CSV and JSON download.
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from app.search.query_builder import build_search_query

logger = logging.getLogger("export")

router = APIRouter(prefix="/export")


@router.get("/csv")
async def export_csv(
    request: Request,
    q: Optional[str] = None,
    service_name: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = Query(10000, ge=1, le=100000),
):
    """Export search results as CSV."""
    pool = request.app.state.db_pool

    params = {
        "q": q, "service_name": service_name, "level": level,
        "start_time": start_time, "end_time": end_time,
        "page": 1, "page_size": limit, "sort_by": "timestamp", "sort_order": "desc",
    }

    sql, query_params = build_search_query(params)

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *query_params)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "level", "service_name", "message", "host", "trace_id", "environment"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in rows:
            writer.writerow([
                row["timestamp"].isoformat(),
                row["level"],
                row["service_name"],
                row["message"][:1000],
                row.get("host", ""),
                row.get("trace_id", ""),
                row.get("environment", ""),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"logsentry_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/json")
async def export_json(
    request: Request,
    q: Optional[str] = None,
    service_name: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = Query(10000, ge=1, le=100000),
):
    """Export search results as JSON."""
    pool = request.app.state.db_pool

    params = {
        "q": q, "service_name": service_name, "level": level,
        "start_time": start_time, "end_time": end_time,
        "page": 1, "page_size": limit, "sort_by": "timestamp", "sort_order": "desc",
    }

    sql, query_params = build_search_query(params)

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *query_params)

    logs = [
        {
            "timestamp": r["timestamp"].isoformat(),
            "level": r["level"],
            "service_name": r["service_name"],
            "message": r["message"],
            "host": r.get("host"),
            "trace_id": r.get("trace_id"),
            "environment": r.get("environment"),
            "metadata": json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r.get("metadata") or {}),
        }
        for r in rows
    ]

    content = json.dumps({"logs": logs, "count": len(logs), "exported_at": datetime.utcnow().isoformat()}, indent=2)
    filename = f"logsentry_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
