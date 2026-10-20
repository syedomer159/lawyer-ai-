"""The one way agents call a model: resolve the role's model, run it inside a traced span, and
record tokens/cost/latency in the case's own store (ADR-0002, ADR-0004)."""

import time
from decimal import Decimal
from typing import overload

from pydantic import BaseModel, SecretStr
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import Settings
from app.contracts.cases import Case
from app.llm.prompts import Prompt
from app.llm.registry import Role, resolve
from app.observability import tracer
from app.store.case_store import CaseStore, LLMCall


@overload
async def run_role[T: BaseModel](
    role: Role, *, case: Case, store: CaseStore, settings: Settings, prompt: Prompt,
    user_prompt: str, output_type: type[T], prompt_vars: dict[str, str] | None = None,
    job_id: str | None = None, session_id: str | None = None,
) -> T: ...  # fmt: skip
@overload
async def run_role(
    role: Role, *, case: Case, store: CaseStore, settings: Settings, prompt: Prompt,
    user_prompt: str, output_type: type[str], prompt_vars: dict[str, str] | None = None,
    job_id: str | None = None, session_id: str | None = None,
) -> str: ...  # fmt: skip
async def run_role(
    role: Role,
    *,
    case: Case,
    store: CaseStore,
    settings: Settings,
    prompt: Prompt,
    user_prompt: str,
    output_type: type[BaseModel] | type[str],
    prompt_vars: dict[str, str] | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
) -> BaseModel | str:
    rm = resolve(role, case, settings.model_profile, settings.models_config)
    structured = output_type is not str
    agent = Agent(
        build_model(rm.model, settings),
        output_type=NativeOutput(output_type) if rm.native_output and structured else output_type,
        instructions=prompt.render(**(prompt_vars or {})),
        model_settings=rm.settings,
        name=role,
    )
    attributes = {
        "case.id": case.id,
        "llm.role": role,
        "llm.profile": rm.profile,
        "llm.model_name": rm.model,
        "prompt.name": prompt.name,
        "prompt.version": prompt.version,
        "job.id": job_id or "",
        "session.id": session_id or "",
    }
    with tracer.start_as_current_span(f"role.{role}", attributes=attributes) as span:
        t0 = time.perf_counter()
        result = await agent.run(user_prompt)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        usage = result.usage
        cost = _cost(usage.cost, rm.model)
        span.set_attribute("llm.cost_usd", cost if cost is not None else -1)
        trace_id = format(span.get_span_context().trace_id, "032x")

    store.record_llm_call(
        LLMCall(
            role=role,
            model=rm.model,
            prompt=prompt.name,
            prompt_version=prompt.version,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            trace_id=trace_id,
            job_id=job_id,
            session_id=session_id,
        )
    )
    return result.output


def _key(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret else None


def build_model(model: str, settings: Settings) -> Model | str:
    """Give each provider its URL/key from Settings (i.e. from .env). A bare model string would
    make pydantic-ai read only process env vars, so keys in .env would be silently ignored."""
    provider_name, _, name = model.partition(":")
    match provider_name:
        case "ollama":
            return OllamaModel(name, provider=OllamaProvider(base_url=settings.ollama_base_url))
        case "google":
            return GoogleModel(name, provider=GoogleProvider(api_key=_key(settings.gemini_api_key)))
        case "anthropic":
            key = _key(settings.anthropic_api_key)
            return AnthropicModel(name, provider=AnthropicProvider(api_key=key))
        case "openai":
            return OpenAIChatModel(
                name, provider=OpenAIProvider(api_key=_key(settings.openai_api_key))
            )
        case _:
            return model  # e.g. "test"


def _cost(reported: Decimal | None, model: str) -> float | None:
    if reported is not None:
        return float(reported)
    # Models on this machine are free; anything else unpriced stays unknown (None), not zero.
    return 0.0 if model.startswith("ollama:") or model == "test" else None
