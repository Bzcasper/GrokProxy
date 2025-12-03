# SECURITY NOTICE

## Credential Management

**IMPORTANT**: This repository does NOT contain any real credentials. All sensitive values have been removed and replaced with placeholders.

### Real Credentials Location

Real credentials are stored in:

- **`.env.local.secret`** - Local file (NOT committed to git)
- **Vercel Environment Variables** - For production deployment

### What to Do

1. **Never commit real credentials** to this repository
2. **Use `.env.local.secret`** for local development (already in `.gitignore`)
3. **Use Vercel dashboard** to set production credentials
4. **Rotate cookies regularly** (every 30-60 days)

### Files Cleaned

The following files have had real credentials removed:

- ✅ `.env.production` - Now contains only placeholders
- ✅ `cookies.yaml` - Now contains only placeholders
- ✅ `DEPLOYMENT_CHECKLIST.md` - No real values
- ✅ `COOKIE_SETUP_GUIDE.md` - Examples only

### What NOT to Commit

Never commit files containing:

- Real cookie values (starting with `sso=` followed by actual JWT tokens)
- API keys
- Database passwords
- Any other sensitive credentials

### Safe Practices

1. Always check `git diff` before committing
2. Use `.gitignore` for sensitive files
3. Store credentials in environment variables
4. Use Vercel's environment variable system for deployment
5. Regularly audit repository for leaked credentials

---

**Last Security Audit**: 2025-12-02
**Status**: ✅ All credentials removed and secured
