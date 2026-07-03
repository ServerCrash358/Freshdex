-- Freshdex milestone 1: source tables + outbox, per design doc Sections 2 & 4.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- Source-of-truth table. content_checksum is computed IN Postgres (Section 2:
-- "Computed in Postgres, not application code") so Debezium picks it up as
-- part of the row image automatically -- no app-side step to forget.
CREATE TABLE documents (
    doc_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title             text,
    content           text NOT NULL,
    content_checksum  text GENERATED ALWAYS AS (md5(content)) STORED,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- REPLICA IDENTITY FULL: Debezium needs the full OLD row image (not just the
-- primary key) to emit accurate before/after payloads on UPDATE and DELETE.
-- Default REPLICA IDENTITY only logs the PK, which isn't enough for the
-- update/delete row images the design doc's topic table expects.
ALTER TABLE documents REPLICA IDENTITY FULL;

-- Outbox table (Debezium "Outbox Event Router" pattern, Section 3.1): a
-- stable (aggregate_type, aggregate_id, type, payload) contract instead of
-- exposing documents' raw schema directly to Debezium/Kafka.
CREATE TABLE outbox (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  text NOT NULL,
    aggregate_id    text NOT NULL,
    type            text NOT NULL,
    payload         jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE outbox REPLICA IDENTITY FULL;

-- Keeps updated_at current on every content-changing write.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_set_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Writes an outbox row in the SAME transaction as the documents write (the
-- whole point of the outbox pattern, Section 3.1: no 2PC needed because it's
-- one database, one transaction, two tables).
CREATE OR REPLACE FUNCTION documents_to_outbox()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO outbox (aggregate_type, aggregate_id, type, payload)
        VALUES ('document', OLD.doc_id::text, 'deleted',
                jsonb_build_object('doc_id', OLD.doc_id));
        RETURN OLD;
    ELSE
        INSERT INTO outbox (aggregate_type, aggregate_id, type, payload)
        VALUES ('document', NEW.doc_id::text,
                CASE WHEN TG_OP = 'INSERT' THEN 'created' ELSE 'updated' END,
                jsonb_build_object(
                    'doc_id', NEW.doc_id,
                    'title', NEW.title,
                    'content', NEW.content,
                    'content_checksum', NEW.content_checksum
                ));
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_outbox_insert
    AFTER INSERT ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_to_outbox();

CREATE TRIGGER documents_outbox_update
    AFTER UPDATE ON documents
    FOR EACH ROW
    WHEN (OLD.content IS DISTINCT FROM NEW.content OR OLD.title IS DISTINCT FROM NEW.title)
    EXECUTE FUNCTION documents_to_outbox();

CREATE TRIGGER documents_outbox_delete
    AFTER DELETE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_to_outbox();
