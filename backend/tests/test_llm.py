from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.ollama import OllamaModel

from app.config import REPO_ROOT
from app.contracts.cases import Case
from app.llm.prompts import Prompt, load_prompt
from app.llm.registry import load_models_config, resolve
from app.llm.runner import (
    _answering_model,
    _run_with_transport_retry,
    build_chain,
    build_model,
    run_role,
)
from app.store.case_store import CaseStore
from tests.conftest import TestSettings, create_case

REAL_CONFIG = REPO_ROOT / "config" / "models.yaml"
_exporter = InMemorySpanExporter()


@pytest.fixture(scope="session", autouse=True)
def _span_capture() -> None:
    # The global tracer provider can be set once per process: capture spans in memory.
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_exporter))
    trace.set_tracer_provider(provider)


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    _exporter.clear()
    yield _exporter


def make_case(local_only: bool = False) -> Case:
    return Case(
        id="a" * 32,
        title="t",
        client="c",
        user_side="defence",
        charges=[],
        local_only=local_only,
        embed_model="nomic-embed-text",
        created_at="now",
    )


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(body, encoding="utf-8")
    return path


TEST_CONFIG = """
profiles:
  local: {default: test}
  hybrid: {default: test}
  cloud: {default: test}
"""


# --- routing --------------------------------------------------------------------------------


def test_roles_fall_back_to_profile_default() -> None:
    case = make_case()
    assert resolve("judge", case, "cloud", REAL_CONFIG).primary == "google:gemini-3.5-flash"
    assert resolve("witness", case, "cloud", REAL_CONFIG).models == (
        "google:gemini-3.5-flash-lite",
    )


def test_local_models_get_reasoning_off_and_native_output() -> None:
    rm = resolve("witness", make_case(), "hybrid", REAL_CONFIG)
    assert rm.primary.startswith("ollama:")
    assert rm.native_output
    assert rm.settings.get("openai_reasoning_effort") == "none"
    assert not resolve("judge", make_case(), "hybrid", REAL_CONFIG).native_output


def test_local_only_case_never_uses_a_cloud_model() -> None:
    case = make_case(local_only=True)
    for role in ("judge", "analyst", "witness", "assistant"):
        rm = resolve(role, case, "cloud", REAL_CONFIG)
        assert rm.profile == "local" and all(m.startswith("ollama:") for m in rm.models), role


def test_config_rejects_unknown_role(tmp_path: Path) -> None:
    path = write_config(tmp_path, TEST_CONFIG + "  extra: {default: test, jduge: test}\n")
    with pytest.raises(ValidationError):
        load_models_config(path)


def test_config_rejects_cloud_model_in_local_profile(tmp_path: Path) -> None:
    body = TEST_CONFIG.replace("local: {default: test}", "local: {default: test, judge: google:x}")
    with pytest.raises(ValueError, match="non-Ollama"):
        load_models_config(write_config(tmp_path, body))


def test_prompt_version_tracks_text_and_render_requires_values() -> None:
    a, b = Prompt("p", "Hello $name", "v1"), load_prompt("smoke")
    assert a.render(name="court") == "Hello court"
    with pytest.raises(KeyError):
        a.render()
    assert len(b.version) == 8


# --- runner ---------------------------------------------------------------------------------


class Claims(BaseModel):
    claims: list[str]


def _spans_named(spans: InMemorySpanExporter, name: str) -> list[ReadableSpan]:
    return [s for s in spans.get_finished_spans() if s.name == name]


