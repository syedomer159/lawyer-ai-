"""Step 4: what the prosecution must prove vs. what the evidence shows, the procedural checklist,
and the evidence that hurts our client (role: analyst)."""

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.agents.run import AnalysisRun
from app.citations import Citation
from app.contracts.analysis import ElementKind, ElementStatus
from app.store.analysis_store import AdverseRow, ClaimRow, ElementRow

REFS_DIR = Path(__file__).parent.parent / "legal_refs"


class ElementFinding(BaseModel):
    kind: ElementKind
    element: str
    status: ElementStatus
    explanation: str
    citations: list[Citation]


class AdverseFinding(BaseModel):
    explanation: str
    citations: list[Citation]


class Assessment(BaseModel):
    elements: list[ElementFinding]
    adverse: list[AdverseFinding]


@cache
def _load(name: str) -> Any:
    return yaml.safe_load((REFS_DIR / name).read_text(encoding="utf-8"))


def legal_checklist(charges: list[str]) -> tuple[str, bool]:
    """Elements of the charged sections + procedure checklist, and whether any is unverified."""
    offences: dict[str, Any] = _load("offences.yaml")
    lines, unverified = ["ELEMENTS"], False
    for charge in charges:
        match = re.search(r"BNS\s*(\d+)", charge, re.IGNORECASE)
        ref = offences.get(f"BNS {match.group(1)}") if match else None
        if ref is None:
            lines.append(f"- {charge}: no curated elements; use general knowledge (UNVERIFIED)")
            unverified = True
            continue
        unverified |= not ref["verified"]
        lines += [f"- [{charge}] {e}" for e in ref["elements"]]
    lines.append("PROCEDURE")
    for item in _load("procedure.yaml"):
        lines.append(f"- {item['item']}" + (f" ({item['ref']})" if item.get("ref") else ""))
        unverified |= not item["verified"]
    return "\n".join(lines), unverified


async def assess(
    run: AnalysisRun, claims: list[ClaimRow]
) -> tuple[list[ElementRow], list[AdverseRow]]:
    checklist, unverified = legal_checklist(run.case.charges)
    note = (
        "Some section numbers above are not confirmed; never state them as settled law."
        if unverified
        else ""
    )
    evidence = "\n".join(run.evidence_line(c) for c in claims)
    out = await run.call(
        "analyst",
        "assessment",
        f"{checklist}\n\nEVIDENCE\n{evidence}",
        Assessment,
        check=lambda a: run.cite_problems(
            [c for e in a.elements for c in e.citations]
            + [c for x in a.adverse for c in x.citations]
        ),
        extra_vars={"unverified_note": note},
    )
    elements = [
        ElementRow(
            e.kind, e.element, e.status, e.explanation, [run.checker.check(c) for c in e.citations]
        )
        for e in out.elements
    ]
    adverse = [
        AdverseRow(a.explanation, [run.checker.check(c) for c in a.citations]) for a in out.adverse
    ]
    return elements, adverse
