from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from .config import Settings
from .reranker import Reranker
from .retriever import Retriever
from .routers.query import router as query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=1, max_size=5)

    app.state.settings = settings
    app.state.pool = pool
    app.state.retriever = Retriever(pool, settings.embedder_model)
    app.state.reranker = Reranker(settings.reranker_model)

    yield

    await pool.close()


app = FastAPI(title="Freshdex Query API", lifespan=lifespan)
app.include_router(query_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
