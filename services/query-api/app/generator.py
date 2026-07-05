import asyncio
import logging

from google import genai
from google.genai.errors import ServerError

logger = logging.getLogger("generator")

_PROMPT_TEMPLATE = """Answer the question using only the context below. If the context doesn't contain the answer, say so plainly rather than guessing.

Context:
{context}

Question: {query}

Answer:"""

# Gemini's free tier returns transient 503s under demand/rate pressure
# (observed directly during milestone 8's eval-flow testing, which makes
# many calls in quick succession). A few retries with backoff absorbs that
# without failing the whole query.
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 2


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

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                return response.text
            except ServerError:
                if attempt == _MAX_ATTEMPTS:
                    raise
                wait = _BACKOFF_SECONDS * attempt
                logger.warning("Gemini ServerError, retrying in %ss (attempt %d/%d)", wait, attempt, _MAX_ATTEMPTS)
                await asyncio.sleep(wait)
