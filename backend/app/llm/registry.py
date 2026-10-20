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


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo'd role name fails loudly

    default: str
    # One optional override per role (pydantic needs real fields to forbid unknown keys).
    extractor: str | None = None
    analyst: str | None = None
    argument: str | None = None
    judge: str | None = None
    opposing_counsel: str | None = None
    io: str | None = None
    witness: str | None = None
    assistant: str | None = None
    debrief: str | None = None
    vision: str | None = None
    eval_judge: str | None = None


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: dict[Profile, ProfileConfig]


@dataclass(frozen=True)
class RoleModel:
    role: Role
    profile: Profile
    model: str
    settings: ModelSettings
    native_output: bool  # Ollama: grammar-constrained JSON schema output (ADR-0002)


def is_offline(model: str) -> bool:
    """Ollama runs on this machine; "test" is pydantic-ai's offline fake used by the tests."""
    return model.startswith("ollama:") or model == "test"


@cache
def load_models_config(path: Path) -> ModelsConfig:
    config = ModelsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    missing = set(get_args(Profile)) - set(config.profiles)
    if missing:
        raise ValueError(f"{path}: missing profiles {sorted(missing)}")
    # local_only cases rely on this: the local profile must never route text off the machine.
    local = config.profiles["local"].model_dump(exclude_none=True)
    if leaks := {role: m for role, m in local.items() if not is_offline(m)}:
        raise ValueError(f"{path}: local profile has non-Ollama models {leaks}")
    return config


def resolve(role: Role, case: Case, profile: Profile, config_path: Path) -> RoleModel:
    effective: Profile = "local" if case.local_only else profile
    profile_config = load_models_config(config_path).profiles[effective]
    model = getattr(profile_config, role) or profile_config.default
    local = model.startswith("ollama:")
    # qwen3.5 is a thinking model: with reasoning on, a short CPU call takes 10+ minutes.
    settings: ModelSettings = {}
    if local:
        settings = OpenAIChatModelSettings(openai_reasoning_effort="none")
    return RoleModel(role, effective, model, settings, native_output=local)
