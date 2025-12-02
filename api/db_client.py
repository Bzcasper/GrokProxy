"""
Serverless-optimized database client for Vercel deployment.
"""

import os
import asyncpg
from typing import Optional, Dict, Any, List
from datetime import datetime
import json


class DatabaseClient:
    """Lightweight database client for serverless environments."""
    
    def __init__(self, database_url: Optional[str] = None, min_size: int = 1, max_size: int = 3):
        """
        Initialize database client.
        
        Args:
            database_url: PostgreSQL connection string
            min_size: Minimum pool size (keep small for serverless)
            max_size: Maximum pool size (keep small for serverless)
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60
            )
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def test_connection(self) -> bool:
        """Test database connection."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False
    
    # Session Management
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE id = $1",
                session_id
            )
            if row:
                return dict(row)
            return None
    
    async def get_healthy_session(self, provider: str = "grok") -> Optional[Dict[str, Any]]:
        """Get a healthy session for use."""
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
            if row:
                result = dict(row)
                # Convert UUID to string
                result['id'] = str(result['id'])
                # Parse JSON metadata if it's a string
                if isinstance(result.get('metadata'), str):
                    result['metadata'] = json.loads(result['metadata'])
                return result
            return None
    
    async def update_session_usage(self, session_id: str):
        """Update session usage timestamp and count."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET usage_count = usage_count + 1,
                    last_used_at = NOW()
                WHERE id = $1
                """,
                session_id
            )
    
    async def update_session_status(self, session_id: str, status: str):
        """Update session status."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE sessions SET status = $1 WHERE id = $2",
                status,
                session_id
            )
    
    async def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all sessions."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT $1",
                limit
            )
            return [dict(row) for row in rows]
    
    # Generation Tracking
    
    async def insert_generation(
        self,
        request_id: str,
        provider: str,
        model: str,
        prompt: str,
        status: int,
        latency_ms: int,
        session_id: Optional[str] = None,
        response_text: Optional[str] = None,
        response_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        response_raw: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert a generation record."""
        async with self.pool.acquire() as conn:
            # Convert dicts to JSON strings for JSONB columns
            response_raw_json = json.dumps(response_raw) if response_raw else None
            metadata_json = json.dumps(metadata) if metadata else None
            
            row = await conn.fetchrow(
                """
                INSERT INTO generations (
                    request_id, session_id, provider, model, prompt,
                    prompt_tokens, response_text, response_tokens,
                    response_raw, status, latency_ms, error_message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13::jsonb)
                RETURNING id
                """,
                request_id,
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
            return str(row['id'])
    
    async def get_generation(self, generation_id: str) -> Optional[Dict[str, Any]]:
        """Get generation by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM generations WHERE id = $1",
                generation_id
            )
            if row:
                return dict(row)
            return None
    
    async def list_generations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent generations."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM generations ORDER BY created_at DESC LIMIT $1",
                limit
            )
            return [dict(row) for row in rows]
    
    # User Management
    
    async def get_user_by_api_key_hash(self, api_key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user by API key hash."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE api_key_hash = $1",
                api_key_hash
            )
            if row:
                return dict(row)
            return None
    
    async def update_user_last_active(self, user_id: str):
        """Update user last active timestamp."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_active_at = NOW() WHERE id = $1",
                user_id
            )
