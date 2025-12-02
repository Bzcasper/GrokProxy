"""
Prometheus metrics for GrokProxy.

Provides counters, histograms, and gauges for monitoring.
"""

import os
import time
from typing import Optional
from functools import wraps

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    """Centralized metrics collector for GrokProxy."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize metrics collector.
        
        Args:
            enabled: Whether metrics collection is enabled
        """
        self.enabled = enabled
        self.registry = CollectorRegistry()
        
        if not self.enabled:
            return
        
        # Request metrics
        self.requests_total = Counter(
            "grokproxy_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status", "user_id"],
            registry=self.registry
        )
        
        self.request_duration_seconds = Histogram(
            "grokproxy_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry
        )
        
        # Generation metrics
        self.generations_total = Counter(
            "grokproxy_generations_total",
            "Total number of generations",
            ["model", "provider", "status"],
            registry=self.registry
        )
        
        self.generation_latency_seconds = Histogram(
            "grokproxy_generation_latency_seconds",
            "Generation latency in seconds",
            ["model", "provider"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.generation_tokens = Histogram(
            "grokproxy_generation_tokens",
            "Number of tokens in generations",
            ["type"],  # prompt, response
            buckets=[10, 50, 100, 500, 1000, 2000, 4000, 8000],
            registry=self.registry
        )
        
        # Session metrics
        self.active_sessions = Gauge(
            "grokproxy_active_sessions",
            "Number of active sessions",
            ["status"],  # healthy, quarantined, expired
            registry=self.registry
        )
        
        self.session_rotations_total = Counter(
            "grokproxy_session_rotations_total",
            "Total number of session rotations",
            ["reason"],  # usage_limit, failure_rate, age_limit, manual
            registry=self.registry
        )
        
        self.session_usage = Counter(
            "grokproxy_session_usage_total",
            "Total session usage count",
            ["session_id", "success"],
            registry=self.registry
        )
        
        # Database metrics
        self.db_queries_total = Counter(
            "grokproxy_db_queries_total",
            "Total number of database queries",
            ["operation", "table"],
            registry=self.registry
        )
        
        self.db_query_duration_seconds = Histogram(
            "grokproxy_db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation", "table"],
            registry=self.registry
        )
        
        self.db_connection_pool_size = Gauge(
            "grokproxy_db_pool_size",
            "Database connection pool size",
            ["state"],  # min, max, current
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            "grokproxy_errors_total",
            "Total number of errors",
            ["type", "endpoint"],
            registry=self.registry
        )
    
    def record_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
        user_id: Optional[str] = None
    ) -> None:
        """Record an HTTP request."""
        if not self.enabled:
            return
        
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
            user_id=user_id or "anonymous"
        ).inc()
        
        self.request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_generation(
        self,
        model: str,
        provider: str,
        status: int,
        latency_ms: int,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None
    ) -> None:
        """Record a generation."""
        if not self.enabled:
            return
        
        self.generations_total.labels(
            model=model,
            provider=provider,
            status=str(status)
        ).inc()
        
        self.generation_latency_seconds.labels(
            model=model,
            provider=provider
        ).observe(latency_ms / 1000.0)
        
        if prompt_tokens:
            self.generation_tokens.labels(type="prompt").observe(prompt_tokens)
        
        if response_tokens:
            self.generation_tokens.labels(type="response").observe(response_tokens)
    
    def record_session_rotation(self, reason: str) -> None:
        """Record a session rotation."""
        if not self.enabled:
            return
        
        self.session_rotations_total.labels(reason=reason).inc()
    
    def update_active_sessions(self, healthy: int, quarantined: int, expired: int) -> None:
        """Update active session gauges."""
        if not self.enabled:
            return
        
        self.active_sessions.labels(status="healthy").set(healthy)
        self.active_sessions.labels(status="quarantined").set(quarantined)
        self.active_sessions.labels(status="expired").set(expired)
    
    def record_db_query(self, operation: str, table: str, duration: float) -> None:
        """Record a database query."""
        if not self.enabled:
            return
        
        self.db_queries_total.labels(operation=operation, table=table).inc()
        self.db_query_duration_seconds.labels(operation=operation, table=table).observe(duration)
    
    def record_error(self, error_type: str, endpoint: str) -> None:
        """Record an error."""
        if not self.enabled:
            return
        
        self.errors_total.labels(type=error_type, endpoint=endpoint).inc()
    
    def get_metrics(self) -> bytes:
        """
        Get Prometheus metrics in text format.
        
        Returns:
            Metrics as bytes
        """
        if not self.enabled:
            return b"# Metrics disabled\n"
        
        return generate_latest(self.registry)


# Global metrics instance
metrics_enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"
metrics = MetricsCollector(enabled=metrics_enabled)


def track_time(metric_name: str):
    """
    Decorator to track execution time.
    
    Args:
        metric_name: Name of the metric to track
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                # This is a simplified version - you'd need to pass labels
                # For real usage, use the record_* methods directly
        
        return wrapper
    return decorator


# Example FastAPI endpoint for metrics
def create_metrics_endpoint():
    """Create a /metrics endpoint for Prometheus scraping."""
    from fastapi import Response
    
    def metrics_endpoint():
        """Serve Prometheus metrics."""
        return Response(
            content=metrics.get_metrics(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    return metrics_endpoint
