"""
Production session manager with automatic rotation, health checks, and rate limiting.

Replaces the YAML-based ChangeCookie with a database-backed approach.
"""

import os
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

from session_manager.models import Session, SessionStatus, SessionCreate
from observability import get_logger, metrics

logger = get_logger(__name__)


class SessionManager:
    """Manages cookie/session pool with automatic rotation and health checks."""
    
    def __init__(
        self,
        db_client,
        rotation_threshold: Optional[int] = None,
        failure_threshold: Optional[float] = None,
        max_age_hours: Optional[int] = None,
        health_check_interval: Optional[int] = None
    ):
        """
        Initialize session manager.
        
        Args:
            db_client: Database client instance
            rotation_threshold: Max usage count before rotation
            failure_threshold: Max failure rate before rotation
            max_age_hours: Max session age in hours
            health_check_interval: Health check interval in seconds
        """
        self.db = db_client
        
        # Configuration from environment or defaults
        self.rotation_threshold = rotation_threshold or int(
            os.getenv("SESSION_ROTATION_THRESHOLD", "500")
        )
        self.failure_threshold = failure_threshold or float(
            os.getenv("SESSION_FAILURE_THRESHOLD", "0.2")
        )
        self.max_age_hours = max_age_hours or int(
            os.getenv("SESSION_MAX_AGE_HOURS", "24")
        )
        self.health_check_interval = health_check_interval or int(
            os.getenv("SESSION_HEALTH_CHECK_INTERVAL", "30")
        )
        
        # In-memory tracking of in-flight requests per session
        self.in_flight: Dict[str, int] = {}
        self.lock = asyncio.Lock()
        
        # Background task
        self._health_check_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"SessionManager initialized: rotation_threshold={self.rotation_threshold}, "
            f"failure_threshold={self.failure_threshold}, "
            f"max_age_hours={self.max_age_hours}, "
            f"health_check_interval={self.health_check_interval}s"
        )
    
    async def start(self) -> None:
        """Start background tasks."""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Session manager background tasks started")
    
    async def stop(self) -> None:
        """Stop background tasks."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            logger.info("Session manager background tasks stopped")
    
    async def acquire_session(self, provider: str = "grok") -> Optional[Session]:
        """
        Acquire a healthy session for use.
        
        Args:
            provider: Provider name
        
        Returns:
            Session object or None if no healthy sessions available
        """
        async with self.lock:
            # Get healthy session from database (LRU selection)
            session_dict = await self.db.get_healthy_session(provider=provider)
            
            if not session_dict:
                logger.warning(f"No healthy sessions available for provider {provider}")
                return None
            
            # Convert to Pydantic model
            session = Session(**session_dict)
            
            # Track in-flight
            self.in_flight[session.id] = self.in_flight.get(session.id, 0) + 1
            
            # Update last_used_at
            await self.db.update_session_last_used(session.id)
            
            logger.debug(
                f"Acquired session {session.id[:8]}... "
                f"(usage={session.usage_count}, in_flight={self.in_flight[session.id]})"
            )
            
            return session
    
    async def release_session(self, session_id: str, success: bool = True, error: Optional[str] = None) -> None:
        """
        Release a session after use.
        
        Args:
            session_id: Session UUID
            success: Whether the request was successful
            error: Optional error message
        """
        async with self.lock:
            # Decrement in-flight counter
            if session_id in self.in_flight:
                self.in_flight[session_id] = max(0, self.in_flight[session_id] - 1)
            
            # Update usage counters in database
            await self.db.increment_session_usage(session_id, success=success)
            
            # Record metrics
            metrics.session_usage.labels(
                session_id=session_id[:8],
                success=str(success)
            ).inc()
            
            # Check if session should be quarantined due to failure
            if not success:
                # Get updated session data
                sessions = await self.db.list_sessions(limit=1)
                session_dict = next((s for s in sessions if s["id"] == session_id), None)
                
                if session_dict:
                    session = Session(**session_dict)
                    
                    # Check if failure rate exceeds threshold
                    if session.failure_rate >= self.failure_threshold and session.usage_count > 10:
                        await self.quarantine_session(
                            session_id,
                            reason=f"High failure rate: {session.failure_rate:.2%}"
                        )
                        metrics.record_session_rotation("failure_rate")
            
            logger.debug(
                f"Released session {session_id[:8]}... "
                f"(success={success}, error={error or 'none'})"
            )
    
    async def quarantine_session(self, session_id: str, reason: str) -> None:
        """
        Quarantine a session.
        
        Args:
            session_id: Session UUID
            reason: Reason for quarantine
        """
        await self.db.update_session_status(session_id, SessionStatus.QUARANTINED.value)
        logger.warning(f"Session {session_id[:8]}... quarantined: {reason}")
    
    async def create_session(self, session_create: SessionCreate) -> str:
        """
        Create a new session.
        
        Args:
            session_create: Session creation data
        
        Returns:
            Session UUID
        """
        cookie_hash = session_create.get_cookie_hash()
        
        session_id = await self.db.create_session(
            cookie_text=session_create.cookie_text,
            cookie_hash=cookie_hash,
            provider=session_create.provider,
            expires_at=session_create.expires_at,
            metadata=session_create.metadata
        )
        
        logger.info(f"Created new session {session_id[:8]}... for provider {session_create.provider}")
        return session_id
    
    async def delete_session(self, session_id: str) -> None:
        """
        Delete a session.
        
        Args:
            session_id: Session UUID
        """
        await self.db.delete_session(session_id)
        logger.info(f"Deleted session {session_id[:8]}...")
    
    async def _health_check_loop(self) -> None:
        """Background task to perform health checks and rotation."""
        logger.info("Health check loop started")
        
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}", exc_info=True)
    
    async def _perform_health_check(self) -> None:
        """Perform health check and rotation on all sessions."""
        try:
            # Get all sessions
            sessions = await self.db.list_sessions(limit=1000)
            
            healthy_count = 0
            quarantined_count = 0
            expired_count = 0
            rotated_count = 0
            
            for session_dict in sessions:
                session = Session(**session_dict)
                
                # Count by status
                if session.status == SessionStatus.HEALTHY:
                    healthy_count += 1
                elif session.status == SessionStatus.QUARANTINED:
                    quarantined_count += 1
                elif session.status == SessionStatus.EXPIRED:
                    expired_count += 1
                
                # Skip non-healthy sessions
                if session.status != SessionStatus.HEALTHY:
                    continue
                
                # Check if session should be rotated
                should_rotate, reason = session.should_rotate(
                    usage_threshold=self.rotation_threshold,
                    failure_threshold=self.failure_threshold,
                    max_age_hours=self.max_age_hours
                )
                
                if should_rotate:
                    # Mark as expired
                    await self.db.update_session_status(
                        session.id,
                        SessionStatus.EXPIRED.value
                    )
                    
                    rotated_count += 1
                    healthy_count -= 1
                    expired_count += 1
                    
                    logger.info(
                        f"Rotated session {session.id[:8]}... "
                        f"(reason={reason}, usage={session.usage_count}, "
                        f"failure_rate={session.failure_rate:.2%}, age={session.age_hours:.1f}h)"
                    )
                    
                    metrics.record_session_rotation(reason)
            
            # Update metrics
            metrics.update_active_sessions(
                healthy=healthy_count,
                quarantined=quarantined_count,
                expired=expired_count
            )
            
            if rotated_count > 0:
                logger.info(
                    f"Health check complete: {rotated_count} sessions rotated, "
                    f"{healthy_count} healthy, {quarantined_count} quarantined, {expired_count} expired"
                )
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
    
    async def get_stats(self) -> Dict:
        """
        Get session manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        sessions = await self.db.list_sessions(limit=1000)
        
        stats = {
            "total": len(sessions),
            "healthy": sum(1 for s in sessions if s["status"] == "healthy"),
            "quarantined": sum(1 for s in sessions if s["status"] == "quarantined"),
            "expired": sum(1 for s in sessions if s["status"] == "expired"),
            "revoked": sum(1 for s in sessions if s["status"] == "revoked"),
            "in_flight": sum(self.in_flight.values()),
            "config": {
                "rotation_threshold": self.rotation_threshold,
                "failure_threshold": self.failure_threshold,
                "max_age_hours": self.max_age_hours,
                "health_check_interval": self.health_check_interval
            }
        }
        
        return stats
