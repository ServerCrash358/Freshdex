from abc import ABC, abstractmethod


class Embedder(ABC):
    """Pluggable embedder interface (Section 4: 'pluggable embedder --
    sentence-transformers local / OpenAI swap'). The consumer only ever
    talks to this interface, never to a specific backend.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class SentenceTransformerEmbedder(Embedder):
    """Local, default backend -- no API cost, no network dependency at
    query time. Model is baked into the image at build time (see Dockerfile)
    so containers start without needing internet access.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()


class OpenAIEmbedder(Embedder):
    """Swap-in remote backend (Section 4). Not wired up by default -- no
    API key configured in this local-only setup -- but the interface is
    ready if a future milestone needs it.
    """

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: str | None = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model_name = model_name
        self._dim = 1536 if "small" in model_name else 3072

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self._model_name, input=text)
        return response.data[0].embedding

    @property
    def dimension(self) -> int:
        return self._dim


def build_embedder(backend: str, model_name: str) -> Embedder:
    if backend == "openai":
        return OpenAIEmbedder(model_name=model_name)
    return SentenceTransformerEmbedder(model_name=model_name)
