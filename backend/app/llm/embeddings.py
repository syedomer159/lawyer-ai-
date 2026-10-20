"""Text embeddings. Always local (Ollama) so raw case text is never sent out just to be indexed;
the model is pinned per case (ADR-0002)."""

from typing import Protocol

import numpy as np
from pydantic_ai import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.providers.ollama import OllamaProvider

BATCH = 32


class CaseEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    async def embed_query(self, text: str) -> np.ndarray: ...


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class OllamaEmbedder:
    # nomic-embed-text is trained with task prefixes; without them retrieval quality drops.
    DOC_PREFIX = "search_document: "
    QUERY_PREFIX = "search_query: "

    def __init__(self, model: str, base_url: str) -> None:
        self._embedder = Embedder(
            OpenAIEmbeddingModel(model, provider=OllamaProvider(base_url=base_url))
        )

    async def _embed(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            result = await self._embedder.embed_documents(texts[i : i + BATCH])
            rows.extend(list(v) for v in result.embeddings)
        return _normalise(np.array(rows, dtype=np.float32))

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        return await self._embed([self.DOC_PREFIX + t for t in texts])

    async def embed_query(self, text: str) -> np.ndarray:
        return (await self._embed([self.QUERY_PREFIX + text]))[0]
