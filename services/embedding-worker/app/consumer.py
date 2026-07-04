import asyncio
import json
import logging

import asyncpg
from aiokafka import AIOKafkaConsumer

from .config import Settings
from .db import upsert_embedding
from .embedder import Embedder

logger = logging.getLogger("embedding-worker.requests")


class RequestConsumer:
    """Consumes freshdex.embedding.requests. Dedicated logic, separate from
    tombstone handling (Section 2: mixing update/delete into one handler is
    a known bug source) -- see tombstone_consumer.py.
    """

    def __init__(self, settings: Settings, pool: asyncpg.Pool, embedder: Embedder):
        self._settings = settings
        self._pool = pool
        self._embedder = embedder

    async def run(self) -> None:
        s = self._settings
        consumer = AIOKafkaConsumer(
            s.requests_topic,
            bootstrap_servers=s.kafka_bootstrap_servers,
            group_id=s.requests_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("embedding worker (requests) started, consuming %s", s.requests_topic)
        try:
            async for msg in consumer:
                await self._handle(msg)
                await consumer.commit()
        finally:
            await consumer.stop()

    async def _handle(self, msg) -> None:
        payload = json.loads(msg.value)
        doc_id = payload["doc_id"]
        content = payload["content"]

        # CPU-bound model inference -- run off the event loop so it doesn't
        # block consumer heartbeats/rebalancing.
        embedding = await asyncio.to_thread(self._embedder.embed, content)

        await upsert_embedding(
            self._pool,
            doc_id=doc_id,
            title=payload.get("title"),
            content=content,
            content_checksum=payload["content_checksum"],
            embedding=embedding,
        )
        logger.info("embedded and upserted doc_id=%s", doc_id)
