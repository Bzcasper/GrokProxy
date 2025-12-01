import json
import time
import logging
import uvicorn

from typing import List, Optional
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette import status

from grok_client import GrokClient
from pydantic import BaseModel, Field, validator
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import StreamingResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Chat message with role and content."""
    role: str = Field(..., description="Role of the message sender (user/assistant/system)")
    content: str = Field(..., description="Content of the message")
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError('Role must be user, assistant, or system')
        return v


class OpenAIRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = Field(default="grok-3", description="Model to use")
    stream: bool = Field(default=False, description="Whether to stream responses")
    max_tokens: Optional[int] = Field(default=4096, description="Maximum tokens to generate")
    messages: List[Message] = Field(..., description="List of messages in the conversation")
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError('Messages list cannot be empty')
        return v


class Model(BaseModel):
    """Model information."""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    """List of available models."""
    object: str = "list"
    data: List[Model]


class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# Available models
models_data = ModelList(
    data=[
        Model(id="grok-latest", created=int(time.time()), owned_by="xai"),
        Model(id="grok-3", created=int(time.time()), owned_by="xai"),
        Model(id="grok-2", created=int(time.time()), owned_by="xai"),
    ]
)

# Global state
grok_client: Optional[GrokClient] = None
security = HTTPBearer()
valid_api_keys: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global grok_client, valid_api_keys
    
    # Startup
    logger.info("🚀 Starting GrokProxy server with httpx-based client...")
    
    try:
        # Load configuration
        with open("cookies.yaml", "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        
        password = config.get("password", "")
        valid_api_keys = [password] if isinstance(password, str) else password
        
        if not valid_api_keys:
            logger.warning("⚠️  No API password configured - server will reject all requests!")
        else:
            logger.info(f"✓ Loaded API authentication")
        
        # Load rate limit configuration (optional)
        if "rate_limit" in config:
            delay = config["rate_limit"].get("delay_seconds", 1.0)
            logger.info(f"✓ Rate limit delay: {delay}s")
        
        # Initialize cookie manager
        from changecookie import ChangeCookie
        cookie_manager = ChangeCookie()
        
        # Initialize Grok client with cookie manager
        grok_client = GrokClient(cookie_manager=cookie_manager)
        logger.info("✓ GrokClient initialized with httpx")
        logger.info("✓ Server ready to accept requests")
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down GrokProxy server...")
    if grok_client:
        await grok_client.close()
    logger.info("✓ Server shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="GrokProxy",
    description="OpenAI-compatible API proxy for Grok AI with cookie rotation",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(
    authorization: HTTPAuthorizationCredentials = Depends(security),
):
    """Verify the API key from the authorization header."""
    if not valid_api_keys:
        logger.error("API keys not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API keys not configured",
        )

    if authorization.credentials not in valid_api_keys:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
        )


async def generate_response(messages: List[Message], model: str):
    """Generate a non-streaming response."""
    message_content = messages[-1].content if messages else ""
    tokens = []
    
    # Map grok-latest to grok-3
    if model == "grok-latest":
        model = "grok-3"
        
    logger.info(f"Generating non-streaming response for model: {model}")
    
    async for token in grok_client.chat(prompt=message_content, model=model, reasoning=False):
        tokens.append(token)
    
    return tokens


async def generate_stream_response(messages: List[Message], model: str):
    """Generate a streaming response in OpenAI format."""
    message_content = messages[-1].content if messages else ""
    
    # Map grok-latest to grok-3
    if model == "grok-latest":
        model = "grok-3"
        
    logger.info(f"Generating streaming response for model: {model}")
    
    async for token in grok_client.chat(prompt=message_content, model=model, reasoning=False):
        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token, "role": "assistant"},
                    "finish_reason": None
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    # Send final chunk
    end_chunk = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }
        ],
    }
    yield f"data: {json.dumps(end_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/")
async def root():
    """Root endpoint."""
    from ngrok_manager import get_current_url
    
    ngrok_url = get_current_url()
    base_url = ngrok_url if ngrok_url else "http://localhost:8080"
    
    return {
        "name": "GrokProxy",
        "version": "1.0.0",
        "status": "operational",
        "base_url": base_url,
        "ngrok_url": ngrok_url,
        "endpoints": {
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "ngrok_info": "/ngrok"
        }
    }


@app.get("/ngrok")
async def get_ngrok_info():
    """Get current ngrok tunnel information."""
    from ngrok_manager import ngrok_manager
    
    url = ngrok_manager.get_public_url(force_refresh=True)
    
    if url:
        return {
            "status": "active",
            "public_url": url,
            "chat_endpoint": f"{url}/v1/chat/completions",
            "models_endpoint": f"{url}/v1/models",
            "dashboard": "http://localhost:4040"
        }
    else:
        return {
            "status": "unavailable",
            "message": "Ngrok tunnel not detected",
            "local_url": "http://localhost:8080",
            "dashboard": "http://localhost:4040"
        }


@app.get("/v1/images/proxy")
async def proxy_image(url: str):
    """
    Proxy an image download through the authenticated session.
    
    Args:
        url: The image URL to download
        
    Returns:
        StreamingResponse with the image content
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    return StreamingResponse(
        grok_client.download_image(url),
        media_type="image/png"  # Default to PNG, could be dynamic
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": int(time.time())}


@app.get("/v1/models", response_model=ModelList, dependencies=[Depends(verify_api_key)])
async def get_models():
    """Get list of available models (OpenAI-compatible)."""
    logger.info("Models list requested")
    return models_data


@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def handle_openai_request(request: OpenAIRequest, http_request: Request):
    """
    Handle OpenAI-compatible chat completion requests.
    
    Supports both streaming and non-streaming responses.
    """
    client_ip = http_request.client.host
    logger.info(f"Chat completion request from {client_ip} - Model: {request.model}, Stream: {request.stream}")
    
    try:
        if request.stream:
            # Streaming response
            return StreamingResponse(
                generate_stream_response(request.messages, request.model),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming response
            tokens = "".join(await generate_response(request.messages, request.model))
            
            response = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": tokens
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": UsageInfo(
                    prompt_tokens=len(request.messages[-1].content.split()),
                    completion_tokens=len(tokens.split()),
                    total_tokens=len(request.messages[-1].content.split()) + len(tokens.split())
                ).dict()
            }
            
            logger.info(f"✓ Response generated successfully ({len(tokens)} chars)")
            return response
            
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
