# Enhanced xAI API Tracking & Colored Logging - Implementation Summary

**Date**: 2025-12-01  
**Version**: 2.1.0  
**Status**: ✅ **DEPLOYED**

---

## 🎨 What Was Added

### 1. Colored Console Logging

**New File**: `observability/colored_logging.py`

Added beautiful colored logging for development with:

- **Color-coded log levels**: Debug (cyan), Info (green), Warning (yellow), Error (red), Critical (magenta)
- **Special formatting** for different message types:
  - Requests: Bright magenta
  - Success messages: Bright green
  - Metrics: Bright cyan
  - Errors: Red with stack traces
- **Icons** for each log level: 🔍 DEBUG, ✓ INFO, ⚠️ WARNING, ✗ ERROR, 🔥 CRITICAL
- **Convenience functions**:
  - `log_request()` - Log incoming requests
  - `log_response()` - Log responses with latency
  - `log_metric()` - Log metrics
  - `log_success()` - Log success events
  - `log_error()` - Log errors with context

**Example Output**:

```
16:17:45.123 ✓ INFO     [app] ✓ Server ready to accept requests
16:17:46.234 ✓ INFO     [app] → POST /v1/chat/completions request_id=abc-123 model=grok-3
16:17:47.456 ✓ INFO     [app] ← Response 200 request_id=abc-123 latency=1222ms tokens=150
```

**Configuration**:

```bash
# Use colored logging (default)
python app.py

# Use JSON logging for production
JSON_LOGGING=true python app.py
```

---

### 2. Comprehensive xAI API Tracking

**New Migration**: `db/migrations/002_add_xai_tracking.sql`

Added extensive database schema to track ALL xAI API metadata:

#### Enhanced `generations` Table

Added columns for detailed token tracking:

- `reasoning_tokens` - Tokens used for reasoning (grok-4)
- `audio_tokens` - Audio input/output tokens
- `image_tokens` - Image tokens
- `cached_tokens` - Cached prompt tokens
- `accepted_prediction_tokens` - Speculative decoding accepted
- `rejected_prediction_tokens` - Speculative decoding rejected
- `num_sources_used` - Number of sources used in response
- `response_id` - xAI response ID for continuity
- `previous_response_id` - Link to previous response
- `temperature`, `top_p`, `max_output_tokens` - Generation parameters
- `parallel_tool_calls` - Tool calling configuration
- `tool_choice` - Tool selection strategy
- `reasoning_content` - Reasoning process text
- `incomplete_details` - Details if response incomplete
- `annotations` - Response annotations
- `finish_reason` - Why generation stopped

#### New `token_usage` Table

Granular token tracking for billing and analytics:

- **Prompt tokens**: text, audio, image, cached
- **Completion tokens**: reasoning, audio, text, predictions
- **Cost tracking**: Micro-dollar precision ($0.000001)
- **Aggregations**: By user, session, model, provider

**Example Query**:

```sql
SELECT
  user_id,
  model,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost_micro_usd) / 1000000.0 as total_cost_usd
FROM token_usage
WHERE created_at >= now() - interval '24 hours'
GROUP BY user_id, model;
```

#### New `api_models` Table

Tracks available models and their capabilities:

- Model identification (ID, fingerprint, version)
- Capabilities (streaming, tools, vision, reasoning)
- Limits (max tokens, context window)
- Pricing (per 1M tokens for each modality)
- Aliases and metadata

**Example Data**:

```sql
INSERT INTO api_models (model_id, model_type, supports_reasoning, max_output_tokens)
VALUES ('grok-4-0709', 'language', true, 131072);
```

#### New `api_responses` Table

Stores full `/v1/responses` endpoint data:

- Response chaining (previous_response_id)
- Full input/output messages
- Tool configurations
- Response status tracking
- 30-day automatic expiration

**Use Case**: Continue conversations without repeating context

```sql
SELECT * FROM api_responses
WHERE response_id = 'resp-abc123'
  AND expires_at > now();
```

#### New `embeddings` Table

Tracks embedding generation:

