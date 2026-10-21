from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.llm import keys
from app.llm.keys import KeyPool, NoGeminiKey, classify, fingerprint, prune_env
from app.llm.runner import _run_rotating_keys

K1, K2, K3 = ("AIza" + c * 35 for c in "abc")
QUOTA = {
    "error": {
        "code": 429,
        "status": "RESOURCE_EXHAUSTED",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1434s"}],
    }
}
INVALID = {
    "error": {
        "code": 400,
        "message": "API key expired.",
        "status": "INVALID_ARGUMENT",
        "details": [{"reason": "API_KEY_INVALID"}],
    }
}


def test_classify_quota_invalid_and_other() -> None:
    kind, reset = classify(ModelHTTPError(429, "m", QUOTA))
    assert kind == "quota" and reset is not None
    assert timedelta(seconds=1400) < reset - keys._now() < timedelta(seconds=1440)
    assert classify(ModelHTTPError(400, "m", INVALID)) == ("invalid", None)
    assert classify(ModelHTTPError(500, "m", {"error": "boom"})) == (None, None)


@pytest.mark.anyio
async def test_pool_rotates_and_parks_bad_keys(tmp_path: Path) -> None:
    pool = KeyPool([K1, K2, K3], tmp_path / "status.json")
    assert [await pool.acquire("flash") for _ in range(4)] == [K1, K2, K3, K1]

    pool.report(K2, "flash", ModelHTTPError(429, "flash", QUOTA))
    pool.report(K3, "flash", ModelHTTPError(400, "flash", INVALID))
    assert {await pool.acquire("flash") for _ in range(3)} == {K1}  # K2 parked, K3 invalid
    assert await pool.acquire("lite") in {K1, K2}  # quota is per model; invalid is per key

    saved = (tmp_path / "status.json").read_text()
    assert fingerprint(K2) in saved and K2 not in saved  # never write the key itself

    pool.report(K1, "flash", ModelHTTPError(429, "flash", QUOTA))
    with pytest.raises(NoGeminiKey, match="out of quota"):
        await pool.acquire("flash")


@pytest.mark.anyio
async def test_run_moves_to_next_key_when_one_is_out_of_quota(tmp_path: Path) -> None:
    pool = KeyPool([K1, K2], tmp_path / "status.json")

    async def make_agent(leases: dict[str, str]) -> Agent[object, BaseModel | str]:
        leases.clear()
        leases["gemini-x"] = await pool.acquire("gemini-x")
        key = leases["gemini-x"]

        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if key == K1:
                raise ModelHTTPError(429, "gemini-x", QUOTA)
            return ModelResponse(parts=[TextPart("ok")])

        return Agent(FunctionModel(respond), output_type=str)

    result = await _run_rotating_keys(make_agent, pool, "hi")
    assert result.output == "ok"
    assert "gemini-x" in pool.status[fingerprint(K1)].exhausted_until


def test_prune_env_drops_only_invalid_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"MODEL_PROFILE=cloud\nGEMINI_API_KEY={K1}\n# GEMINI_API_KEY={K2}\n# {K3}\n")
    pool = KeyPool([K1, K2, K3], tmp_path / "status.json")
    pool.report(K3, "m", ModelHTTPError(400, "m", INVALID))
    pool.report(K2, "m", ModelHTTPError(429, "m", QUOTA))  # out of quota is kept: it resets

    assert prune_env(env, pool) == (2, 1)
    text = env.read_text()
    assert f"GEMINI_API_KEYS={K1},{K2}" in text and K3 not in text and "MODEL_PROFILE=cloud" in text
    assert K3 in (tmp_path / ".env.bak").read_text()
