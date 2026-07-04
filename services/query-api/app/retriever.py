import asyncio

import asyncpg
from sentence_transformers import SentenceTransformer

# ANN search against pgvector, per Section 4 ("retriever.py -- pgvector ANN
# search"). Filters deleted_at IS NULL so tombstoned docs disappear from
# results immediately (Section 2: "filtered from query results immediately",
# not waiting on VACUUM/REINDEX).
_SEARCH_SQL = """
    SELECT doc_id, title, content, content_checksum, indexed_at,
           1 - (embedding <=> $1::vector) AS similarity
    FROM indexed_documents
    WHERE deleted_at IS NULL AND embedding IS NOT NULL
    ORDER BY embedding <=> $1::vector
    LIMIT $2
"""


class Retriever:
    def __init__(self, pool: asyncpg.Pool, model_name: str):
        self._pool = pool
        self._embedder = SentenceTransformer(model_name)

    def _embed_query(self, query: str) -> str:
        vec = self._embedder.encode(query, normalize_embeddings=True).tolist()
        return "[" + ",".join(map(str, vec)) + "]"

    async def search(self, query: str, candidates: int) -> list[dict]:
        query_vector = await asyncio.to_thread(self._embed_query, query)
        rows = await self._pool.fetch(_SEARCH_SQL, query_vector, candidates)
        return [dict(row) for row in rows]
