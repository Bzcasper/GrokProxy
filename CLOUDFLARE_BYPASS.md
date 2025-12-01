# GrokProxy Cloudflare Bypass Guide

## 🛡️ Cloudflare Bypass Features

Your GrokProxy now includes comprehensive Cloudflare bypass mechanisms to handle rate limiting, challenges, and IP-based blocking.

---

## ✨ Features Implemented

### 1. Enhanced Cloudflare Headers

Added authentic browser headers that match real Chrome 131 requests:

```python
cloudflare_headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "upgrade-insecure-requests": "1"
}
```

### 2. Progressive Retry Logic

**Handles these HTTP status codes:**

- `429` - Rate Limit
- `503` - Service Unavailable / Cloudflare Challenge
- `401/403` - Authentication Failed / Expired Cookies

**Progressive backoff delays:**

```python
retry_delays = [2, 5, 10, 20, 30]  # seconds
```

**Behavior:**

- Attempt 1 fails → Wait 2s
- Attempt 2 fails → Wait 5s
- Attempt 3 fails → Wait 10s
- Attempt 4 fails → Wait 20s
- Attempt 5 fails → Wait 30s

### 3. Rate Limiting

**Automatic delay between requests** (default: 1 second)

Prevents rate limiting by spacing out requests automatically.

### 4. cf_clearance Token Detection

Your cookies already include `cf_clearance` token:

```
cf_clearance=_b7Lw7fa54OqkMs9E2safg5.HsSP...
```

The proxy now:

- ✅ Automatically extracts and uses it
- ✅ Logs when it's present (debug mode)
- ✅ Warns when expired/missing

### 5. Proxy Support

**Optional residential/datacenter proxy support** for IP-based blocking.

---

## ⚙️ Configuration

### Rate Limiting Adjustment

