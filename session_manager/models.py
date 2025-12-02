"""
Pydantic models for session management.
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import hashlib


class SessionStatus(str, Enum):
    """Session health status."""
    HEALTHY = "healthy"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SessionCreate(BaseModel):
    """Model for creating a new session."""
    
    cookie_text: str = Field(..., description="Full cookie string")
    provider: str = Field(default="grok", description="Provider name")
    expires_at: Optional[datetime] = Field(None, description="Cookie expiration time")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator("cookie_text")
    def validate_cookie(cls, v):
        """Validate cookie is not empty."""
        if not v or not v.strip():
            raise ValueError("Cookie text cannot be empty")
        return v.strip()
    
    def get_cookie_hash(self) -> str:
        """Generate hash of cookie for uniqueness check."""
        return hashlib.sha256(self.cookie_text.encode()).hexdigest()


class Session(BaseModel):
    """Session model matching database schema."""
    
    id: str
    cookie_text: str
    cookie_hash: str
    provider: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    usage_count: int
    success_count: int
    failure_count: int
    status: SessionStatus
    last_health_check_at: Optional[datetime]
    metadata: Dict[str, Any]
    
    class Config:
        use_enum_values = False
        
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.usage_count == 0:
            return 0.0
        return self.failure_count / self.usage_count
    
    @property
    def age_hours(self) -> float:
        """Calculate session age in hours."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        created = self.created_at
        if created.tzinfo is None:
            # Assume UTC if naive
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        return delta.total_seconds() / 3600
    
    def should_rotate(
        self,
        usage_threshold: int = 500,
        failure_threshold: float = 0.2,
        max_age_hours: int = 24
    ) -> tuple[bool, Optional[str]]:
        """
        Check if session should be rotated.
        
        Args:
            usage_threshold: Max usage count before rotation
            failure_threshold: Max failure rate before rotation
            max_age_hours: Max age in hours before rotation
        
        Returns:
            Tuple of (should_rotate, reason)
        """
        if self.usage_count >= usage_threshold:
            return True, "usage_limit"
        
        if self.failure_rate >= failure_threshold and self.usage_count > 10:
            return True, "failure_rate"
        
        if self.age_hours >= max_age_hours:
            return True, "age_limit"
        
        return False, None
