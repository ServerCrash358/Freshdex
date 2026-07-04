import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN", "postgresql://freshdex:freshdex@postgres:5432/freshdex"
    )
    # Must match the embedding worker's model exactly (services/embedding-worker
    # /app/config.py EMBEDDER_MODEL) -- a different model produces an
    # incompatible vector space, even at the same dimensionality, and
    # similarity scores become meaningless silently (no error, just garbage
    # rankings). Kept as two independently-set env vars with matching
    # defaults rather than a shared constant since these are separate
    # services/images.
    embedder_model: str = os.getenv("EMBEDDER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    reranker_model: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    default_top_k: int = int(os.getenv("DEFAULT_TOP_K", "5"))
    default_candidates: int = int(os.getenv("DEFAULT_CANDIDATES", "20"))
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
