# Cookie Refresh Guide for GrokProxy

## Why Cookies Need Refreshing

Cloudflare's `cf_clearance` cookie expires periodically (typically every 1-2 hours). When this happens, you'll see:

```
"Request rejected by anti-bot rules" (403 error)
```

## How to Get Fresh Cookies

### Method 1: Browser DevTools (Recommended)

1. **Open Grok.com in your browser**

   - Visit https://grok.com and log in
   - Wait for the page to fully load

2. **Open DevTools**

   - Press `F12` or right-click → "Inspect"
   - Go to the "Application" tab (Chrome) or "Storage" tab (Firefox)

3. **Copy Cookies**

   - Navigate to: Cookies → https://grok.com
   - Copy these cookies (right-click → Copy value):
     - `sso`
     - `sso-rw`
     - `cf_clearance`
     - `x-userid`
     - `x-anonuserid`
     - `x-challenge`
     - `x-signature`
     - `i18nextLng`
     - `mp_ea93da913ddb66b6372b89d97b1029ac_mixpanel`
     - `_ga`
     - `_ga_8FEWB057YH`

4. **Format as Cookie String**
   Combine all cookies in this format:

   ```
   name1=value1; name2=value2; name3=value3
   ```

5. **Update cookies.yaml**
   Replace the cookie string in `cookies.yaml`:

   ```yaml
   cookies:
     - "your-complete-cookie-string-here"
   ```

6. **Restart Services**
   ```bash
   docker compose restart grokproxy
   ```

### Method 2: Using Cookie Export Extension

1. Install "EditThisCookie" or "Cookie-Editor" browser extension
2. Visit https://grok.com (logged in)
3. Click the extension icon
4. Export cookies as Netscape format
5. Convert to the format needed for `cookies.yaml`

## Quick Cookie Update Script

Save this as `update_cookies.sh`:

```bash
#!/bin/bash
# Quick cookie update helper

echo "Paste your new cookie string (press Ctrl+D when done):"
read -d '' COOKIE_STRING

# Backup current cookies
cp cookies.yaml cookies.yaml.backup

# Update cookies.yaml
cat > cookies.yaml << EOF
cookies:
  - "$COOKIE_STRING"

password: "Bcmoney69$"

rate_limit:
  delay_seconds: 1.0

user_agent:
  - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
  - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
EOF

echo "✓ Cookies updated!"
echo "Restarting services..."
docker compose restart grokproxy

echo "✓ Done! Test with: curl http://localhost:8080/health"
```

## Verification

After updating cookies, test the proxy:

```bash
# Health check
curl http://localhost:8080/health

# Full API test
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer Bcmoney69$" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-latest",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## Troubleshooting

### Still Getting 403 Errors?

- Make sure you're logged into Grok.com when copying cookies
- Verify all required cookies are included
- Check that cookies aren't URL-encoded (should be plain text)
- Try using a different browser or incognito mode

### Cookies Expire Too Quickly?

- This is normal Cloudflare behavior
- Consider setting up automated cookie refresh
- Use multiple cookie sets for rotation

## Automated Cookie Refresh (Advanced)

For production use, consider:

1. Using Puppeteer/Playwright to automate browser sessions
2. Implementing a cookie refresh service
3. Setting up monitoring to detect expired cookies
4. Rotating between multiple valid cookie sets
