"""Applies the lawyer's moves and runs the AI side's turns, following phases.py.

Every request does a bounded amount of work (a handful of model calls), records each turn, and
returns. All calls carry the session id, so a whole trial can be followed in Phoenix."""

from fastapi import HTTPException

from app.agents.trial import roles
from app.agents.trial.phases import awaiting_user, examiner, next_state, user_has_argued
from app.agents.trial.roles import COUNSEL_TITLE, TrialContext
from app.contracts.trial import Speaker, TrialPhase, TrialTurn, TrialWitness, TurnKind, UserTurn
from app.observability import tracer
from app.store import trial_store
from app.store.trial_store import TrialRecord

AI_QUESTIONS_PER_EXAMINATION = 2  # keeps a demo trial short and cheap
STAGE_NAME = {"chief": "examination-in-chief", "cross": "cross-examination"}


def _record(ctx: TrialContext) -> TrialRecord:
    rec = trial_store.get_session(ctx.store, ctx.session_id)
    if rec is None:
        raise HTTPException(404, "trial session not found")
    return rec


def _turns(ctx: TrialContext) -> list[TrialTurn]:
    return trial_store.get_turns(ctx.store, ctx.session_id)


def _add(
    ctx: TrialContext, phase: TrialPhase, speaker: Speaker, name: str, kind: TurnKind, text: str
) -> None:
    trial_store.add_turn(ctx.store, ctx.session_id, phase, speaker, name, kind, text)


async def start(ctx: TrialContext, witnesses: list[TrialWitness]) -> None:
    with tracer.start_as_current_span("trial.start", attributes={"session.id": ctx.session_id}):
        task = (
            "Open the trial: state the charges against the accused in one or two sentences "
            "and call upon the prosecution to begin."
        )
        _add(ctx, "opening", "judge", "Court", "statement", await roles.judge_says(ctx, task, []))
        if ctx.ai_side == "prosecution":
            text = await roles.counsel_says(
                ctx,
                "Give a short opening statement: what the prosecution will prove and how.",
                _turns(ctx),
            )
            _add(ctx, "opening", "counsel", COUNSEL_TITLE["prosecution"], "statement", text)
        await _enter(ctx, "chief", 0)


async def _enter(ctx: TrialContext, phase: TrialPhase, idx: int) -> None:
    """Move to a state and run whatever the AI side does there, until the lawyer must act."""
    rec = _record(ctx)
    trial_store.set_state(ctx.store, ctx.session_id, phase, idx)
    if phase in ("chief", "cross"):
        w = rec.witnesses[idx]
        opener = (
            f"PW-{idx + 1} {w.name} is called and sworn. Examination-in-chief."
            if phase == "chief"
            else f"Cross-examination of PW-{idx + 1} {w.name}."
        )
        _add(ctx, phase, "judge", "Court", "statement", opener)
        if examiner(phase) != ctx.user_side:
            await _ai_examination(ctx, w, phase)
            nxt = next_state(phase, idx, len(rec.witnesses))
            await _enter(ctx, *nxt)
    elif phase == "final":
        _add(ctx, phase, "judge", "Court", "statement", "Evidence is closed. Final arguments.")
        if ctx.ai_side == "prosecution":  # the prosecution argues first
            await _ai_final_argument(ctx)
    elif phase == "judgment":
        task = (
            "Give the court's observations on the evidence heard: which testimony was shaken, "
            "what remains unproved, and what the court would weigh. Do not pronounce a "
            "final verdict; this is a practice hearing."
        )
        text = await roles.judge_says(ctx, task, _turns(ctx))
        _add(ctx, phase, "judge", "Court", "statement", text)
        trial_store.set_state(ctx.store, ctx.session_id, "closed", 0)


async def _ai_examination(ctx: TrialContext, w: TrialWitness, phase: TrialPhase) -> None:
    for _ in range(AI_QUESTIONS_PER_EXAMINATION):
        task = (
            f"Ask the next question in your {STAGE_NAME[phase]} of {w.name}. Ask ONE short "
            "question only, building on the answers so far; do not repeat a question. "
            f"The witness's statement:\n{roles.witness_statements(ctx.store, w.name)}"
        )
        question = await roles.counsel_says(ctx, task, _turns(ctx))
        _add(ctx, phase, "counsel", COUNSEL_TITLE[ctx.ai_side], "question", question)
        answer = await roles.witness_answers(ctx, w, question, _turns(ctx))
        _add(ctx, phase, "witness", w.name, "answer", answer)


