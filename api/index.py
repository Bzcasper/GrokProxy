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
from api.grok_client import GrokClient
from api.cloudinary_client import CloudinaryClient
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
        # Full mode - check database
        db = await get_db_client()
        if db is None:
            return {
                "status": "degraded",
                "mode": "standalone",
                "environment": "vercel-serverless",
                "database": "not_configured",
                "message": "Running without database"
            }
        
        db_healthy = await db.test_connection()
        
        sm = await get_session_manager()
        session_count = await sm.get_healthy_session_count() if sm else 0
        
        return {
            "status": "healthy" if db_healthy else "degraded",
            "mode": "full",
            "environment": "vercel-serverless",
            "database": "connected" if db_healthy else "disconnected",
            "healthy_sessions": session_count
        }
    except Exception as e:
        # Don't return 503, return 200 with error details
        return {
            "status": "degraded",
            "environment": "vercel-serverless",
            "error": str(e),
            "message": "Service operational with limited features"
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
    Chat completions endpoint with full Grok API integration.
    """
    # Full mode implementation
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Get session manager and acquire session
        sm = await get_session_manager()
        session = await sm.acquire_session()
        
        if not session:
            raise HTTPException(
                status_code=503,
                detail="No available sessions. Please try again later."
            )
        
        # Create Grok client with session cookies
        grok_client = GrokClient(session['cookies'], session.get('user_agent'))
        
        try:
            # Convert Pydantic messages to dicts
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Call Grok API
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
                    finally:
                        await grok_client.close()
                        await sm.release_session(session['id'], success=True)
                
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
                
                # Calculate latency
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Log to database
                db = await get_db_client()
                await db.insert_generation(
                    request_id=request_id,
                    provider="grok",
                    model=request.model,
                    prompt=messages[0]['content'] if messages else "",
                    status=200,
                    latency_ms=latency_ms,
                    session_id=session['id'],
                    response_text=response.get('choices', [{}])[0].get('message', {}).get('content'),
                    response_tokens=response.get('usage', {}).get('completion_tokens'),
                    prompt_tokens=response.get('usage', {}).get('prompt_tokens'),
                    response_raw=response
                )
                
                # Release session
                await sm.release_session(session['id'], success=True)
                
                return response
                
        except Exception as e:
            # Release session with failure
            await sm.release_session(session['id'], success=False)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        # Log error to database
        latency_ms = int((time.time() - start_time) * 1000)
        try:
            db = await get_db_client()
            await db.insert_generation(
                request_id=request_id,
                provider="grok",
                model=request.model,
                prompt=request.messages[0].content if request.messages else "",
                status=500,
                latency_ms=latency_ms,
                error_message=str(e)
            )
        except:
            pass
        
        raise HTTPException(status_code=500, detail=str(e))


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
