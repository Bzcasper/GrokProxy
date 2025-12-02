# Rate Limiting & Cloudinary Integration

## 🚀 New Features Added

### 1. Rate Limiting

**File**: `middleware/rate_limit.py`

Comprehensive rate limiting system with:

- **Token bucket algorithm** for smooth rate limiting
- **Redis backend** for distributed systems (with in-memory fallback)
- **Per-user limits** - Different limits per user
- **Per-endpoint limits** - Different limits per API endpoint
- **Burst capacity** - Allow short bursts of requests
- **Automatic headers** - X-RateLimit-\* headers in responses

#### Configuration

```python
# In app.py
from middleware import RateLimiter, RateLimitMiddleware

# Initialize rate limiter
rate_limiter = RateLimiter(
    redis_url=os.getenv("REDIS_URL"),  # Optional
    default_rate=60,  # 60 requests per minute
    default_burst=10,  # Allow bursts of 10
    enabled=True
)

# Add middleware
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
```

#### Endpoint-Specific Limits

```python
# Default limits in middleware
endpoint_limits = {
    "/v1/chat/completions": {"rate": 30, "burst": 5},
    "/v1/images/generations": {"rate": 20, "burst": 3},
    "/v1/embeddings": {"rate": 60, "burst": 10},
}
```

#### Response Headers

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1764637200
Retry-After: 45
```

---

### 2. Cloudinary Integration

**File**: `storage/cloudinary_manager.py`

Automatic image/video storage with organization:

- **Auto-upload** to Cloudinary
- **Folder organization** by date (YYYY/MM/DD)
- **Automatic tagging** from prompts
- **Metadata storage** (prompt, timestamp, source)
- **Duplicate detection**
- **Batch operations**
- **Search functionality**

#### Setup

```bash
# Install Cloudinary
pip install cloudinary

# Set environment variables
export CLOUDINARY_CLOUD_NAME="your-cloud-name"
export CLOUDINARY_API_KEY="your-api-key"
export CLOUDINARY_API_SECRET="your-api-secret"
```

#### Usage

```python
from storage import get_cloudinary_manager

# Get manager
cloudinary = get_cloudinary_manager()

# Upload image
result = cloudinary.upload_image(
    image_path="path/to/image.png",
    prompt="A beautiful sunset",
    tags=["sunset", "nature"],
    metadata={"model": "grok-3"}
)

# Result
{
    "url": "https://res.cloudinary.com/...",
    "public_id": "grokproxy/2025/12/01/images/img_abc123",
    "format": "png",
    "width": 1024,
    "height": 1024,
    "bytes": 245678,
    "folder": "grokproxy/2025/12/01/images",
    "tags": ["sunset", "nature", "grokproxy", "ai-generated"]
}
```

#### Folder Structure

```
grokproxy/
├── 2025/
│   ├── 12/
│   │   ├── 01/
│   │   │   ├── images/
│   │   │   │   ├── img_abc123.png
│   │   │   │   ├── img_def456.png
│   │   │   └── videos/
│   │   │       ├── vid_xyz789.mp4
│   │   ├── 02/
│   │   └── ...
```

#### Batch Upload

```python
files = [
    {"path": "image1.png", "prompt": "sunset", "type": "image"},
    {"path": "image2.png", "prompt": "ocean", "type": "image"},
    {"path": "video1.mp4", "prompt": "timelapse", "type": "video"}
]

results = cloudinary.batch_upload(files)
```

#### Search Images

```python
# Search by tags
images = cloudinary.search_images("tags:sunset AND folder:grokproxy/*")

# Search by date
images = cloudinary.search_images("folder:grokproxy/2025/12/01/*")
```

#### Usage Stats

```python
stats = cloudinary.get_usage_stats()
# {
#     "images": {"count": 150, "bytes": 12345678},
#     "videos": {"count": 25, "bytes": 98765432},
#     "storage": {"used": 111111110, "limit": 10000000000},
#     "bandwidth": {"used": 555555555, "limit": 50000000000}
# }
```

---

## 🔧 Integration with Content Generator

### Updated content_generator.py

```python
from storage import get_cloudinary_manager

