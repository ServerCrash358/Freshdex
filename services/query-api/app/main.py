from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI

from .cache import AnswerCache
from .config import Settings
from .generator import Generator
from .reranker import Reranker
from .retriever import Retriever
from .routers.query import router as query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=1, max_size=5)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    app.state.settings = settings
    app.state.pool = pool
    app.state.retriever = Retriever(pool, settings.embedder_model)
    app.state.reranker = Reranker(settings.reranker_model)
    app.state.generator = Generator(settings.gemini_api_key, settings.gemini_model)
    app.state.cache = AnswerCache(redis_client)

    yield

    await pool.close()
    await redis_client.aclose()


app = FastAPI(title="Freshdex Query API", lifespan=lifespan)
app.include_router(query_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
