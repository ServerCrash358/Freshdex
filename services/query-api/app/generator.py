from google import genai

_PROMPT_TEMPLATE = """Answer the question using only the context below. If the context doesn't contain the answer, say so plainly rather than guessing.

Context:
{context}

Question: {query}

Answer:"""


class Generator:
    """Section 3.3's "generation" step -- the piece the design doc referenced
    (retrieval+rerank+generation, answer cache) without ever naming a
    library for. Uses Gemini's free tier (gemini-2.5-flash-lite).
    """

    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(self, query: str, chunks: list[dict]) -> str:
        context = "\n\n".join(f"[{c['title'] or c['doc_id']}] {c['content']}" for c in chunks)
        prompt = _PROMPT_TEMPLATE.format(context=context, query=query)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return response.text
