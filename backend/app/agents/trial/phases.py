"""The trial's procedure as a pure state machine (ADR-0003): code decides who acts next, agents
only produce their own turn. Simplified Indian sessions trial:

  opening -> [chief -> cross] for each prosecution witness -> final -> judgment -> closed

Examination-in-chief is by the prosecution, cross-examination by the defence. Whichever side
the lawyer is on, the AI counsel plays the other.
"""

from typing import Literal

from app.contracts.trial import TrialPhase, TrialTurn

Side = Literal["defence", "prosecution"]


def examiner(phase: TrialPhase) -> Side | None:
    match phase:
        case "chief":
            return "prosecution"
        case "cross":
            return "defence"
        case _:
            return None


def other(side: Side) -> Side:
    return "prosecution" if side == "defence" else "defence"


def next_state(phase: TrialPhase, witness_index: int, n_witnesses: int) -> tuple[TrialPhase, int]:
    match phase:
        case "opening":
            return "chief", 0
        case "chief":
            return "cross", witness_index
        case "cross":
            return ("chief", witness_index + 1) if witness_index + 1 < n_witnesses else ("final", 0)
        case "final":
            return "judgment", 0
        case _:
            return "closed", 0


def user_has_argued(turns: list[TrialTurn]) -> bool:
    return any(t.phase == "final" and t.speaker == "user" and t.kind == "argument" for t in turns)


def awaiting_user(phase: TrialPhase, user_side: Side, turns: list[TrialTurn]) -> bool:
    if phase in ("chief", "cross"):
        return examiner(phase) == user_side
    return phase == "final"  # the lawyer argues, then moves on to judgment


def hint(phase: TrialPhase, user_side: Side, turns: list[TrialTurn], witness: str) -> str:
    if phase in ("chief", "cross") and examiner(phase) == user_side:
        kind = "examination-in-chief" if phase == "chief" else "cross-examination"
        return f"Your {kind} of {witness}: ask questions, then 'No further questions'."
    if phase == "final":
        if user_has_argued(turns):
            return "Final arguments done: proceed to the judge's observations."
        return "Make your final argument to the court."
    if phase == "closed":
        return "The trial is over. Ask for a debrief on your performance."
    return "The court is proceeding."
