import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN", "postgresql://freshdex:freshdex@postgres:5432/freshdex"
    )
    query_api_url: str = os.getenv("QUERY_API_URL", "http://query-api:8000")
    pushgateway_url: str = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    freshness_poll_interval_seconds: float = float(os.getenv("FRESHNESS_POLL_INTERVAL_SECONDS", "1"))
    freshness_poll_timeout_seconds: float = float(os.getenv("FRESHNESS_POLL_TIMEOUT_SECONDS", "60"))
    ragas_corpus_settle_seconds: float = float(os.getenv("RAGAS_CORPUS_SETTLE_SECONDS", "20"))
    schedule_interval_seconds: int = int(os.getenv("SCHEDULE_INTERVAL_SECONDS", "1800"))
