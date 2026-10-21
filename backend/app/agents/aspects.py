"""Step 2: decide which claims to compare with which (role: analyst + local embeddings).

The LLM names the factual questions in the case (a short list it is good at). Code then assigns
EVERY claim to its closest questions by embedding similarity, so no claim can be silently dropped.
(Asking one LLM call to cluster ~100 claims dropped whole topics, differently on every run.)
Contradictions are then looked for within each question, not across every pair of claims."""

import numpy as np
from pydantic import BaseModel

from app.agents.run import AnalysisRun
from app.store.analysis_store import ClaimRow

ASPECTS_PER_CLAIM = 2  # a claim can bear on two questions (e.g. a car's speed and point of impact)


class Aspect(BaseModel):
    name: str
    question: str


class AspectList(BaseModel):
    aspects: list[Aspect]


class AspectGroup(BaseModel):
    name: str
    claim_keys: list[int]


async def group_aspects(run: AnalysisRun, claims: list[ClaimRow]) -> list[AspectGroup]:
    if not claims:
        return []
    lines = "\n".join(
        f"{c.speaker} ({run.doc(c.citation.chunk_id)}) | {c.aspect} | {c.statement}" for c in claims
    )
    out = await run.call("analyst", "aspects", lines, AspectList)
    if not out.aspects:
        return []

    claim_vecs = await run.embedder.embed_documents([f"{c.aspect}: {c.statement}" for c in claims])
    aspect_vecs = np.vstack(
        [await run.embedder.embed_query(f"{a.name}: {a.question}") for a in out.aspects]
    )
    best = np.argsort(-(claim_vecs @ aspect_vecs.T), axis=1)[:, :ASPECTS_PER_CLAIM]
    members: dict[int, list[int]] = {i: [] for i in range(len(out.aspects))}
    for claim, aspect_ids in zip(claims, best, strict=True):
        for a in aspect_ids:
            members[int(a)].append(claim.key)
    return [
        AspectGroup(name=a.name, claim_keys=members[i])
        for i, a in enumerate(out.aspects)
        if members[i]
    ]