Edit [`cookies.yaml`](file:///home/trapgod/projects/GrokProxy/cookies.yaml):

```yaml
rate_limit:
  delay_seconds: 1.0 # Adjust as needed (0.5 - 5.0 seconds)
```

**Recommendations:**

- Light usage: `0.5s`
- Normal usage: `1.0s` (default)
- Heavy usage / rate-limited: `2.0s - 5.0s`

### Proxy Configuration

#### Single Proxy

Uncomment and configure in `cookies.yaml`:

```yaml
proxy:
  enabled: true
  url: "http://username:password@proxy-server.com:port"
```

**Supported proxy types:**

- HTTP: `http://user:pass@host:port`
- HTTPS: `https://user:pass@host:port`
- SOCKS5: `socks5://user:pass@host:port`

#### Multiple Proxies (Future Enhancement)

```yaml
# Not yet implemented - coming soon
proxies:
  - "http://user:pass@proxy1.com:8080"
  - "http://user:pass@proxy2.com:8080"
  - "http://user:pass@proxy3.com:8080"
```

---

## 🚨 Cloudflare Challenge Detection

The proxy automatically detects and logs Cloudflare challenges:

### Warning Signs in Logs

**503 with Cloudflare challenge:**

```
ERROR - Cloudflare challenge detected (503). May need fresh cookies.
```

**401/403 with Cloudflare protection:**

```
ERROR - Cloudflare protection triggered. cf_clearance may be expired.
```

### What to Do

1. **Get fresh cookies:**

   - Visit `https://grok.com` in your browser
   - Open DevTools (F12) → Network tab
   - Send a message to Grok
   - Find the `new` or `responses` request
   - Copy the entire `Cookie` header value
   - Update `cookies.yaml`

2. **Check cf_clearance expiry:**

   - Cloudflare clearance tokens typically expire after 30-60 minutes
   - Some may last 24 hours
   - Update when you see auth failures

3. **Use a proxy if IP-blocked:**
   - Enable proxy in `cookies.yaml`
   - Use residential proxies for best results
   - Datacenter proxies may also work

---

## 📊 Monitoring Logs

### Successful Request

```
INFO - Sending request to Grok API (attempt 1/5)
DEBUG - Using cf_clearance: _b7Lw7fa54OqkMs9E2s...
INFO - ✓ Request successful (200 OK)
INFO - ✓ Stream completed successfully (245 tokens)
```

### Rate Limited

```
WARNING - Rate limit hit (429), waiting 5s before retry...
INFO - Credentials rotated to next cookie
```

### Cloudflare Challenge

```
ERROR - Cloudflare challenge detected (503). May need fresh cookies.
```

### Using Proxy

```
INFO - Using proxy: proxy-server.com:8080
INFO - GrokRequest initialized with Cloudflare bypass features
```

---

## 🔧 Troubleshooting

### Issue: Getting 429 Rate Limits

**Solutions:**

1. Increase `rate_limit.delay_seconds` to `2.0` or higher
2. Add more cookies to rotation
3. Enable proxy with residential IPs

### Issue: Getting 503 Cloudflare Challenges

**Solutions:**

1. Update `cf_clearance` token (get fresh cookies)
2. Use residential proxy
3. Ensure user agent matches browser used to get cookies

### Issue: Getting 401/403 Authentication Errors

**Solutions:**

1. Check if cookies have expired (re-extract from browser)
2. Verify all cookie parts are present (sso, cf_clearance, x-challenge, etc.)
3. Ensure cookies aren't truncated in YAML file

### Issue: Proxy Not Working

**Solutions:**

1. Verify proxy URL format: `http://user:pass@host:port`
2. Test proxy independently first
3. Check if proxy requires authentication
4. Try different proxy type (HTTP vs SOCKS5)

---

## 📝 Best Practices

### 1. Cookie Management

- **Rotate multiple cookies** for longer uptime
- **Update cookies weekly** or when auth fails
- **Keep backup cookies** in case of bans

### 2. Rate Limiting

- **Start with default** (1.0s delay)
- **Increase if rate-limited** (2.0s - 5.0s)
- **Monitor logs** for rate limit warnings

### 3. Proxy Usage

- **Use residential proxies** for best results
- **Rotate proxy IPs** if available
- **Test proxy latency** before production use

### 4. Monitoring

- **Enable DEBUG logging** when troubleshooting
- **Watch for cf_clearance warnings**
- **Monitor retry counts** in logs

---

## 🎯 Example Configuration

### Optimal Setup for Heavy Usage

```yaml
cookies:
  - "sso=token1; cf_clearance=clearance1; ..."
  - "sso=token2; cf_clearance=clearance2; ..."
  - "sso=token3; cf_clearance=clearance3; ..."

password: "Bcmoney69$"

proxy:
  enabled: true
  url: "http://user:pass@residential-proxy.com:8080"

rate_limit:
  delay_seconds: 2.0 # Higher delay for safety

user_agent:
  # 10 diverse user agents rotating automatically
  - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
  - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ..."
  # ... etc
```

---

## 🔐 Security Notes

- **Never commit cookies to git** (already in .gitignore)
- **Rotate passwords regularly**
- **Use environment variables** for sensitive proxy credentials
- **Monitor logs** for unauthorized access attempts

---

## 📚 References

**Related Files:**

- [`grok.py`](file:///home/trapgod/projects/GrokProxy/grok.py) - Core request handler with Cloudflare bypass
- [`cookies.yaml`](file:///home/trapgod/projects/GrokProxy/cookies.yaml) - Configuration file
- [`openairequest.py`](file:///home/trapgod/projects/GrokProxy/openairequest.py) - FastAPI application

**Cloudflare Bypass Features:**

- ✅ Authentic browser headers
- ✅ Progressive retry with backoff
- ✅ Rate limiting enforcement
- ✅ cf_clearance token handling
- ✅ Proxy support
- ✅ Automatic credential rotation
- ✅ Challenge detection
