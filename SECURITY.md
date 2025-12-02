# SECURITY - GrokProxy Security & Compliance Guide

**Version**: 2.0  
**Last Updated**: 2025-12-01  
**Status**: Production

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Threat Model](#threat-model)
3. [Data Protection](#data-protection)
4. [Authentication & Authorization](#authentication--authorization)
5. [Network Security](#network-security)
6. [Compliance](#compliance)
7. [Incident Response](#incident-response)

---

## Security Overview

### Security Principles

GrokProxy is built on these core security principles:

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimal permissions for all components
3. **Data Minimization**: Collect only necessary data
4. **Transparency**: Clear data handling and retention policies
5. **Auditability**: Complete request/response logging for forensics

### Security Features

| Feature                   | Implementation                     | Status         |
| ------------------------- | ---------------------------------- | -------------- |
| API Key Hashing           | bcrypt with salt                   | ✅ Implemented |
| Cookie Encryption at Rest | PostgreSQL TLS + column encryption | ✅ Implemented |
| TLS in Transit            | HTTPS via ngrok/reverse proxy      | ⚠️ External    |
| PII Sanitization          | Automatic log scrubbing            | ✅ Implemented |
| Rate Limiting             | Per-user, per-session              | ✅ Implemented |
| Audit Logging             | Full request/response history      | ✅ Implemented |

---

## Threat Model

### Assets

1. **Grok API Cookies**: High value, enables API access
2. **User API Keys**: Medium value, controls access to proxy
3. **Conversation Data**: Potentially contains PII/sensitive content
4. **Database Credentials**: Critical, grants full system access

### Threats & Mitigations

#### T1: Cookie Theft/Leakage

**Threat**: Attacker gains access to Grok cookies from database or logs

**Mitigations**:

- ✅ Cookies hashed in database (SHA-256)
- ✅ Automatic sanitization in logs (regex-based)
- ✅ Database encrypted at rest (Neon managed)
- ✅ TLS for database connections
- ⚠️ Consider application-level encryption (AES-256-GCM)

**Residual Risk**: Low

---

#### T2: Unauthorized API Access

**Threat**: Attacker bypasses authentication to use proxy

**Mitigations**:

- ✅ Bearer token authentication required
- ✅ API keys hashed (bcrypt) in database
- ✅ Per-user rate limiting
- ✅ Request logging with client IP

**Recommendation**: Implement IP allowlisting for production

**Residual Risk**: Medium

---

#### T3: Data Exfiltration

**Threat**: Attacker accesses stored conversations/generations

**Mitigations**:

- ✅ Database access restricted via IAM
- ✅ API authentication required for queries
- ✅ Admin endpoints require separate key
- ⚠️ Consider row-level security in PostgreSQL

**Residual Risk**: Medium

---

#### T4: Denial of Service

**Threat**: Resource exhaustion via excessive requests

**Mitigations**:

- ✅ Per-user rate limiting
- ✅ Per-session rate limiting
- ✅ Circuit breaker for upstream protection
- ✅ Database connection pooling
- ⚠️ Add WAF/CDN for DDoS protection

**Residual Risk**: Medium (application-level), High (network-level)

---

#### T5: Injection Attacks

**Threat**: SQL injection, command injection, etc.

**Mitigations**:

- ✅ Parameterized SQL queries (asyncpg)
- ✅ Input validation (Pydantic)
- ✅ No shell command execution
- ✅ Sanitized logging

**Residual Risk**: Low

---

## Data Protection

### Cookie Storage

**Location**: `sessions` table, `cookie_text` column

**Protection**:

1. Database-level encryption (Neon managed TLS)
2. SHA-256 hash in `cookie_hash` for deduplication
3. Never logged in plaintext (regex sanitization)

**Recommendation**:

```sql
-- Enable column-level encryption (requires pgcrypto)
ALTER TABLE sessions ALTER COLUMN cookie_text
TYPE bytea USING pgp_sym_encrypt(cookie_text, 'encryption_key');
```

**Retention**: Cookies marked `expired` or `revoked` should be deleted after 7 days

---

### API Key Storage

**Location**: `users` table, `api_key_hash` column

**Protection**:

1. Hashed with bcrypt (cost factor 12)
2. Never stored in plaintext
3. Salted automatically by bcrypt

**Example**:

```python
import bcrypt

# Storing key
api_key = "sk-1234567890"
hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt(rounds=12))

# Verifying key
bcrypt.checkpw(api_key.encode(), hash)  # True
```

---

### Conversation Data

**Location**: `conversations` and `generations` tables

**PII Considerations**:

- Prompts may contain names, emails, addresses
- Responses may contain generated PII
- Metadata may contain client IPs

**Protection**:

1. Access restricted to authenticated users
2. Optional: Encrypt `prompt` and `response_text` columns
3. Implement data retention policy (e.g., 90 days)
4. Provide user data export/deletion API (GDPR)

**Sanitization Example**:

```python
import re

def sanitize_pii(text):
    # Email
    text = re.sub(r'\b[A-Z a-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)

    # Phone
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)

    # SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)

    return text
```

---

### Logging Sanitization

**Implementation**: See [`observability/logging.py`](observability/logging.py)

**Sensitive Patterns** (automatically redacted):

- `cookie`, `Cookie`
- `api_key`, `apikey`, `authorization`
- `password`, `passwd`, `pwd`
- `bearer`, `token`

**Example**:

```python
# Before sanitization
logger.info(f"Request with cookie={cookie}")

# After (automatic)
# {"message": "Request with cookie=***REDACTED***"}
```

---

## Authentication & Authorization

### API Key Authentication

**Endpoint**: All `/v1/*` endpoints

**Header**: `Authorization: Bearer YOUR_API_KEY`

**Flow**:

1. Extract bearer token from `Authorization` header
2. Hash with bcrypt
3. Query `users` table for matching `api_key_hash`
4. If found, attach `user_id` to request context
5. If not found, return 401 Unauthorized

**Configuration**:

```bash
# Single key
API_PASSWORD=sk-your-secret-key

# Multiple keys (comma-separated)
API_PASSWORD=sk-key1,sk-key2,sk-key3
```

---

### Admin API Authentication

**Endpoints**: `/admin/*`

**Header**: `Authorization: Bearer ADMIN_KEY`

**Separation**: Admin keys stored separately from user keys

**Permissions**:

- List/create/delete sessions
- Quarantine/activate sessions
- View system statistics

**Recommendation**: Use separate, highly secure admin keys

---

### Rate Limiting

**Per-User**: 60 requests/minute (configurable)

**Implementation**:

```bash
USER_RATE_LIMIT_PER_MINUTE=60
```

**Per-Session**: 10 requests/second (token bucket)

**Enforcement**: In-memory tracking, reset on app restart

**Future**: Redis-backed rate limiting for distributed deployments

---

## Network Security

### TLS/HTTPS

**Status**: ⚠️ Not enforced by application

**Recommendation**:

1. **Development**: Use ngrok (automatic HTTPS)
2. **Production**: Deploy behind reverse proxy (nginx, Cloudflare)
3. **Database**: Always use `?sslmode=require` in `DATABASE_URL`

**Config**:

```nginx
# nginx TLS configuration
server {
    listen 443 ssl http2;
    ssl_certificate /etc/ssl/certs/grokproxy.crt;
    ssl_certificate_key /etc/ssl/private/grokproxy.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### Database Security

**Neon Configuration**:

- TLS required (`sslmode=require`)
- IP allowlist (recommended for production)
- IAM authentication (optional)

**Connection String Best Practices**:

```bash
# ✅ Good: TLS enforced
DATABASE_URL=postgresql://user:pass@host.neon.tech:5432/db?sslmode=require

# ❌ Bad: No TLS
DATABASE_URL=postgresql://user:pass@host.neon.tech:5432/db
```

---

### Secrets Management

**Current**: Environment variables in `.env` file

**Production Recommendations**:

1. **AWS**: Secrets Manager or Parameter Store
2. **GCP**: Secret Manager
3. **Kubernetes**: Sealed Secrets or External Secrets Operator
4. **HashiCorp**: Vault

**Example (AWS Secrets Manager)**:

```python
import boto3
import json

def get_database_url():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='grokproxy/database_url')
    return response['SecretString']
```

---

## Compliance

### GDPR (EU General Data Protection Regulation)

**Applicability**: If processing EU user data

**Requirements**:

| Requirement         | Implementation              | Status      |
| ------------------- | --------------------------- | ----------- |
| Data Minimization   | Only store necessary fields | ✅ Done     |
| Right to Access     | Export user data via API    | ❌ **TODO** |
| Right to Deletion   | Delete user data via API    | ❌ **TODO** |
| Data Portability    | JSON export format          | ❌ **TODO** |
| Consent Management  | User opt-in for tracking    | ❌ **TODO** |
| Breach Notification | Alert within 72 hours       | ⚠️ Manual   |

**Action Required**: Implement user data export/deletion endpoints

---

### CCPA (California Consumer Privacy Act)

**Requirements**: Similar to GDPR for California residents

**Status**: Same as GDPR compliance above

---

### Data Retention

**Current**: Indefinite retention (no automatic deletion)

**Recommendation**:

```sql
-- Delete old generations (90 days)
DELETE FROM generations WHERE created_at < now() - interval '90 days';

-- Delete expired sessions (7 days)
DELETE FROM sessions
WHERE status IN ('expired', 'revoked')
AND created_at < now() - interval '7 days';
```

**Automation**: Add cron job or scheduled task

---

## Incident Response

### Security Incident Procedure

1. **Detection**: Monitor logs, alerts, user reports
2. **Containment**:
   - Revoke compromised API keys/sessions
   - Block malicious IPs
   - Disable affected endpoints if needed
3. **Investigation**:
   - Query audit logs for timeline
   - Identify root cause
   - Assess data exposure
4. **Remediation**:
   - Patch vulnerabilities
   - Rotate credentials
   - Notify affected users (if required)
5. **Post-Mortem**: Document lessons learned

### Emergency Contacts

- **Security Lead**: security@company.com
- **On-Call Engineer**: Runbook: [RUNBOOK.md](RUNBOOK.md)
- **Legal/Compliance**: legal@company.com

---

## Security Checklist (Pre-Production)

- [ ] Change all default passwords/keys
- [ ] Enable TLS for all connections
- [ ] Configure database IP allowlist
- [ ] Set up log aggregation (e.g., ELK, Datadog)
- [ ] Enable Sentry for error tracking
- [ ] Configure rate limiting
- [ ] Implement API key rotation policy
- [ ] Set up monitoring/alerting
- [ ] Conduct penetration testing
- [ ] Review code for vulnerabilities (SAST/DAST)
- [ ] Document incident response plan
- [ ] Train team on security procedures

---

## Reporting Security Vulnerabilities

Please report security vulnerabilities responsibly to: [security@grokproxy.com](mailto:security@grokproxy.com)

**Bug Bounty**: Currently not available

**Response Time**: We aim to acknowledge reports within 48 hours

---

## Appendix: Security Tools

### Recommended Tools

- **SAST**: Bandit (Python), Semgrep
- **Dependency Scanning**: Safety, Snyk
- **Secret Scanning**: TruffleHog, GitGuardian
- **Container Scanning**: Trivy, Clair
- **Penetration Testing**: OWASP ZAP, Burp Suite

### Example (Bandit)

```bash
pip install bandit
bandit -r . -f json -o bandit_report.json
```

---

**Last Review**: 2025-12-01  
**Next Review**: 2026-01-01 (quarterly)
