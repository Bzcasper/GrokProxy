"""
Admin API endpoints for session management.

Requires admin authentication.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from session_manager.models import SessionCreate, SessionStatus

logger = logging.getLogger(__name__)

# Admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()


class SessionResponse(BaseModel):
    """Session response model."""
    id: str
    cookie_hash: str  # Don't expose full cookie in responses
    provider: str
    status: str
    created_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    success_count: int
    failure_count: int
    failure_rate: float


class SessionListResponse(BaseModel):
    """List of sessions response."""
    total: int
    sessions: List[SessionResponse]


class SessionStats(BaseModel):
    """Session statistics."""
    total: int
    healthy: int
    quarantined: int
    expired: int
    revoked: int
    in_flight: int


def verify_admin_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    admin_keys: List[str] = []  # This should be injected from app state
):
    """Verify admin API key."""
    if not admin_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin API keys not configured"
        )
    
    if credentials.credentials not in admin_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key"
        )
    
    return credentials.credentials


def create_admin_endpoints(db_client, session_manager, admin_api_keys: List[str]):
    """
    Create admin endpoints with dependency injection.
    
    Args:
        db_client: Database client instance
        session_manager: Session manager instance
        admin_api_keys: List of valid admin API keys
    
    Returns:
        Configured admin router
    """
    
    @admin_router.get("/sessions", response_model=SessionListResponse)
    async def list_sessions(
        status_filter: Optional[str] = None,
        limit: int = 100,
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """List all sessions with optional status filter."""
        sessions = await db_client.list_sessions(status=status_filter, limit=limit)
        
        session_responses = []
        for s in sessions:
            failure_rate = s["failure_count"] / s["usage_count"] if s["usage_count"] > 0 else 0.0
            session_responses.append(
                SessionResponse(
                    id=s["id"],
                    cookie_hash=s["cookie_hash"][:16] + "...",
                    provider=s["provider"],
                    status=s["status"],
                    created_at=s["created_at"],
                    last_used_at=s["last_used_at"],
                    usage_count=s["usage_count"],
                    success_count=s["success_count"],
                    failure_count=s["failure_count"],
                    failure_rate=failure_rate
                )
            )
        
        return SessionListResponse(
            total=len(session_responses),
            sessions=session_responses
        )
    
    @admin_router.post("/sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(
        session_create: SessionCreate,
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """Create a new session."""
        session_id = await session_manager.create_session(session_create)
        
        return {
            "session_id": session_id,
            "message": "Session created successfully"
        }
    
    @admin_router.patch("/sessions/{session_id}/quarantine")
    async def quarantine_session(
        session_id: str,
        reason: str = "Manual quarantine",
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """Manually quarantine a session."""
        await session_manager.quarantine_session(session_id, reason)
        
        return {
            "session_id": session_id,
            "message": f"Session quarantined: {reason}"
        }
    
    @admin_router.patch("/sessions/{session_id}/activate")
    async def activate_session(
        session_id: str,
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """Manually activate a quarantined session."""
        await db_client.update_session_status(session_id, SessionStatus.HEALTHY.value)
        
        return {
            "session_id": session_id,
            "message": "Session activated"
        }
    
    @admin_router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """Delete a session."""
        await session_manager.delete_session(session_id)
        
        return {
            "session_id": session_id,
            "message": "Session deleted"
        }
    
    @admin_router.get("/stats", response_model=SessionStats)
    async def get_stats(
        admin_key: str = Depends(lambda c=Depends(security): verify_admin_api_key(c, admin_api_keys))
    ):
        """Get session manager statistics."""
        stats = await session_manager.get_stats()
        
        return SessionStats(**stats)
    
    return admin_router
