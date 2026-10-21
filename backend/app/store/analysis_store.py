"""Persistence for analysis results and background jobs (case DB schema v3).

An analysis run builds an AnalysisResult in memory and save_analysis() swaps it in with one
transaction, so a failed run never leaves half-written results."""

import json
import uuid
from dataclasses import dataclass, field

from app.citations import CheckedCitation
from app.contracts.analysis import (
    Adverse,
    Analysis,
    AnalysisJob,
    CitationView,
    Claim,
    Conflict,
    ConflictStatus,
    ConflictType,
    CrossQuestion,
    Effect,
    Element,
    ElementKind,
    ElementStatus,
    Issue,
    Party,
    PartyRole,
    Severity,
)
from app.store.case_store import CaseStore

RESULT_TABLES = ("parties", "claims", "conflicts", "elements", "adverse", "issues")


@dataclass
class ClaimRow:
    key: int  # index within this run; conflicts point at claims by key until saved
    speaker: str
    aspect: str
    statement: str
    when: str | None
    citation: CheckedCitation


@dataclass
class ConflictRow:
    aspect: str
    type: ConflictType
    severity: Severity
    effect: Effect
    explanation: str
    claim_keys: list[int]


@dataclass
class ElementRow:
    kind: ElementKind
    element: str
    status: ElementStatus
    explanation: str
    citations: list[CheckedCitation]


@dataclass
class AdverseRow:
    explanation: str
    citations: list[CheckedCitation]


@dataclass
class IssueRow:
    title: str
    our_argument: str
    opposing_argument: str
    rebuttal: str
    cross_questions: list[CrossQuestion]
    citations: list[CheckedCitation]


@dataclass
class AnalysisResult:
    parties: list[tuple[str, PartyRole]] = field(default_factory=list)
    claims: list[ClaimRow] = field(default_factory=list)
    conflicts: list[ConflictRow] = field(default_factory=list)
    elements: list[ElementRow] = field(default_factory=list)
    adverse: list[AdverseRow] = field(default_factory=list)
    issues: list[IssueRow] = field(default_factory=list)


def _cites_json(cites: list[CheckedCitation]) -> str:
    return json.dumps(
        [{"chunk_id": c.chunk_id, "quote": c.quote, "verified": c.verified} for c in cites]
    )


def save_analysis(store: CaseStore, result: AnalysisResult) -> None:
    db = store.db
    with db:
        for table in RESULT_TABLES:
            db.execute(f"DELETE FROM {table}")
        db.executemany("INSERT INTO parties (name, role) VALUES (?, ?)", result.parties)
        claim_ids: dict[int, int] = {}
        for c in result.claims:
            cur = db.execute(
                "INSERT INTO claims (speaker, aspect, statement, when_iso, chunk_id, quote, "
                "verified) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    c.speaker,
                    c.aspect,
                    c.statement,
                    c.when,
                    c.citation.chunk_id,
                    c.citation.quote,
                    int(c.citation.verified),
                ),
            )
            assert cur.lastrowid is not None
            claim_ids[c.key] = cur.lastrowid
        db.executemany(
            "INSERT INTO conflicts (aspect, type, severity, effect, explanation, status, "
            "claim_ids) VALUES (?, ?, ?, ?, ?, 'open', ?)",
            [
                (
                    f.aspect,
                    f.type,
                    f.severity,
                    f.effect,
                    f.explanation,
                    json.dumps([claim_ids[k] for k in f.claim_keys]),
                )
                for f in result.conflicts
            ],
        )
        db.executemany(
            "INSERT INTO elements (kind, element, status, explanation, citations) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (e.kind, e.element, e.status, e.explanation, _cites_json(e.citations))
                for e in result.elements
            ],
        )
        db.executemany(
            "INSERT INTO adverse (explanation, citations) VALUES (?, ?)",
            [(a.explanation, _cites_json(a.citations)) for a in result.adverse],
        )
        db.executemany(
            "INSERT INTO issues (title, our_argument, opposing_argument, rebuttal, "
            "cross_questions, citations) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    i.title,
                    i.our_argument,
                    i.opposing_argument,
                    i.rebuttal,
                    json.dumps([q.model_dump() for q in i.cross_questions]),
                    _cites_json(i.citations),
                )
                for i in result.issues
            ],
        )


# --- reads ----------------------------------------------------------------------------------


class _Resolver:
    """Turns stored {chunk_id, quote, verified} into CitationViews with page + bbox."""

    def __init__(self, store: CaseStore, chunk_ids: set[int]) -> None:
        self._refs = {cid: ref for cid, (ref, _) in store.chunks_by_id(sorted(chunk_ids)).items()}

    def view(self, chunk_id: int, quote: str, verified: bool) -> CitationView | None:
        ref = self._refs.get(chunk_id)
        return CitationView(ref=ref, quote=quote, verified=verified) if ref else None

    def views(self, raw: str) -> list[CitationView]:
        views = (self.view(c["chunk_id"], c["quote"], c["verified"]) for c in json.loads(raw))
        return [v for v in views if v]


