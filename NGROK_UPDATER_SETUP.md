# Dynamic Ngrok URL Updates - Setup Guide

This guide explains how to set up automatic ngrok URL updates for your Vercel deployment.

## Overview

The system has three components:

1. **Local Docker** - Runs GrokProxy with cookie-based authentication
2. **Ngrok Tunnel** - Exposes local service publicly
3. **Vercel Deployment** - Acts as a proxy to your local instance

When your ngrok URL changes (e.g., after restart), the updater service automatically updates the Vercel environment variable and triggers a redeployment.

---

## Quick Start

### Step 1: Get Vercel Credentials

1. **Get your Vercel API Token**

   - Go to: https://vercel.com/account/tokens
   - Click "Create Token"
   - Name it: `GrokProxy Updater`
   - Scope: **Read and Write**
   - Expiration: Set as needed
   - Copy the token

2. **Get your Project ID**

   - Go to your project: https://vercel.com/[username]/[project-name]/settings
   - Scroll to "Project ID"
   - Copy the ID

3. **Get Team ID** (optional, only if using Vercel Teams)
   - Go to: https://vercel.com/teams/[team-name]/settings
   - Copy the Team ID

### Step 2: Configure the Updater

1. Copy the template configuration:

   ```bash
   cp ngrok_updater_config.yaml.template ngrok_updater_config.yaml
   ```

2. Edit `ngrok_updater_config.yaml`:

   ```yaml
   vercel:
     api_token: "your-actual-vercel-token-here"
     project_id: "your-actual-project-id-here"
     team_id: "" # Leave empty if not using teams
     env_var_name: "NGROK_PROXY_URL"

   ngrok:
     api_url: "http://grokproxy-ngrok:4040/api/tunnels"
     poll_interval: 30

   logging:
     level: "INFO"
   ```

### Step 3: Update Vercel Environment Variables

Set these in your Vercel dashboard (Settings → Environment Variables):

```bash
# Required for proxy mode
PROXY_MODE=true
NGROK_PROXY_URL=  # Will be auto-updated by the service

# Optional - leave empty for proxy mode
DATABASE_URL=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
```

Or use the CLI tool:

```bash
# Install dependencies
pip install httpx

# Set environment variables
export VERCEL_API_TOKEN="your-token"
export VERCEL_PROJECT_ID="your-project-id"

# Update PROXY_MODE
python scripts/update_vercel_env.py --key PROXY_MODE --value true

# Create NGROK_PROXY_URL (will be updated automatically)
python scripts/update_vercel_env.py --key NGROK_PROXY_URL --value ""
```

### Step 4: Deploy with Updater Service

#### Option A: Using Docker Compose (Recommended)

```bash
# Build the updater image
docker build -f Dockerfile.updater -t grokproxy-updater .

# Start all services including updater
docker-compose -f docker-compose.full.yml --profile with-updater up -d

# View updater logs
docker logs -f grokproxy-ngrok-updater
```

#### Option B: Run Updater Separately

```bash
# Install dependencies
pip install httpx pyyaml

# Run the updater
python ngrok_updater.py
```

### Step 5: Verify Setup

1. **Check ngrok URL**:

   ```bash
   curl http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'
   ```

2. **Check updater logs**:

   ```bash
   docker logs grokproxy-ngrok-updater
   ```

   You should see:

   ```
   [2025-12-02 13:00:00] [INFO] Starting ngrok updater service (polling every 30s)
   [2025-12-02 13:00:01] [INFO] Ngrok URL changed: None -> https://xxxxx.ngrok-free.app
   [2025-12-02 13:00:02] [INFO] Successfully updated NGROK_PROXY_URL to https://xxxxx.ngrok-free.app
   ```

3. **Check Vercel deployment**:

   - Go to Vercel dashboard
   - Check if `NGROK_PROXY_URL` is set
   - Verify a new deployment was triggered

