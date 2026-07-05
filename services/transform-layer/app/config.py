import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN", "postgresql://freshdex:freshdex@postgres:5432/freshdex"
    )
    source_topic: str = os.getenv("SOURCE_TOPIC", "freshdex.outbox.document")
    requests_topic: str = os.getenv("REQUESTS_TOPIC", "freshdex.embedding.requests")
    tombstones_topic: str = os.getenv("TOMBSTONES_TOPIC", "freshdex.embedding.tombstones")
    consumer_group: str = os.getenv("CONSUMER_GROUP", "freshdex-transform-layer")
    metrics_port: int = int(os.getenv("METRICS_PORT", "9100"))
