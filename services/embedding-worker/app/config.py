import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN", "postgresql://freshdex:freshdex@postgres:5432/freshdex"
    )
    requests_topic: str = os.getenv("REQUESTS_TOPIC", "freshdex.embedding.requests")
    tombstones_topic: str = os.getenv("TOMBSTONES_TOPIC", "freshdex.embedding.tombstones")
    requests_group: str = os.getenv("REQUESTS_GROUP", "freshdex-embedding-worker-requests")
    tombstones_group: str = os.getenv("TOMBSTONES_GROUP", "freshdex-embedding-worker-tombstones")
    embedder_backend: str = os.getenv("EMBEDDER_BACKEND", "local")
    embedder_model: str = os.getenv("EMBEDDER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