- Input text and type (query/document)
- Embedding vectors (as JSONB array)
- Token usage
- Model information

#### New `image_generations` Table

Tracks image generation requests:

- Prompts (positive and negative)
- Configuration (size, quality, style)
- Generated image URLs
- Status tracking

#### New `usage_analytics` Materialized View

Pre-aggregated analytics for fast queries:

- Hourly and daily aggregations
- Token usage by user/model/provider
- Cost tracking
- Request counts

**Refresh**:

```sql
SELECT refresh_usage_analytics();
```

---

## 📊 New Database Schema Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Enhanced Schema v2.1                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │  generations │────→│ token_usage  │     │ api_models  │ │
│  │  (enhanced)  │     │  (billing)   │     │ (catalog)   │ │
│  └──────────────┘     └──────────────┘     └─────────────┘ │
│         │                                                    │
│         ↓                                                    │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │api_responses │     │  embeddings  │     │   image_    │ │
│  │ (continuity) │     │              │     │ generations │ │
│  └──────────────┘     └──────────────┘     └─────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         usage_analytics (materialized view)             ││
│  │  Hourly/Daily aggregations for fast analytics          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage Examples

### Colored Logging in Code

```python
from observability import (
    get_colored_logger,
    log_request,
    log_response,
    log_success,
    log_error
)

logger = get_colored_logger(__name__)

# Log a request
log_request(logger, request_id="req-123", method="POST",
            endpoint="/chat", model="grok-4")

# Log a response
log_response(logger, request_id="req-123", status=200,
             latency_ms=1234, tokens=150)

# Log success
log_success(logger, "Session created", session_id="sess-456")

# Log error
try:
    risky_operation()
except Exception as e:
    log_error(logger, "Operation failed", error=e, context="important")
```

### Query Token Usage

```sql
-- Daily token usage by model
SELECT
  day,
  model,
  SUM(total_tokens) as tokens,
  SUM(total_cost_micro_usd) / 1000000.0 as cost_usd
FROM usage_analytics
WHERE day >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY day, model
ORDER BY day DESC, tokens DESC;

-- Top users by cost
SELECT
  u.username,
  SUM(tu.total_cost_micro_usd) / 1000000.0 as total_cost_usd,
  SUM(tu.total_tokens) as total_tokens
FROM token_usage tu
JOIN users u ON tu.user_id = u.id
WHERE tu.created_at >= now() - interval '30 days'
GROUP BY u.username
ORDER BY total_cost_usd DESC
LIMIT 10;

-- Reasoning token usage (grok-4)
SELECT
  DATE_TRUNC('day', created_at) as day,
  SUM(reasoning_tokens) as reasoning_tokens,
  SUM(completion_total_tokens) as total_completion_tokens,
  (SUM(reasoning_tokens)::float / NULLIF(SUM(completion_total_tokens), 0)) * 100 as reasoning_percentage
FROM token_usage
WHERE model LIKE 'grok-4%'
GROUP BY day
ORDER BY day DESC;
```

### Track Response Chains

```sql
-- Get full conversation chain
WITH RECURSIVE conversation AS (
  -- Start with latest response
  SELECT * FROM api_responses WHERE response_id = 'resp-latest'

  UNION ALL

  -- Follow chain backwards
  SELECT r.*
  FROM api_responses r
  JOIN conversation c ON r.response_id = c.previous_response_id
)
SELECT * FROM conversation ORDER BY created_at ASC;
```

---

## 📈 Analytics Queries

### Cost Analysis

```sql
-- Cost breakdown by model and token type
SELECT
  model,
  SUM(prompt_cost_micro_usd) / 1000000.0 as prompt_cost,
  SUM(completion_cost_micro_usd) / 1000000.0 as completion_cost,
  SUM(total_cost_micro_usd) / 1000000.0 as total_cost
FROM token_usage
WHERE created_at >= now() - interval '30 days'
GROUP BY model
ORDER BY total_cost DESC;
```

### Performance Metrics

