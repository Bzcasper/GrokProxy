"""
Async PostgreSQL/Neon database client using asyncpg.

Provides connection pooling, CRUD operations, and transactions for all tables.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import asyncpg
from asyncpg.pool import Pool

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Async database client with connection pooling."""
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        min_size: int = 10,
        max_size: int = 20,
        timeout: float = 10.0
    ):
        """
        Initialize database client.
        
        Args:
            database_url: PostgreSQL connection string (defaults to DATABASE_URL env var)
            min_size: Minimum pool size
            max_size: Maximum pool size
            timeout: Connection timeout in seconds
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL must be provided or set in environment")
        
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self.pool: Optional[Pool] = None
    
    async def connect(self) -> None:
        """Initialize connection pool."""
        if self.pool:
            logger.warning("Database pool already initialized")
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.timeout,
                command_timeout=30.0
            )
            logger.info(f"✓ Database pool created (min={self.min_size}, max={self.max_size})")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("✓ Database pool closed")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    # ==================== SESSION OPERATIONS ====================
    
    async def create_session(
        self,
        cookie_text: str,
        cookie_hash: str,
        provider: str = "grok",
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new session.
        
        Returns:
            Session UUID
        """
        async with self.pool.acquire() as conn:
            metadata_json = json.dumps(metadata or {})
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (cookie_text, cookie_hash, provider, expires_at, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                RETURNING id
                """,
                cookie_text,
                cookie_hash,
                provider,
                expires_at,
                metadata_json
            )
            session_id = str(row["id"])
            logger.info(f"Created session {session_id} for provider {provider}")
            return session_id
    
    async def get_healthy_session(self, provider: str = "grok") -> Optional[Dict[str, Any]]:
        """
        Get least recently used healthy session.
        
        Returns:
            Session dict or None if no healthy sessions available
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM sessions
                WHERE status = 'healthy' AND provider = $1
                ORDER BY last_used_at NULLS FIRST, usage_count ASC
                LIMIT 1
                """,
                provider
            )
            if not row:
                return None
            
            # Convert to dict and fix types
            result = dict(row)
            result["id"] = str(result["id"])  # Convert UUID to string
            if isinstance(result.get("metadata"), str):
                result["metadata"] = json.loads(result["metadata"])  # Parse JSON
            return result
    
    async def update_session_last_used(self, session_id: str) -> None:
        """Update session last_used_at timestamp."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET last_used_at = now()
                WHERE id = $1
                """,
                session_id
            )
    
    async def increment_session_usage(
        self,
        session_id: str,
        success: bool = True
    ) -> None:
        """
        Atomically increment session usage counters.
        
        Args:
            session_id: Session UUID
            success: Whether the request was successful
        """
        async with self.pool.acquire() as conn:
            if success:
                await conn.execute(
                    """
                    UPDATE sessions
                    SET usage_count = usage_count + 1,
                        success_count = success_count + 1,
                        last_used_at = now()
                    WHERE id = $1
                    """,
                    session_id
                )
            else:
                await conn.execute(
                    """
                    UPDATE sessions
                    SET usage_count = usage_count + 1,
                        failure_count = failure_count + 1,
                        last_used_at = now()
                    WHERE id = $1
                    """,
                    session_id
                )
    
    async def update_session_status(
        self,
        session_id: str,
        status: str
    ) -> None:
        """
        Update session health status.
        
        Args:
            status: One of 'healthy', 'quarantined', 'expired', 'revoked'
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = $1, last_health_check_at = now()
                WHERE id = $2
                """,
                status,
                session_id
            )
            logger.info(f"Session {session_id} status updated to {status}")
    
    async def list_sessions(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List sessions with optional status filter.
        
        Args:
            status: Optional status filter
            limit: Maximum number of sessions to return
        """
        async with self.pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    status,
                    limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            
            # Convert UUIDs and JSON
            results = []
            for row in rows:
                result = dict(row)
                result["id"] = str(result["id"])  # Convert UUID to string
                if isinstance(result.get("metadata"), str):
                    result["metadata"] = json.loads(result["metadata"])  # Parse JSON
                results.append(result)
            
            return results
    
    async def delete_session(self, session_id: str) -> None:
        """Delete a session (hard delete)."""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE id = $1", session_id)
            logger.info(f"Deleted session {session_id}")
    
    # ==================== USER OPERATIONS ====================
    
    async def create_user(
        self,
        api_key_hash: str,
        username: Optional[str] = None,
        role: str = "user",
        rate_limit_per_minute: int = 60,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new user.
        
        Returns:
            User UUID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (api_key_hash, username, role, rate_limit_per_minute, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                api_key_hash,
                username,
                role,
                rate_limit_per_minute,
                metadata or {}
            )
            user_id = str(row["id"])
            logger.info(f"Created user {user_id} (role={role})")
            return user_id
    
    async def get_user_by_api_key_hash(self, api_key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user by API key hash."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM users
                WHERE api_key_hash = $1 AND is_active = true
                """,
                api_key_hash
            )
            return dict(row) if row else None
    
    async def update_user_last_active(self, user_id: str) -> None:
        """Update user last_active_at timestamp."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET last_active_at = now()
                WHERE id = $1
                """,
                user_id
            )
    
    # ==================== CONVERSATION OPERATIONS ====================
    
    async def create_conversation(
        self,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new conversation.
        
        Returns:
            Conversation UUID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (user_id, title, metadata)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_id,
                title,
                metadata or {}
            )
            return str(row["id"])
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                conversation_id
            )
            return dict(row) if row else None
    
    # ==================== GENERATION OPERATIONS ====================
    
    async def insert_generation(
        self,
        request_id: str,
        provider: str,
        model: str,
        prompt: str,
        status: int,
        latency_ms: int,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        response_text: Optional[str] = None,
        response_tokens: Optional[int] = None,
        response_raw: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Insert a generation record.
        
        Returns:
            Generation UUID
        """
        async with self.pool.acquire() as conn:
            # Convert dicts to JSON strings
            response_raw_json = json.dumps(response_raw or {})
            metadata_json = json.dumps(metadata or {})
            
            row = await conn.fetchrow(
                """
                INSERT INTO generations (
                    request_id, user_id, conversation_id, session_id,
                    provider, model, prompt, prompt_tokens,
                    response_text, response_tokens, response_raw,
                    status, latency_ms, error_message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13, $14, $15::jsonb)
                RETURNING id
                """,
                request_id,
                user_id,
                conversation_id,
                session_id,
                provider,
                model,
                prompt,
                prompt_tokens,
                response_text,
                response_tokens,
                response_raw_json,
                status,
                latency_ms,
                error_message,
                metadata_json
            )
            return str(row["id"])
    
    async def get_generations_by_conversation(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all generations for a conversation."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM generations
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                conversation_id,
                limit
            )
            return [dict(row) for row in rows]
    
    # ==================== HEALTH CHECK ====================
    
    async def health_check(self) -> bool:
        """
        Check database connectivity.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.pool:
                return False
            
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
