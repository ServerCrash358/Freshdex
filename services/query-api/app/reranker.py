from sentence_transformers import CrossEncoder


class Reranker:
    """Second, more accurate re-scoring pass over the ANN candidates
    (Section 4: sentence-transformers CrossEncoder). ANN retrieval is fast
    but approximate; the cross-encoder actually attends over (query, passage)
    jointly, so it's used to cut a wider candidate set down to the final
    top_k rather than trusting raw cosine similarity for final ranking.
    """

    def __init__(self, model_name: str):
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        pairs = [(query, c["content"]) for c in candidates]
        scores = self._model.predict(pairs)
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)
        return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]
