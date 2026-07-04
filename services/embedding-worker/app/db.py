import asyncpg


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=5)


def _to_vector_literal(embedding: list[float]) -> str:
    # pgvector accepts its text representation "[0.1,0.2,...]" cast to
    # `vector` -- simpler than registering an asyncpg type codec.
    return "[" + ",".join(map(str, embedding)) + "]"


async def upsert_embedding(
    pool: asyncpg.Pool,
    doc_id: str,
    title: str | None,
    content: str,
    content_checksum: str,
    embedding: list[float],
) -> None:
    # Single statement, both the vector and its checksum in the same write --
    # per Section 2, this is what makes the checksum column double as the
    # completion marker: there's no state where the vector is written but
    # the checksum isn't, so a crash can't leave things half-applied.
    # ON CONFLICT DO UPDATE is idempotency layer 2 (Section 2): even if the
    # checksum short-circuit in the transform layer were bypassed, replaying
    # this write is a safe overwrite, not a duplicate row.
    await pool.execute(
        """
        INSERT INTO indexed_documents (doc_id, title, content, content_checksum, embedding, indexed_at, deleted_at)
        VALUES ($1, $2, $3, $4, $5::vector, now(), NULL)
        ON CONFLICT (doc_id) DO UPDATE SET
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            content_checksum = EXCLUDED.content_checksum,
            embedding = EXCLUDED.embedding,
            indexed_at = EXCLUDED.indexed_at,
            deleted_at = NULL
        """,
        doc_id,
        title,
        content,
        content_checksum,
        _to_vector_literal(embedding),
    )


async def mark_deleted(pool: asyncpg.Pool, doc_id: str) -> None:
    # Logical delete (Section 2): mark deleted_at, clear the checksum so a
    # stale value can't be mistaken for "already indexed" later. Row stays
    # for autovacuum's normal HNSW graph repair -- no REINDEX here.
    await pool.execute(
        "UPDATE indexed_documents SET deleted_at = now(), content_checksum = NULL WHERE doc_id = $1",
        doc_id,
    )
