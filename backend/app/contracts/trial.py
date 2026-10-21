from typing import Literal, get_args

from pydantic import BaseModel, Field

from app.contracts.analysis import CrossQuestion, PartyRole

# opening -> (chief -> cross) per witness -> final -> judgment -> closed
TrialPhase = Literal["opening", "chief", "cross", "final", "judgment", "closed"]
Speaker = Literal["judge", "user", "counsel", "witness"]  # counsel = the AI opposing counsel
TurnKind = Literal["statement", "question", "answer", "objection", "ruling", "argument"]
Demeanour = Literal["cooperative", "nervous", "hostile"]
UserTurnKind = Literal["question", "argument", "objection"]

TRIAL_PHASES: tuple[str, ...] = get_args(TrialPhase)
SPEAKERS: tuple[str, ...] = get_args(Speaker)
TURN_KINDS: tuple[str, ...] = get_args(TurnKind)


class TrialWitness(BaseModel):
    name: str
    role: PartyRole
    demeanour: Demeanour = "cooperative"


class TrialCreate(BaseModel):
    witnesses: list[TrialWitness] = Field(min_length=1, max_length=6)


class TrialTurn(BaseModel):
    id: int
    phase: TrialPhase
    speaker: Speaker
    speaker_name: str
    kind: TurnKind
    text: str
    struck: bool  # struck from the record after a sustained objection


class Debrief(BaseModel):
    score: int = Field(ge=1, le=10)
    summary: str
    strengths: list[str]
    missed: list[str]  # contradictions or gaps the lawyer did not use
    better_questions: list[CrossQuestion]


class TrialSession(BaseModel):
    id: str
    user_side: Literal["defence", "prosecution"]
    phase: TrialPhase
    witnesses: list[TrialWitness]
    witness_index: int
    awaiting_user: bool  # True when the next move is the lawyer's
    hint: str  # what the lawyer can do now
    turns: list[TrialTurn]
    debrief: Debrief | None


class TrialSessionSummary(BaseModel):
    id: str
    created_at: str
    phase: TrialPhase
    witnesses: list[str]


class UserTurn(BaseModel):
    kind: UserTurnKind
    text: str = Field(min_length=1, max_length=2000)
