-- Migration 002: Add comprehensive xAI API tracking
-- Adds tables and columns to track all xAI API metadata, token usage, and detailed response information

-- Add new columns to generations table for xAI-specific metadata
ALTER TABLE generations
ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS audio_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS image_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS cached_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS accepted_prediction_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS rejected_prediction_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS num_sources_used INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS response_id TEXT,
ADD COLUMN IF NOT EXISTS previous_response_id TEXT,
ADD COLUMN IF NOT EXISTS temperature FLOAT,
ADD COLUMN IF NOT EXISTS top_p FLOAT,
ADD COLUMN IF NOT EXISTS max_output_tokens INTEGER,
ADD COLUMN IF NOT EXISTS parallel_tool_calls BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS tool_choice TEXT,
ADD COLUMN IF NOT EXISTS reasoning_content TEXT,
ADD COLUMN IF NOT EXISTS incomplete_details JSONB,
ADD COLUMN IF NOT EXISTS annotations JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS finish_reason TEXT;

-- Create index on response_id for quick lookups
CREATE INDEX IF NOT EXISTS idx_generations_response_id ON generations(response_id);
CREATE INDEX IF NOT EXISTS idx_generations_previous_response_id ON generations(previous_response_id);

-- Create table for tracking token usage over time
CREATE TABLE IF NOT EXISTS token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES generations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    
    -- Model info
    provider TEXT NOT NULL DEFAULT 'xai',
    model TEXT NOT NULL,
    
    -- Token counts (prompt)
    prompt_text_tokens INTEGER DEFAULT 0,
    prompt_audio_tokens INTEGER DEFAULT 0,
    prompt_image_tokens INTEGER DEFAULT 0,
    prompt_cached_tokens INTEGER DEFAULT 0,
    prompt_total_tokens INTEGER DEFAULT 0,
    
    -- Token counts (completion)
    completion_reasoning_tokens INTEGER DEFAULT 0,
    completion_audio_tokens INTEGER DEFAULT 0,
    completion_text_tokens INTEGER DEFAULT 0,
    completion_accepted_prediction_tokens INTEGER DEFAULT 0,
    completion_rejected_prediction_tokens INTEGER DEFAULT 0,
    completion_total_tokens INTEGER DEFAULT 0,
    
    -- Total
    total_tokens INTEGER DEFAULT 0,
    
    -- Cost tracking (in micro-dollars, e.g., 1000000 = $1.00)
    prompt_cost_micro_usd BIGINT DEFAULT 0,
    completion_cost_micro_usd BIGINT DEFAULT 0,
    total_cost_micro_usd BIGINT DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for token_usage
CREATE INDEX IF NOT EXISTS idx_token_usage_generation_id ON token_usage(generation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_session_id ON token_usage(session_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider);

-- Create table for tracking API models and their capabilities
CREATE TABLE IF NOT EXISTS api_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model identification
    model_id TEXT UNIQUE NOT NULL,
    fingerprint TEXT,
    version TEXT,
    provider TEXT NOT NULL DEFAULT 'xai',
    
    -- Model type
    model_type TEXT NOT NULL, -- 'language', 'embedding', 'image_generation'
    object_type TEXT NOT NULL DEFAULT 'model',
    
    -- Ownership
    owned_by TEXT DEFAULT 'xai',
    
    -- Capabilities
    modalities JSONB DEFAULT '[]'::jsonb, -- ['text', 'image', 'audio']
    supports_streaming BOOLEAN DEFAULT true,
    supports_tools BOOLEAN DEFAULT false,
    supports_vision BOOLEAN DEFAULT false,
    supports_reasoning BOOLEAN DEFAULT false,
    
    -- Limits
    max_prompt_length INTEGER,
    max_output_tokens INTEGER,
    context_window INTEGER,
    
    -- Pricing (in micro-dollars per 1M tokens)
    prompt_text_token_price BIGINT,
    prompt_image_token_price BIGINT,
    prompt_audio_token_price BIGINT,
    generated_text_token_price BIGINT,
    generated_image_token_price BIGINT,
    generated_audio_token_price BIGINT,
    
    -- Metadata
    aliases JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    model_created_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_deprecated BOOLEAN DEFAULT false
);

-- Indexes for api_models
CREATE INDEX IF NOT EXISTS idx_api_models_model_id ON api_models(model_id);
CREATE INDEX IF NOT EXISTS idx_api_models_provider ON api_models(provider);
CREATE INDEX IF NOT EXISTS idx_api_models_model_type ON api_models(model_type);
CREATE INDEX IF NOT EXISTS idx_api_models_is_active ON api_models(is_active);

