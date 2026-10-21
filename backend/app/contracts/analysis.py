from typing import Literal, get_args

from pydantic import BaseModel

from app.contracts.documents import SourceRef

PartyRole = Literal["accused", "complainant", "witness", "io", "police", "doctor", "panch", "other"]
ConflictType = Literal[
    "testimony_vs_testimony",
    "testimony_vs_document",
    "testimony_vs_physical",
    "document_vs_document",
]
Severity = Literal["high", "medium", "low"]
SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}  # for sorting, most severe first
Effect = Literal["helps", "hurts"]  # effect on OUR client (the case's user_side)
ConflictStatus = Literal["open", "dismissed"]
ElementKind = Literal["offence", "procedure"]
ElementStatus = Literal["supported", "weak", "missing"]
JobStatus = Literal["running", "done", "failed"]

PARTY_ROLES: tuple[str, ...] = get_args(PartyRole)
CONFLICT_TYPES: tuple[str, ...] = get_args(ConflictType)
SEVERITIES: tuple[str, ...] = get_args(Severity)
EFFECTS: tuple[str, ...] = get_args(Effect)
CONFLICT_STATUSES: tuple[str, ...] = get_args(ConflictStatus)
ELEMENT_KINDS: tuple[str, ...] = get_args(ElementKind)
ELEMENT_STATUSES: tuple[str, ...] = get_args(ElementStatus)
JOB_STATUSES: tuple[str, ...] = get_args(JobStatus)


class CitationView(BaseModel):
    ref: SourceRef
    quote: str
    # quote found in the cited chunk (app/citations.py); never shown as fact if False
    verified: bool


class Party(BaseModel):
    id: int
    name: str
    role: PartyRole


class Claim(BaseModel):
    id: int
    speaker: str
    aspect: str
    statement: str
    when: str | None  # ISO date/time if the source states one
    citation: CitationView


class Conflict(BaseModel):
    id: int
    aspect: str
    type: ConflictType
    severity: Severity
    effect: Effect
    explanation: str
    status: ConflictStatus
    claims: list[Claim]


class Element(BaseModel):
    id: int
    kind: ElementKind
    element: str
    status: ElementStatus
    explanation: str
    citations: list[CitationView]


class Adverse(BaseModel):
    id: int
    explanation: str
    citations: list[CitationView]


class CrossQuestion(BaseModel):
    witness: str
    question: str


class Issue(BaseModel):
    id: int
    title: str
    our_argument: str
    opposing_argument: str
    rebuttal: str
    cross_questions: list[CrossQuestion]
    citations: list[CitationView]


class AnalysisJob(BaseModel):
    id: str
    status: JobStatus
    step: str
    progress: float  # 0..1
    error: str | None
    started_at: str
    finished_at: str | None


class Analysis(BaseModel):
    job: AnalysisJob | None  # latest run; results below are from the last successful run
    parties: list[Party]
    timeline: list[Claim]  # claims with a known date/time, in order
    conflicts: list[Conflict]
    elements: list[Element]
    adverse: list[Adverse]
    issues: list[Issue]


class ConflictUpdate(BaseModel):
    status: ConflictStatus
