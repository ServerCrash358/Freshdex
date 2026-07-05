import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    # Consumes the RAW outbox topic directly -- not embedding.completed --
    # per Section 3.3's revised decision: waiting for embedding.completed
    # means a stale cached answer is served for the entire embedding
    # pipeline latency after the source doc changed.
    source_topic: str = os.getenv("SOURCE_TOPIC", "freshdex.outbox.document")
    consumer_group: str = os.getenv("CONSUMER_GROUP", "freshdex-cache-invalidator")
    metrics_port: int = int(os.getenv("METRICS_PORT", "9101"))
