"""
Minimal Vercel serverless entry point for GrokProxy.
Last updated: 2025-12-01 18:20 PST
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

# Get the directory containing this file
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Create minimal FastAPI app
app = FastAPI(
    title="GrokProxy",
    description="Production-grade proxy for xAI's Grok API",
    version="2.1.0"
)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve beautiful homepage."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    
    # Fallback JSON response
    return {
        "service": "GrokProxy",
        "version": "2.1.0",
        "status": "operational",
        "environment": "vercel-serverless",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat": "/v1/chat/completions"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": "vercel-serverless"
    }


@app.get("/v1/models")
async def models():
    """List models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "grok-3",
                "object": "model",
                "created": 1234567890,
                "owned_by": "xai"
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat():
    """Chat completions (minimal)."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "grok-3",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "GrokProxy is running on Vercel! Full implementation coming soon."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20
        }
    }
