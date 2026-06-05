-- SOILL Public RAG Chatbot — initial schema (Postgres + pgvector)
-- Run via: uv run soill-db-init

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    source_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    last_processed TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'indexed'
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    location_type TEXT NOT NULL,
    location_start INTEGER NOT NULL,
    location_end INTEGER NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS soill_conversations (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    thread_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    visitor_fingerprint TEXT NOT NULL,
    client_type TEXT NOT NULL DEFAULT 'webapp',
    question TEXT NOT NULL,
    answer TEXT,
    error TEXT,
    cited_sources_count INTEGER NOT NULL DEFAULT 0,
    rag_top_k INTEGER,
    chat_model TEXT,
    embed_model TEXT,
    client_ip TEXT,
    user_agent TEXT,
    forwarded_for TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_path ON chunks (source_path);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_conversations_created_at
    ON soill_conversations (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_thread_created
    ON soill_conversations (thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_visitor_created
    ON soill_conversations (visitor_fingerprint, created_at DESC);
