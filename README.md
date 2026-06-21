# 🔍Distributed Task Analysis System

<div align="center">

**A scalable, enterprise-grade observability platform for collecting, processing, analyzing, and monitoring application logs in real time across distributed services.**

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-red?style=for-the-badge&logo=redis)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?style=for-the-badge&logo=docker)](https://docker.com)

</div>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Dashboard (:8080)                     │
│                    Glassmorphism Dark Theme UI                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    API Gateway (:8000)                            │
│              JWT Auth │ Routing │ WebSocket/SSE                   │
└───────┬──────────┬─────────┬──────────┬────────────────────────┘
        │          │         │          │
┌───────┴───┐ ┌───┴────┐ ┌──┴──────┐ ┌┴──────────────┐
│ Ingestion │ │ Query  │ │ Anomaly │ │ Log Simulator  │
│  (:8001)  │ │ Engine │ │   ML    │ │  (Demo Data)   │
│           │ │(:8004) │ │ (:8003) │ │                │
└─────┬─────┘ └───┬────┘ └───┬─────┘ └────────────────┘
      │            │          │
┌─────┴────────────┴──────────┴───┐
│        Redis Streams + Pub/Sub   │
│         (Message Queue)          │
└─────────────┬───────────────────┘
              │
┌─────────────┴───────────────────┐
│        Log Processor (:8002)     │
│   Enrichment │ Storage │ Alerts  │
└─────────────┬───────────────────┘
              │
┌─────────────┴───────────────────┐
│    PostgreSQL 16 (Full-Text      │
│    Search + JSONB + Analytics)   │
└─────────────────────────────────┘
```

## ✨ Features

### Core Platform
- 🔄 **Real-time Log Ingestion** — Multi-format log intake (JSON, syslog, plain text, Apache/Nginx)
- 🔍 **Full-Text Search** — PostgreSQL GIN indexes with weighted ranking and highlighting
- 📊 **Time-Series Analytics** — Log volume, error rates, latency trends with configurable intervals
- 🏥 **Service Health Monitoring** — Per-service health scores, error budgets, status tracking
- 🔔 **Alert System** — Rule-based alerts (threshold, pattern, spike, absence detection)
- 📤 **Data Export** — CSV and JSON export of search results

### Machine Learning
- 🤖 **Isolation Forest** — Multivariate anomaly detection on service metrics
- 📈 **Statistical Detection** — Z-score, EWMA, and spike detection on time-series data
- 🧬 **Pattern Analysis** — TF-IDF + DBSCAN clustering for novel log pattern discovery
- ⚡ **Real-time Scoring** — Continuous anomaly scoring with automatic alerting

### Enterprise Features
- 🔐 **JWT Authentication** — Secure login/register with role-based access control
- 📡 **Live Log Tailing** — WebSocket + SSE for real-time log streaming
- 🎯 **Distributed Tracing** — Trace ID correlation across services
- 🐳 **Containerized Deployment** — Full Docker Compose orchestration
- 🎨 **Premium Dashboard** — Glassmorphism dark theme with Chart.js visualizations

## 🚀 Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- 4GB RAM minimum
- 4 CPU cores recommended

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env to customize settings (defaults work for local dev)
```

### 2. Launch

```bash
docker-compose up -d
```

### 3. Access

| Service | URL |
|---------|-----|
| 🎨 **Dashboard** | http://localhost:8080 |
| 🔗 **API Gateway** | http://localhost:8000 |
| 📖 **API Docs** | http://localhost:8000/docs |
| 🐘 **PostgreSQL** | localhost:5432 |
| 🔴 **Redis** | localhost:6379 |

### 4. Login

Default credentials:
- **Username:** `admin`
- **Password:** `admin123`

The log simulator starts automatically and generates realistic log data from 5 simulated microservices.

## 📁 Project Structure

```
logsentry/
├── docker-compose.yml           # Full stack orchestration
├── .env.example                 # Environment template
├── database/
│   └── init.sql                 # PostgreSQL schema + FTS indexes
├── shared/                      # Shared libraries
│   ├── schemas/log_entry.py     # Pydantic schemas
│   └── database/                # DB connection pool
├── services/
│   ├── api-gateway/             # Auth + Routing (FastAPI :8000)
│   ├── log-ingestion/           # Log intake (FastAPI :8001)
│   ├── log-processor/           # Async processing (FastAPI :8002)
│   ├── anomaly-detection/       # ML models (FastAPI :8003)
│   ├── query-engine/            # Search + Analytics (FastAPI :8004)
│   └── log-simulator/           # Demo data generator
└── dashboard/                   # Web UI (Vanilla JS + CSS)
```

## 🔌 API Reference

### Authentication
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","email":"user1@example.com","password":"password123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Log Ingestion
```bash
# Single log
curl -X POST http://localhost:8000/api/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"level":"ERROR","service_name":"my-app","message":"Connection timeout"}'

# Batch (up to 1000)
curl -X POST http://localhost:8000/api/ingest/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"logs":[{"level":"INFO","service_name":"my-app","message":"Started"}]}'
```

### Search & Analytics
```bash
# Full-text search
curl "http://localhost:8000/api/search?q=error+timeout&service_name=payment-service&level=ERROR" \
  -H "Authorization: Bearer $TOKEN"

# Time-series analytics
curl "http://localhost:8000/api/analytics/timeseries?interval=1h&service_name=auth-service" \
  -H "Authorization: Bearer $TOKEN"

# Dashboard stats
curl "http://localhost:8000/api/analytics/dashboard-stats" \
  -H "Authorization: Bearer $TOKEN"
```

### Anomaly Detection
```bash
# List anomalies
curl "http://localhost:8000/api/anomalies" \
  -H "Authorization: Bearer $TOKEN"

# Trigger model retraining
curl -X POST "http://localhost:8000/api/anomalies/train" \
  -H "Authorization: Bearer $TOKEN"
```

## 🧪 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | FastAPI | Async Python web framework |
| **Message Queue** | Redis Streams | High-throughput log pipeline |
| **Primary Storage** | PostgreSQL 16 | Logs + FTS + Analytics |
| **Cache/Pub-Sub** | Redis 7 | Caching, real-time pub/sub |
| **ML Engine** | scikit-learn | Anomaly detection models |
| **Frontend** | Vanilla JS + CSS | Premium dashboard SPA |
| **Charts** | Chart.js | Data visualization |
| **Auth** | JWT (python-jose) | Stateless authentication |
| **Container** | Docker Compose | Development orchestration |

## 📊 ML Anomaly Detection

LogSentry uses three complementary ML approaches:

1. **Isolation Forest** — Detects multivariate anomalies across metrics (error rate, log volume, response time, unique errors)
2. **Statistical Methods** — Z-score and EWMA for time-series spike detection
3. **Pattern Analysis** — TF-IDF + DBSCAN discovers novel log patterns and unusual messages

Models retrain automatically every 6 hours on the latest 7 days of data.

## 🛠️ Development

```bash
# Start in development mode (with hot-reload)
docker-compose up

# Rebuild a specific service
docker-compose build log-processor
docker-compose up -d log-processor

# View logs for a service
docker-compose logs -f api-gateway

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <strong>Built with ❤️ for observability</strong>
</div>
