import asyncpg


class ChecksumStore:
    """Read-only lookup against indexed_documents.

    Deliberately has no write method: per Section 2, the checksum is only
    ever updated by the embedding worker, in the same write as the vector
    itself (crash-safety -- see db/init/02_indexed_documents.sql). The
    transform layer only ever compares against what's already there.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def get_checksum(self, doc_id: str) -> str | None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT content_checksum FROM indexed_documents WHERE doc_id = $1",
                doc_id,
            )
            return row["content_checksum"] if row else None
