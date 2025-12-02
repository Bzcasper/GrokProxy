"""
Sentry integration for error tracking and performance monitoring.

Optional integration - only initializes if SENTRY_DSN is set.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def setup_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1
) -> bool:
    """
    Initialize Sentry SDK if DSN is provided.
    
    Args:
        dsn: Sentry DSN (defaults to SENTRY_DSN env var)
        environment: Environment name (defaults to SENTRY_ENVIRONMENT env var or 'production')
        traces_sample_rate: Sample rate for performance monitoring (0.0-1.0)
        profiles_sample_rate: Sample rate for profiling (0.0-1.0)
    
    Returns:
        True if Sentry was initialized, False otherwise
    """
    dsn = dsn or os.getenv("SENTRY_DSN")
    
    if not dsn:
        logger.info("Sentry DSN not provided - error tracking disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
        from sentry_sdk.integrations.httpx import HttpxIntegration
        
        environment = environment or os.getenv("SENTRY_ENVIRONMENT", "production")
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                AsyncPGIntegration(),
                HttpxIntegration(),
            ],
            # Add custom tags
            before_send=_before_send,
        )
        
        logger.info(f"✓ Sentry initialized (environment={environment})")
        return True
        
    except ImportError:
        logger.warning("sentry-sdk not installed - error tracking disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter and sanitize events before sending to Sentry.
    
    Args:
        event: Sentry event
        hint: Event hint with additional context
    
    Returns:
        Modified event or None to drop the event
    """
    # Sanitize sensitive data from breadcrumbs
    if "breadcrumbs" in event:
        for breadcrumb in event["breadcrumbs"].get("values", []):
            if "data" in breadcrumb:
                _sanitize_dict(breadcrumb["data"])
    
    # Sanitize request data
    if "request" in event:
        request = event["request"]
        
        # Redact headers
        if "headers" in request:
            _sanitize_dict(request["headers"])
        
        # Redact cookies
        if "cookies" in request:
            request["cookies"] = "***REDACTED***"
        
        # Redact query params with sensitive keys
        if "query_string" in request:
            _sanitize_query_string(request)
    
    # Sanitize extra data
    if "extra" in event:
        _sanitize_dict(event["extra"])
    
    return event


def _sanitize_dict(data: Dict[str, Any]) -> None:
    """Sanitize sensitive keys in a dictionary (in-place)."""
    sensitive_keys = {
        "cookie", "cookies", "authorization", "auth",
        "api_key", "apikey", "api-key",
        "password", "passwd", "pwd",
        "token", "access_token", "refresh_token",
        "secret", "private_key", "session"
    }
    
    for key in list(data.keys()):
        key_lower = key.lower()
        
        # Check if key contains sensitive keywords
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            data[key] = "***REDACTED***"
        
        # Recursively sanitize nested dicts
        elif isinstance(data[key], dict):
            _sanitize_dict(data[key])


def _sanitize_query_string(request: Dict[str, Any]) -> None:
    """Sanitize sensitive query parameters."""
    if "query_string" in request:
        qs = request["query_string"]
        
        # Simple sanitization for common sensitive params
        sensitive_params = ["api_key", "token", "password", "secret"]
        
        for param in sensitive_params:
            if param in qs.lower():
                request["query_string"] = "***REDACTED***"
                return


def capture_exception(
    error: Exception,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **extra
) -> None:
    """
    Capture an exception with additional context.
    
    Args:
        error: The exception to capture
        user_id: Optional user ID
        request_id: Optional request ID
        session_id: Optional session ID
        **extra: Additional context to attach
    """
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            # Add user context
            if user_id:
                scope.set_user({"id": user_id})
            
            # Add tags
            if request_id:
                scope.set_tag("request_id", request_id)
            
            if session_id:
                scope.set_tag("session_id", session_id)
            
            # Add extra context
            for key, value in extra.items():
                scope.set_extra(key, value)
            
            sentry_sdk.capture_exception(error)
            
    except ImportError:
        # Sentry not available
        pass
    except Exception as e:
        logger.error(f"Failed to capture exception in Sentry: {e}")


def capture_message(
    message: str,
    level: str = "info",
    **extra
) -> None:
    """
    Capture a message in Sentry.
    
    Args:
        message: Message to capture
        level: Severity level (info, warning, error)
        **extra: Additional context
    """
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            
            sentry_sdk.capture_message(message, level=level)
            
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to capture message in Sentry: {e}")


# Example usage
if __name__ == "__main__":
    # Test Sentry setup
    if setup_sentry():
        print("Sentry initialized successfully")
        
        # Test exception capture
        try:
            raise ValueError("Test exception for Sentry")
        except Exception as e:
            capture_exception(
                e,
                user_id="test-user",
                request_id="test-request-123",
                extra_field="test value"
            )
        
        print("Test exception sent to Sentry")
    else:
        print("Sentry not configured")
