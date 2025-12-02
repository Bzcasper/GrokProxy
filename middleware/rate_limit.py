"""
Rate limiting middleware for GrokProxy.

Implements token bucket algorithm with Redis backend for distributed rate limiting.
"""

import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with Redis backend.
    
    Supports per-user, per-endpoint, and global rate limits.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_rate: int = 60,  # requests per minute
        default_burst: int = 10,  # burst capacity
        enabled: bool = True
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL (optional, falls back to in-memory)
            default_rate: Default requests per minute
            default_burst: Default burst capacity
            enabled: Whether rate limiting is enabled
        """
        self.enabled = enabled
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.redis_client: Optional[redis.Redis] = None
        self.in_memory_store = {}  # Fallback for when Redis unavailable
        
        if redis_url and redis:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("✓ Rate limiter using Redis backend")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis, using in-memory: {e}")
        else:
            logger.info("Rate limiter using in-memory backend")
    
    async def check_rate_limit(
        self,
        key: str,
        rate: Optional[int] = None,
        burst: Optional[int] = None
    ) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit.
        
        Args:
            key: Unique identifier (e.g., "user:123:endpoint:/chat")
            rate: Requests per minute (uses default if None)
            burst: Burst capacity (uses default if None)
        
        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        if not self.enabled:
            return True, {"limit": -1, "remaining": -1, "reset": 0}
        
        rate = rate or self.default_rate
        burst = burst or self.default_burst
        
        if self.redis_client:
            return await self._check_redis(key, rate, burst)
        else:
            return await self._check_memory(key, rate, burst)
    
    async def _check_redis(
        self,
        key: str,
        rate: int,
        burst: int
    ) -> Tuple[bool, dict]:
        """Check rate limit using Redis."""
        now = time.time()
        window = 60  # 1 minute window
        
        # Token bucket algorithm
        bucket_key = f"ratelimit:{key}"
        
        try:
            # Get current bucket state
            pipe = self.redis_client.pipeline()
            pipe.hgetall(bucket_key)
            result = await pipe.execute()
            bucket = result[0] if result else {}
            
            # Initialize or parse bucket
            tokens = float(bucket.get("tokens", burst))
            last_update = float(bucket.get("last_update", now))
            
            # Calculate tokens to add based on time passed
            time_passed = now - last_update
            tokens_to_add = (time_passed / window) * rate
            tokens = min(burst, tokens + tokens_to_add)
            
            # Check if we have tokens
            if tokens >= 1:
                # Consume token
                tokens -= 1
                allowed = True
            else:
                allowed = False
            
            # Update bucket
            pipe = self.redis_client.pipeline()
            pipe.hset(bucket_key, mapping={
                "tokens": str(tokens),
                "last_update": str(now)
            })
            pipe.expire(bucket_key, window * 2)  # Expire after 2 minutes
            await pipe.execute()
            
            # Calculate reset time
            if tokens < 1:
                reset_time = int(now + ((1 - tokens) / rate) * window)
            else:
                reset_time = int(now + window)
            
            return allowed, {
                "limit": rate,
                "remaining": int(tokens),
                "reset": reset_time
            }
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fail open - allow request
            return True, {"limit": rate, "remaining": -1, "reset": 0}
    
    async def _check_memory(
        self,
        key: str,
        rate: int,
        burst: int
    ) -> Tuple[bool, dict]:
        """Check rate limit using in-memory store."""
        now = time.time()
        window = 60
        
        # Get or create bucket
        if key not in self.in_memory_store:
            self.in_memory_store[key] = {
                "tokens": burst,
                "last_update": now
            }
        
        bucket = self.in_memory_store[key]
        
        # Calculate tokens to add
        time_passed = now - bucket["last_update"]
        tokens_to_add = (time_passed / window) * rate
        bucket["tokens"] = min(burst, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now
        
        # Check if we have tokens
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            allowed = True
        else:
            allowed = False
        
        # Calculate reset time
        if bucket["tokens"] < 1:
            reset_time = int(now + ((1 - bucket["tokens"]) / rate) * window)
        else:
            reset_time = int(now + window)
        
        # Cleanup old entries
        self._cleanup_memory()
        
        return allowed, {
            "limit": rate,
            "remaining": int(bucket["tokens"]),
            "reset": reset_time
        }
    
    def _cleanup_memory(self):
        """Remove old entries from in-memory store."""
        now = time.time()
        to_remove = []
        
        for key, bucket in self.in_memory_store.items():
            if now - bucket["last_update"] > 120:  # 2 minutes
                to_remove.append(key)
        
        for key in to_remove:
            del self.in_memory_store[key]
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Applies rate limits based on user ID and endpoint.
    """
    
    def __init__(self, app, rate_limiter: RateLimiter, get_user_id_func=None):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI app
            rate_limiter: RateLimiter instance
            get_user_id_func: Function to extract user ID from request
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.get_user_id = get_user_id_func or self._default_get_user_id
        
        # Endpoint-specific limits (requests per minute)
        self.endpoint_limits = {
            "/v1/chat/completions": {"rate": 30, "burst": 5},
            "/v1/images/generations": {"rate": 20, "burst": 3},
            "/v1/embeddings": {"rate": 60, "burst": 10},
            "/v1/completions": {"rate": 30, "burst": 5},
        }
    
    def _default_get_user_id(self, request: Request) -> str:
        """Extract user ID from request."""
        # Try to get from state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return user_id
        
        # Fall back to IP address
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/"]:
            return await call_next(request)
        
        # Get user ID
        user_id = self.get_user_id(request)
        
        # Get endpoint-specific limits
        endpoint = request.url.path
        limits = self.endpoint_limits.get(endpoint, {})
        rate = limits.get("rate")
        burst = limits.get("burst")
        
        # Check rate limit
        key = f"user:{user_id}:endpoint:{endpoint}"
        allowed, info = await self.rate_limiter.check_rate_limit(key, rate, burst)
        
        if not allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: user={user_id}, endpoint={endpoint}, "
                f"limit={info['limit']}, reset={info['reset']}"
            )
            
            return Response(
                content='{"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}',
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["reset"] - int(time.time())),
                    "Content-Type": "application/json"
                }
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response


# Decorator for rate limiting specific endpoints
def rate_limit(rate: int = 60, burst: int = 10):
    """
    Decorator to apply rate limiting to specific endpoints.
    
    Usage:
        @app.post("/endpoint")
        @rate_limit(rate=30, burst=5)
        async def endpoint():
            pass
    """
    def decorator(func):
        func._rate_limit = {"rate": rate, "burst": burst}
        return func
    return decorator
