-- Schema for MTG Assistant with PostgreSQL & pgvector
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Rules Knowledge Base (Hybrid Search: Vector with pgvector HNSW + Full Text Search)
CREATE TABLE IF NOT EXISTS mtg_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id VARCHAR(100) UNIQUE NOT NULL,
    rule_number VARCHAR(50) NOT NULL,
    category VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536), -- 1536 for OpenAI text-embedding-3-small
    embedding_model VARCHAR(100),
    content_hash VARCHAR(64),
    tsv_content tsvector GENERATED ALWAYS AS (
        to_tsvector('spanish', coalesce(title, '') || ' ' || coalesce(content, ''))
    ) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for ultra-fast Hybrid Search
CREATE INDEX IF NOT EXISTS idx_mtg_rules_embedding_hnsw 
ON mtg_rules USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_mtg_rules_tsv 
ON mtg_rules USING gin (tsv_content);

CREATE INDEX IF NOT EXISTS idx_mtg_rules_number 
ON mtg_rules (rule_number);

CREATE INDEX IF NOT EXISTS idx_mtg_rules_rule_id 
ON mtg_rules (rule_id);

-- 2. Call Center Chat Sessions & Multi-turn Memory
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) DEFAULT 'anonymous',
    channel VARCHAR(32) DEFAULT 'webchat',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system', 'tool'
    content TEXT NOT NULL,
    tool_calls JSONB,
    tokens_input INT DEFAULT 0,
    tokens_output INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session 
ON chat_messages (session_id, created_at ASC);

-- 3. Cache for External MTG Cards API (magicthegathering.io)
CREATE TABLE IF NOT EXISTS mtg_card_cache (
    card_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    name_normalized VARCHAR(255) NOT NULL,
    colors TEXT[],
    mana_cost VARCHAR(50),
    cmc NUMERIC(5,2),
    types TEXT[],
    subtypes TEXT[],
    image_url TEXT,
    oracle_text TEXT,
    raw_data JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '7 days')
);

CREATE INDEX IF NOT EXISTS idx_mtg_card_cache_name 
ON mtg_card_cache (name_normalized);

CREATE INDEX IF NOT EXISTS idx_mtg_card_cache_subtypes 
ON mtg_card_cache USING gin (subtypes);

CREATE INDEX IF NOT EXISTS idx_mtg_card_cache_colors 
ON mtg_card_cache USING gin (colors);
