import hashlib
import json

import redis.asyncio as redis

_CACHE_PREFIX = "freshdex:cache:"
_DOCREFS_PREFIX = "freshdex:docrefs:"


class AnswerCache:
    """Query-result cache (Section 2: "this is a query-result cache, not a
    KV-cache"). Cache-aside, per Section 3.3's resolved decision -- populated
    only on a miss, never eagerly.

    Also maintains the reverse index (doc_id -> cache keys that cited it)
    Section 3.3 specifies: a Redis set per doc_id, so the cache-invalidator
    service can evict every affected answer when that doc_id changes,
    without scanning the whole cache.
    """

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    @staticmethod
    def make_key(query: str) -> str:
        digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()
        return f"{_CACHE_PREFIX}{digest}"

    async def get(self, query: str) -> dict | None:
        raw = await self._redis.get(self.make_key(query))
        return json.loads(raw) if raw else None

    async def set(self, query: str, answer: str, cited_doc_ids: list[str]) -> None:
        key = self.make_key(query)
        value = json.dumps({"answer": answer, "cited_doc_ids": cited_doc_ids})
        await self._redis.set(key, value)
        for doc_id in cited_doc_ids:
            await self._redis.sadd(f"{_DOCREFS_PREFIX}{doc_id}", key)
