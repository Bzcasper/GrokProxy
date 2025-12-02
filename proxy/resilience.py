"""
Resilience patterns: retry with exponential backoff, circuit breaker.

Uses tenacity for retries and implements a simple circuit breaker.
"""

import time
import logging
import asyncio
from typing import Optional, Callable, Any
from enum import Enum

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Simple circuit breaker pattern implementation.
    
    After N consecutive failures, the circuit opens and rejects requests
    for a cooldown period. Then it goes to half-open to test recovery.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying to recover
            expected_exception: Exception type that triggers circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s"
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Any exception from the function
        """
        # Check if circuit should transition from open to half-open
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                logger.info(f"Circuit '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Async version of call()."""
        # Check if circuit should transition from open to half-open
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                logger.info(f"Circuit '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit '{self.name}' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit '{self.name}' recovered, transitioning to CLOSED")
            self.state = CircuitState.CLOSED
        
        self.failure_count = 0
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit '{self.name}' threshold reached ({self.failure_count} failures), "
                f"opening circuit"
            )
            self.state = CircuitState.OPEN
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        logger.info(f"Circuit '{self.name}' manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Tenacity retry decorator for common patterns
def retry_with_backoff(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exception_types: tuple = (Exception,)
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        exception_types: Tuple of exception types to retry on
    
    Returns:
        Decorated function with retry logic
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exception_types),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# Example usage
if __name__ == "__main__":
    import random
    
    # Test circuit breaker
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=5)
    
    def flaky_function():
        """Randomly fails."""
        if random.random() < 0.7:
            raise ValueError("Random failure")
        return "Success"
    
    for i in range(10):
        try:
            result = cb.call(flaky_function)
            print(f"Attempt {i+1}: {result}")
        except CircuitBreakerOpenError as e:
            print(f"Attempt {i+1}: Circuit is open")
        except ValueError as e:
            print(f"Attempt {i+1}: Function failed - {e}")
        
        time.sleep(1)
