"""
Health check system for GrokProxy.

Checks database connectivity, session pool health, and external dependencies.
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Health status for a single component."""
    
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "status": self.status.value,
        }
        
        if self.message:
            result["message"] = self.message
        
        if self.details:
            result["details"] = self.details
        
        return result


class HealthChecker:
    """Performs health checks on system components."""
    
    def __init__(self, db_client=None, session_manager=None):
        """
        Initialize health checker.
        
        Args:
            db_client: Database client instance
            session_manager: Session manager instance
        """
        self.db_client = db_client
        self.session_manager = session_manager
    
    async def check_database(self) -> ComponentHealth:
        """Check database connectivity."""
        if not self.db_client:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message="Database client not initialized"
            )
        
        try:
            is_healthy = await self.db_client.health_check()
            
            if is_healthy:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection OK"
                )
            else:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database health check failed"
                )
        
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}"
            )
    
    async def check_session_pool(self) -> ComponentHealth:
        """Check session pool health."""
        if not self.db_client:
            return ComponentHealth(
                name="session_pool",
                status=HealthStatus.UNHEALTHY,
                message="Cannot check sessions - database not available"
            )
        
        try:
            # Count sessions by status
            sessions = await self.db_client.list_sessions(limit=1000)
            
            healthy = sum(1 for s in sessions if s["status"] == "healthy")
            quarantined = sum(1 for s in sessions if s["status"] == "quarantined")
            expired = sum(1 for s in sessions if s["status"] == "expired")
            total = len(sessions)
            
            # Determine overall health
            if healthy == 0:
                status = HealthStatus.UNHEALTHY
                message = "No healthy sessions available"
            elif healthy < 3:
                status = HealthStatus.DEGRADED
                message = "Low number of healthy sessions"
            else:
                status = HealthStatus.HEALTHY
                message = "Session pool OK"
            
            return ComponentHealth(
                name="session_pool",
                status=status,
                message=message,
                details={
                    "total": total,
                    "healthy": healthy,
                    "quarantined": quarantined,
                    "expired": expired
                }
            )
        
        except Exception as e:
            logger.error(f"Session pool health check error: {e}")
            return ComponentHealth(
                name="session_pool",
                status=HealthStatus.UNHEALTHY,
                message=f"Session pool check failed: {str(e)}"
            )
    
    async def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks.
        
        Returns:
            Dictionary with overall status and component details
        """
        components: List[ComponentHealth] = []
        
        # Check database
        db_health = await self.check_database()
        components.append(db_health)
        
        # Check session pool (only if DB is healthy)
        if db_health.status != HealthStatus.UNHEALTHY:
            session_health = await self.check_session_pool()
            components.append(session_health)
        
        # Determine overall status
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            "status": overall_status.value,
            "components": [c.to_dict() for c in components]
        }


async def create_health_endpoint(health_checker: HealthChecker):
    """
    Create a FastAPI health check endpoint.
    
    Args:
        health_checker: HealthChecker instance
    
    Returns:
        Async function for health endpoint
    """
    async def health_endpoint():
        """Health check endpoint."""
        result = await health_checker.check_all()
        
        # Return 503 if unhealthy, 200 if healthy or degraded
        status_code = 503 if result["status"] == "unhealthy" else 200
        
        from fastapi import Response
        import json
        
        return Response(
            content=json.dumps(result, indent=2),
            media_type="application/json",
            status_code=status_code
        )
    
    return health_endpoint