class ContentGenerator:
    def __init__(self, ...):
        # ... existing code ...
        self.cloudinary = get_cloudinary_manager()

    def generate_image(self, prompt: str, ...):
        # Generate image
        result = self._call_api(prompt)

        # Upload to Cloudinary if enabled
        if self.cloudinary.enabled and result.get("image_url"):
            cloudinary_result = self.cloudinary.upload_image(
                image_path=result["image_url"],
                prompt=prompt,
                metadata={
                    "model": "grok-3",
                    "request_id": result.get("id")
                }
            )

            if cloudinary_result:
                result["cloudinary_url"] = cloudinary_result["url"]
                result["cloudinary_id"] = cloudinary_result["public_id"]

        return result
```

---

## 📊 Environment Variables

### Required for Rate Limiting (Optional)

```bash
# Redis for distributed rate limiting (optional, uses in-memory if not set)
REDIS_URL=redis://localhost:6379/0

# Rate limit configuration
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_RATE=60  # requests per minute
RATE_LIMIT_DEFAULT_BURST=10  # burst capacity
```

### Required for Cloudinary

```bash
# Cloudinary credentials (get from cloudinary.com)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

---

## 🎯 Benefits

### Rate Limiting

- ✅ Prevent API abuse
- ✅ Fair usage across users
- ✅ Protect backend resources
- ✅ Smooth traffic with burst handling
- ✅ Clear feedback to clients (headers)

### Cloudinary

- ✅ Organized storage (no local clutter)
- ✅ Automatic CDN delivery
- ✅ Image transformations on-the-fly
- ✅ Searchable by tags/metadata
- ✅ Backup and redundancy
- ✅ Usage tracking

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install redis cloudinary
```

### 2. Configure Environment

```bash
# Add to .env
REDIS_URL=redis://localhost:6379/0
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

### 3. Update app.py

```python
from middleware import RateLimiter, RateLimitMiddleware

# Initialize rate limiter
rate_limiter = RateLimiter(
    redis_url=os.getenv("REDIS_URL"),
    enabled=True
)

# Add middleware (before other middlewares)
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
```

### 4. Test

```bash
# Test rate limiting
for i in {1..100}; do
  curl http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -d '{"model":"grok-3","messages":[{"role":"user","content":"hi"}]}'
  echo
done

# Should see 429 responses after limit exceeded
```

---

## 📚 API Examples

### Check Rate Limit Status

```python
# Headers in response
X-RateLimit-Limit: 30        # Total allowed per minute
X-RateLimit-Remaining: 25    # Remaining in current window
X-RateLimit-Reset: 1764637200  # Unix timestamp when resets
```

### Handle Rate Limit Errors

```python
import requests
import time

def generate_with_retry(prompt):
    while True:
        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "grok-3", "messages": [{"role": "user", "content": prompt}]}
        )

        if response.status_code == 429:
            # Rate limited
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        return response.json()
```

---

## 🔍 Monitoring

### Rate Limit Metrics

```python
# In your monitoring dashboard
rate_limit_exceeded_count = Counter("rate_limit_exceeded_total")
rate_limit_remaining = Gauge("rate_limit_remaining")

# Track in middleware
if not allowed:
    rate_limit_exceeded_count.inc()
else:
    rate_limit_remaining.set(info["remaining"])
```

### Cloudinary Usage

```python
# Check usage periodically
stats = cloudinary.get_usage_stats()

if stats["storage"]["used"] > stats["storage"]["limit"] * 0.9:
    logger.warning("Cloudinary storage at 90% capacity!")
```

---

## ✅ Testing Checklist

- [ ] Rate limiting works for chat endpoint
- [ ] Rate limiting works for image endpoint
- [ ] 429 responses include proper headers
- [ ] Burst capacity allows short spikes
- [ ] Cloudinary uploads images successfully
- [ ] Images organized in correct folders
- [ ] Tags extracted from prompts
- [ ] Metadata stored correctly
- [ ] Search functionality works
- [ ] Batch upload works

---

**Your GrokProxy now has enterprise-grade rate limiting and organized cloud storage!** 🚀
