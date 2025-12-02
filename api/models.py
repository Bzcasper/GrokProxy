"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# Chat Completion Models

class ChatMessage(BaseModel):
    """Chat message."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Chat completion request."""
    model: str = "grok-3"
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = False


class ChatCompletionChoice(BaseModel):
    """Chat completion choice."""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    """Token usage."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


# Session Models

class Session(BaseModel):
    """Session model."""
    id: str
    provider: str
    status: str
    cookies: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    usage_count: int = 0
    created_at: datetime
    last_used_at: Optional[datetime] = None


# Generation Models

class Generation(BaseModel):
    """Generation record."""
    id: str
    request_id: str
    session_id: Optional[str] = None
    provider: str
    model: str
    prompt: str
    prompt_tokens: Optional[int] = None
    response_text: Optional[str] = None
    response_tokens: Optional[int] = None
    response_raw: Optional[Dict[str, Any]] = None
    status: int
    latency_ms: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


# Image Generation Models

class ImageGenerationRequest(BaseModel):
    """Image generation request."""
    prompt: str
    style: Optional[str] = "cinematic"
    model: str = "grok-3"


class ImageGenerationResponse(BaseModel):
    """Image generation response."""
    id: str
    created: int
    data: List[Dict[str, str]]  # [{"url": "...", "cloudinary_url": "..."}]
