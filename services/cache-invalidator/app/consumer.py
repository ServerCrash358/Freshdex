import json
import logging

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer

from .config import Settings
from .metrics import cache_keys_invalidated_total

logger = logging.getLogger("cache-invalidator")

_DOCREFS_PREFIX = "freshdex:docrefs:"


class CacheInvalidator:
    """Consumes the raw outbox topic directly (Section 3.3's revised
    decision, Section 4's file tree comment) -- a completely independent
    consumer group from the transform layer, reading the same topic.

    For every create/update/delete on a doc_id, looks up the reverse index
    (Section 2/3.3: "doc_id -> [cache_keys that cited it]") and evicts every
    cache entry that cited it. A query landing in the resulting gap just
    cache-misses and re-queries the (possibly still-stale) vector -- Section
    3.3 explicitly accepts that as strictly better than serving a wrong
    answer indefinitely.
    """

    def __init__(self, settings: Settings, redis_client: redis.Redis):
        self._settings = settings
        self._redis = redis_client

    async def run(self) -> None:
        s = self._settings
        consumer = AIOKafkaConsumer(
            s.source_topic,
            bootstrap_servers=s.kafka_bootstrap_servers,
            group_id=s.consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("cache invalidator started, consuming %s", s.source_topic)
        try:
            async for msg in consumer:
                await self._handle(msg)
                await consumer.commit()
        finally:
            await consumer.stop()

    async def _handle(self, msg) -> None:
        headers = dict(msg.headers or ())
        event_type_raw = headers.get("event_type")
        event_type = event_type_raw.decode() if event_type_raw else None
        trigger = "tombstone" if event_type == "deleted" else "cdc-event"

        payload = json.loads(msg.value)
        doc_id = payload["doc_id"]

        docrefs_key = f"{_DOCREFS_PREFIX}{doc_id}"
        cache_keys = await self._redis.smembers(docrefs_key)
        if cache_keys:
            await self._redis.delete(*cache_keys, docrefs_key)
        cache_keys_invalidated_total.labels(trigger=trigger).inc(len(cache_keys))
        logger.info(
            "invalidated %d cache entries doc_id=%s trigger=%s",
            len(cache_keys),
            doc_id,
            trigger,
        )
