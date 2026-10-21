"""Step 3: contradictions inside one aspect (role: analyst)."""

from pydantic import BaseModel

from app.agents.run import AnalysisRun
from app.contracts.analysis import ConflictType, Effect, Severity
from app.store.analysis_store import ClaimRow, ConflictRow


class FoundConflict(BaseModel):
    claim_keys: list[int]
    type: ConflictType
    severity: Severity
    effect: Effect
    explanation: str


class Conflicts(BaseModel):
    conflicts: list[FoundConflict]


def _problems(found: FoundConflict, by_key: dict[int, ClaimRow], run: AnalysisRun) -> list[str]:
    unknown = [k for k in found.claim_keys if k not in by_key]
    if unknown:
        return [f"unknown claim keys {unknown}"]
    docs = {run.doc(by_key[k].citation.chunk_id) for k in found.claim_keys}
    if len(docs) < 2:
        return [f"conflict {found.claim_keys} must use claims from at least 2 different documents"]
    return []


async def find_conflicts(
    run: AnalysisRun, aspect: str, claims: list[ClaimRow]
) -> list[ConflictRow]:
    by_key = {c.key: c for c in claims}
    if len({run.doc(c.citation.chunk_id) for c in claims}) < 2:
        return []  # one source cannot contradict itself across documents
    lines = "\n".join(
        f"[{c.key}] {c.speaker} ({run.doc(c.citation.chunk_id)}) | {c.statement} | "
        f'"{c.citation.quote}"'
        for c in claims
    )
    out = await run.call(
        "analyst",
        "contradictions",
        f"ASPECT: {aspect}\n{lines}",
        Conflicts,
        check=lambda r: [p for f in r.conflicts for p in _problems(f, by_key, run)],
    )
    return [
        ConflictRow(
            aspect, f.type, f.severity, f.effect, f.explanation, list(dict.fromkeys(f.claim_keys))
        )
        for f in out.conflicts
        if not _problems(f, by_key, run)
    ]
