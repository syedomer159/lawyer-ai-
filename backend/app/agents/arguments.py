"""Step 5: arguments, the other side's answer, our rebuttal and cross-examination questions,
one call per issue (role: argument)."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.agents.run import AnalysisRun
from app.citations import Citation
from app.contracts.analysis import SEVERITY_RANK, CrossQuestion
from app.store.analysis_store import AdverseRow, ClaimRow, ConflictRow, ElementRow, IssueRow

MAX_ISSUES = 12  # caps cost; the most important issues come first


class Argument(BaseModel):
    title: str
    our_argument: str
    opposing_argument: str
    rebuttal: str
    cross_questions: list[CrossQuestion]
    citations: list[Citation]


@dataclass
class IssueInput:
    description: str
    evidence: list[ClaimRow]


def select_issues(
    conflicts: list[ConflictRow],
    elements: list[ElementRow],
    adverse: list[AdverseRow],
    claims: list[ClaimRow],
) -> list[IssueInput]:
    """Contradictions that help us, then weak/missing elements, then what hurts us (to rebut)."""
    by_key = {c.key: c for c in claims}
    by_chunk: dict[int, list[ClaimRow]] = {}
    for c in claims:
        by_chunk.setdefault(c.citation.chunk_id, []).append(c)

    def cited(chunk_ids: list[int]) -> list[ClaimRow]:
        return [c for cid in dict.fromkeys(chunk_ids) for c in by_chunk.get(cid, [])]

    issues = [
        IssueInput(
            f"Contradiction about {f.aspect}: {f.explanation}", [by_key[k] for k in f.claim_keys]
        )
        for f in sorted(conflicts, key=lambda f: SEVERITY_RANK[f.severity])
        if f.effect == "helps" and f.severity != "low"
    ]
    issues += [
        IssueInput(
            f"The {e.kind} point '{e.element}' is {e.status}: {e.explanation}",
            cited([c.chunk_id for c in e.citations]),
        )
        for e in elements
        if e.status != "supported"
    ]
    issues += [
        IssueInput(
            f"Evidence against our client: {a.explanation}",
            cited([c.chunk_id for c in a.citations]),
        )
        for a in adverse
    ]
    return issues[:MAX_ISSUES]


async def build_argument(run: AnalysisRun, issue: IssueInput) -> IssueRow:
    evidence = "\n".join(run.evidence_line(c) for c in issue.evidence) or "(no direct evidence)"
    out = await run.call(
        "argument",
        "arguments",
        f"ISSUE: {issue.description}\n\nEVIDENCE\n{evidence}",
        Argument,
        check=lambda a: run.cite_problems(a.citations),
    )
    return IssueRow(
        out.title,
        out.our_argument,
        out.opposing_argument,
        out.rebuttal,
        out.cross_questions,
        [run.checker.check(c) for c in out.citations],
    )
