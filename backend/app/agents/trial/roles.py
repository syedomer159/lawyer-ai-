"""One function per courtroom role. Each role sees only what that person would know:
- witness / IO: their own statements and documents (nothing else from the case file);
- judge: the court transcript only;
- AI counsel: the case analysis brief + the transcript;
- debrief coach: the transcript + the analysis findings."""

import re
from dataclasses import dataclass

from pydantic import BaseModel

from app.agents.analysis import party_key
from app.agents.trial.phases import Side
from app.config import Settings
from app.contracts.cases import Case
from app.contracts.trial import Debrief, TrialTurn, TrialWitness
from app.llm.prompts import load_prompt
from app.llm.registry import Role
from app.llm.runner import run_role
from app.store.analysis_store import load_analysis
from app.store.case_store import CaseStore

TRANSCRIPT_TURNS = 16  # recent turns each role sees; keeps context (and cost) bounded
MAX_STATEMENT_CHARS = 8_000
COUNSEL_TITLE: dict[Side, str] = {"prosecution": "Public Prosecutor", "defence": "Defence Counsel"}


@dataclass
class TrialContext:
    case: Case
    store: CaseStore
    settings: Settings
    session_id: str

    @property
    def user_side(self) -> Side:
        return self.case.user_side

    @property
    def ai_side(self) -> Side:
        return "prosecution" if self.case.user_side == "defence" else "defence"

    async def call[T: BaseModel](
        self, role: Role, prompt: str, user_prompt: str, output: type[T], **vars: str
    ) -> T:
        return await run_role(
            role,
            case=self.case,
            store=self.store,
            settings=self.settings,
            prompt=load_prompt(prompt),
            user_prompt=user_prompt,
            output_type=output,
            prompt_vars={
                "court": "trial court",
                "charges": ", ".join(self.case.charges) or "not specified",
                **vars,
            },
            session_id=self.session_id,
        )

    async def say(self, role: Role, prompt: str, user_prompt: str, **vars: str) -> str:
        return (await self.call(role, prompt, user_prompt, Utterance, **vars)).text


class Utterance(BaseModel):
    text: str


class ObjectionDecision(BaseModel):
    object: bool
    ground: str


class Ruling(BaseModel):
    sustained: bool
    reason: str


def label(t: TrialTurn, user_side: Side) -> str:
    if t.speaker == "judge":
        return "COURT"
    if t.speaker == "user":
        return COUNSEL_TITLE[user_side].upper()
    if t.speaker == "counsel":
        return COUNSEL_TITLE["prosecution" if user_side == "defence" else "defence"].upper()
    return t.speaker_name


def transcript(turns: list[TrialTurn], user_side: Side, limit: int = TRANSCRIPT_TURNS) -> str:
    kept = [t for t in turns if not t.struck][-limit:]
    return "\n".join(f"[{label(t, user_side)}] {t.text}" for t in kept) or "(nothing yet)"


def witness_statements(store: CaseStore, name: str) -> str:
    """The witness's own documents: those where analysis found them speaking, else documents
    that mention their full name. Never the rest of the case file."""
    key = party_key(name)
    rows = store.db.execute(
        "SELECT DISTINCT c.doc_id, cl.speaker FROM claims cl JOIN chunks c ON c.id = cl.chunk_id"
    ).fetchall()
    speaking = {r["doc_id"] for r in rows if party_key(r["speaker"]) == key}
    # Fallback match on the FULL name: a surname alone ("More") would match ordinary words.
    full_name = r"\s+".join(re.escape(part) for part in key.split())
    docs = [
        d
        for d in store.list_documents()
        if d.id in speaking
        or (
            not speaking
            and full_name
            and re.search(rf"\b{full_name}\b", store.doc_text(d.id), re.I)
        )
    ]
    text = "\n\n".join(f"--- {d.filename} ---\n{store.doc_text(d.id)}" for d in docs)
    return text[:MAX_STATEMENT_CHARS] or "(no statement on record)"


def counsel_brief(store: CaseStore) -> str:
    a = load_analysis(store)
    if not (a.elements or a.conflicts or a.adverse):
        return "No case analysis has been run; rely on the court record."
    lines = [f"- [{e.status}] {e.element}: {e.explanation}" for e in a.elements]
    lines += [f"- Evidence against the accused: {x.explanation}" for x in a.adverse]
    lines += [f"- Contradiction ({c.aspect}): {c.explanation}" for c in a.conflicts]
    return "\n".join(lines)[:6_000]


def witness_role(w: TrialWitness) -> Role:
    return "io" if w.role in ("io", "police") else "witness"


# --- the roles -------------------------------------------------------------------------------


async def judge_says(ctx: TrialContext, task: str, turns: list[TrialTurn]) -> str:
    return await ctx.say(
        "judge", "judge", f"TRANSCRIPT\n{transcript(turns, ctx.user_side)}", task=task
    )


async def judge_rules(ctx: TrialContext, objection: str, target: str, stage: str) -> Ruling:
    prompt = f"STAGE: {stage}\nOBJECTED TO: {target}\nOBJECTION: {objection}"
    return await ctx.call("judge", "judge_ruling", prompt, Ruling)


async def counsel_says(ctx: TrialContext, task: str, turns: list[TrialTurn]) -> str:
    return await ctx.say(
        "opposing_counsel",
        "counsel",
        f"TRANSCRIPT\n{transcript(turns, ctx.user_side)}",
        title=COUNSEL_TITLE[ctx.ai_side],
        brief=counsel_brief(ctx.store),
        task=task,
    )


async def counsel_objects(ctx: TrialContext, question: str, stage: str) -> ObjectionDecision:
    return await ctx.call(
        "opposing_counsel",
        "objection",
        f"QUESTION: {question}",
        ObjectionDecision,
        title=COUNSEL_TITLE[ctx.ai_side],
        stage=stage,
    )


async def witness_answers(
    ctx: TrialContext, w: TrialWitness, question: str, turns: list[TrialTurn]
) -> str:
    # The witness hears only its own examination, not the rest of the trial.
    own = [t for t in turns if t.phase in ("chief", "cross")][-10:]
    return await ctx.say(
        witness_role(w),
        "witness",
        f"EARLIER IN YOUR EVIDENCE\n{transcript(own, ctx.user_side)}\n\nQUESTION: {question}",
        name=w.name,
        witness_role=w.role,
        demeanour=w.demeanour,
        statements=witness_statements(ctx.store, w.name),
    )


async def debrief(ctx: TrialContext, turns: list[TrialTurn]) -> Debrief:
    a = load_analysis(ctx.store)
    findings = [f"- Contradiction ({c.aspect}): {c.explanation}" for c in a.conflicts]
    findings += [
        f"- {e.status} {e.kind}: {e.element}" for e in a.elements if e.status != "supported"
    ]
    prompt = (
        "ANALYSIS FINDINGS\n"
        + ("\n".join(findings) or "(no analysis run)")
        + f"\n\nTRANSCRIPT\n{transcript(turns, ctx.user_side, limit=200)}"
    )
    return await ctx.call(
        "debrief", "debrief", prompt, Debrief, side=ctx.user_side, client=ctx.case.client
    )
