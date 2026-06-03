-- ============================================
-- LogSentry - Database Schema
-- PostgreSQL 16 with Full-Text Search
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- Users table (for authentication)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer' CHECK (role IN ('admin', 'editor', 'viewer')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default admin user (password: admin123)
-- bcrypt hash for 'admin123'
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@logsentry.io', '$2b$12$LJ3m4ys3Hz.jF4T3EXVOVuDgNqQwof9wn0Xk4f3hZQz0W0h5Afp.i', 'admin')
ON CONFLICT (username) DO NOTHING;

-- ============================================
-- Services registry
-- ============================================
CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    environment VARCHAR(50) DEFAULT 'production',
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'degraded', 'down')),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================
-- Log entries (main table)
-- ============================================
CREATE TABLE IF NOT EXISTS log_entries (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL CHECK (level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')),
    service_name VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    trace_id VARCHAR(64),
    span_id VARCHAR(32),
    environment VARCHAR(50) DEFAULT 'production',
    host VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    error_fingerprint VARCHAR(64),
    -- Auto-maintained full-text search vector with weighted fields
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(level, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(service_name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(message, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(host, '')), 'C')
    ) STORED,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Indexes for performance
-- ============================================

-- Full-text search GIN index
CREATE INDEX IF NOT EXISTS idx_log_entries_search ON log_entries USING GIN (search_vector);

-- Timestamp index (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_log_entries_timestamp ON log_entries (timestamp DESC);

-- Composite index for filtered queries
CREATE INDEX IF NOT EXISTS idx_log_entries_service_level ON log_entries (service_name, level, timestamp DESC);

-- Service name index
CREATE INDEX IF NOT EXISTS idx_log_entries_service ON log_entries (service_name);

-- Level index
CREATE INDEX IF NOT EXISTS idx_log_entries_level ON log_entries (level);

-- Trace ID for distributed tracing correlation
CREATE INDEX IF NOT EXISTS idx_log_entries_trace ON log_entries (trace_id) WHERE trace_id IS NOT NULL;

-- Error fingerprint for grouping similar errors
CREATE INDEX IF NOT EXISTS idx_log_entries_fingerprint ON log_entries (error_fingerprint) WHERE error_fingerprint IS NOT NULL;

-- JSONB metadata GIN index for flexible queries
CREATE INDEX IF NOT EXISTS idx_log_entries_metadata ON log_entries USING GIN (metadata);

-- Trigram index on message for LIKE/ILIKE queries
CREATE INDEX IF NOT EXISTS idx_log_entries_message_trgm ON log_entries USING GIN (message gin_trgm_ops);

-- ============================================
-- Alerts table
-- ============================================
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),
    service_name VARCHAR(255),
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('threshold', 'pattern', 'anomaly', 'absence')),
    rule_config JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'silenced')),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_service ON alerts (service_name);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);

-- ============================================
-- Anomalies table (ML-detected)
-- ============================================
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    anomaly_type VARCHAR(50) NOT NULL CHECK (anomaly_type IN ('error_spike', 'volume_anomaly', 'latency_anomaly', 'pattern_anomaly', 'novel_error')),
    service_name VARCHAR(255),
    severity_score FLOAT NOT NULL CHECK (severity_score >= 0 AND severity_score <= 1),
    description TEXT,
    features JSONB DEFAULT '{}'::jsonb,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES users(id),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_anomalies_detected ON anomalies (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_service ON anomalies (service_name);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies (anomaly_type);

-- ============================================
-- Materialized views for analytics
-- ============================================

-- Hourly log volume aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_stats AS
SELECT
    date_trunc('hour', timestamp) AS hour,
    service_name,
    level,
    COUNT(*) AS log_count,
    COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL')) AS error_count,
    COUNT(DISTINCT trace_id) AS unique_traces,
    COUNT(DISTINCT error_fingerprint) AS unique_errors
FROM log_entries
GROUP BY date_trunc('hour', timestamp), service_name, level
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_hourly_stats
ON mv_hourly_stats (hour, service_name, level);

-- Service health summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_service_health AS
SELECT
    service_name,
    COUNT(*) AS total_logs_24h,
    COUNT(*) FILTER (WHERE level = 'ERROR') AS errors_24h,
    COUNT(*) FILTER (WHERE level = 'FATAL') AS fatals_24h,
    COUNT(*) FILTER (WHERE level = 'WARN') AS warns_24h,
    ROUND(
        (COUNT(*) FILTER (WHERE level IN ('ERROR', 'FATAL'))::numeric /
        GREATEST(COUNT(*), 1) * 100), 2
    ) AS error_rate_pct,
    MIN(timestamp) AS first_log,
    MAX(timestamp) AS last_log,
    COUNT(DISTINCT error_fingerprint) AS unique_errors
FROM log_entries
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY service_name
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_service_health
ON mv_service_health (service_name);

-- ============================================
-- Functions
-- ============================================

-- Refresh materialized views (called periodically)
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_service_health;
END;
$$ LANGUAGE plpgsql;

-- Auto-update service registry on log insert
CREATE OR REPLACE FUNCTION update_service_registry()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO services (name, last_seen_at, environment)
    VALUES (NEW.service_name, NEW.timestamp, NEW.environment)
    ON CONFLICT (name) DO UPDATE SET
        last_seen_at = GREATEST(services.last_seen_at, EXCLUDED.last_seen_at),
        status = 'active';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_update_service_registry
AFTER INSERT ON log_entries
FOR EACH ROW
EXECUTE FUNCTION update_service_registry();
