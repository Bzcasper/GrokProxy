# Quick Start: Deploy to Vercel

## Prerequisites

1. Vercel account
2. Upstash Redis account (free tier)
3. Neon PostgreSQL (already configured)

## Steps

### 1. Install Vercel CLI

```bash
npm install -g vercel
```

### 2. Setup Upstash Redis

- Go to https://console.upstash.com/
- Create new database
- Copy REST URL and Token

### 3. Deploy

```bash
cd /home/trapgod/projects/GrokProxy
vercel login
vercel
```

### 4. Set Environment Variables

```bash
vercel env add DATABASE_URL production
vercel env add UPSTASH_REDIS_REST_URL production
vercel env add UPSTASH_REDIS_REST_TOKEN production
vercel env add API_PASSWORD production
```

### 5. Deploy to Production

```bash
vercel --prod
```

### 6. Test

```bash
curl https://your-app.vercel.app/health
```

## See VERCEL_DEPLOYMENT.md for full guide