async def _ai_final_argument(ctx: TrialContext) -> None:
    task = (
        "Make your final argument: what the evidence heard in court proves or fails to "
        "prove, in under 200 words."
    )
    text = await roles.counsel_says(ctx, task, _turns(ctx))
    _add(ctx, "final", "counsel", COUNSEL_TITLE[ctx.ai_side], "argument", text)


async def user_turn(ctx: TrialContext, turn: UserTurn) -> None:
    rec = _record(ctx)
    with tracer.start_as_current_span(
        "trial.turn", attributes={"session.id": ctx.session_id, "turn.kind": turn.kind}
    ):
        if turn.kind == "objection":
            await _user_objection(ctx, rec, turn.text)
        elif turn.kind == "question":
            await _user_question(ctx, rec, turn.text)
        else:
            await _user_argument(ctx, rec, turn.text)


async def _user_question(ctx: TrialContext, rec: TrialRecord, question: str) -> None:
    if rec.phase not in ("chief", "cross") or examiner(rec.phase) != ctx.user_side:
        raise HTTPException(409, "it is not your turn to examine a witness")
    w, name = rec.witnesses[rec.witness_index], COUNSEL_TITLE[ctx.user_side]
    q = trial_store.add_turn(
        ctx.store, ctx.session_id, rec.phase, "user", name, "question", question
    )
    decision = await roles.counsel_objects(ctx, question, STAGE_NAME[rec.phase])
    if decision.object:
        objection = f"Objection, Your Honour: {decision.ground}"
        _add(ctx, rec.phase, "counsel", COUNSEL_TITLE[ctx.ai_side], "objection", objection)
        ruling = await roles.judge_rules(ctx, objection, question, STAGE_NAME[rec.phase])
        verdict = "Sustained." if ruling.sustained else "Overruled."
        _add(ctx, rec.phase, "judge", "Court", "ruling", f"{verdict} {ruling.reason}")
        if ruling.sustained:
            trial_store.strike_turn(ctx.store, q.id)
            return
    answer = await roles.witness_answers(ctx, w, question, _turns(ctx))
    _add(ctx, rec.phase, "witness", w.name, "answer", answer)


async def _user_objection(ctx: TrialContext, rec: TrialRecord, ground: str) -> None:
    turns = _turns(ctx)
    target = next(
        (
            t
            for t in reversed(turns)
            if t.speaker == "counsel"
            and t.kind in ("question", "argument", "statement")
            and not t.struck
        ),
        None,
    )
    if target is None:
        raise HTTPException(409, "there is nothing from opposing counsel to object to")
    objection = f"Objection, Your Honour: {ground}"
    _add(ctx, rec.phase, "user", COUNSEL_TITLE[ctx.user_side], "objection", objection)
    ruling = await roles.judge_rules(
        ctx, objection, target.text, STAGE_NAME.get(rec.phase, rec.phase)
    )
    verdict = "Sustained." if ruling.sustained else "Overruled."
    _add(ctx, rec.phase, "judge", "Court", "ruling", f"{verdict} {ruling.reason}")
    if ruling.sustained:  # strike the objected turn and the answer it drew
        for t in turns:
            if t.id == target.id or (t.id > target.id and t.speaker == "witness"):
                trial_store.strike_turn(ctx.store, t.id)


async def _user_argument(ctx: TrialContext, rec: TrialRecord, text: str) -> None:
    turns = _turns(ctx)
    if rec.phase != "final" or user_has_argued(turns):
        raise HTTPException(409, "arguments are made once, in the final arguments phase")
    _add(ctx, "final", "user", COUNSEL_TITLE[ctx.user_side], "argument", text)
    if ctx.ai_side == "defence":  # the defence replies after the prosecution
        await _ai_final_argument(ctx)


async def advance(ctx: TrialContext) -> None:
    """'No further questions' / 'proceed': only when the lawyer holds the floor."""
    rec = _record(ctx)
    turns = _turns(ctx)
    if not awaiting_user(rec.phase, ctx.user_side, turns):
        raise HTTPException(409, "the court is not waiting on you")
    if rec.phase == "final" and not user_has_argued(turns):
        raise HTTPException(409, "make your final argument first")
    with tracer.start_as_current_span("trial.advance", attributes={"session.id": ctx.session_id}):
        await _enter(ctx, *next_state(rec.phase, rec.witness_index, len(rec.witnesses)))


async def run_debrief(ctx: TrialContext) -> None:
    if not any(t.speaker == "user" for t in _turns(ctx)):
        raise HTTPException(409, "take part in the trial before asking for a debrief")
    with tracer.start_as_current_span("trial.debrief", attributes={"session.id": ctx.session_id}):
        result = await roles.debrief(ctx, _turns(ctx))
    trial_store.save_debrief(ctx.store, ctx.session_id, result)
