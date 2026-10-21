"""The one way agents call a model: resolve the role's model, run it inside a traced span, and
record tokens/cost/latency in the case's own store (ADR-0002, ADR-0004)."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from typing import Any, overload

from google.genai.types import HttpRetryOptions
from pydantic import BaseModel, SecretStr
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
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

# A tool the model may call: a plain async function with typed args and a docstring.
ToolFunc = Callable[..., Awaitable[str]]


@overload
async def run_role[T: BaseModel](
    role: Role, *, case: Case, store: CaseStore, settings: Settings, prompt: Prompt,
    user_prompt: str, output_type: type[T], prompt_vars: dict[str, str] | None = None,
    job_id: str | None = None, session_id: str | None = None,
    check: Callable[[T], list[str]] | None = None, tools: Sequence[ToolFunc] = (),
) -> T: ...  # fmt: skip
@overload
async def run_role(
    role: Role, *, case: Case, store: CaseStore, settings: Settings, prompt: Prompt,
    user_prompt: str, output_type: type[str], prompt_vars: dict[str, str] | None = None,
    job_id: str | None = None, session_id: str | None = None,
    check: Callable[[str], list[str]] | None = None, tools: Sequence[ToolFunc] = (),
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
    check: Callable[[Any], list[str]] | None = None,
    tools: Sequence[ToolFunc] = (),
) -> BaseModel | str:
    """`check` returns problems with an output (e.g. citations not found in the text). The model
    gets ONE corrective retry with those problems; after that the output is accepted and callers
    flag what is still wrong (unverified citations) instead of failing the whole run."""
    rm = resolve(role, case, settings.model_profile, settings.models_config)
    structured = output_type is not str
    agent = Agent(
        build_chain(rm.models, settings),
        output_type=NativeOutput(output_type) if rm.native_output and structured else output_type,
        instructions=prompt.render(**(prompt_vars or {})),
        model_settings=rm.settings,
        name=role,
        tools=list(tools),  # read-only functions bound to this case's store (case assistant)
    )
    if check is not None:

        @agent.output_validator
        def _validate(ctx: RunContext[object], output: BaseModel | str) -> BaseModel | str:
            problems = check(output)
            if problems and ctx.retry == 0:
                raise ModelRetry("Fix these problems:\n- " + "\n- ".join(problems[:15]))
            return output

    attributes = {
        "case.id": case.id,
        "llm.role": role,
        "llm.profile": rm.profile,
        "llm.model_name": rm.primary,
        "prompt.name": prompt.name,
        "prompt.version": prompt.version,
        "job.id": job_id or "",
        "session.id": session_id or "",
    }
    with tracer.start_as_current_span(f"role.{role}", attributes=attributes) as span:
        t0 = time.perf_counter()
        result = await _run_with_transport_retry(agent, user_prompt)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        usage = result.usage
        used = _answering_model(rm.models, result.response.model_name)
        cost = _cost(usage.cost, used)
        span.set_attribute("llm.model_used", used)
        span.set_attribute("llm.cost_usd", cost if cost is not None else -1)
        trace_id = format(span.get_span_context().trace_id, "032x")

    store.record_llm_call(
        LLMCall(
            role=role,
            model=used,
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


TRANSPORT_ATTEMPTS = 3


async def _run_with_transport_retry[T](agent: Agent[Any, T], user_prompt: str) -> AgentRunResult[T]:
    """Retry calls that never got an HTTP response (connect/read timeouts, dropped connections).
    HTTP errors are not retried here: the provider SDKs already retried 429/5xx with backoff."""
    for attempt in range(TRANSPORT_ATTEMPTS):
        try:
            return await agent.run(user_prompt)
        except ModelAPIError as exc:
            if isinstance(exc, ModelHTTPError) or attempt == TRANSPORT_ATTEMPTS - 1:
                raise
            await asyncio.sleep(2 * 2**attempt)
    raise AssertionError("unreachable")


# Transient provider errors (rate limit, "model overloaded") are retried with backoff by the
# Gemini SDK itself; the OpenAI and Anthropic SDKs retry these by default.
GEMINI_RETRY = HttpRetryOptions(
    attempts=4, initial_delay=2, max_delay=30, http_status_codes=[429, 500, 502, 503, 504]
)


def build_chain(models: tuple[str, ...], settings: Settings) -> Model | str:
    """One model, or a FallbackModel that moves to the next one if a call still fails."""
    built = [build_model(m, settings) for m in models]
    return built[0] if len(built) == 1 else FallbackModel(*built)


def _answering_model(models: tuple[str, ...], response_model: str | None) -> str:
    """Which configured model produced the response (matters for cost when a fallback ran)."""
    # Providers may append a version ("gemini-3.5-flash-001"), so match by prefix, longest first:
    # "gemini-3.5-flash-lite" must not be credited to "gemini-3.5-flash".
    for m in sorted(models, key=len, reverse=True):
        if response_model and response_model.startswith(m.partition(":")[2] or m):
            return m
    return models[0]


def build_model(model: str, settings: Settings) -> Model | str:
    """Give each provider its URL/key from Settings (i.e. from .env). A bare model string would
    make pydantic-ai read only process env vars, so keys in .env would be silently ignored."""
    provider_name, _, name = model.partition(":")
    match provider_name:
        case "ollama":
            return OllamaModel(name, provider=OllamaProvider(base_url=settings.ollama_base_url))
        case "google":
            key = _key(settings.gemini_api_key)
            return GoogleModel(
                name, provider=GoogleProvider(api_key=key, retry_options=GEMINI_RETRY)
            )
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