@pytest.mark.anyio
async def test_run_role_traces_and_records_usage(
    tmp_path: Path, spans: InMemorySpanExporter
) -> None:
    settings = TestSettings(data_dir=tmp_path, models_config=write_config(tmp_path, TEST_CONFIG))
    store = CaseStore(tmp_path / "case")
    prompt = load_prompt("smoke")
    try:
        out = await run_role(
            "extractor", case=make_case(), store=store, settings=settings, prompt=prompt,
            user_prompt="<document>x</document>", output_type=Claims, job_id="job-1",
        )  # fmt: skip
        assert isinstance(out, Claims)

        (span,) = _spans_named(spans, "role.extractor")
        attrs = span.attributes or {}
        assert attrs["case.id"] == "a" * 32
        assert attrs["prompt.version"] == prompt.version
        assert attrs["job.id"] == "job-1"

        summary = store.usage_summary()
        assert summary.calls == 1 and summary.by_role[0].role == "extractor"
        assert summary.cost_usd == 0  # the offline test model is free, not "unknown"
        row = store.db.execute("SELECT trace_id, prompt_version FROM llm_calls").fetchone()
        assert span.context is not None
        assert row["trace_id"] == format(span.context.trace_id, "032x")  # DB row -> Phoenix trace
        assert row["prompt_version"] == prompt.version
    finally:
        store.close()


@pytest.mark.anyio
async def test_run_role_local_profile_uses_native_output(tmp_path: Path) -> None:
    settings = TestSettings(data_dir=tmp_path, models_config=write_config(tmp_path, TEST_CONFIG))
    store = CaseStore(tmp_path / "case")
    try:
        out = await run_role(
            "witness", case=make_case(local_only=True), store=store, settings=settings,
            prompt=load_prompt("smoke"), user_prompt="q", output_type=Claims,
        )  # fmt: skip
        assert isinstance(out, Claims)
    finally:
        store.close()


def test_usage_endpoint_starts_empty(client: TestClient) -> None:
    case_id = create_case(client)
    usage = client.get(f"/api/cases/{case_id}/usage").json()
    assert usage == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                     "by_role": []}  # fmt: skip


def test_ollama_models_use_configured_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    model = build_model(
        "ollama:qwen3.5:4b", TestSettings(data_dir=tmp_path, ollama_base_url="http://x:1/v1")
    )
    assert isinstance(model, OllamaModel)
    assert model.model_name == "qwen3.5:4b"
    assert model.base_url.startswith("http://x:1/v1")


def test_cloud_keys_come_from_settings_not_process_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    s = TestSettings(data_dir=tmp_path, gemini_api_key=SecretStr("from-dotenv"))
    assert isinstance(build_model("google:gemini-3.5-flash-lite", s), GoogleModel)
    assert build_model("test", s) == "test"


def test_fallback_chains(tmp_path: Path) -> None:
    rm = resolve("judge", make_case(), "cloud", REAL_CONFIG)
    assert rm.models == ("google:gemini-3.5-flash", "google:gemini-3.5-flash-lite")
    s = TestSettings(data_dir=tmp_path, gemini_api_key=SecretStr("k"))
    assert isinstance(build_chain(rm.models, s), FallbackModel)
    assert _answering_model(rm.models, "gemini-3.5-flash-lite") == "google:gemini-3.5-flash-lite"
    assert _answering_model(rm.models, None) == "google:gemini-3.5-flash"


def test_config_rejects_chain_mixing_local_and_cloud(tmp_path: Path) -> None:
    body = TEST_CONFIG.replace("cloud: {default: test}", "cloud: {default: [ollama:x, google:y]}")
    with pytest.raises(ValueError, match="mixes local and cloud"):
        load_models_config(write_config(tmp_path, body))


def _flaky_agent(failures: int, error: Exception) -> tuple[Agent[None, str], list[int]]:
    """A real Agent whose model fails like a dropped connection for its first calls."""
    calls: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        if len(calls) <= failures:
            raise error
        return ModelResponse(parts=[TextPart("ok")])

    return Agent(FunctionModel(respond)), calls


@pytest.mark.anyio
async def test_transport_errors_are_retried_but_http_errors_are_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_sleep(_: float) -> None: ...

    monkeypatch.setattr("app.llm.runner.asyncio.sleep", no_sleep)
    agent, calls = _flaky_agent(2, ModelAPIError("m", "ConnectTimeout"))
    assert (await _run_with_transport_retry(agent, "p")).output == "ok"
    assert len(calls) == 3

    agent, calls = _flaky_agent(1, ModelHTTPError(503, "m", "overloaded"))
    with pytest.raises(ModelHTTPError):
        await _run_with_transport_retry(agent, "p")
    assert len(calls) == 1
