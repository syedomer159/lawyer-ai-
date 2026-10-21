from fastapi import APIRouter, HTTPException

from app.agents.trial import orchestrator
from app.agents.trial.phases import awaiting_user, hint
from app.agents.trial.roles import TrialContext
from app.api.deps import CaseDep, SettingsDep, StoreDep
from app.contracts.analysis import Party
from app.contracts.trial import TrialCreate, TrialSession, TrialSessionSummary, UserTurn
from app.store import trial_store
from app.store.analysis_store import load_analysis
from app.store.case_store import CaseStore

router = APIRouter(prefix="/api/cases/{case_id}/trial", tags=["trial"])


def _session(store: CaseStore, session_id: str) -> TrialSession:
    rec = trial_store.get_session(store, session_id)
    if rec is None:
        raise HTTPException(404, "trial session not found")
    turns = trial_store.get_turns(store, session_id)
    witness = rec.witnesses[min(rec.witness_index, len(rec.witnesses) - 1)].name
    return TrialSession(
        id=rec.id,
        user_side=rec.user_side,
        phase=rec.phase,
        witnesses=rec.witnesses,
        witness_index=rec.witness_index,
        awaiting_user=awaiting_user(rec.phase, rec.user_side, turns),
        hint=hint(rec.phase, rec.user_side, turns, witness),
        turns=turns,
        debrief=rec.debrief,
    )


@router.get("/witnesses")
def list_witnesses(store: StoreDep) -> list[Party]:
    """People from the case analysis who can be called to give evidence (not the accused)."""
    return [p for p in load_analysis(store).parties if p.role != "accused"]


@router.get("/sessions")
def list_sessions(store: StoreDep) -> list[TrialSessionSummary]:
    return trial_store.list_sessions(store)


@router.post("/sessions", status_code=201)
async def start_session(
    body: TrialCreate, case: CaseDep, store: StoreDep, settings: SettingsDep
) -> TrialSession:
    """Opens the trial and runs the AI side until the lawyer must act (a few model calls)."""
    session_id = trial_store.create_session(store, case.user_side, body.witnesses)
    await orchestrator.start(TrialContext(case, store, settings, session_id), body.witnesses)
    return _session(store, session_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, store: StoreDep) -> TrialSession:
    return _session(store, session_id)


@router.post("/sessions/{session_id}/turns")
async def post_turn(
    session_id: str, body: UserTurn, case: CaseDep, store: StoreDep, settings: SettingsDep
) -> TrialSession:
    _session(store, session_id)  # 404 before doing any work
    await orchestrator.user_turn(TrialContext(case, store, settings, session_id), body)
    return _session(store, session_id)


@router.post("/sessions/{session_id}/advance")
async def advance(
    session_id: str, case: CaseDep, store: StoreDep, settings: SettingsDep
) -> TrialSession:
    _session(store, session_id)
    await orchestrator.advance(TrialContext(case, store, settings, session_id))
    return _session(store, session_id)


@router.post("/sessions/{session_id}/debrief")
async def debrief(
    session_id: str, case: CaseDep, store: StoreDep, settings: SettingsDep
) -> TrialSession:
    _session(store, session_id)
    await orchestrator.run_debrief(TrialContext(case, store, settings, session_id))
    return _session(store, session_id)
