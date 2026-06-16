-- Public source metadata for ingested documents (optional URLs for citations).
-- Run via: uv run soill-db-init  or  uv run soill-source-catalog

ALTER TABLE documents ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS public_url TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;
