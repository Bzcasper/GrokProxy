# GrokProxy Cookie-Based Authentication Setup Guide

## Overview

GrokProxy now uses **cookie-based authentication** with automatic rotation. This eliminates the need for API keys and ngrok setup - everything runs directly on Vercel serverless functions.

## How It Works

1. **Load cookies from environment**: System loads `COOKIE_1`, `COOKIE_2`, etc. from Vercel environment variables
2. **Round-robin rotation**: Cookies are rotated automatically between requests
3. **Automatic failure detection**: When a cookie hits rate limits or authentication errors, it's automatically rotated
4. **Health tracking**: Each cookie tracks success/failure counts and error types
5. **Graceful degradation**: System continues to work even if some cookies fail

## Getting Your Grok Cookies

1. Go to [grok.com](https://grok.com) and log in
2. Open DevTools (F12)
3. Go to the **Network** tab
4. Send a message to Grok
5. Find the request to `/rest/app-chat/conversations/new`
6. In the request headers, find the **Cookie** header
7. Copy the value that starts with `sso=` (e.g., `sso=eyJ0eXAiOiJKV1QiLCJ...`)
8. This is your cookie value!

## Setting Up Cookies in Vercel

### Method 1: Via Vercel Dashboard

1. Go to your Vercel project
2. Navigate to **Settings** → **Environment Variables**
3. Add your cookies:
   - **Name**: `COOKIE_1`
   - **Value**: `sso=YOUR_COOKIE_VALUE_HERE`
   - **Environment**: `Production` (or all environments)
4. Click **Save**
5. Repeat for `COOKIE_2`, `COOKIE_3`, etc.

### Method 2: Via Vercel CLI

```bash
# Navigate to your project
cd /home/trapgod/projects/GrokProxy

# Add cookies (you'll be prompted to paste the value)
vercel env add COOKIE_1 production
vercel env add COOKIE_2 production
vercel env add COOKIE_3 production
```

## Configuration Options

Add these to your Vercel environment variables:

```bash
# Required: At least one cookie
COOKIE_1=sso=YOUR_FIRST_COOKIE

# Optional: Additional cookies for rotation
COOKIE_2=sso=YOUR_SECOND_COOKIE
COOKIE_3=sso=YOUR_THIRD_COOKIE

# Optional: Custom user agents per cookie
USER_AGENT_1=Mozilla/5.0 (Windows NT 10.0; Win64; x64)...
USER_AGENT_2=Mozilla/5.0 (Macintosh; Intel Mac OS X)...

# Cookie rotation settings
COOKIE_FAILURE_THRESHOLD=3    # Number of failures before marking unhealthy
COOKIE_ROTATION_ENABLED=true  # Enable/disable rotation
```

## Testing Your Setup

### 1. Deploy to Vercel

```bash
cd /home/trapgod/projects/GrokProxy
vercel --prod
```

### 2. Test Health Endpoint

```bash
# Replace with your Vercel URL
VERCEL_URL="https://your-app.vercel.app"

curl $VERCEL_URL/health
```

Expected response:

```json
{
  "status": "healthy",
  "mode": "cookieonly",
  "environment": "vercel-serverless",
  "database": "not_configured",
  "cookies": {
    "total_cookies": 1,
    "healthy_cookies": 1,
    "rotation_enabled": true
  },
  "message": "Running with cookie-based rotation only"
}
```

### 3. Test Chat Completion

```bash
curl -X POST $VERCEL_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [
      {"role": "user", "content": "Hello! Say hi back."}
    ]
  }'
```

### 4. Check Cookie Statistics

```bash
curl $VERCEL_URL/admin/cookies
```

Expected response:

```json
{
  "total_cookies": 1,
  "healthy_cookies": 1,
  "rotation_enabled": true,
  "failure_threshold": 3,
  "cookies": [
    {
      "index": 0,
      "healthy": true,
      "success_count": 1,
      "failure_count": 0,
      "last_used": "2025-12-02T18:50:00Z",
      "error_types": {},
      "cookie_preview": "sso=eyJ0eXAiOiJKV1Qi..."
    }
  ]
}
```

## How Cookie Rotation Works

### Automatic Rotation Triggers

The system automatically rotates to the next cookie when:

1. **HTTP 429** (Rate Limit) - Cookie hit rate limit
2. **HTTP 401/403** (Authentication Failed) - Cookie expired or invalid
3. **"rate limit" in error message** - Detected in response text
4. **"unauthorized/expired" in error message** - Authentication issues
5. **3+ consecutive failures** - Cookie marked unhealthy (default threshold)

### Rotation Algorithm

```
1. Get next cookie (round-robin)
2. Try request with this cookie
3. If successful:
   - Mark cookie as healthy
   - Reset failure count
   - Return response
4. If failed:
   - Mark cookie with error type (rate_limit, auth_failed, etc.)
   - Increment failure count
   - Try next cookie
5. Repeat until all cookies exhausted or success
```

### Cookie Health States

- **Healthy**: `failure_count < failure_threshold`
- **Unhealthy**: `failure_count >= failure_threshold`
- **Fallback**: If no healthy cookies, tries any cookie as last resort

## Multiple Cookie Strategy

### Why Use Multiple Cookies?

1. **Higher throughput**: Distribute requests across multiple accounts
2. **Rate limit resilience**: When one cookie hits rate limit, use another
3. **Redundancy**: If one cookie expires, others keep working
4. **Load balancing**: Round-robin ensures even distribution

### Best Practices

- **3-5 cookies**: Good balance for most use cases
- **Different accounts**: Use separate Grok accounts for each cookie
- **Monitor health**: Check `/admin/cookies` regularly
- **Rotate manually**: Replace expired cookies via Vercel dashboard
- **Update together**: If updating cookies, do all at once to avoid version mismatch

## Monitoring & Troubleshooting

### View Cookie Statistics

```bash
curl https://your-app.vercel.app/admin/cookies
```

### Common Issues

#### Issue: "No cookies configured"

**Cause**: `COOKIE_1` environment variable not set

**Solution**:

1. Go to Vercel dashboard → Settings → Environment Variables
2. Add `COOKIE_1` with your cookie value
3. Redeploy or wait for next function invocation

#### Issue: "All cookies failed authentication"

**Cause**: All cookies have expired

**Solution**:

1. Get fresh cookies from grok.com (see "Getting Your Grok Cookies" above)
2. Update `COOKIE_1`, `COOKIE_2`, etc. in Vercel dashboard
3. Redeploy or wait for next function invocation

#### Issue: "All cookies exhausted due to rate limits"

**Cause**: All cookies hit rate limits simultaneously

**Solution**:

1. Add more cookies to distribute load
2. Implement request throttling on client side
3. Wait for rate limits to reset (usually a few minutes)

### Viewing Logs

```bash
# Real-time logs
vercel logs --follow

# Look for cookie rotation events
vercel logs | grep "Cookie"
```

## Security Best Practices

1. ✅ **Never commit cookies**: Keep `.env` in `.gitignore`
2. ✅ **Use Vercel secrets**: Store cookies as environment variables
3. ✅ **Rotate regularly**: Update cookies every 30-60 days
4. ✅ **Monitor usage**: Check `/admin/cookies` for suspicious activity
5. ✅ **Limit access**: Use API passwords for `/admin/*` endpoints

## Database (Optional)

The database is now **optional**. Without a database:

- ✅ Cookie rotation works perfectly
- ✅ All API endpoints function normally
- ❌ No analytics/logging
- ❌ No generation history

To enable database logging:

1. Set `DATABASE_URL` in Vercel environment variables
2. System will automatically log requests
3. View history at `/admin/generations`

## Advanced Configuration

### Custom Failure Thresholds

```bash
# Allow more failures before marking unhealthy
COOKIE_FAILURE_THRESHOLD=5
```

### Disable Rotation (Testing Only)

```bash
# Use only COOKIE_1, never rotate
COOKIE_ROTATION_ENABLED=false
```

### Custom User Agents

```bash
# Match user agent to account browser
USER_AGENT_1=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
USER_AGENT_2=Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

## API Endpoints

### Public Endpoints

- `GET /` - Homepage
- `GET /health` - Health check with cookie stats
- `POST /v1/chat/completions` - Chat with automatic cookie rotation
- `POST /v1/images/generations` - Image generation
- `GET /v1/models` - List available models

### Admin Endpoints

- `GET /admin/cookies` - Detailed cookie statistics
- `GET /admin/sessions` - Database sessions (if DB enabled)
- `GET /admin/generations` - Request history (if DB enabled)

## Support

If you encounter issues:

1. Check `/health` endpoint for cookie status
2. Check `/admin/cookies` for detailed stats
3. View Vercel logs: `vercel logs --follow`
4. Verify cookie format: should start with `sso=`
5. Ensure cookies are fresh (< 30 days old)

---

**You're all set!** Your GrokProxy is now running 100% on Vercel with automatic cookie rotation. No more ngrok, no more local server! 🎉
