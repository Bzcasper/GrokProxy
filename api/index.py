"""
Minimal Vercel serverless entry point for GrokProxy.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Create minimal FastAPI app
app = FastAPI(
    title="GrokProxy",
    description="Production-grade proxy for xAI's Grok API",
    version="2.1.0"
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "GrokProxy",
        "version": "2.1.0",
        "status": "operational",
        "environment": "vercel-serverless"
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
