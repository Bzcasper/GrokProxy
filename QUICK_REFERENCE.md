# GrokProxy - Quick Reference

## What Was Implemented

✅ **Proxy Mode** - Vercel forwards requests to your local Docker instance  
✅ **Database Optional** - No more 503 errors on Vercel  
✅ **Auto Ngrok Updates** - Background service syncs ngrok URL to Vercel  
✅ **Vercel API Utility** - Easy environment variable management

---

## Quick Commands

### Check Current Status

```bash
# Local proxy status
curl http://localhost:8080/health

# Ngrok URL
curl -s http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'

# Vercel health (after deployment)
curl https://your-app.vercel.app/health
```

### Deploy with Auto-Updater

```bash
# 1. Configure updater
cp ngrok_updater_config.yaml.template ngrok_updater_config.yaml
# Edit with your Vercel credentials

# 2. Build updater image
docker build -f Dockerfile.updater -t grokproxy-updater .

# 3. Start all services
docker-compose -f docker-compose.full.yml --profile with-updater up -d

# 4. Watch updater logs
docker logs -f grokproxy-ngrok-updater
```

### Manual Vercel Update

```bash
# Get current ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

# Update Vercel
export VERCEL_API_TOKEN="your-token"
export VERCEL_PROJECT_ID="your-project-id"

python scripts/update_vercel_env.py \
  --key NGROK_PROXY_URL \
  --value "$NGROK_URL"
```

---

## Vercel Environment Variables

Set these in Vercel Dashboard (Settings → Environment Variables):

```bash
# Required for proxy mode
PROXY_MODE=true
NGROK_PROXY_URL=  # Auto-updated by ngrok-updater

# Optional - leave empty for proxy mode
DATABASE_URL=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=

# Keep these
CLOUDINARY_CLOUD_NAME=dpciejkg5
CLOUDINARY_API_KEY=961336647366346
CLOUDINARY_API_SECRET=8Za1XuTXfdbvXi3j_UrpziuWGfE
ELEVENLABS_API_KEY=sk_892e7c2338fd899e456d871239958968f79912b8774b396e
```

---

## File Structure

```
GrokProxy/
├── api/
│   ├── index.py              # ✏️ Modified - database optional, proxy mode
│   ├── proxy_mode.py         # ✨ New - proxy client
│   └── ...
├── scripts/
│   └── update_vercel_env.py  # ✨ New - Vercel API utility
├── ngrok_updater.py          # ✨ New - auto-update service
├── ngrok_updater_config.yaml # ✨ New - configuration
├── docker-compose.full.yml   # ✨ New - complete Docker setup
├── Dockerfile.updater        # ✨ New - updater Dockerfile
├── .env.production           # ✏️ Modified - proxy mode vars
└── NGROK_UPDATER_SETUP.md    # ✨ New - setup guide
```

---

## Architecture

### Proxy Mode (Current)

```
Client → Vercel → Ngrok → Local Docker → Grok API
         ↑
         └── NGROK_PROXY_URL (auto-updated)
```

### Full Mode (Future)

```
Client → Vercel → Database → Session Manager → Grok API
```

---

## Next Steps

1. **Get Vercel credentials** (see NGROK_UPDATER_SETUP.md)
2. **Configure ngrok_updater_config.yaml**
3. **Set Vercel environment variables**
4. **Deploy updater service**
5. **Test end-to-end**

---

## Documentation

- **Setup Guide**: [NGROK_UPDATER_SETUP.md](file:///home/trapgod/projects/GrokProxy/NGROK_UPDATER_SETUP.md)
- **Diagnostic Report**: [diagnostic_report.md](file:///home/trapgod/.gemini/antigravity/brain/47128cd1-2465-48e6-9bb8-2a34f8795ce6/diagnostic_report.md)
- **Implementation Plan**: [implementation_plan.md](file:///home/trapgod/.gemini/antigravity/brain/47128cd1-2465-48e6-9bb8-2a34f8795ce6/implementation_plan.md)
- **Walkthrough**: [walkthrough.md](file:///home/trapgod/.gemini/antigravity/brain/47128cd1-2465-48e6-9bb8-2a34f8795ce6/walkthrough.md)

---

## Troubleshooting

**Vercel still showing 503?**

- Check if `PROXY_MODE=true` is set
- Verify `NGROK_PROXY_URL` is set (can be empty initially)
- Check Vercel deployment logs

**Updater not working?**

- Verify Vercel API token is correct
- Check ngrok API is accessible: `curl http://localhost:4040/api/tunnels`
- View updater logs: `docker logs grokproxy-ngrok-updater`

**Proxy not forwarding?**

- Verify ngrok URL is accessible
- Check local Docker is running
- Test local endpoint: `curl http://localhost:8080/health`