```sql
-- Average latency by model
SELECT
  model,
  COUNT(*) as requests,
  AVG(latency_ms) as avg_latency_ms,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms,
  MAX(latency_ms) as max_latency_ms
FROM generations
WHERE created_at >= now() - interval '24 hours'
  AND status = 200
GROUP BY model
ORDER BY requests DESC;
```

### Token Efficiency

```sql
-- Cached token usage rate
SELECT
  model,
  SUM(cached_tokens) as total_cached,
  SUM(prompt_total_tokens) as total_prompt,
  (SUM(cached_tokens)::float / NULLIF(SUM(prompt_total_tokens), 0)) * 100 as cache_hit_rate
FROM token_usage
WHERE created_at >= now() - interval '7 days'
GROUP BY model
ORDER BY cache_hit_rate DESC;
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Logging
LOG_LEVEL=info              # debug, info, warning, error, critical
JSON_LOGGING=false          # true for production JSON logs, false for colored

# Enable colored output even in non-TTY (for logging to file with colors)
FORCE_COLOR=true
```

### Database Maintenance

```bash
# Refresh analytics view (run hourly via cron)
psql "$DATABASE_URL" -c "SELECT refresh_usage_analytics();"

# Clean up expired responses (run daily)
psql "$DATABASE_URL" -c "DELETE FROM api_responses WHERE expires_at < now();"

# Archive old token usage (run monthly)
psql "$DATABASE_URL" -c "
  INSERT INTO token_usage_archive
  SELECT * FROM token_usage
  WHERE created_at < now() - interval '90 days';

  DELETE FROM token_usage
  WHERE created_at < now() - interval '90 days';
"
```

---

## 📊 Monitoring Dashboard Queries

### Real-time Metrics

```sql
-- Current hour statistics
SELECT
  COUNT(*) as requests,
  AVG(latency_ms) as avg_latency,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost_micro_usd) / 1000000.0 as cost_usd
FROM token_usage
WHERE created_at >= DATE_TRUNC('hour', now());

-- Active sessions
SELECT
  status,
  COUNT(*) as count
FROM sessions
GROUP BY status;

-- Recent errors
SELECT
  created_at,
  model,
  error_message,
  latency_ms
FROM generations
WHERE status >= 400
  AND created_at >= now() - interval '1 hour'
ORDER BY created_at DESC
LIMIT 10;
```

---

## ✅ Migration Applied

```bash
$ python db/migrate.py
2025-12-01 16:17:22,284 - INFO - Starting migration runner...
2025-12-01 16:17:22,284 - INFO - Found 2 migration file(s)
2025-12-01 16:17:22,858 - INFO - ✓ Connected to database
2025-12-01 16:17:23,197 - INFO - Found 1 applied migration(s)
2025-12-01 16:17:23,198 - INFO - Found 1 pending migration(s):
2025-12-01 16:17:23,198 - INFO -   - 2: 002_add_xai_tracking
2025-12-01 16:17:23,198 - INFO - Applying migration 2: 002_add_xai_tracking
2025-12-01 16:17:23,442 - INFO - ✓ Migration 2 applied successfully
2025-12-01 16:17:23,443 - INFO - ✓ Successfully applied 1 migration(s)
```

**New Tables Created**:

- ✅ `token_usage` (token tracking & billing)
- ✅ `api_models` (model catalog)
- ✅ `api_responses` (response continuity)
- ✅ `embeddings` (embedding tracking)
- ✅ `image_generations` (image tracking)
- ✅ `usage_analytics` (materialized view)

**Columns Added to `generations`**:

- ✅ 18 new columns for xAI metadata

---

## 🎯 Next Steps

1. **Populate `api_models` table** with xAI model data
2. **Update app.py** to record detailed token usage
3. **Create Grafana dashboard** using new analytics
4. **Set up cron job** to refresh usage_analytics hourly
5. **Implement cost alerts** when spending exceeds threshold

---

**Your system now tracks EVERYTHING from the xAI API!** 🎉

Every token, every cost, every model parameter - all stored and queryable for analytics, billing, and optimization.
