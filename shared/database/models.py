"""
LogSentry - SQLAlchemy-style model definitions.
These mirror the PostgreSQL schema for reference and documentation.
Actual queries use asyncpg for performance.
"""

# Database table definitions for reference
# The actual schema is managed by database/init.sql

LOG_ENTRIES_TABLE = "log_entries"
USERS_TABLE = "users"
SERVICES_TABLE = "services"
ALERTS_TABLE = "alerts"
ANOMALIES_TABLE = "anomalies"

# Column definitions for dynamic query building
LOG_ENTRY_COLUMNS = [
    "id", "timestamp", "level", "service_name", "message",
    "trace_id", "span_id", "environment", "host", "metadata",
    "error_fingerprint", "ingested_at"
]

LOG_ENTRY_SEARCHABLE_COLUMNS = [
    "level", "service_name", "message", "host"
]

LOG_ENTRY_FILTERABLE_COLUMNS = {
    "level": "varchar",
    "service_name": "varchar",
    "environment": "varchar",
    "host": "varchar",
    "trace_id": "varchar",
    "error_fingerprint": "varchar",
}

VALID_LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]

ALERT_SEVERITIES = ["info", "warning", "critical", "emergency"]

ANOMALY_TYPES = [
    "error_spike", "volume_anomaly", "latency_anomaly",
    "pattern_anomaly", "novel_error"
]

SERVICE_STATUSES = ["active", "inactive", "degraded", "down"]


# SQL query templates
QUERIES = {
    "insert_log": """
        INSERT INTO log_entries (timestamp, level, service_name, message, trace_id, 
                                  span_id, environment, host, metadata, error_fingerprint)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
    """,
    "insert_log_batch": """
        INSERT INTO log_entries (timestamp, level, service_name, message, trace_id,
                                  span_id, environment, host, metadata, error_fingerprint)
        SELECT * FROM unnest($1::timestamptz[], $2::varchar[], $3::varchar[], $4::text[],
                             $5::varchar[], $6::varchar[], $7::varchar[], $8::varchar[],
                             $9::jsonb[], $10::varchar[])
    """,
    "search_logs": """
        SELECT id, timestamp, level, service_name, message, trace_id, span_id,
               environment, host, metadata, error_fingerprint, ingested_at,
               ts_rank(search_vector, query) AS rank
        FROM log_entries, plainto_tsquery('english', $1) query
        WHERE search_vector @@ query
        ORDER BY rank DESC, timestamp DESC
        LIMIT $2 OFFSET $3
    """,
    "count_search": """
        SELECT COUNT(*) 
        FROM log_entries, plainto_tsquery('english', $1) query
        WHERE search_vector @@ query
    """,
    "get_service_health": """
        SELECT * FROM mv_service_health ORDER BY error_rate_pct DESC
    """,
    "get_hourly_stats": """
        SELECT * FROM mv_hourly_stats 
        WHERE hour >= $1 AND hour <= $2
        ORDER BY hour ASC
    """,
    "refresh_views": "SELECT refresh_analytics_views()",
}