4. **Test the proxy**:

   ```bash
   # Test via Vercel
   curl https://your-app.vercel.app/health

   # Should return:
   {
     "status": "healthy",
     "mode": "proxy",
     "ngrok_url": "https://xxxxx.ngrok-free.app"
   }
   ```

---

## Manual Updates

If you need to manually update the Vercel environment variable:

```bash
# Get current ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

# Update Vercel
python scripts/update_vercel_env.py \
  --key NGROK_PROXY_URL \
  --value "$NGROK_URL"
```

---

## Troubleshooting

### Updater Not Working

1. **Check configuration**:

   ```bash
   cat ngrok_updater_config.yaml
   ```

   Verify API token and project ID are correct.

2. **Check ngrok API**:

   ```bash
   curl http://localhost:4040/api/tunnels
   ```

   Should return tunnel information.

3. **Check updater logs**:

   ```bash
   docker logs grokproxy-ngrok-updater
   ```

   Look for error messages.

4. **Test Vercel API manually**:
   ```bash
   python scripts/update_vercel_env.py --list
   ```
   Should list all environment variables.

### Vercel Deployment Not Updating

1. **Check if env var changed**:

   - Go to Vercel dashboard
   - Settings → Environment Variables
   - Check `NGROK_PROXY_URL` value

2. **Manually trigger deployment**:

   - Go to Deployments tab
   - Click "Redeploy"

3. **Check deployment logs**:
   - Look for errors in build/runtime logs

### Proxy Not Working

1. **Check health endpoint**:

   ```bash
   curl https://your-app.vercel.app/health
   ```

   Should return `"mode": "proxy"`.

2. **Check ngrok URL is accessible**:

   ```bash
   curl https://xxxxx.ngrok-free.app/health
   ```

3. **Check Vercel logs**:
   - Go to Deployments → Latest → Runtime Logs
   - Look for proxy errors

---

## Architecture Diagrams

### Request Flow

```
Client Request
    ↓
Vercel (your-app.vercel.app)
    ↓
Proxy Mode Handler
    ↓
Ngrok Tunnel (xxxxx.ngrok-free.app)
    ↓
Local Docker (localhost:8080)
    ↓
GrokProxy → Grok API
    ↓
Response back to client
```

### Update Flow

```
Ngrok Restarts (new URL)
    ↓
Ngrok Updater detects change
    ↓
Calls Vercel API
    ↓
Updates NGROK_PROXY_URL env var
    ↓
Vercel auto-redeploys
    ↓
New deployment uses new URL
```

---

## Advanced Configuration

### Change Polling Interval

Edit `ngrok_updater_config.yaml`:

```yaml
ngrok:
  poll_interval: 60 # Check every 60 seconds
```

### Update Multiple Projects

Create separate config files:

```bash
# Project 1
python ngrok_updater.py --config project1_config.yaml

# Project 2
python ngrok_updater.py --config project2_config.yaml
```

### Use Different Environment Variable Name

Edit `ngrok_updater_config.yaml`:

```yaml
vercel:
  env_var_name: "MY_CUSTOM_NGROK_URL"
```

Then update your Vercel deployment to read from this variable.

---

## Security Notes

1. **Keep API tokens secure**:

   - Never commit `ngrok_updater_config.yaml` to Git
   - Add it to `.gitignore`
   - Use environment variables in production

2. **Limit token scope**:

   - Only grant "Read and Write" permissions
   - Consider using project-specific tokens

3. **Rotate tokens regularly**:
   - Update tokens every 90 days
   - Revoke old tokens after rotation

---

## Next Steps

Once the automatic updater is working:

1. **Optional: Set up database** for full mode

   - Create Neon PostgreSQL database
   - Update `DATABASE_URL` in Vercel
   - Disable `PROXY_MODE`

2. **Monitor performance**:

   - Check Vercel analytics
   - Monitor response times
   - Track error rates

3. **Set up alerts**:
   - Use Vercel integrations
   - Monitor updater service health
   - Alert on failed updates
