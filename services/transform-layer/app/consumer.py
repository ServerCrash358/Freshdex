import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .checksum_store import ChecksumStore
from .config import Settings
from .metrics import checksums_matched_total, checksums_mismatched_total

logger = logging.getLogger("transform-layer")


class TransformLayer:
    """Consumes the raw outbox topic, splits it into embedding.requests and
    embedding.tombstones, and does the checksum short-circuit from Section 2.

    Per Section 2: transform layer exists so embedding workers stay dumb --
    it insulates them from the outbox's row shape and is "one clean place to
    do checksum comparison and topic-splitting."
    """

    def __init__(self, settings: Settings, checksum_store: ChecksumStore):
        self._settings = settings
        self._checksum_store = checksum_store
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None

    async def run(self) -> None:
        s = self._settings
        self._consumer = AIOKafkaConsumer(
            s.source_topic,
            bootstrap_servers=s.kafka_bootstrap_servers,
            group_id=s.consumer_group,
            # Manual commits: an offset is only committed after the
            # downstream produce succeeds (see _handle). This is what makes
            # a mid-processing crash cause redelivery (at-least-once, per
            # Section 1) instead of a silently skipped event.
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=s.kafka_bootstrap_servers,
            acks="all",
        )
        await self._consumer.start()
        await self._producer.start()
        logger.info("transform layer started, consuming %s", s.source_topic)
        try:
            async for msg in self._consumer:
                await self._handle(msg)
                await self._consumer.commit()
        finally:
            await self._consumer.stop()
            await self._producer.stop()

    async def _handle(self, msg) -> None:
        s = self._settings
        headers = dict(msg.headers or ())
        event_type_raw = headers.get("event_type")
        event_type = event_type_raw.decode() if event_type_raw else None

        payload = json.loads(msg.value)
        doc_id = payload["doc_id"]

        # Tombstones are routed by an explicit header set on the outbox row
        # itself (Section 2: "not inferred from an update payload that
        # happens to look empty" -- ambiguity there is a known bug source).
        if event_type == "deleted":
            await self._producer.send_and_wait(
                s.tombstones_topic,
                key=msg.key,
                value=json.dumps({"doc_id": doc_id}).encode(),
            )
            logger.info("tombstone forwarded doc_id=%s", doc_id)
            return

        # created / updated: checksum-gated. A redelivered or no-op change
        # (e.g. Debezium noise where content didn't actually change) is a
        # safe drop here -- no re-embed, no cost.
        new_checksum = payload["content_checksum"]
        last_checksum = await self._checksum_store.get_checksum(doc_id)

        if last_checksum == new_checksum:
            checksums_matched_total.inc()
            logger.info("checksum match, dropping doc_id=%s", doc_id)
            return

        checksums_mismatched_total.inc()
        await self._producer.send_and_wait(
            s.requests_topic,
            key=msg.key,
            value=json.dumps(payload).encode(),
        )
        logger.info(
            "checksum mismatch (last=%s new=%s), enqueued doc_id=%s",
            last_checksum,
            new_checksum,
            doc_id,
        )
