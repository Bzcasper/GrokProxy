# GrokProxy Vercel Deployment Guide

Complete guide to deploying GrokProxy to Vercel as a serverless application.

---

## 📋 Prerequisites

### Required Accounts

1. **Vercel Account** - [Sign up](https://vercel.com/signup)
2. **Neon PostgreSQL** - Already configured ✅
3. **Upstash Redis** - [Sign up](https://console.upstash.com/) (Free tier available)
4. **Cloudinary** (Optional) - [Sign up](https://cloudinary.com/users/register/free)

### Local Requirements

```bash
# Install Vercel CLI
npm install -g vercel

# Or use pnpm
pnpm add -g vercel
```

---

## 🚀 Quick Deployment

### 1. Setup Upstash Redis

```bash
# Go to https://console.upstash.com/
# 1. Create new database
# 2. Select region closest to your Vercel deployment
# 3. Copy REST URL and Token
```

### 2. Configure Environment Variables

Create `.env` file or add to Vercel dashboard:

```bash
# Required
DATABASE_URL=postgresql://...  # Your Neon URL
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...
API_PASSWORD=your-secure-password

# Optional
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

### 3. Deploy to Vercel

```bash
# Login to Vercel
vercel login

# Deploy (first time)
cd /home/trapgod/projects/GrokProxy
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name: grokproxy
# - Directory: ./
# - Override settings? No

# Deploy to production
vercel --prod
```

---

## 📝 Detailed Setup

### Step 1: Prepare Code

```bash
# Ensure all files are committed
cd /home/trapgod/projects/GrokProxy
git add .
git commit -m "Prepare for Vercel deployment"
```

### Step 2: Configure Vercel Project

```bash
# Initialize Vercel project
vercel

# This creates .vercel directory with project config
```

### Step 3: Set Environment Variables

**Option A: Via Vercel CLI**

```bash
# Set production environment variables
vercel env add DATABASE_URL production
vercel env add UPSTASH_REDIS_REST_URL production
vercel env add UPSTASH_REDIS_REST_TOKEN production
vercel env add API_PASSWORD production
```

**Option B: Via Vercel Dashboard**

1. Go to your project settings
2. Navigate to "Environment Variables"
3. Add each variable from `.env.production`
4. Select "Production" environment

### Step 4: Import Sessions

Before first deployment, import your sessions to the database:

```bash
# Run locally (connects to Neon)
export $(cat .env | grep -v '^#' | xargs)
python -m session_manager.import_cookies --file cookies.yaml
```

### Step 5: Deploy

```bash
# Deploy to preview
vercel

# Test the preview URL
curl https://your-deployment-preview.vercel.app/health

# Deploy to production
vercel --prod
```

---

## 🧪 Testing Deployment

### Test Health Endpoint

```bash
# Replace with your Vercel URL
VERCEL_URL="https://your-app.vercel.app"

# Health check
curl $VERCEL_URL/health

# Expected response:
# {
#   "status": "healthy",
#   "environment": "serverless",
#   "database": "connected"
# }
```

### Test Chat Endpoint

```bash
curl -X POST $VERCEL_URL/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Test Rate Limiting

```bash
# Make multiple requests quickly
for i in {1..35}; do
  curl -s $VERCEL_URL/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_PASSWORD" \
    -H "Content-Type: application/json" \
    -d '{"model":"grok-3","messages":[{"role":"user","content":"hi"}]}' \
    | jq -r '.error.message // "OK"'
done

# Should see "Rate limit exceeded" after ~30 requests
```

---

## ⚙️ Configuration

### Vercel Project Settings

**Build Settings**:

- Framework Preset: Other
- Build Command: (leave empty)
- Output Directory: (leave empty)
- Install Command: `pip install -r requirements.txt`

**Function Settings**:

- Region: `iad1` (or closest to your users)
- Max Duration: 60 seconds
- Memory: 1024 MB

### Cron Jobs

Cron jobs are configured in `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/cron/health-check",
      "schedule": "*/5 * * * *" // Every 5 minutes
    },
    {
      "path": "/api/cron/cleanup",
      "schedule": "0 0 * * *" // Daily at midnight
    }
  ]
}
```

**Note**: Cron jobs require Vercel Pro plan ($20/month)

---

## 🔍 Monitoring

### View Logs

```bash
# Real-time logs
vercel logs --follow

# Recent logs
vercel logs
```

### Vercel Dashboard

1. Go to your project dashboard
2. Click "Deployments" to see all deployments
3. Click "Logs" to view function logs
4. Click "Analytics" for usage metrics

### Metrics Endpoint

```bash
# Prometheus metrics
curl $VERCEL_URL/metrics
```

---

## 🐛 Troubleshooting

### Issue: Cold Start Timeout

**Symptom**: First request after inactivity times out

**Solution**:

1. Increase function timeout in `vercel.json`:
   ```json
   "functions": {
     "api/index.py": {
       "maxDuration": 60
     }
   }
   ```
2. Implement warming (ping health endpoint every 5 min)

### Issue: Database Connection Errors

**Symptom**: `asyncpg.exceptions.TooManyConnectionsError`

**Solution**:

1. Reduce connection pool size (already set to 1-3)
2. Check Neon connection limits
3. Upgrade Neon plan if needed

### Issue: Rate Limiting Not Working

**Symptom**: No rate limit headers or limits not enforced

**Solution**:

1. Verify Upstash Redis credentials
2. Check Redis connection in logs
3. Ensure `RATE_LIMIT_ENABLED=true`

### Issue: Import Errors

**Symptom**: `ModuleNotFoundError` in logs

**Solution**:

1. Verify all dependencies in `requirements.txt`
2. Check Python version (should be 3.12)
3. Redeploy: `vercel --prod --force`

---

## 💰 Cost Estimate

### Vercel

- **Hobby**: Free (limited, no cron jobs)
- **Pro**: $20/month (recommended)
  - Unlimited deployments
  - Cron jobs
  - Analytics
  - 100GB bandwidth

### Upstash Redis

- **Free**: 10,000 requests/day
- **Pay-as-you-go**: $0.2 per 100K requests
- **Estimated**: ~$5/month for moderate use

### Neon PostgreSQL

- **Free**: 0.5GB storage, 1 project
- **Launch**: $19/month
  - 10GB storage
  - Autoscaling
  - Point-in-time recovery

### Cloudinary (Optional)

- **Free**: 25GB storage, 25GB bandwidth
- **Plus**: $99/month (if needed)

**Total Monthly Cost**: $0 (free tiers) to $44 (recommended plans)

---

## 🔄 Rollback

### Instant Rollback

```bash
# List deployments
vercel ls

# Rollback to previous deployment
vercel rollback
```

### Via Dashboard

1. Go to Deployments
2. Find previous working deployment
3. Click "..." menu
4. Select "Promote to Production"

---

## 📊 Performance Optimization

### Reduce Cold Starts

1. **Keep Functions Warm**:

   ```bash
   # Use external service to ping every 5 minutes
   curl https://your-app.vercel.app/health
   ```

2. **Optimize Imports**:

   - Move heavy imports inside functions
   - Use lazy loading

3. **Connection Pooling**:
   - Already optimized (1-3 connections)
   - Consider external connection pooler

### Improve Response Time

1. **Enable Caching**:

   ```python
   @app.get("/v1/models")
   async def list_models(response: Response):
       response.headers["Cache-Control"] = "public, max-age=3600"
       return models
   ```

2. **Use Edge Functions** (if available):
   - Move static responses to edge
   - Reduce latency for global users

---

## 🔐 Security Checklist

- [ ] Strong API passwords set
- [ ] Environment variables configured
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Database uses SSL
- [ ] Secrets not in code
- [ ] `.env` in `.gitignore`
- [ ] Vercel authentication enabled

---

## 📚 Additional Resources

- [Vercel Python Documentation](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [Upstash Redis Docs](https://docs.upstash.com/redis)
- [Neon PostgreSQL Docs](https://neon.tech/docs/introduction)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

## ✅ Post-Deployment Checklist

- [ ] Health endpoint returns 200
- [ ] Chat completions work
- [ ] Rate limiting enforced
- [ ] Database queries successful
- [ ] Cron jobs running (check logs)
- [ ] Metrics accessible
- [ ] Logs visible in dashboard
- [ ] Custom domain configured (optional)
- [ ] Monitoring alerts set up
- [ ] Team members added (if applicable)

---

**Your GrokProxy is now deployed to Vercel!** 🎉

Access your API at: `https://your-app.vercel.app`

For support, check the troubleshooting section or Vercel documentation.
