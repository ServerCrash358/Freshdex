import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..metrics import query_result_age_seconds

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    candidates: int | None = None


class RetrievedChunk(BaseModel):
    doc_id: str
    title: str | None
    content: str
    similarity: float
    rerank_score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    cited_doc_ids: list[str]
    cached: bool
    results: list[RetrievedChunk]


@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    state = request.app.state
    settings = state.settings

    # Cache-aside (Section 3.3, eager population explicitly rejected there):
    # check first, only do the expensive work on a miss.
    cached = await state.cache.get(body.query)
    if cached:
        return QueryResponse(
            query=body.query,
            answer=cached["answer"],
            cited_doc_ids=cached["cited_doc_ids"],
            cached=True,
            results=[],
        )

    top_k = body.top_k or settings.default_top_k
    candidates = body.candidates or settings.default_candidates

    ranked = await state.retriever.search(body.query, candidates)
    if ranked:
        ranked = await asyncio.to_thread(state.reranker.rerank, body.query, ranked, top_k)

    now = datetime.now(timezone.utc)
    for r in ranked:
        query_result_age_seconds.observe((now - r["indexed_at"]).total_seconds())

    if ranked:
        answer = await state.generator.generate(body.query, ranked)
    else:
        answer = "No relevant documents were found for this query."

    cited_doc_ids = [str(r["doc_id"]) for r in ranked]
    await state.cache.set(body.query, answer, cited_doc_ids)

    return QueryResponse(
        query=body.query,
        answer=answer,
        cited_doc_ids=cited_doc_ids,
        cached=False,
        results=[
            RetrievedChunk(
                doc_id=str(r["doc_id"]),
                title=r["title"],
                content=r["content"],
                similarity=r["similarity"],
                rerank_score=r["rerank_score"],
            )
            for r in ranked
        ],
    )
