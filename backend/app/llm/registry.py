"""Role -> model resolution (ADR-0002). Agents never name a model; they name a role."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.settings import ModelSettings

from app.contracts.cases import Case

Profile = Literal["local", "hybrid", "cloud"]
Role = Literal[
    "extractor",  # claims/parties from each document
    "analyst",  # contradictions and gaps
    "argument",  # arguments, rebuttals, cross-examination questions
    "judge",
    "opposing_counsel",
    "io",  # investigating officer
    "witness",
    "assistant",  # case chat
    "debrief",  # coach after a mock trial
    "vision",  # captions for photos with no text
    "eval_judge",  # LLM-as-judge in evals
]
ROLES: tuple[str, ...] = get_args(Role)


# A role's model, or a fallback chain tried in order (e.g. when the first is overloaded).
ModelSpec = str | list[str]


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo'd role name fails loudly

    default: ModelSpec
    # One optional override per role (pydantic needs real fields to forbid unknown keys).
    extractor: ModelSpec | None = None
    analyst: ModelSpec | None = None
    argument: ModelSpec | None = None
    judge: ModelSpec | None = None
    opposing_counsel: ModelSpec | None = None
    io: ModelSpec | None = None
    witness: ModelSpec | None = None
    assistant: ModelSpec | None = None
    debrief: ModelSpec | None = None
    vision: ModelSpec | None = None
    eval_judge: ModelSpec | None = None


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: dict[Profile, ProfileConfig]


@dataclass(frozen=True)
class RoleModel:
    role: Role
    profile: Profile
    models: tuple[str, ...]  # primary first, then fallbacks
    settings: ModelSettings
    native_output: bool  # Ollama: grammar-constrained JSON schema output (ADR-0002)

    @property
    def primary(self) -> str:
        return self.models[0]


def is_offline(model: str) -> bool:
    """Ollama runs on this machine; "test" is pydantic-ai's offline fake used by the tests."""
    return model.startswith("ollama:") or model == "test"


def _chain(spec: ModelSpec) -> tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)


@cache
def load_models_config(path: Path) -> ModelsConfig:
    config = ModelsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    missing = set(get_args(Profile)) - set(config.profiles)
    if missing:
        raise ValueError(f"{path}: missing profiles {sorted(missing)}")
    for name, profile in config.profiles.items():
        for role, spec in profile.model_dump(exclude_none=True).items():
            chain = _chain(spec)
            # Settings and output mode are chosen per role, so a chain can't mix local and cloud.
            if not chain or len({m.startswith("ollama:") for m in chain}) > 1:
                raise ValueError(f"{path}: {name}.{role} mixes local and cloud models: {chain}")
            # local_only cases rely on this: the local profile must never send text off the machine.
            if name == "local" and not all(is_offline(m) for m in chain):
                raise ValueError(f"{path}: local profile has non-Ollama models in {role}: {chain}")
    return config


def resolve(role: Role, case: Case, profile: Profile, config_path: Path) -> RoleModel:
    effective: Profile = "local" if case.local_only else profile
    profile_config = load_models_config(config_path).profiles[effective]
    models = _chain(getattr(profile_config, role) or profile_config.default)
    local = models[0].startswith("ollama:")
    # qwen3.5 is a thinking model: with reasoning on, a short CPU call takes 10+ minutes.
    settings: ModelSettings = {}
    if local:
        settings = OpenAIChatModelSettings(openai_reasoning_effort="none")
    return RoleModel(role, effective, models, settings, native_output=local)
