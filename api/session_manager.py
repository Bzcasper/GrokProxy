"""
Session manager for handling Grok API sessions.
"""

from typing import Optional, Dict, Any
from .db_client import DatabaseClient


class SessionManager:
    """Manage Grok API sessions."""
    
    def __init__(self, db_client: DatabaseClient):
        """
        Initialize session manager.
        
        Args:
            db_client: Database client instance
        """
        self.db = db_client
    
    async def acquire_session(self, provider: str = "grok") -> Optional[Dict[str, Any]]:
        """
        Acquire a healthy session for use.
        
        Args:
            provider: Provider name (default: grok)
            
        Returns:
            Session dict or None if no sessions available
        """
        session = await self.db.get_healthy_session(provider)
        
        if session:
            # Update usage
            await self.db.update_session_usage(session['id'])
        
        return session
    
    async def release_session(self, session_id: str, success: bool = True):
        """
        Release a session after use.

        Args:
            session_id: Session ID
            success: Whether the request was successful
        """
        if not success:
            # TODO: Mark session as degraded if request failed
            # Currently disabled due to database constraint
            # await self.db.update_session_status(session_id, "degraded")
            pass
    
    async def get_session_count(self) -> int:
        """Get total number of sessions."""
        sessions = await self.db.list_sessions()
        return len(sessions)
    
    async def get_healthy_session_count(self) -> int:
        """Get number of healthy sessions."""
        sessions = await self.db.list_sessions()
        return len([s for s in sessions if s.get('status') == 'healthy'])
