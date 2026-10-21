"""Persistence for mock trial sessions and their transcript (case DB schema v4)."""

import json
import uuid
from dataclasses import dataclass
from typing import Literal

from app.contracts.trial import (
    Debrief,
    Speaker,
    TrialPhase,
    TrialSessionSummary,
    TrialTurn,
    TrialWitness,
    TurnKind,
)
from app.store.case_store import CaseStore


@dataclass
class TrialRecord:
    """A session's state as stored (the API adds whose turn it is via the phase machine)."""

    id: str
    user_side: Literal["defence", "prosecution"]
    phase: TrialPhase
    witness_index: int
    witnesses: list[TrialWitness]
    debrief: Debrief | None


def create_session(
    store: CaseStore, user_side: Literal["defence", "prosecution"], witnesses: list[TrialWitness]
) -> str:
    session_id = uuid.uuid4().hex
    with store.db:
        store.db.execute(
            "INSERT INTO trial_sessions (id, created_at, user_side, phase, witness_index, "
            "witnesses) VALUES (?, datetime('now'), ?, 'opening', 0, ?)",
            (session_id, user_side, json.dumps([w.model_dump() for w in witnesses])),
        )
    return session_id


def get_session(store: CaseStore, session_id: str) -> TrialRecord | None:
    r = store.db.execute("SELECT * FROM trial_sessions WHERE id = ?", (session_id,)).fetchone()
    if r is None:
        return None
    return TrialRecord(
        r["id"],
        r["user_side"],
        r["phase"],
        r["witness_index"],
        [TrialWitness(**w) for w in json.loads(r["witnesses"])],
        Debrief.model_validate_json(r["debrief"]) if r["debrief"] else None,
    )


def list_sessions(store: CaseStore) -> list[TrialSessionSummary]:
    rows = store.db.execute("SELECT * FROM trial_sessions ORDER BY created_at DESC").fetchall()
    return [
        TrialSessionSummary(
            id=r["id"],
            created_at=r["created_at"],
            phase=r["phase"],
            witnesses=[w["name"] for w in json.loads(r["witnesses"])],
        )
        for r in rows
    ]


def set_state(store: CaseStore, session_id: str, phase: TrialPhase, witness_index: int) -> None:
    with store.db:
        store.db.execute(
            "UPDATE trial_sessions SET phase = ?, witness_index = ? WHERE id = ?",
            (phase, witness_index, session_id),
        )


def save_debrief(store: CaseStore, session_id: str, debrief: Debrief) -> None:
    with store.db:
        store.db.execute(
            "UPDATE trial_sessions SET debrief = ? WHERE id = ?",
            (debrief.model_dump_json(), session_id),
        )


def add_turn(
    store: CaseStore,
    session_id: str,
    phase: TrialPhase,
    speaker: Speaker,
    speaker_name: str,
    kind: TurnKind,
    text: str,
) -> TrialTurn:
    with store.db:
        cur = store.db.execute(
            "INSERT INTO trial_turns (session_id, phase, speaker, speaker_name, kind, text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, phase, speaker, speaker_name, kind, text),
        )
    assert cur.lastrowid is not None
    return TrialTurn(
        id=cur.lastrowid,
        phase=phase,
        speaker=speaker,
        speaker_name=speaker_name,
        kind=kind,
        text=text,
        struck=False,
    )


def strike_turn(store: CaseStore, turn_id: int) -> None:
    with store.db:
        store.db.execute("UPDATE trial_turns SET struck = 1 WHERE id = ?", (turn_id,))


def get_turns(store: CaseStore, session_id: str) -> list[TrialTurn]:
    rows = store.db.execute(
        "SELECT * FROM trial_turns WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall()
    return [
        TrialTurn(
            id=r["id"],
            phase=r["phase"],
            speaker=r["speaker"],
            speaker_name=r["speaker_name"],
            kind=r["kind"],
            text=r["text"],
            struck=bool(r["struck"]),
        )
        for r in rows
    ]
