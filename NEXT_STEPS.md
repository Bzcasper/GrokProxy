# GrokProxy - Immediate Next Steps

## Priority 1: Add More Sessions (CRITICAL)

You currently have only **1 session**, which means:
- ⚠️ Single point of failure
- ⚠️ No redundancy if session fails
- ⚠️ Health status shows "degraded"

### How to Add Sessions

**Option A: Via Admin API** (Recommended)
```bash
curl -X POST http://localhost:8000/admin/sessions \
  -H "Authorization: Bearer Bcmoney69$" \
  -H "Content-Type: application/json" \
  -d '{
    "cookie_text": "sso=YOUR_GROK_COOKIE_HERE",
    "provider": "grok"
  }'
```

**Option B: Update cookies.yaml and Re-import**
1. Edit `cookies.yaml` and add more cookies to the list
2. Run: `python -m session_manager.import_cookies --file cookies.yaml`

**Target**: At least 5-10 sessions for production use

---

## Priority 2: Set Up Monitoring

### Install Grafana (Optional but Recommended)

```bash
# Install Grafana
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Access at http://localhost:3000 (admin/admin)
```

### Configure Prometheus Data Source
1. Go to Configuration → Data Sources
2. Add Prometheus
3. URL: `http://localhost:8000/metrics`
4. Save & Test

### Set Up Alerts
Create alerts for:
- Error rate > 5%
- Healthy sessions < 2
- Database connection failures
- Circuit breaker open

---

## Priority 3: Production Deployment

### Option A: Systemd Service (Recommended for VPS)

Create `/etc/systemd/system/grokproxy.service`:
```ini
[Unit]
Description=GrokProxy Production Server
After=network.target

[Service]
Type=simple
User=trapgod
WorkingDirectory=/home/trapgod/projects/GrokProxy
EnvironmentFile=/home/trapgod/projects/GrokProxy/.env
ExecStart=/home/trapgod/projects/GrokProxy/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable grokproxy
sudo systemctl start grokproxy
sudo systemctl status grokproxy
```

### Option B: Docker Compose

Update `docker-compose.yml`:
```yaml
version: '3.8'

services:
  grokproxy:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SESSION_ROTATION_THRESHOLD=500
      - LOG_LEVEL=info
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"\]
      interval: 30s
      timeout: 10s
      retries: 3

  ngrok:
    image: ngrok/ngrok:latest
    command: http grokproxy:8000
    environment:
      - NGROK_AUTHTOKEN=${NGROK_AUTHTOKEN}
    ports:
      - "4040:4040"
    depends_on:
      - grokproxy
```

Start:
```bash
docker compose up -d
```

---

## Priority 4: Enable HTTPS

### Option A: Nginx Reverse Proxy

Install nginx:
```bash
sudo apt-get install nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/grokproxy`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000\;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and get SSL:
```bash
sudo ln -s /etc/nginx/sites-available/grokproxy /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

### Option B: Use Ngrok (Already Configured)

Ngrok automatically provides HTTPS. Just ensure it's running:
```bash
ngrok http 8000 --authtoken=$NGROK_AUTHTOKEN
```

---

## Priority 5: Database Backups

### Automated Backup Script

Create `/home/trapgod/scripts/backup-grokproxy.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/trapgod/backups/grokproxy"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
pg_dump "$DATABASE_URL" > "$BACKUP_DIR/grokproxy_$DATE.sql"

# Compress
gzip "$BACKUP_DIR/grokproxy_$DATE.sql"

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: grokproxy_$DATE.sql.gz"
```

Make executable and schedule:
```bash
chmod +x /home/trapgod/scripts/backup-grokproxy.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/trapgod/scripts/backup-grokproxy.sh
```

---

## Quick Reference Commands

### Server Management
```bash
# Start
nohup python app.py > /tmp/grokproxy.log 2>&1 &

# Stop
pkill -f "python app.py"

# Restart
pkill -f "python app.py" && sleep 2 && nohup python app.py > /tmp/grokproxy.log 2>&1 &

# View logs
tail -f /tmp/grokproxy.log

# View logs (JSON formatted)
tail -f /tmp/grokproxy.log | jq .
```

### Health Checks
```bash
# Overall health
curl http://localhost:8000/health | jq .

# Session stats
curl -H "Authorization: Bearer Bcmoney69$" \
  http://localhost:8000/admin/stats | jq .

# Metrics
curl http://localhost:8000/metrics
```

### Database
```bash
# Connect
psql "$DATABASE_URL"

# Quick stats
psql "$DATABASE_URL" -c "SELECT status, COUNT(*) FROM sessions GROUP BY status;"

# Recent requests
psql "$DATABASE_URL" -c "SELECT request_id, model, status, latency_ms FROM generations ORDER BY created_at DESC LIMIT 10;"
```

---

## Testing Checklist

- [ ] Health endpoint returns 200
- [ ] Chat completion works
- [ ] Metrics endpoint accessible
- [ ] Admin API requires authentication
- [ ] Sessions rotate after threshold
- [ ] Failed sessions get quarantined
- [ ] Database persists all requests
- [ ] Logs are structured JSON
- [ ] Circuit breaker triggers on failures
- [ ] Multiple concurrent requests work

---

## Support

If you encounter issues:
1. Check logs: `tail -f /tmp/grokproxy.log`
2. Check health: `curl http://localhost:8000/health`
3. Check database: `psql "$DATABASE_URL" -c "SELECT 1"`
4. Review RUNBOOK.md for troubleshooting
5. Review SECURITY.md for security concerns

**Your system is production-ready-f "python app.py" && sleep 2 && export $(cat .env | grep -v '^#' | xargs) && . venv/bin/activate && nohup python app.py > /tmp/grokproxy.log 2>&1 & sleep 4 && curl -X POST http://localhost:8000/v1/chat/completions -H "Authorization: Bearer Bcmoney69$" -H "Content-Type: application/json" -d '{"model": "grok-3", "messages": [{"role": "user", "content": "Say hello in one sentence"}]}'* Focus on adding more sessions and monitoring. 🚀
