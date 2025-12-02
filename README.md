# GrokProxy - Production-Grade Reverse Proxy for xAI/Grok

<div align="center">

![GitHub Repo stars](https://img.shields.io/github/stars/Bzcasper/GrokProxy?style=social)
![License](https://img.shields.io/github/license/Bzcasper/GrokProxy)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)

**A production-ready, OpenAI-compatible reverse proxy for Grok AI with database persistence, automatic session rotation, and comprehensive observability.**

[Features](#-key-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 🎯 Overview

GrokProxy is an enterprise-grade reverse proxy system for xAI/Grok that transforms cookie-based access into a robust, observable, and scalable API service. It provides OpenAI API compatibility, automatic session management, full telemetry tracking, and production-ready resilience patterns.

## ✨ Key Features

### Core Capabilities

- **OpenAI API Compatibility**: Drop-in replacement for OpenAI client libraries
- **Database Persistence**: All requests, sessions, and conversations tracked in PostgreSQL/Neon
- **Automatic Session Rotation**: Intelligent cookie rotation based on usage, failure rate, and age
- **Circuit Breaker**: Automatic failover and recovery for upstream failures
- **Health Checks**: Background monitoring of session pool and database connectivity

### Observability

- **Structured JSON Logging**: Request correlation, automatic PII sanitization
- **Prometheus Metrics**: Request rates, latency percentiles, session health
- **Sentry Integration**: Error tracking with full context
- **Admin API**: RESTful endpoints for session management and statistics

### Security & Compliance

- **API Key Authentication**: Hashed storage, per-user rate limiting
- **Cookie Encryption**: Secure storage with automatic sanitization in logs
- **PII Protection**: Configurable data retention and anonymization
- **Audit Trail**: Complete request/response history for compliance

## 🏗️ Architecture

```mermaid
graph TB
    Client[Client Application] -->|HTTP/JSON| Proxy[GrokProxy FastAPI]
    Proxy -->|Acquire Session| SM[Session Manager]
    SM -->|Query/Update| DB[(Neon Postgres)]
    Proxy -->|Forward Request| Grok[Grok API]
    Proxy -->|Record Metrics| Prom[Prometheus]
    Proxy -->|Log Events| Sentry[Sentry]
    SM -->|Health Check Loop| DB

    style Proxy fill:#4CAF50
    style DB fill:#2196F3
    style SM fill:#FF9800
```

### Components

| Component           | Purpose                         | Technology          |
| ------------------- | ------------------------------- | ------------------- |
| **FastAPI Proxy**   | API gateway, request validation | FastAPI, Pydantic   |
| **Session Manager** | Cookie pool, rotation logic     | AsyncIO, PostgreSQL |
| **Database Layer**  | Persistence, queries            | asyncpg, Neon       |
| **Observability**   | Logging, metrics, tracing       | Prometheus, Sentry  |
| **Resilience**      | Retry, circuit breaker          | tenacity            |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon recommended for free tier)
- Grok account with valid cookies
- Optional: ngrok for external access

### 1. Clone & Install

```bash
git clone https://github.com/Bzcasper/GrokProxy.git
cd GrokProxy
pip install -r requirements.txt
```

### 2. Setup Database

Create a free Neon database at [neon.tech](https://neon.tech) and copy the connection string.

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your DATABASE_URL
nano .env
```

Run migrations:

```bash
python db/migrate.py
```

### 3. Import Sessions

If you have cookies from the old YAML-based setup:

```bash
python -m session_manager.import_cookies --file cookies.yaml
```

Or manually add sessions via the admin API (see [Admin API](#admin-api)).

### 4. Start Server

```bash
# Development
python app.py

# Production (with Gunicorn)
gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 5. Verify

```bash
# Health check
curl http://localhost:8000/health

# Send test request
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 📊 Configuration

All configuration via environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host.neon.tech:5432/db?sslmode=require
DB_POOL_MIN_SIZE=10
DB_POOL_MAX_SIZE=20

# Authentication
API_PASSWORD=your_api_key_here

# Session Management
SESSION_ROTATION_THRESHOLD=500
SESSION_MAX_AGE_HOURS=24
SESSION_FAILURE_THRESHOLD=0.2
SESSION_HEALTH_CHECK_INTERVAL=30

# Observability
LOG_LEVEL=info
SENTRY_DSN=https://...@sentry.io/...
METRICS_ENABLED=true

# Optional
NGROK_AUTHTOKEN=your_ngrok_token
```

See [`.env.example`](.env.example) for full reference.

## 🔌 API Usage

### Chat Completions

```python
import openai

client = openai.OpenAI(
    api_key="YOUR_API_KEY",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="grok-3",
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ]
)

print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="grok-3",
    messages=[{"role": "user", "content": "Write a poem"}],
    stream=True
)

for chunk in stream:
    print(chunk.choices[0].delta.content, end="")
```

## 🛠️ Admin API

Manage sessions programmatically (requires admin API key):

```bash
# List all sessions
curl -H "Authorization: Bearer ADMIN_KEY" \
  http://localhost:8000/admin/sessions

# Add new session
curl -X POST -H "Authorization: Bearer ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"cookie_text": "sso=...", "provider": "grok"}' \
  http://localhost:8000/admin/sessions

# Quarantine session
curl -X PATCH -H "Authorization: Bearer ADMIN_KEY" \
  http://localhost:8000/admin/sessions/{id}/quarantine?reason=manual

# Get statistics
curl -H "Authorization: Bearer ADMIN_KEY" \
  http://localhost:8000/admin/stats
```

## 📈 Monitoring

### Prometheus Metrics

Metrics available at `/metrics`:

- `grokproxy_requests_total`: Total requests by endpoint/status
- `grokproxy_generation_latency_seconds`: Generation latency histogram
- `grokproxy_active_sessions`: Session count by status
- `grokproxy_session_rotations_total`: Rotation events by reason

### Grafana Dashboard

Import the included dashboard ([grafana/dashboard.json](grafana/dashboard.json)) for visualization.

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Returns:

```json
{
  "status": "healthy",
  "components": [
    {
      "name": "database",
      "status": "healthy",
      "message": "Database connection OK"
    },
    {
      "name": "session_pool",
      "status": "healthy",
      "details": {
        "total": 10,
        "healthy": 8,
        "quarantined": 1,
        "expired": 1
      }
    }
  ]
}
```

## 🐳 Docker Deployment

### Docker Compose (Recommended)

```bash
docker compose up -d
```

Access the service:

- Proxy: http://localhost:8080
- Metrics: http://localhost:8080/metrics
- Ngrok dashboard: http://localhost:4040

### Kubernetes

See [`k8s/`](k8s/) directory for manifests:

```bash
kubectl apply -f k8s/
```

## 📚 Documentation

- [RUNBOOK.md](RUNBOOK.md) - Operational guide for on-call engineers
- [SECURITY.md](SECURITY.md) - Security considerations and compliance
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migrating from YAML to Postgres sessions
- [API.md](API.md) - Complete API reference

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
docker compose -f tests/docker-compose.test.yml up -d
pytest tests/integration/ -v
docker compose -f tests/docker-compose.test.yml down

# Load testing
locust -f tests/load_test.py
```

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## ⚠️ Disclaimer

This project is for educational and personal use only. Users are responsible for complying with xAI's Terms of Service and all applicable laws. The authors assume no liability for misuse.

## 🙏 Acknowledgments

- Original GrokProxy by [CNFlyCat](https://github.com/CNFlyCat/GrokProxy)
- xAI for the Grok API
- FastAPI and asyncpg communities

---

<div align="center">

**[⬆ Back to Top](#grokproxy---production-grade-reverse-proxy-for-xaigrok)**

Made with ❤️ by the GrokProxy contributors

</div>
