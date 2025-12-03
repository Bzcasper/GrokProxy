# GrokProxy Vercel Deployment Checklist

## Prerequisites

- [x] GrokProxy code with cookie rotation system
- [x] At least one valid Grok cookie (you have COOKIE_1 set in Vercel)
- [ ] Vercel account with project configured
- [ ] Vercel CLI installed (optional)

---

## Deployment Steps

### 1. Verify Cookie in Vercel Dashboard

Go to: https://vercel.com/your-username/grokproxy/settings/environment-variables

Check that you have:

- ✅ `COOKIE_1` set with value `sso=YOUR_COOKIE_VALUE_HERE`

Optional (add if you have multiple cookies):

- [ ] `COOKIE_2` - Second cookie value
- [ ] `COOKIE_3` - Third cookie value

### 2. Set Optional Configuration (Recommended)

```bash
# Via Vercel Dashboard or CLI
COOKIE_FAILURE_THRESHOLD=3
COOKIE_ROTATION_ENABLED=true
```

### 3. Deploy to Vercel

```bash
cd /home/trapgod/projects/GrokProxy

# Deploy to production
vercel --prod

# Or deploy to preview first
vercel
```

### 4. Test Deployment

Once deployed, get your Vercel URL (e.g., `https://grokproxy.vercel.app`)

**Test Health Endpoint:**

```bash
curl https://your-app.vercel.app/health
```

**Expected Response:**

```json
{
  "status": "healthy",
  "mode": "cookieonly",
  "cookies": {
    "total_cookies": 1,
    "healthy_cookies": 1,
    "rotation_enabled": true
  }
}
```

**Test Chat Endpoint:**

```bash
curl -X POST https://your-app.vercel.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [
      {"role": "user", "content": "Hello! Just testing the system."}
    ]
  }'
```

**Test Cookie Statistics:**

```bash
curl https://your-app.vercel.app/admin/cookies
```

### 5. Monitor Logs

```bash
# Real-time logs
vercel logs --follow

# Look for cookie rotation events
vercel logs | grep "Cookie"
```

---

## Common Issues & Solutions

### Issue: "No cookies configured"

**Solution**:

1. Check Vercel dashboard → Environment Variables
2. Ensure `COOKIE_1` is set with correct format: `sso=YOUR_VALUE`
3. Redeploy: `vercel --prod --force`

### Issue: "All cookies failed authentication"

**Solution**:

1. Cookie may have expired
2. Get a fresh cookie from grok.com (see COOKIE_SETUP_GUIDE.md)
3. Update `COOKIE_1` in Vercel dashboard
4. Redeploy or wait for next cold start

### Issue: Health check shows 0 cookies

**Solution**:

1. Environment variable may not be loading
2. Check exact variable name: must be `COOKIE_1` (not `COOKIE1`)
3. Check value format: must include `sso=` prefix
4. Redeploy with `vercel --prod --force`

---

## Post-Deployment Checklist

- [ ] Health endpoint returns `"status": "healthy"`
- [ ] Chat completions work without errors
- [ ] Cookie statistics show successful requests
- [ ] Logs show cookie rotation events
- [ ] No database errors (database is optional now)

---

## Adding More Cookies (Optional)

To add more cookies for better throughput:

1. Get additional cookies from grok.com (use different accounts)
2. Add to Vercel environment variables:
   ```
   COOKIE_2=sso=another-cookie-value
   COOKIE_3=sso=third-cookie-value
   ```
3. Redeploy
4. Verify in `/admin/cookies` endpoint

---

## Next Steps

Once deployed and working:

1. **Update your applications** to use the Vercel URL instead of ngrok
2. **Monitor cookie health** via `/admin/cookies`
3. **Set up alerts** for when cookies become unhealthy
4. **Rotate cookies periodically** (every 30-60 days recommended)

---

## Support

- **Documentation**: See `COOKIE_SETUP_GUIDE.md`
- **Walkthrough**: See `walkthrough.md` in artifacts
- **Logs**: `vercel logs --follow`
- **Health Check**: `https://your-app.vercel.app/health`
- **Cookie Stats**: `https://your-app.vercel.app/admin/cookies`

---

**Ready to deploy!** 🚀
