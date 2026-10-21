"""The case assistant: the one open-ended, tool-calling agent (ADR-0003).

Its tools are read-only closures over ONE case's store, so it cannot reach another case. Its
answer carries citations that get one corrective retry and are then checked in code."""

import json

from pydantic import BaseModel

from app.citations import Citation, CitationChecker
from app.config import Settings
from app.contracts.analysis import CitationView
from app.contracts.assistant import ChatMessage
from app.contracts.cases import Case
from app.llm.embeddings import CaseEmbedder
from app.llm.prompts import load_prompt
from app.llm.runner import ToolFunc, run_role
from app.retrieval.search import search
from app.store.analysis_store import load_analysis
from app.store.case_store import CaseStore

HISTORY_MESSAGES = 6  # earlier messages shown to the model for follow-up questions


class Answer(BaseModel):
    answer: str
    citations: list[Citation]


def case_tools(store: CaseStore, embedder: CaseEmbedder) -> list[ToolFunc]:
    def cites(views: list[CitationView]) -> str:
        return " ".join(f"[chunk {c.ref.chunk_id}]" for c in views)

    async def search_case(query: str) -> str:
        """Search this case's documents. Returns the best passages, each marked [chunk N]."""
        hits = await search(store, embedder, query, k=6)
        return (
            "\n\n".join(
                f"[chunk {h.ref.chunk_id}] {h.ref.filename} p{h.ref.page}:\n{h.text}" for h in hits
            )
            or "No matching passages."
        )

    async def list_contradictions() -> str:
        """Contradictions found by the case analysis, with the claims on each side."""
        a = load_analysis(store)
        return (
            "\n".join(
                f"- {c.aspect} [{c.severity}, {c.effect} us]: {c.explanation} | "
                + "; ".join(
                    f'{x.speaker}: "{x.citation.quote}" [chunk {x.citation.ref.chunk_id}]'
                    for x in c.claims
                )
                for c in a.conflicts
                if c.status == "open"
            )
            or "No analysis results yet."
        )

    async def list_gaps() -> str:
        """Elements of the charges and procedural points, with how well the evidence covers them."""
        a = load_analysis(store)
        return (
            "\n".join(
                f"- [{e.status}] {e.element}: {e.explanation} {cites(e.citations)}"
                for e in a.elements
            )
            or "No analysis results yet."
        )

    async def list_arguments() -> str:
        """Prepared arguments, the other side's likely answer, our rebuttal and cross questions."""
        a = load_analysis(store)
        return (
            "\n".join(
                f"- {i.title}: {i.our_argument} | They say: {i.opposing_argument} | "
                f"Reply: {i.rebuttal} {cites(i.citations)}"
                for i in a.issues
            )
            or "No analysis results yet."
        )

    async def timeline() -> str:
        """Dated events as each source tells them, in order."""
        a = load_analysis(store)
        return (
            "\n".join(
                f"- {c.when} {c.speaker}: {c.statement} [chunk {c.citation.ref.chunk_id}]"
                for c in a.timeline
            )
            or "No dated events found yet."
        )

    return [search_case, list_contradictions, list_gaps, list_arguments, timeline]


def _history(store: CaseStore) -> str:
    rows = store.db.execute(
        "SELECT role, text FROM assistant_messages ORDER BY id DESC LIMIT ?", (HISTORY_MESSAGES,)
    ).fetchall()
    return "\n".join(f"{r['role'].upper()}: {r['text']}" for r in reversed(rows))


def _save(store: CaseStore, role: str, text: str, citations: list[dict]) -> int:
    with store.db:
        cur = store.db.execute(
            "INSERT INTO assistant_messages (role, text, citations) VALUES (?, ?, ?)",
            (role, text, json.dumps(citations)),
        )
    assert cur.lastrowid is not None
    return cur.lastrowid


def list_messages(store: CaseStore) -> list[ChatMessage]:
    rows = store.db.execute("SELECT * FROM assistant_messages ORDER BY id").fetchall()
    raw = [(r, json.loads(r["citations"])) for r in rows]
    refs = {
        cid: ref
        for cid, (ref, _) in store.chunks_by_id(
            sorted({c["chunk_id"] for _, cs in raw for c in cs})
        ).items()
    }
    return [
        ChatMessage(
            id=r["id"],
            role=r["role"],
            text=r["text"],
            citations=[
                CitationView(ref=refs[c["chunk_id"]], quote=c["quote"], verified=c["verified"])
                for c in cs
                if c["chunk_id"] in refs
            ],
        )
        for r, cs in raw
    ]


async def ask(
    case: Case, store: CaseStore, settings: Settings, embedder: CaseEmbedder, question: str
) -> None:
    history = _history(store)
    _save(store, "user", question, [])
    checker = CitationChecker(store)
    prompt = (f"CONVERSATION SO FAR\n{history}\n\n" if history else "") + f"QUESTION: {question}"
    out = await run_role(
        "assistant",
        case=case,
        store=store,
        settings=settings,
        prompt=load_prompt("assistant"),
        user_prompt=prompt,
        output_type=Answer,
        prompt_vars={
            "side": case.user_side,
            "client": case.client,
            "charges": ", ".join(case.charges) or "not specified",
        },
        check=lambda a: checker.problems(a.citations),
        tools=case_tools(store, embedder),
    )
    checked = [checker.check(c) for c in out.citations]
    _save(
        store,
        "assistant",
        out.answer,
        [{"chunk_id": c.chunk_id, "quote": c.quote, "verified": c.verified} for c in checked],
    )
