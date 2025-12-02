# RUNBOOK - GrokProxy Operations Guide

**Version**: 2.0  
**Last Updated**: 2025-12-01  
**Audience**: On-call engineers, DevOps, SREs

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Common Alerts](#common-alerts)
3. [Troubleshooting](#troubleshooting)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Emergency Procedures](#emergency-procedures)

---

## System Overview

### Architecture Components

- **FastAPI Proxy**: Main API server (port 8000)
- **PostgreSQL/Neon**: Database for sessions, generations, users
- **Session Manager**: Background service managing cookie pool
- **Circuit Breaker**: Protects against upstream failures

### Key Metrics

| Metric                   | Normal Range | Alert Threshold |
| ------------------------ | ------------ | --------------- |
| Request latency (p95)    | < 2s         | > 5s            |
| Error rate               | < 1%         | > 5%            |
| Healthy sessions         | > 3          | < 2             |
| DB connection pool usage | < 80%        | > 90%           |

---

## Common Alerts

### Alert: High Error Rate

**Trigger**: `grokproxy_requests_total{status=~"5.."}` > 5% over 5 minutes

**Symptoms**:

- 500/502/503 responses to clients
- Errors in application logs
- Circuit breaker may be open

**Investigation**:

1. Check circuit breaker state:

   ```bash
   curl http://localhost:8000/health | jq '.components[]'
   ```

2. Review recent error logs:

   ```bash
   docker logs grokproxy --tail=100 | grep '"level":"ERROR"'
   ```

3. Check session pool health:
   ```bash
   curl -H "Authorization: Bearer ADMIN_KEY" \
     http://localhost:8000/admin/stats
   ```

**Remediation**:

- If no healthy sessions: Add new sessions via admin API
- If circuit breaker open: Wait for recovery timeout (60s) or reset manually
- If database errors: Check DATABASE_URL and connection pool

---

### Alert: No Healthy Sessions

**Trigger**: `grokproxy_active_sessions{status="healthy"}` < 2

**Symptoms**:

- 503 errors: "No available sessions"
- All sessions quarantined or expired

**Investigation**:

```bash
# Check session status distribution
curl -H "Authorization: Bearer ADMIN_KEY" \
  http://localhost:8000/admin/sessions | jq '.sessions[] | {id, status, failure_rate}'
```

**Remediation**:

1. **Option A**: Add fresh cookies

   ```bash
   curl -X POST -H "Authorization: Bearer ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{"cookie_text": "sso=NEW_COOKIE_HERE", "provider": "grok"}' \
     http://localhost:8000/admin/sessions
   ```

2. **Option B**: Reactivate quarantined sessions (if cookies still valid)

   ```bash
   SESSION_ID="..."
   curl -X PATCH -H "Authorization: Bearer ADMIN_KEY" \
     http://localhost:8000/admin/sessions/$SESSION_ID/activate
   ```

3. **Option C**: Restart application to reset circuit breaker
   ```bash
   docker compose restart grokproxy
   ```

---

### Alert: High Database Latency

**Trigger**: `grokproxy_db_query_duration_seconds{quantile="0.95"}` > 1s

**Symptoms**:

- Slow API responses
- Database connection pool exhausted
- Timeout errors

**Investigation**:

1. Check database health:

   ```bash
   curl http://localhost:8000/health | jq '.components[] | select(.name=="database")'
   ```

2. Check connection pool metrics:
   ```bash
   curl http://localhost:8000/metrics | grep grokproxy_db_pool_size
   ```

**Remediation**:

- **Immediate**: Increase pool size in `.env`:

  ```bash
  DB_POOL_MAX_SIZE=30
  docker compose restart grokproxy
  ```

- **Long-term**: Review slow queries, add indexes, consider read replicas

---

### Alert: Session Rotation Failures

**Trigger**: No `grokproxy_session_rotations_total` events in 1 hour

**Symptoms**:

- Session manager background task crashed
- Old sessions not being expired

**Investigation**:

```bash
# Check if health check loop is running
docker logs grokproxy | grep "Health check complete"
```

**Remediation**:

```bash
# Restart application
docker compose restart grokproxy

# Verify background task started
docker logs grokproxy --tail=50 | grep "Health check loop started"
```

---

## Troubleshooting

### Symptom: Circuit Breaker Always Open

**Causes**:

- Upstream Grok API down
- All sessions invalid
- Network issues

**Debug Steps**:

1. Test Grok API directly:

   ```bash
   curl -H "Cookie: sso=YOUR_COOKIE" https://grok.x.ai/api/...
   ```

2. Check failure patterns:

   ```bash
   docker logs grokproxy | grep -i "circuit.*open"
   ```

3. Manually reset circuit breaker:
   ```python
   # In Python shell
   from app import circuit_breaker
   circuit_breaker.reset()
   ```

---

### Symptom: Database Connection Refused

**Causes**:

- Neon database paused (free tier)
- Invalid DATABASE_URL
- SSL/TLS configuration

**Debug Steps**:

1. Test connection manually:

   ```bash
   psql "$DATABASE_URL"
   ```

2. Check SSL mode:

   ```bash
   echo $DATABASE_URL | grep sslmode
   # Should contain: ?sslmode=require
   ```

3. Verify Neon project is active in dashboard

**Remediation**:

- Neon free tier auto-pauses after inactivity - any connection will wake it
- Wait 30 seconds for database to resume
- Application will auto-reconnect

---

### Symptom: Memory Leak / High Memory Usage

**Causes**:

- Database connection pool not properly cleaned
- In-flight request tracking accumulation
- Large response bodies

**Debug Steps**:

1. Check memory usage:

   ```bash
   docker stats grokproxy
   ```

2. Profile memory:
   ```bash
   # Install memory_profiler
   pip install memory-profiler
   python -m memory_profiler app.py
   ```

**Remediation**:

- Restart service
- Review DB connection pool settings
- Implement response body size limits

---

## Maintenance Procedures

### Adding New Sessions

```bash
# 1. Obtain fresh Grok cookie
#    (see README for instructions)

# 2. Add via API
curl -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "cookie_text": "sso=...",
    "provider": "grok",
    "metadata": {"source": "manual_add"}
  }' \
  http://localhost:8000/admin/sessions

# 3. Verify
curl -H "Authorization: Bearer $ADMIN_KEY" \
  http://localhost:8000/admin/sessions | jq '.sessions[-1]'
```

### Database Backup

```bash
# Neon provides automatic backups
# Manual backup:
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d).sql

# Restore:
psql "$DATABASE_URL" < backup_YYYYMMDD.sql
```

### Rotating API Keys

```bash
# 1. Add new key to .env
API_PASSWORD=old_key,new_key

# 2. Restart app
docker compose restart grokproxy

# 3. Notify users to update to new key

# 4. After migration period, remove old key
API_PASSWORD=new_key
docker compose restart grokproxy
```

### Upgrading Database Schema

```bash
# 1. Create migration file
cat > db/migrations/002_add_index.sql <<EOF
CREATE INDEX idx_generations_user_created
ON generations(user_id, created_at DESC);
EOF

# 2. Run migration
python db/migrate.py

# 3. Verify
python db/migrate.py --dry
```

---

## Emergency Procedures

### Total System Failure

1. **Stop all services**:

   ```bash
   docker compose down
   ```

2. **Check database accessibility**:

   ```bash
   psql "$DATABASE_URL" -c "SELECT 1;"
   ```

3. **Start in safe mode** (disable background tasks):

   ```bash
   # Temporarily increase health check interval
   export SESSION_HEALTH_CHECK_INTERVAL=999999
   docker compose up -d
   ```

4. **Diagnose** via logs and health endpoint

5. **Restore normal operation**:
   ```bash
   unset SESSION_HEALTH_CHECK_INTERVAL
   docker compose restart grokproxy
   ```

### Emergency Session Injection

If admin API is down but database is accessible:

```sql
-- Connect to database
psql "$DATABASE_URL"

-- Insert session directly
INSERT INTO sessions (cookie_text, cookie_hash, provider, status)
VALUES (
  'sso=YOUR_COOKIE_HERE',
  encode(sha256('sso=YOUR_COOKIE_HERE'::bytea), 'hex'),
  'grok',
  'healthy'
);
```

### Rollback to Previous Version

```bash
# Using Docker
docker compose down
docker tag grokproxy:current grokproxy:backup
docker pull grokproxy:previous
docker compose up -d

# Manual
git checkout v1.9.0
pip install -r requirements.txt
python app.py
```

---

## Contact Information

- **On-call rotation**: [PagerDuty link]
- **Slack channel**: #grokproxy-alerts
- **Escalation**: devops-lead@company.com

## Related Documentation

- [Architecture Decision Records](docs/adr/)
- [Database Schema](db/migrations/)
- [API Documentation](API.md)
