# Vercel Environment Variables Setup Guide

## Quick Setup via Vercel Dashboard

Go to your Vercel project settings:
**https://vercel.com/[your-username]/grokproxy/settings/environment-variables**

Add these environment variables for **Production**:

### Required Variables

```bash
# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://neondb_owner:...@ep-soft-queen-a4znups6-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require

# API Authentication
API_PASSWORD=Bcmoney69$

# Cloudinary (Image Storage)
CLOUDINARY_CLOUD_NAME=dpciejkg5
CLOUDINARY_API_KEY=961336647366346
CLOUDINARY_API_SECRET=8Za1XuTXfdbvXi3j_UrpziuWGfE

# ElevenLabs (Voice)
ELEVENLABS_API_KEY=sk_892e7c2338fd899e456d871239958968f79912b8774b396e
```

### Optional Variables

```bash
# Redis (Upstash) - for rate limiting
UPSTASH_REDIS_REST_URL=https://your-db.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token

# Admin password (if different from API_PASSWORD)
ADMIN_PASSWORD=your-admin-password

# Sentry (error tracking)
SENTRY_DSN=your-sentry-dsn

# Configuration
LOG_LEVEL=info
JSON_LOGGING=true
RATE_LIMIT_ENABLED=true
```

---

## Setup via Vercel CLI

If you have Vercel CLI installed:

```bash
cd /home/trapgod/projects/GrokProxy

# Run the setup script
./scripts/setup-vercel-env.sh

# Or manually add each variable:
vercel env add DATABASE_URL production
vercel env add API_PASSWORD production
vercel env add CLOUDINARY_CLOUD_NAME production
vercel env add CLOUDINARY_API_KEY production
vercel env add CLOUDINARY_API_SECRET production
vercel env add ELEVENLABS_API_KEY production
```

---

## After Adding Variables

1. **Redeploy** your project in Vercel dashboard
2. Or trigger a new deployment:

   ```bash
   vercel --prod
   ```

3. **Test** the deployment:
   ```bash
   curl https://your-app.vercel.app/health
   ```

---

## Security Notes

✅ **DO**: Add to Vercel dashboard  
✅ **DO**: Keep in local `.env` file  
❌ **DON'T**: Commit to git  
❌ **DON'T**: Share publicly

The `.env` file is already in `.gitignore` to prevent accidental commits.
