-- Freshdex milestone 4: extends indexed_documents (created in milestone 3
-- as a checksum-only lookup table) into the actual pgvector store, per the
-- comment left in 02_indexed_documents.sql -- same table, not a new one.

CREATE EXTENSION IF NOT EXISTS vector;  -- pin: pgvector 0.8.2+ per Section 2

-- Relaxed from milestone 3: the tombstone handler nulls this out on delete
-- (Section 2: "remove/invalidate the stored checksum for that doc_id").
ALTER TABLE indexed_documents ALTER COLUMN content_checksum DROP NOT NULL;

ALTER TABLE indexed_documents
    ADD COLUMN IF NOT EXISTS title      text,
    ADD COLUMN IF NOT EXISTS content    text,
    -- 384 dims matches the default embedder (sentence-transformers
    -- all-MiniLM-L6-v2, see services/embedding-worker/app/embedder.py).
    -- Swapping to a different-dimension model requires a matching migration.
    ADD COLUMN IF NOT EXISTS embedding  vector(384),
    -- Logical delete per Section 2's tombstone handling: mark deleted_at,
    -- filter at query time immediately, rely on autovacuum's normal HNSW
    -- graph repair rather than periodic REINDEX.
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS indexed_documents_embedding_hnsw
    ON indexed_documents
    USING hnsw (embedding vector_cosine_ops);
