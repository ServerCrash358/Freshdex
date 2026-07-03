-- Freshdex milestone 3: checksum lookup target for the transform layer.
--
-- This is a placeholder for "the checksum stored alongside the vector in
-- pgvector" (Section 2) -- pgvector itself doesn't exist until milestone 4.
-- The embedding worker will extend this same table with the actual vector
-- column rather than replacing it, so this isn't throwaway.
--
-- Deliberately NOT written by the transform layer -- only read. Section 2's
-- crash-safety argument is that the checksum update must happen in the SAME
-- write as the vector, so there's no state where "checksum says done" but
-- the vector isn't. Only the embedding worker (milestone 4) writes this
-- table; the transform layer only queries it.
CREATE TABLE indexed_documents (
    doc_id            uuid PRIMARY KEY,
    content_checksum  text NOT NULL,
    indexed_at        timestamptz NOT NULL DEFAULT now()
);