def _chunk_ids(rows: list, column: str) -> set[int]:
    return {c["chunk_id"] for r in rows for c in json.loads(r[column])}


def load_analysis(store: CaseStore) -> Analysis:
    db = store.db
    claims_rows = db.execute("SELECT * FROM claims ORDER BY id").fetchall()
    element_rows = db.execute("SELECT * FROM elements ORDER BY id").fetchall()
    adverse_rows = db.execute("SELECT * FROM adverse ORDER BY id").fetchall()
    issue_rows = db.execute("SELECT * FROM issues ORDER BY id").fetchall()
    resolver = _Resolver(
        store,
        {r["chunk_id"] for r in claims_rows}
        | _chunk_ids(element_rows, "citations")
        | _chunk_ids(adverse_rows, "citations")
        | _chunk_ids(issue_rows, "citations"),
    )

    claims: dict[int, Claim] = {}
    for r in claims_rows:
        view = resolver.view(r["chunk_id"], r["quote"], bool(r["verified"]))
        if view:
            claims[r["id"]] = Claim(
                id=r["id"],
                speaker=r["speaker"],
                aspect=r["aspect"],
                statement=r["statement"],
                when=r["when_iso"],
                citation=view,
            )

    conflicts = [
        Conflict(
            id=r["id"],
            aspect=r["aspect"],
            type=r["type"],
            severity=r["severity"],
            effect=r["effect"],
            explanation=r["explanation"],
            status=r["status"],
            claims=[claims[i] for i in json.loads(r["claim_ids"]) if i in claims],
        )
        for r in db.execute("SELECT * FROM conflicts ORDER BY id")
    ]
    return Analysis(
        job=latest_job(store, "analysis"),
        parties=[
            Party(id=r["id"], name=r["name"], role=r["role"])
            for r in db.execute("SELECT * FROM parties ORDER BY name")
        ],
        timeline=sorted((c for c in claims.values() if c.when), key=lambda c: c.when or ""),
        conflicts=conflicts,
        elements=[
            Element(
                id=r["id"],
                kind=r["kind"],
                element=r["element"],
                status=r["status"],
                explanation=r["explanation"],
                citations=resolver.views(r["citations"]),
            )
            for r in element_rows
        ],
        adverse=[
            Adverse(
                id=r["id"], explanation=r["explanation"], citations=resolver.views(r["citations"])
            )
            for r in adverse_rows
        ],
        issues=[
            Issue(
                id=r["id"],
                title=r["title"],
                our_argument=r["our_argument"],
                opposing_argument=r["opposing_argument"],
                rebuttal=r["rebuttal"],
                cross_questions=[CrossQuestion(**q) for q in json.loads(r["cross_questions"])],
                citations=resolver.views(r["citations"]),
            )
            for r in issue_rows
        ],
    )


def set_conflict_status(store: CaseStore, conflict_id: int, status: ConflictStatus) -> bool:
    with store.db:
        cur = store.db.execute(
            "UPDATE conflicts SET status = ? WHERE id = ?", (status, conflict_id)
        )
    return cur.rowcount == 1


# --- jobs -----------------------------------------------------------------------------------


def start_job(store: CaseStore, kind: str) -> str:
    job_id = uuid.uuid4().hex
    with store.db:
        store.db.execute(
            "INSERT INTO jobs (id, kind, status, step, progress, started_at) "
            "VALUES (?, ?, 'running', 'starting', 0, datetime('now'))",
            (job_id, kind),
        )
    return job_id


def update_job(store: CaseStore, job_id: str, step: str, progress: float) -> None:
    with store.db:
        store.db.execute(
            "UPDATE jobs SET step = ?, progress = ? WHERE id = ?", (step, progress, job_id)
        )


def finish_job(store: CaseStore, job_id: str, error: str | None = None) -> None:
    with store.db:
        store.db.execute(
            "UPDATE jobs SET status = ?, error = ?, progress = CASE WHEN ? IS NULL THEN 1 "
            "ELSE progress END, finished_at = datetime('now') WHERE id = ?",
            ("failed" if error else "done", error, error, job_id),
        )


def latest_job(store: CaseStore, kind: str) -> AnalysisJob | None:
    r = store.db.execute(
        "SELECT * FROM jobs WHERE kind = ? ORDER BY started_at DESC, rowid DESC LIMIT 1", (kind,)
    ).fetchone()
    if r is None:
        return None
    return AnalysisJob(
        id=r["id"],
        status=r["status"],
        step=r["step"],
        progress=r["progress"],
        error=r["error"],
        started_at=r["started_at"],
        finished_at=r["finished_at"],
    )
