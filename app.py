"""
Production-grade GrokProxy application.

Integrates database persistence, session management, observability, and resilience patterns.
"""

import os
import json
import uuid
import time
import logging
from typing import List, Optional
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette import status
from prometheus_client import CONTENT_TYPE_LATEST

# Project imports
from db.client import DatabaseClient
from session_manager import SessionManager
from session_manager.models import Session
from observability import (
    setup_colored_logging,
    get_colored_logger,
    log_request,
    log_response,
    log_success,
    log_error,
    metrics,
    setup_sentry,
    HealthChecker
)
from observability.logging import RequestIDMiddleware
from proxy.admin import create_admin_endpoints
from proxy.resilience import CircuitBreaker, CircuitBreakerOpenError
from openairequest import (
    Message,
    OpenAIRequest,
    Model,
    ModelList,
    UsageInfo,
    models_data
)
from modules.api import start_grok_conversation

# Setup colored logging for development
import os
use_json_logging = os.getenv("JSON_LOGGING", "false").lower() == "true"
setup_colored_logging(
    level=os.getenv("LOG_LEVEL", "info"),
    enable_colors=True,
    json_output=use_json_logging
)
logger = get_colored_logger(__name__)

# Initialize Sentry if configured
setup_sentry()

# Global state
db_client: Optional[DatabaseClient] = None
session_manager: Optional[SessionManager] = None
health_checker: Optional[HealthChecker] = None
circuit_breaker: Optional[CircuitBreaker] = None
valid_api_keys: List[str] = []
admin_api_keys: List[str] = []
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_client, session_manager, health_checker, circuit_breaker
    global valid_api_keys, admin_api_keys
    
    logger.info("🚀 Starting GrokProxy production server...")
    
    try:
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "cookies.yaml")
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            password = config.get("password", "")
            valid_api_keys = [password] if isinstance(password, str) else password or []
            
            # Admin keys (separate from regular API keys)
            admin_password = config.get("admin_password", "")
            admin_api_keys = [admin_password] if admin_password else valid_api_keys
            
            logger.info("✓ Loaded API configuration")
        else:
            logger.warning(f"Config file {config_path} not found, using environment variables")
            api_key = os.getenv("API_PASSWORD")
            if api_key:
                valid_api_keys = [api_key]
                admin_api_keys = [api_key]
        
        if not valid_api_keys:
            logger.error("⚠️  No API keys configured!")
        
        # Initialize database
        db_client = DatabaseClient(
            min_size=int(os.getenv("DB_POOL_MIN_SIZE", "10")),
            max_size=int(os.getenv("DB_POOL_MAX_SIZE", "20"))
        )
        await db_client.connect()
        logger.info("✓ Database connected")
        
        # Initialize session manager
        session_manager = SessionManager(db_client)
        await session_manager.start()
        logger.info("✓ Session manager started")
        
        # Initialize health checker
        health_checker = HealthChecker(db_client, session_manager)
        logger.info("✓ Health checker initialized")
        
        # Initialize circuit breaker
        circuit_breaker = CircuitBreaker(
            name="grok_api",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        logger.info("✓ Circuit breaker initialized")
        
        logger.info("✓ Server ready to accept requests")
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down GrokProxy server...")
    
    if session_manager:
        await session_manager.stop()
    
    if db_client:
        await db_client.disconnect()
    
    logger.info("✓ Server shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="GrokProxy",
    description="Production-grade OpenAI-compatible proxy for Grok AI with observability",
    version="2.0.0",
    lifespan=lifespan
)

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)


