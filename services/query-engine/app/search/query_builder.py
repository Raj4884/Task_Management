"""
LogSentry Query Engine - Dynamic SQL Query Builder.

Builds parameterised SQL queries for full-text search and filtered lookups
against the log_entries table.  All user-provided values are bound via
asyncpg's $N parameter placeholders to prevent SQL injection.
"""

import json
import logging
from datetime import datetime

from app.search.filters import validate_sort_field, validate_sort_order

logger = logging.getLogger("query-engine.query_builder")

# Columns returned by search queries
SELECT_COLUMNS = (
    "id, timestamp, level, service_name, message, trace_id, span_id, "
    "environment, host, metadata, error_fingerprint, ingested_at"
)


def build_search_query(params: dict) -> tuple[str, list]:
    """Build a parameterised SELECT query from search parameters.

    When ``q`` is provided the query uses PostgreSQL full-text search
    (``plainto_tsquery``) with ``ts_rank`` scoring.  Otherwise a standard
    filtered query is built.

    Supported filter keys in *params*:
        q, service_name, level, levels, environment, trace_id, host,
        start_time, end_time, metadata_filters, page, page_size,
        sort_by, sort_order

    Args:
        params: Dictionary of search parameters (values may be ``None``).

    Returns:
        Tuple of ``(sql_string, bound_params_list)``.
    """
    bound: list = []
    conditions: list[str] = []
    idx = 1  # asyncpg uses $1, $2, …

    q: str | None = params.get("q")
    use_fts = bool(q and q.strip())

    # ----- Full-text search clause -----
    if use_fts:
        bound.append(q.strip())
        query_ref = f"plainto_tsquery('english', ${idx})"
        conditions.append(f"search_vector @@ {query_ref}")
        rank_expr = f"ts_rank(search_vector, {query_ref}) AS rank"
        idx += 1
    else:
        rank_expr = "0 AS rank"

    # ----- Equality filters -----
    if params.get("service_name"):
        bound.append(params["service_name"])
        conditions.append(f"service_name = ${idx}")
        idx += 1

    if params.get("level"):
        level_val = params["level"]
        if hasattr(level_val, "value"):
            level_val = level_val.value
        bound.append(level_val)
        conditions.append(f"level = ${idx}")
        idx += 1

    if params.get("levels"):
        levels_list = params["levels"]
        if isinstance(levels_list, str):
            levels_list = [l.strip().upper() for l in levels_list.split(",") if l.strip()]
        else:
            levels_list = [l.value if hasattr(l, "value") else str(l) for l in levels_list]
        if levels_list:
            bound.append(levels_list)
            conditions.append(f"level = ANY(${idx})")
            idx += 1

    if params.get("environment"):
        bound.append(params["environment"])
        conditions.append(f"environment = ${idx}")
        idx += 1

    if params.get("trace_id"):
        bound.append(params["trace_id"])
        conditions.append(f"trace_id = ${idx}")
        idx += 1

    if params.get("host"):
        bound.append(params["host"])
        conditions.append(f"host = ${idx}")
        idx += 1

    # ----- Time range -----
    if params.get("start_time"):
        start = params["start_time"]
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        bound.append(start)
        conditions.append(f"timestamp >= ${idx}")
        idx += 1

    if params.get("end_time"):
        end = params["end_time"]
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        bound.append(end)
        conditions.append(f"timestamp <= ${idx}")
        idx += 1

    # ----- JSONB metadata containment filter -----
    metadata_filters = params.get("metadata_filters")
    if metadata_filters:
        if isinstance(metadata_filters, str):
            metadata_filters = json.loads(metadata_filters)
        bound.append(json.dumps(metadata_filters))
        conditions.append(f"metadata @> ${idx}::jsonb")
        idx += 1

    # ----- WHERE clause -----
    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # ----- ORDER BY -----
    sort_by = validate_sort_field(params.get("sort_by", "timestamp"))
    sort_order = validate_sort_order(params.get("sort_order", "desc"))

    if use_fts and sort_by == "timestamp":
        order_by = f"ORDER BY rank DESC, timestamp {sort_order.upper()}"
    else:
        order_by = f"ORDER BY {sort_by} {sort_order.upper()}"

    # ----- PAGINATION -----
    page = max(int(params.get("page", 1)), 1)
    page_size = min(max(int(params.get("page_size", 50)), 1), 500)
    offset = (page - 1) * page_size

    bound.append(page_size)
    limit_placeholder = f"${idx}"
    idx += 1

    bound.append(offset)
    offset_placeholder = f"${idx}"

    sql = (
        f"SELECT {SELECT_COLUMNS}, {rank_expr} "
        f"FROM log_entries "
        f"{where} "
        f"{order_by} "
        f"LIMIT {limit_placeholder} OFFSET {offset_placeholder}"
    )

    logger.debug("Built search SQL: %s | params: %s", sql, bound)
    return sql, bound


def build_count_query(params: dict) -> tuple[str, list]:
    """Build a COUNT(*) query with the same filters as ``build_search_query``.

    Args:
        params: Dictionary of search parameters.

    Returns:
        Tuple of ``(sql_string, bound_params_list)``.
    """
    bound: list = []
    conditions: list[str] = []
    idx = 1

    q: str | None = params.get("q")
    if q and q.strip():
        bound.append(q.strip())
        conditions.append(f"search_vector @@ plainto_tsquery('english', ${idx})")
        idx += 1

    if params.get("service_name"):
        bound.append(params["service_name"])
        conditions.append(f"service_name = ${idx}")
        idx += 1

    if params.get("level"):
        level_val = params["level"]
        if hasattr(level_val, "value"):
            level_val = level_val.value
        bound.append(level_val)
        conditions.append(f"level = ${idx}")
        idx += 1

    if params.get("levels"):
        levels_list = params["levels"]
        if isinstance(levels_list, str):
            levels_list = [l.strip().upper() for l in levels_list.split(",") if l.strip()]
        else:
            levels_list = [l.value if hasattr(l, "value") else str(l) for l in levels_list]
        if levels_list:
            bound.append(levels_list)
            conditions.append(f"level = ANY(${idx})")
            idx += 1

    if params.get("environment"):
        bound.append(params["environment"])
        conditions.append(f"environment = ${idx}")
        idx += 1

    if params.get("trace_id"):
        bound.append(params["trace_id"])
        conditions.append(f"trace_id = ${idx}")
        idx += 1

    if params.get("host"):
        bound.append(params["host"])
        conditions.append(f"host = ${idx}")
        idx += 1

    if params.get("start_time"):
        start = params["start_time"]
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        bound.append(start)
        conditions.append(f"timestamp >= ${idx}")
        idx += 1

    if params.get("end_time"):
        end = params["end_time"]
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        bound.append(end)
        conditions.append(f"timestamp <= ${idx}")
        idx += 1

    metadata_filters = params.get("metadata_filters")
    if metadata_filters:
        if isinstance(metadata_filters, str):
            metadata_filters = json.loads(metadata_filters)
        bound.append(json.dumps(metadata_filters))
        conditions.append(f"metadata @> ${idx}::jsonb")
        idx += 1

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = f"SELECT COUNT(*) FROM log_entries {where}"

    logger.debug("Built count SQL: %s | params: %s", sql, bound)
    return sql, bound
