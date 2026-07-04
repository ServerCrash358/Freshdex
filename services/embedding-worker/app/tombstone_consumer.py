import json
import logging

import asyncpg
from aiokafka import AIOKafkaConsumer

from .config import Settings
from .db import mark_deleted

logger = logging.getLogger("embedding-worker.tombstones")


class TombstoneConsumer:
    """Consumes freshdex.embedding.tombstones -- deliberately a separate
    consumer from RequestConsumer (Section 2: deletes are handled by
    dedicated logic, never inferred from an update payload). No embedding
    happens here at all; a delete is unconditional, so there's no checksum
    comparison to do.
    """

    def __init__(self, settings: Settings, pool: asyncpg.Pool):
        self._settings = settings
        self._pool = pool

    async def run(self) -> None:
        s = self._settings
        consumer = AIOKafkaConsumer(
            s.tombstones_topic,
            bootstrap_servers=s.kafka_bootstrap_servers,
            group_id=s.tombstones_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("embedding worker (tombstones) started, consuming %s", s.tombstones_topic)
        try:
            async for msg in consumer:
                await self._handle(msg)
                await consumer.commit()
        finally:
            await consumer.stop()

    async def _handle(self, msg) -> None:
        payload = json.loads(msg.value)
        doc_id = payload["doc_id"]
        await mark_deleted(self._pool, doc_id)
        logger.info("marked deleted doc_id=%s", doc_id)
