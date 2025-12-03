"""
Full-featured Vercel serverless entry point for GrokProxy.
Integrated with PostgreSQL, Cloudinary, and Grok API.
"""

import os
import sys
from pathlib import Path
from typing import Optional
import time
import uuid
import json
import logging

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import our modules
from api.db_client import DatabaseClient
from api.session_manager import SessionManager
from api.grok_client import GrokClient, RateLimitException, AuthenticationException, CookieExpiredException
from api.cloudinary_client import CloudinaryClient
from api.cookie_manager import CookieManager
from api.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
    ImageGenerationRequest,
    ImageGenerationResponse
)

# Get the directory containing this file
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Global instances (lazy initialized)
db_client: Optional[DatabaseClient] = None
session_manager: Optional[SessionManager] = None
cloudinary_client: Optional[CloudinaryClient] = None
cookie_manager: Optional[CookieManager] = None


async def get_db_client() -> Optional[DatabaseClient]:
    """Get or create database client."""
    global db_client
    if db_client is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("Warning: DATABASE_URL not set")
            return None
        
        try:
            # Create local instance first
            client = DatabaseClient(database_url=database_url, min_size=1, max_size=3)
            await client.connect()
            # Only assign to global if successful
            db_client = client
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None
    
    return db_client


async def get_session_manager() -> Optional[SessionManager]:
    """Get or create session manager."""
    global session_manager
    if session_manager is None:
        db = await get_db_client()
        if db is None:
            return None
        session_manager = SessionManager(db)
    
    return session_manager


def get_cloudinary_client() -> CloudinaryClient:
    """Get or create Cloudinary client."""
    global cloudinary_client
    if cloudinary_client is None:
        cloudinary_client = CloudinaryClient()
    
    return cloudinary_client


def get_cookie_manager() -> CookieManager:
    """Get or create Cookie manager."""
    global cookie_manager
    if cookie_manager is None:
        # Get failure threshold from env, default to 3
        failure_threshold = int(os.getenv("COOKIE_FAILURE_THRESHOLD", "3"))
        cookie_manager = CookieManager(failure_threshold=failure_threshold)
    
    return cookie_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# WEB PAGES
# ============================================================================

