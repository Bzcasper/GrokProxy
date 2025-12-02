-- GrokProxy Database Schema v1
-- PostgreSQL/Neon compatible
-- Purpose: Store sessions, users, conversations, and generations

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Sessions table: manages cookie pool with health tracking
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cookie_text TEXT NOT NULL,
    cookie_hash TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT 'grok',
    
    -- Lifecycle tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Usage metrics
    usage_count BIGINT NOT NULL DEFAULT 0,
    success_count BIGINT NOT NULL DEFAULT 0,
    failure_count BIGINT NOT NULL DEFAULT 0,
    
    -- Health status
    status TEXT NOT NULL DEFAULT 'healthy' CHECK (status IN ('healthy', 'quarantined', 'expired', 'revoked')),
    last_health_check_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT positive_usage CHECK (usage_count >= 0),
    CONSTRAINT positive_success CHECK (success_count >= 0),
    CONSTRAINT positive_failure CHECK (failure_count >= 0)
);

-- Indexes for session management
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_last_used ON sessions(last_used_at);
CREATE INDEX idx_sessions_provider ON sessions(provider);
CREATE INDEX idx_sessions_health_check ON sessions(last_health_check_at) WHERE status = 'healthy';

-- Users table: API key management
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_hash TEXT NOT NULL UNIQUE,
    username TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    
    -- Lifecycle
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for users
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_users_role ON users(role);

-- Conversations table: multi-turn chat tracking
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Lifecycle
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Metadata
    title TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for conversations
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_created_at ON conversations(created_at DESC);

-- Generations table: full telemetry for every request
CREATE TABLE IF NOT EXISTS generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request tracking
    request_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Provider info
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    
    -- Request data
    prompt TEXT NOT NULL,
    prompt_tokens INTEGER,
    
    -- Response data
    response_text TEXT,
    response_tokens INTEGER,
    response_raw JSONB,
    
    -- Status and performance
    status INTEGER NOT NULL,  -- HTTP status code
    latency_ms INTEGER NOT NULL,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT positive_latency CHECK (latency_ms >= 0)
);

-- Indexes for generations (optimized for analytics queries)
CREATE INDEX idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX idx_generations_user_id ON generations(user_id);
CREATE INDEX idx_generations_conversation_id ON generations(conversation_id);
CREATE INDEX idx_generations_request_id ON generations(request_id);
CREATE INDEX idx_generations_session_id ON generations(session_id);
CREATE INDEX idx_generations_model ON generations(model);
CREATE INDEX idx_generations_status ON generations(status);

-- Composite indexes for common queries
CREATE INDEX idx_generations_user_created ON generations(user_id, created_at DESC);
CREATE INDEX idx_generations_conversation_created ON generations(conversation_id, created_at DESC);

-- Schema migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Insert initial migration record
INSERT INTO schema_migrations (version, name) VALUES (1, '001_create_tables');

-- Trigger to update conversations.updated_at
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations SET updated_at = now() WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_conversation_on_generation
    AFTER INSERT ON generations
    FOR EACH ROW
    WHEN (NEW.conversation_id IS NOT NULL)
    EXECUTE FUNCTION update_conversation_timestamp();

-- Comments for documentation
COMMENT ON TABLE sessions IS 'Cookie/session pool with health tracking and rotation logic';
COMMENT ON TABLE users IS 'API key management with role-based access';
COMMENT ON TABLE conversations IS 'Multi-turn conversation tracking';
COMMENT ON TABLE generations IS 'Full telemetry for every proxied request';
COMMENT ON TABLE schema_migrations IS 'Tracks applied database migrations';
