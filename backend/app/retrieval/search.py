"""Hybrid search inside ONE case: FTS5 BM25 + cosine similarity, fused with reciprocal rank
fusion. Keyword search catches exact names, numbers and dates; vectors catch paraphrases."""

import re

import numpy as np

from app.contracts.documents import SearchHit
from app.llm.embeddings import CaseEmbedder
from app.store.case_store import CaseStore

CANDIDATES = 30  # per retriever, before fusion
RRF_K = 60  # standard constant from the RRF paper; damps the weight of top ranks
# fmt: off
_STOPWORDS = {
    "a", "an", "and", "the", "of", "to", "in", "on", "at", "is", "was", "what", "who", "when",
    "where", "which", "how", "did", "does", "do", "for", "by", "with", "were",
}
# fmt: on


def fts_query(text: str) -> str:
    """User text -> safe FTS5 query: each word quoted (no operator injection), OR-ed."""
    words = [w for w in re.findall(r"\w+", text.lower()) if w not in _STOPWORDS]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


def rrf(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


async def search(
    store: CaseStore, embedder: CaseEmbedder, query: str, k: int = 8
) -> list[SearchHit]:
    ids, matrix = store.embeddings()
    if len(ids) == 0 or not query.strip():
        return []
    q = await embedder.embed_query(query)
    by_vector = ids[np.argsort(-(matrix @ q))[:CANDIDATES]].tolist()
    match = fts_query(query)
    by_keyword = store.fts(match, CANDIDATES) if match else []

    fused = rrf([by_vector, by_keyword])[:k]
    chunks = store.chunks_by_id([cid for cid, _ in fused])
    return [SearchHit(ref=chunks[cid][0], text=chunks[cid][1], score=s) for cid, s in fused]
