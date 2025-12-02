"""
Structured JSON logging for GrokProxy.

Provides JSON-formatted logging to stdout with request ID correlation
and automatic sanitization of sensitive data.
"""

import os
import sys
import json
import logging
import re
from typing import Any, Dict, Optional
from contextvars import ContextVar
from datetime import datetime

# Context variable for request ID
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    
    # Patterns for sensitive data to sanitize
    SENSITIVE_PATTERNS = [
        (re.compile(r'(cookie|Cookie)["\s:=]+([^"\s,}]+)', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'(api[_-]?key|apikey|authorization|auth)["\s:=]+([^"\s,}]+)', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'(password|passwd|pwd)["\s:=]+([^"\s,}]+)', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'(bearer|token)["\s:=]+([^"\s,}]+)', re.IGNORECASE), r'\1=***REDACTED***'),
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID if available
        request_id = request_id_ctx.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields from record
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add source location for errors and above
        if record.levelno >= logging.ERROR:
            log_data["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }
        
        # Sanitize the entire log data
        log_json = json.dumps(log_data, default=str)
        log_json = self._sanitize(log_json)
        
        return log_json
    
    def _sanitize(self, text: str) -> str:
        """Remove sensitive data from log text."""
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def sanitize_log_data(data: Any) -> Any:
    """
    Sanitize sensitive data from log payloads.
    
    Args:
        data: Data to sanitize (dict, str, or other)
    
    Returns:
        Sanitized copy of the data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Redact sensitive keys
            if any(sensitive in key_lower for sensitive in ["cookie", "password", "api_key", "apikey", "token", "auth"]):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_log_data(value)
        
        return sanitized
    
    elif isinstance(data, (list, tuple)):
        return [sanitize_log_data(item) for item in data]
    
    elif isinstance(data, str):
        # Apply pattern-based sanitization
        result = data
        for pattern, replacement in JSONFormatter.SENSITIVE_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
    
    else:
        return data


def setup_logging(
    log_level: Optional[str] = None,
    force_json: bool = True
) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   Defaults to LOG_LEVEL env var or INFO
        force_json: Force JSON formatting even for non-production
    """
    # Determine log level
    level_str = log_level or os.getenv("LOG_LEVEL", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Use JSON formatter
    if force_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    root_logger.info(f"Logging configured with level={level_str}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class RequestIDMiddleware:
    """FastAPI middleware to inject request ID into logs."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        """Process request with request ID context."""
        if scope["type"] == "http":
            import uuid
            
            # Generate or extract request ID
            headers = dict(scope.get("headers", []))
            request_id = headers.get(b"x-request-id", str(uuid.uuid4()).encode()).decode()
            
            # Set context
            token = request_id_ctx.set(request_id)
            
            try:
                # Add request ID to response headers
                async def send_with_request_id(message):
                    if message["type"] == "http.response.start":
                        headers = message.get("headers", [])
                        headers.append((b"x-request-id", request_id.encode()))
                        message["headers"] = headers
                    await send(message)
                
                await self.app(scope, receive, send_with_request_id)
            finally:
                request_id_ctx.reset(token)
        else:
            await self.app(scope, receive, send)


# Example usage
if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)
    
    # Set request ID for testing
    request_id_ctx.set("test-request-123")
    
    logger.info("This is an info message")
    logger.warning("This is a warning", extra={"user_id": "user-456"})
    
    # Test sanitization
    logger.info("Cookie: sso=secret_value_here; api_key=sk-1234567890")
    
    try:
        raise ValueError("Test exception")
    except Exception:
        logger.exception("An error occurred")