-- Create table for tracking API responses (for /v1/responses endpoint)
CREATE TABLE IF NOT EXISTS api_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Response identification
    response_id TEXT UNIQUE NOT NULL,
    previous_response_id TEXT,
    
    -- Request info
    request_id TEXT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Model
    model TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'xai',
    
    -- Input/Output
    input_messages JSONB NOT NULL,
    output_messages JSONB,
    
    -- Configuration
    temperature FLOAT,
    top_p FLOAT,
    max_output_tokens INTEGER,
    parallel_tool_calls BOOLEAN DEFAULT true,
    tool_choice TEXT DEFAULT 'auto',
    tools JSONB DEFAULT '[]'::jsonb,
    
    -- Response details
    status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'failed', 'cancelled'
    finish_reason TEXT,
    reasoning_content TEXT,
    incomplete_details JSONB,
    
    -- Usage
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    num_sources_used INTEGER DEFAULT 0,
    
    -- Storage
    store BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for api_responses
CREATE INDEX IF NOT EXISTS idx_api_responses_response_id ON api_responses(response_id);
CREATE INDEX IF NOT EXISTS idx_api_responses_previous_response_id ON api_responses(previous_response_id);
CREATE INDEX IF NOT EXISTS idx_api_responses_request_id ON api_responses(request_id);
CREATE INDEX IF NOT EXISTS idx_api_responses_user_id ON api_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_api_responses_session_id ON api_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_api_responses_status ON api_responses(status);
CREATE INDEX IF NOT EXISTS idx_api_responses_created_at ON api_responses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_responses_expires_at ON api_responses(expires_at) WHERE expires_at IS NOT NULL;

-- Create table for tracking embeddings
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request info
    request_id TEXT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Model
    model TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'xai',
    
    -- Input
    input_text TEXT NOT NULL,
    input_type TEXT DEFAULT 'text', -- 'text', 'query', 'document'
    
    -- Output (stored as JSONB array of floats)
    embedding_json JSONB NOT NULL,
    embedding_dimension INTEGER,
    
    -- Usage
    prompt_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for embeddings
CREATE INDEX IF NOT EXISTS idx_embeddings_request_id ON embeddings(request_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_user_id ON embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_session_id ON embeddings(session_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings(created_at DESC);

-- Create table for tracking image generations
CREATE TABLE IF NOT EXISTS image_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request info
    request_id TEXT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Model
    model TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'xai',
    
    -- Input
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    
    -- Configuration
    width INTEGER,
    height INTEGER,
    num_images INTEGER DEFAULT 1,
    quality TEXT DEFAULT 'standard', -- 'standard', 'hd'
    style TEXT, -- 'vivid', 'natural'
    
    -- Output
    image_urls JSONB DEFAULT '[]'::jsonb,
    revised_prompt TEXT,
    
    -- Usage
    prompt_tokens INTEGER DEFAULT 0,
    image_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'failed'
    error_message TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for image_generations
CREATE INDEX IF NOT EXISTS idx_image_generations_request_id ON image_generations(request_id);
CREATE INDEX IF NOT EXISTS idx_image_generations_user_id ON image_generations(user_id);
CREATE INDEX IF NOT EXISTS idx_image_generations_session_id ON image_generations(session_id);
CREATE INDEX IF NOT EXISTS idx_image_generations_model ON image_generations(model);
CREATE INDEX IF NOT EXISTS idx_image_generations_status ON image_generations(status);
CREATE INDEX IF NOT EXISTS idx_image_generations_created_at ON image_generations(created_at DESC);

-- Create materialized view for usage analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS usage_analytics AS
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    DATE_TRUNC('day', created_at) as day,
    user_id,
    model,
    provider,
    COUNT(*) as request_count,
    SUM(prompt_total_tokens) as total_prompt_tokens,
    SUM(completion_total_tokens) as total_completion_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(total_cost_micro_usd) as total_cost_micro_usd,
    AVG(total_tokens) as avg_tokens_per_request,
    MAX(total_tokens) as max_tokens_per_request
FROM token_usage
GROUP BY hour, day, user_id, model, provider;

-- Index for materialized view
CREATE INDEX IF NOT EXISTS idx_usage_analytics_day ON usage_analytics(day DESC);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_hour ON usage_analytics(hour DESC);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_user_id ON usage_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_model ON usage_analytics(model);

-- Create function to refresh usage analytics
CREATE OR REPLACE FUNCTION refresh_usage_analytics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY usage_analytics;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to update updated_at on api_responses
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_api_responses_updated_at
    BEFORE UPDATE ON api_responses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_models_updated_at
    BEFORE UPDATE ON api_models
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE token_usage IS 'Tracks detailed token usage and costs for all API requests';
COMMENT ON TABLE api_models IS 'Stores information about available API models and their capabilities';
COMMENT ON TABLE api_responses IS 'Tracks responses from the /v1/responses endpoint for conversation continuity';
COMMENT ON TABLE embeddings IS 'Stores embedding generation requests and results';
COMMENT ON TABLE image_generations IS 'Tracks image generation requests and results';
COMMENT ON MATERIALIZED VIEW usage_analytics IS 'Aggregated usage statistics by hour/day for analytics and billing';
