"""The analysis workflow (ADR-0003): a fixed order of single-purpose agents with typed outputs.

  extract (per document) -> group claims into aspects -> contradictions (per aspect)
  -> elements / procedure / adverse evidence -> arguments (per issue) -> save

Every citation is checked in code (app/citations.py). Claims whose quote is not in the cited
chunk are dropped, so everything downstream rests on text that really is in the case file."""

import asyncio
import logging
import re
from pathlib import Path

from app.agents.arguments import build_argument, select_issues
from app.agents.aspects import group_aspects
from app.agents.assessment import assess
from app.agents.contradictions import find_conflicts
from app.agents.extractor import Extraction, extract_document
from app.agents.run import AnalysisRun
from app.config import Settings
from app.contracts.analysis import SEVERITY_RANK, PartyRole
from app.contracts.cases import Case
from app.contracts.documents import Document
from app.llm.embeddings import CaseEmbedder
from app.observability import tracer
from app.store.analysis_store import (
    AnalysisResult,
    ClaimRow,
    ConflictRow,
    finish_job,
    save_analysis,
    update_job,
)
from app.store.case_store import CaseStore

log = logging.getLogger(__name__)

_TITLES = re.compile(r"^(smt|shri|sri|mr|mrs|ms|dr|si|asi|hc|head constable|constable)\.?\s+")


def party_key(name: str) -> str:
    key = re.sub(r"[^\w\s]", " ", name.lower()).strip()
    while (stripped := _TITLES.sub("", key)) != key:
        key = stripped
    return re.sub(r"\s+", " ", key)


def merge_parties(extractions: list[Extraction]) -> list[tuple[str, PartyRole]]:
    """One entry per person across documents; a specific role beats 'other'."""
    merged: dict[str, tuple[str, PartyRole]] = {}
    for p in (p for e in extractions for p in e.parties):
        key = party_key(p.name)
        if key and (key not in merged or merged[key][1] == "other"):
            merged[key] = (p.name, p.role)
    return list(merged.values())


def dedupe_conflicts(conflicts: list[ConflictRow]) -> list[ConflictRow]:
    """The same claims can meet in two aspects; keep one conflict per claim set (most severe)."""
    best: dict[frozenset[int], ConflictRow] = {}
    for c in sorted(conflicts, key=lambda c: SEVERITY_RANK[c.severity]):
        best.setdefault(frozenset(c.claim_keys), c)
    return list(best.values())


def collect_claims(run: AnalysisRun, extractions: list[Extraction]) -> tuple[list[ClaimRow], int]:
    claims: list[ClaimRow] = []
    dropped = 0
    for c in (c for e in extractions for c in e.claims):
        checked = run.checker.check(c.citation)
        if not checked.verified:
            dropped += 1
            continue
        claims.append(ClaimRow(len(claims), c.speaker, c.aspect, c.statement, c.when, checked))
    return claims, dropped


async def run_analysis(run: AnalysisRun, docs: list[Document]) -> AnalysisResult:
    def step(name: str, progress: float) -> None:
        update_job(run.store, run.job_id, name, progress)

    done = 0

    async def extract(doc: Document) -> Extraction:
        nonlocal done
        result = await extract_document(run, doc)
        done += 1
        step(f"reading documents ({done}/{len(docs)})", 0.05 + 0.4 * done / len(docs))
        return result

    step(f"reading documents (0/{len(docs)})", 0.05)
    extractions = list(await asyncio.gather(*(extract(d) for d in docs)))
    claims, dropped = collect_claims(run, extractions)

    step(f"grouping {len(claims)} claims ({dropped} dropped: quote not in text)", 0.45)
    groups = await group_aspects(run, claims)
    by_key = {c.key: c for c in claims}
    for g in groups:
        for k in g.claim_keys:
            by_key[k].aspect = g.name

    step(f"finding contradictions in {len(groups)} aspects", 0.55)
    found = await asyncio.gather(
        *(
            find_conflicts(run, g.name, [by_key[k] for k in g.claim_keys])
            for g in groups
            if len(g.claim_keys) >= 2
        )
    )
    conflicts = dedupe_conflicts([c for group in found for c in group])

    step("assessing elements and procedure", 0.7)
    elements, adverse = await assess(run, claims)

    issues = select_issues(conflicts, elements, adverse, claims)
    step(f"preparing arguments for {len(issues)} issues", 0.8)
    arguments = await asyncio.gather(*(build_argument(run, i) for i in issues))

    return AnalysisResult(
        parties=merge_parties(extractions),
        claims=claims,
        conflicts=conflicts,
        elements=elements,
        adverse=adverse,
        issues=list(arguments),
    )


async def analyse_case(
    case: Case, store: CaseStore, settings: Settings, job_id: str, embedder: CaseEmbedder
) -> None:
    """Run the workflow and swap in its results. One trace per run in Phoenix."""
    docs = [d for d in store.list_documents() if d.status == "ready"]
    with tracer.start_as_current_span(
        "analysis", attributes={"case.id": case.id, "job.id": job_id, "documents": len(docs)}
    ):
        run = AnalysisRun.create(case, store, settings, job_id, embedder)
        result = await run_analysis(run, docs)
        save_analysis(store, result)


async def analysis_in_background(
    case_dir: Path, case: Case, settings: Settings, job_id: str, embedder: CaseEmbedder
) -> None:
    """Background task: opens its own store (the request's is closed by the time this runs)."""
    store = CaseStore(case_dir)
    try:
        await analyse_case(case, store, settings, job_id, embedder)
        finish_job(store, job_id)
    except Exception as exc:
        # Boundary of a background job: record the failure for the UI, and log the traceback.
        finish_job(store, job_id, f"{type(exc).__name__}: {exc}")
        log.exception("analysis failed for case %s", case.id)
    finally:
        store.close()
