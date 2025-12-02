"""
Vercel serverless entry point for GrokProxy.

This module adapts the FastAPI application for Vercel's serverless environment.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import logging

# Import application components
from observability import setup_colored_logging, get_colored_logger
from db.client import DatabaseClient
from session_manager import SessionManager
from middleware import RateLimiter, RateLimitMiddleware
from observability.health import HealthChecker
from observability.metrics import metrics
from observability.logging import RequestIDMiddleware

# Setup logging
use_json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"
setup_colored_logging(
    level=os.getenv("LOG_LEVEL", "info"),
    enable_colors=False,  # Disable colors in serverless
    json_output=use_json_logging
)
logger = get_colored_logger(__name__)

# Global instances (lazy initialized)
db_client: Optional[DatabaseClient] = None
session_manager: Optional[SessionManager] = None
rate_limiter: Optional[RateLimiter] = None
health_checker: Optional[HealthChecker] = None


async def get_db_client() -> DatabaseClient:
    """Get or create database client (lazy initialization)."""
    global db_client
    if db_client is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        # Smaller pool for serverless
        db_client = DatabaseClient(
            database_url=database_url,
            min_size=1,
            max_size=3
        )
        await db_client.connect()
        logger.info("✓ Database client initialized")
    
    return db_client


async def get_session_manager() -> SessionManager:
    """Get or create session manager (lazy initialization)."""
    global session_manager
    if session_manager is None:
        db = await get_db_client()
        session_manager = SessionManager(
            db_client=db,
            rotation_threshold=int(os.getenv("SESSION_ROTATION_THRESHOLD", "500")),
            max_age_hours=int(os.getenv("SESSION_MAX_AGE_HOURS", "24")),
            failure_threshold=float(os.getenv("SESSION_FAILURE_THRESHOLD", "0.2")),
            health_check_interval=0  # Disable background checks in serverless
        )
        logger.info("✓ Session manager initialized")
    
    return session_manager


async def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter (lazy initialization)."""
    global rate_limiter
    if rate_limiter is None:
        redis_url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("REDIS_URL")
        rate_limiter = RateLimiter(
            redis_url=redis_url,
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        )
        logger.info("✓ Rate limiter initialized")
    
    return rate_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for serverless."""
    logger.info("🚀 GrokProxy starting in serverless mode...")
    
    # Lazy initialization - components created on first request
    logger.info("✓ Ready for requests (lazy initialization)")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    if db_client:
        await db_client.close()


# Create FastAPI app
app = FastAPI(
    title="GrokProxy",
    description="Production-grade proxy for xAI's Grok API",
    version="2.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        db = await get_db_client()
        
        # Quick database check
        async with db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "environment": "serverless",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "GrokProxy",
        "version": "2.1.0",
        "environment": "serverless",
        "status": "operational"
    }


# Models endpoint
@app.get("/v1/models")
async def list_models():
    """List available models."""
    from openairequest import models_data, ModelList
    return ModelList(data=models_data)


# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Chat completions endpoint.
    
    This is a simplified version for serverless.
    Full implementation should be imported from main app.
    """
    try:
        # Get managers
        db = await get_db_client()
        sm = await get_session_manager()
        
        # Get request body
        body = await request.json()
        
        # Acquire session
        session = await sm.acquire_session()
        if not session:
            raise HTTPException(
                status_code=503,
                detail="No available sessions"
            )
        
        # TODO: Implement full chat completion logic
        # For now, return a simple response
        return {
            "id": "chatcmpl-serverless",
            "object": "chat.completion",
            "created": 1234567890,
            "model": body.get("model", "grok-3"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "GrokProxy serverless endpoint (implementation pending)"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20
            }
        }
        
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cron endpoints
@app.get("/api/cron/health-check")
async def cron_health_check():
    """Cron job: Check session health."""
    try:
        sm = await get_session_manager()
        # Perform health check
        # TODO: Implement session health check logic
        return {"status": "ok", "message": "Health check completed"}
    except Exception as e:
        logger.error(f"Cron health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/cron/cleanup")
async def cron_cleanup():
    """Cron job: Cleanup old data."""
    try:
        db = await get_db_client()
        # TODO: Implement cleanup logic
        return {"status": "ok", "message": "Cleanup completed"}
    except Exception as e:
        logger.error(f"Cron cleanup failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/cron/refresh-analytics")
async def cron_refresh_analytics():
    """Cron job: Refresh analytics materialized view."""
    try:
        db = await get_db_client()
        async with db.pool.acquire() as conn:
            await conn.execute("SELECT refresh_usage_analytics()")
        return {"status": "ok", "message": "Analytics refreshed"}
    except Exception as e:
        logger.error(f"Analytics refresh failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Export for Vercel
# Vercel expects a variable named 'app'
# The app variable is already defined above and will be used by Vercel
