# Multi-Account Cookie Rotation Guide

## Adding Multiple Accounts

To add cookies from other Grok accounts for automatic rotation:

### Step 1: Get Cookies from Each Account

For each account you want to add:

1. **Log in to grok.com** with that account
2. **Send a test message** in the chat
3. **Open browser console** and look for the captured request
4. **Copy the complete cookie string** (including `sso`, `sso-rw`, `cf_clearance`, etc.)

### Step 2: Add to cookies.yaml

Edit `cookies.yaml` and add each cookie string to the `cookies` array:

```yaml
cookies:
  # Account 1
  - "cookie_string_from_account_1"

  # Account 2
  - "cookie_string_from_account_2"

  # Account 3
  - "cookie_string_from_account_3"
```

### Step 3: Restart the Service

```bash
docker compose restart grokproxy
```

## How Rotation Works

The system automatically rotates through accounts when:

1. **Rate limits are hit** (429 error)
2. **Authentication fails** (401/403 errors)
3. **Anti-bot detection** triggers

### Rotation Strategy

- Starts with the first account
- On error, waits with progressive backoff (2s, 5s, 10s, 20s, 30s)
- Rotates to the next account in the list
- Wraps around to the first account after the last one

### Benefits

✅ **Higher throughput** - Multiple accounts = more requests  
✅ **Better reliability** - If one account is rate-limited, use another  
✅ **Automatic failover** - Seamless switching between accounts  
✅ **Load distribution** - Spreads requests across accounts

## Monitoring

Check logs to see rotation in action:

```bash
docker compose logs -f grokproxy | grep "Cookie rotation"
```

You'll see:

```
Cookie rotation: 1/3  # Using account 1 of 3
Cookie rotation: 2/3  # Switched to account 2
Cookie rotation: 3/3  # Switched to account 3
```

## Best Practices

1. **Use different accounts** - Don't use the same account multiple times
2. **Keep cookies fresh** - Refresh all accounts periodically (every 1-2 hours)
3. **Monitor rotation** - Watch logs to ensure all accounts are working
4. **Start with 2-3 accounts** - Test before adding more
5. **Different user agents** - The system automatically rotates user agents too

## Troubleshooting

**All accounts failing?**

- Cookies may be expired - refresh them all
- Check if Grok has new anti-bot measures

**One account keeps failing?**

- That account's cookies may be expired
- Remove it temporarily and refresh later

**Too many rotations?**

- Increase `rate_limit.delay_seconds` in cookies.yaml
- Add more accounts to distribute load