async def verify_api_key(
    authorization: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[str]:
    """
    Verify API key and return user ID if found.
    
    Returns:
        User ID if authenticated, None otherwise
    """
    if not valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API keys not configured"
        )
    
    api_key = authorization.credentials
    
    # Check if key matches any configured key
    if api_key in valid_api_keys:
        # For now, hash the API key to use as user ID
        import hashlib
        user_id_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Try to find user in database
        user = await db_client.get_user_by_api_key_hash(user_id_hash)
        
        if user:
            await db_client.update_user_last_active(user["id"])
            return user["id"]
        
        # If user doesn't exist, return None (anonymous)
        return None
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "message": "Invalid API key",
                "type": "invalid_request_error",
                "code": "invalid_api_key"
            }
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    from ngrok_manager import get_current_url
    
    ngrok_url = get_current_url()
    base_url = ngrok_url if ngrok_url else "http://localhost:8080"
    
    return {
        "name": "GrokProxy",
        "version": "2.0.0",
        "status": "operational",
        "base_url": base_url,
        "endpoints": {
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "health": "/health",
            "metrics": "/metrics",
            "admin": "/admin/*"
        }
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    if not health_checker:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "message": "Health checker not initialized"}
        )
    
    result = await health_checker.check_all()
    status_code = 503 if result["status"] == "unhealthy" else 200
    
    return JSONResponse(status_code=status_code, content=result)


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(
        content=metrics.get_metrics(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/v1/models", response_model=ModelList, dependencies=[Depends(verify_api_key)])
async def get_models():
    """Get list of available models."""
    logger.info("Models list requested")
    return models_data


@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(
    request: OpenAIRequest,
    http_request: Request,
    user_id: Optional[str] = Depends(verify_api_key)
):
    """
    Handle OpenAI-compatible chat completion requests.
    
    Supports both streaming and non-streaming responses.
    """
    request_id = str(uuid.uuid4())
    client_ip = http_request.client.host
    start_time = time.time()
    
    logger.info(
        f"Chat completion request: request_id={request_id}, model={request.model}, "
        f"stream={request.stream}, user_id={user_id or 'anonymous'}"
    )
    
    # Acquire session
    session = await session_manager.acquire_session()
    
    if not session:
        logger.error(f"No healthy sessions available: request_id={request_id}")
        metrics.record_error("no_sessions", "/v1/chat/completions")
        raise HTTPException(
            status_code=503,
            detail="No available sessions - please try again later"
        )
    
    try:
        # Extract prompt from messages
        message_content = request.messages[-1].content if request.messages else ""
        
        # Map model name
        model = request.model if request.model != "grok-latest" else "grok-3"
        
        # Call Grok API through circuit breaker
        async def call_grok():
            import asyncio
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: start_grok_conversation(message_content, session_data=None)
            )
        
        try:
            result = await circuit_breaker.call_async(call_grok)
        except CircuitBreakerOpenError:
            logger.error(f"Circuit breaker open: request_id={request_id}")
            raise HTTPException(
                status_code=503,
                detail="Upstream service temporarily unavailable"
            )
        
        # Check for errors
        if "error" in result:
            error_msg = result["error"]
            logger.error(f"Grok API error: {error_msg}, request_id={request_id}")
            
            # Release session with failure
            await session_manager.release_session(session.id, success=False, error=str(error_msg))
            
            # Record in database
            latency_ms = int((time.time() - start_time) * 1000)
            await db_client.insert_generation(
                request_id=request_id,
                user_id=user_id,
                session_id=session.id,
                provider="grok",
                model=model,
                prompt=message_content,
                status=500,
                latency_ms=latency_ms,
                error_message=str(error_msg)
            )
            
            raise HTTPException(status_code=502, detail=f"Upstream error: {error_msg}")
        
        # Extract response
        response_text = "".join(result.get("stream_response", []))
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Insert generation record
        generation_id = await db_client.insert_generation(
            request_id=request_id,
            user_id=user_id,
            session_id=session.id,
            provider="grok",
            model=model,
            prompt=message_content,
            response_text=response_text,
            response_raw=result,
            status=200,
            latency_ms=latency_ms
        )
        
        # Release session with success
        await session_manager.release_session(session.id, success=True)
        
        # Record metrics
        metrics.record_generation(
            model=model,
            provider="grok",
            status=200,
            latency_ms=latency_ms
        )
        
        logger.info(
            f"Generation complete: request_id={request_id}, generation_id={generation_id}, "
           f"latency_ms={latency_ms}"
        )
        
        # Return response
        if request.stream:
            # For streaming, return simple response for now
            # TODO: Implement proper streaming
            async def generate_stream():
                chunk = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": response_text, "role": "assistant"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                
                end_chunk = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(end_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            response = {
                "id": f"chatcmpl-{request_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": UsageInfo(
                    prompt_tokens=len(message_content.split()),
                    completion_tokens=len(response_text.split()),
                    total_tokens=len(message_content.split()) + len(response_text.split())
                ).dict()
            }
            
            return JSONResponse(content=response, headers={"x-request-id": request_id})
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True, extra={"request_id": request_id})
        
        # Release session with failure
        await session_manager.release_session(session.id, success=False, error=str(e))
        
        # Record error
        metrics.record_error("internal_error", "/v1/chat/completions")
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Mount admin endpoints
admin_router = create_admin_endpoints(db_client, session_manager, admin_api_keys)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True
    )