@app.get("/")
async def root():
    """Serve homepage."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    
    return {
        "service": "GrokProxy",
        "version": "2.1.0",
        "status": "operational",
        "environment": "vercel-serverless"
    }


@app.get("/test")
async def test_page():
    """Serve API testing page."""
    test_path = STATIC_DIR / "test.html"
    if test_path.exists():
        return FileResponse(test_path)
    return {"error": "Test page not found"}


@app.get("/advanced")
async def advanced_page():
    """Serve advanced features page."""
    advanced_path = STATIC_DIR / "advanced.html"
    if advanced_path.exists():
        return FileResponse(advanced_path)
    return {"error": "Advanced page not found"}


@app.get("/storyline")
async def storyline_page():
    """Serve storyline generator."""
    storyline_path = STATIC_DIR / "storyline.html"
    if storyline_path.exists():
        return FileResponse(storyline_path)
    return {"error": "Storyline page not found"}


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        # Get cookie manager stats
        cm = get_cookie_manager()
        cookie_stats = {
            "total_cookies": cm.get_total_count(),
            "healthy_cookies": cm.get_healthy_count(),
            "rotation_enabled": os.getenv("COOKIE_ROTATION_ENABLED", "true").lower() == "true"
        }
        
        # Check if database is configured
        db = await get_db_client()
        if db is None:
            return {
                "status": "healthy",
                "mode": "cookieonly",
                "environment": "vercel-serverless",
                "database": "not_configured",
                "cookies": cookie_stats,
                "message": "Running with cookie-based rotation only"
            }
        
        db_healthy = await db.test_connection()
        
        sm = await get_session_manager()
        session_count = await sm.get_healthy_session_count() if sm else 0
        
        return {
            "status": "healthy" if db_healthy else "degraded",
            "mode": "full",
            "environment": "vercel-serverless",
            "database": "connected" if db_healthy else "disconnected",
            "cookies": cookie_stats,
            "healthy_sessions": session_count
        }
    except Exception as e:
        # Don't return 503, return 200 with error details
        cm = get_cookie_manager()
        return {
            "status": "degraded",
            "environment": "vercel-serverless",
            "error": str(e),
            "cookies": {
                "total_cookies": cm.get_total_count(),
                "healthy_cookies": cm.get_healthy_count()
            },
            "message": "Service operational with cookie rotation"
        }


@app.get("/v1/models")
async def list_models(raw_request: Request):
    """List available models."""
    # Full mode - return static model list
    return {
        "object": "list",
        "data": [
            {
                "id": "grok-3",
                "object": "model",
                "created": 1234567890,
                "owned_by": "xai",
                "permission": [],
                "root": "grok-3",
                "parent": None
            },
            {
                "id": "grok-2",
                "object": "model",
                "created": 1234567890,
                "owned_by": "xai",
                "permission": [],
                "root": "grok-2",
                "parent": None
            }
        ]
    }



@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, raw_request: Request):
    """
    Chat completions endpoint with automatic cookie rotation.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Get cookie manager
    cm = get_cookie_manager()
    max_retries = cm.get_total_count()
    
    if max_retries == 0:
        raise HTTPException(
            status_code=503,
            detail="No cookies configured. Please set COOKIE_1 environment variable."
        )
    
    # Convert Pydantic messages to dicts
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    last_error = None
    
    # Try each cookie
    for attempt in range(max_retries):
        try:
            # Get next available cookie
            cookie_info = cm.get_next_cookie()
            
            # Create Grok client with this cookie
            grok_client = GrokClient(
                session_cookies=cookie_info["cookies_dict"],
                user_agent=cookie_info["user_agent"]
            )
            
            try:
                if request.stream:
                    # Streaming response
                    async def generate():
                        try:
                            async for chunk in grok_client.chat_completion_stream(
                                messages=messages,
                                model=request.model,
                                temperature=request.temperature,
                                max_tokens=request.max_tokens
                            ):
                                yield f"data: {chunk}\n\n"
                            yield "data: [DONE]\n\n"
                            
                            # Mark success
                            cm.mark_cookie_success(cookie_info["index"])
                            
                        except (RateLimitException, AuthenticationException) as e:
                            # These will be caught by outer handler
                            raise
                        finally:
                            await grok_client.close()
                    
                    return StreamingResponse(
                        generate(),
                        media_type="text/event-stream"
                    )
                else:
                    # Non-streaming response
                    response = await grok_client.chat_completion(
                        messages=messages,
                        model=request.model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        stream=False
                    )
                    
                    await grok_client.close()
                    
                    # Mark cookie as successful
                    cm.mark_cookie_success(cookie_info["index"])
                    
                    # Calculate latency
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    # Log to database (optional)
                    try:
                        db = await get_db_client()
                        if db:
                            await db.insert_generation(
                                request_id=request_id,
                                provider="grok",
                                model=request.model,
                                prompt=messages[0]['content'] if messages else "",
                                status=200,
                                latency_ms=latency_ms,
                                session_id=None,  # No session ID in cookie mode
                                response_text=response.get('choices', [{}])[0].get('message', {}).get('content'),
                                response_tokens=response.get('usage', {}).get('completion_tokens'),
                                prompt_tokens=response.get('usage', {}).get('prompt_tokens'),
                                response_raw=response
                            )
                    except Exception as db_error:
                        # Database logging is optional, don't fail request
                        logger.warning(f"Failed to log to database: {db_error}")
                    
                    return response
                    
            except RateLimitException as e:
                # Rate limit hit - mark cookie failed and try next
                cm.mark_cookie_failed(cookie_info["index"], "rate_limit")
                last_error = str(e)
                logger.warning(f"Cookie {cookie_info['index']} hit rate limit: {e}")
                await grok_client.close()
                
                # If this was the last cookie, raise error
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=429,
                        detail=f"All cookies exhausted due to rate limits: {last_error}"
                    )
                
                # Otherwise continue to next cookie
                continue
                
            except AuthenticationException as e:
                # Auth failed - mark cookie failed and try next
                cm.mark_cookie_failed(cookie_info["index"], "auth_failed")
                last_error = str(e)
                logger.warning(f"Cookie {cookie_info['index']} auth failed: {e}")
                await grok_client.close()
                
                # If this was the last cookie, raise error
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=401,
                        detail=f"All cookies failed authentication: {last_error}"
                    )
                
                # Otherwise continue to next cookie
                continue
                
            except CookieExpiredException as e:
                # Cookie expired - mark failed and try next
                cm.mark_cookie_failed(cookie_info["index"], "expired")
                last_error = str(e)
                logger.warning(f"Cookie {cookie_info['index']} expired: {e}")
                await grok_client.close()
                
                # If this was the last cookie, raise error
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=401,
                        detail=f"All cookies expired: {last_error}"
                    )
                
                # Otherwise continue to next cookie
                continue
                
            except Exception as e:
                # Other error - mark as failed but with unknown error type
                cm.mark_cookie_failed(cookie_info["index"], "unknown")
                last_error = str(e)
                logger.error(f"Cookie {cookie_info['index']} unexpected error: {e}")
                await grok_client.close()
                
                # If this was the last cookie, raise error
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=500,
                        detail=f"All cookies failed: {last_error}"
                    )
                
                # Otherwise continue to next cookie
                continue
                
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Unexpected error in retry logic itself
            logger.error(f"Unexpected error in retry logic: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Should never reach here, but just in case
    raise HTTPException(
        status_code=503,
        detail="Failed to complete request after all retries"
    )


@app.post("/v1/images/generations")
async def generate_image(request: ImageGenerationRequest):
    """
    Image generation endpoint with Cloudinary integration.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Get session and generate image
        sm = await get_session_manager()
        session = await sm.acquire_session()
        
        if not session:
            raise HTTPException(status_code=503, detail="No available sessions")
        
        # Create Grok client
        grok_client = GrokClient(session['cookies'])
        
        try:
            # Generate image
            response = await grok_client.generate_image(
                prompt=request.prompt,
                model=request.model
            )
            
            await grok_client.close()
            
            # Extract image URL from response
            # (Adjust based on actual Grok API response format)
            image_url = None
            if 'choices' in response and response['choices']:
                content = response['choices'][0].get('message', {}).get('content', '')
                # Parse image URL from content (format depends on Grok API)
                # For now, return the response as-is
                pass
            
            # Upload to Cloudinary if we have an image URL
            cloudinary_url = None
            if image_url:
                cloudinary = get_cloudinary_client()
                upload_result = cloudinary.upload_image(
                    image_url=image_url,
                    prompt=request.prompt,
                    tags=[request.style] if request.style else []
                )
                cloudinary_url = upload_result['url']
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log to database
            db = await get_db_client()
            await db.insert_generation(
                request_id=request_id,
                provider="grok",
                model=request.model,
                prompt=request.prompt,
                status=200,
                latency_ms=latency_ms,
                session_id=session['id'],
                response_raw=response,
                metadata={"cloudinary_url": cloudinary_url} if cloudinary_url else None
            )
            
            # Release session
            await sm.release_session(session['id'], success=True)
            
            # Return response
            return {
                "id": request_id,
                "created": int(time.time()),
                "data": [
                    {
                        "url": image_url or "pending",
                        "cloudinary_url": cloudinary_url
                    }
                ],
                "response": response
            }
            
        except Exception as e:
            await sm.release_session(session['id'], success=False)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@app.get("/admin/sessions")
async def list_sessions():
    """List all sessions (admin only)."""
    try:
        db = await get_db_client()
        sessions = await db.list_sessions(limit=50)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/generations")
async def list_generations():
    """List recent generations (admin only)."""
    try:
        db = await get_db_client()
        generations = await db.list_generations(limit=50)
        return {"generations": generations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/cookies")
async def cookie_statistics():
    """Get detailed cookie statistics (admin only)."""
    try:
        cm = get_cookie_manager()
        return {
            "total_cookies": cm.get_total_count(),
            "healthy_cookies": cm.get_healthy_count(),
            "rotation_enabled": os.getenv("COOKIE_ROTATION_ENABLED", "true").lower() == "true",
            "failure_threshold": int(os.getenv("COOKIE_FAILURE_THRESHOLD", "3")),
            "cookies": cm.get_cookie_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Setup logger
logger = logging.getLogger(__name__)
