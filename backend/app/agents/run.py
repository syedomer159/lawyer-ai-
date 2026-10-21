"""Shared context for one analysis run: which case, its store, and how to call a role."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.citations import Citation, CitationChecker
from app.config import Settings
from app.contracts.cases import Case
from app.contracts.documents import SourceRef
from app.llm.embeddings import CaseEmbedder
from app.llm.prompts import load_prompt
from app.llm.registry import Role
from app.llm.runner import run_role
from app.store.analysis_store import ClaimRow
from app.store.case_store import CaseStore

MAX_PARALLEL_CALLS = 3  # stays under free-tier rate limits; CPU-bound locally anyway


@dataclass
class AnalysisRun:
    case: Case
    store: CaseStore
    settings: Settings
    job_id: str
    checker: CitationChecker
    sources: dict[int, SourceRef]  # chunk_id -> document/page, for this case only
    embedder: CaseEmbedder  # the case's own (local) embedder
    limit: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(MAX_PARALLEL_CALLS))

    @classmethod
    def create(
        cls, case: Case, store: CaseStore, settings: Settings, job_id: str, embedder: CaseEmbedder
    ) -> "AnalysisRun":
        checker = CitationChecker(store)
        sources = {cid: ref for cid, (ref, _) in store.chunks_by_id(checker.chunk_ids()).items()}
        return cls(case, store, settings, job_id, checker, sources, embedder)

    async def call[T: BaseModel](
        self,
        role: Role,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        check: Callable[[T], list[str]] | None = None,
        extra_vars: dict[str, str] | None = None,
    ) -> T:
        prompt_vars = {
            "side": self.case.user_side,
            "client": self.case.client,
            "charges": ", ".join(self.case.charges) or "not specified",
            **(extra_vars or {}),
        }
        async with self.limit:
            return await run_role(
                role,
                case=self.case,
                store=self.store,
                settings=self.settings,
                prompt=load_prompt(prompt),
                user_prompt=user_prompt,
                output_type=output_type,
                prompt_vars=prompt_vars,
                job_id=self.job_id,
                check=check,
            )

    def cite_problems(self, citations: list[Citation]) -> list[str]:
        return self.checker.problems(citations)

    def doc(self, chunk_id: int) -> str:
        ref = self.sources.get(chunk_id)
        return ref.filename if ref else "unknown document"

    def evidence_line(self, c: ClaimRow) -> str:
        """How claims are shown to analysis/argument agents: citable by chunk id + exact quote."""
        cid = c.citation.chunk_id
        return f'[chunk {cid}] {c.speaker} ({self.doc(cid)}) | {c.statement} | "{c.citation.quote}"'
