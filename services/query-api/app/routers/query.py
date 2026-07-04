import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    candidates: int | None = None


class QueryResult(BaseModel):
    doc_id: str
    title: str | None
    content: str
    content_checksum: str
    indexed_at: str
    similarity: float
    rerank_score: float


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    state = request.app.state
    settings = state.settings

    top_k = body.top_k or settings.default_top_k
    candidates = body.candidates or settings.default_candidates

    ranked = await state.retriever.search(body.query, candidates)
    if ranked:
        ranked = await asyncio.to_thread(state.reranker.rerank, body.query, ranked, top_k)

    return QueryResponse(
        query=body.query,
        results=[
            QueryResult(
                doc_id=str(r["doc_id"]),
                title=r["title"],
                content=r["content"],
                content_checksum=r["content_checksum"],
                indexed_at=r["indexed_at"].isoformat(),
                similarity=r["similarity"],
                rerank_score=r["rerank_score"],
            )
            for r in ranked
        ],
    )
