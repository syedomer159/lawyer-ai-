# ADR-0002: Pydantic AI, with models chosen per role and profile

- Status: accepted
- Date: 2026-10-20

## Context
The app must run on local Ollama (free, private, slow on this CPU-only laptop) or cheap cloud APIs, and a judge or analyst may need a stronger model than a witness. Agents need typed outputs (claims, conflicts, citations) and tests that don't call an LLM.

## Decision
- Pydantic AI (`pydantic-ai-slim[openai,anthropic,google]`) for all agents. Models are plain strings (`ollama:qwen3.5:4b`, `anthropic:...`).
- `config/models.yaml` maps role → model for each profile (`local`, `hybrid` default, `cloud`). Agents ask the registry for their role's model and never hardcode one. A case with `local_only` is forced onto the `local` profile.
- Embeddings are always local `nomic-embed-text` (768-dim) through Ollama's OpenAI-compatible API. The embedding model is pinned per case.
- Tests use `TestModel`/`FunctionModel`.

## Spike results (Stage 0)
- `ollama:qwen3.5:4b` with `NativeOutput` returned a valid typed `Claims` object with verbatim quotes.
- qwen3.5 is a thinking model. With default settings, one paragraph ran for more than 10 minutes without finishing. With `openai_reasoning_effort: "none"` it took 94 s for 367 output tokens (about 4 tok/s on CPU). So `local` is fine for tests and short role-play, but too slow for whole-case analysis, which makes `hybrid` the default.
- Ollama context defaults to 4096 tokens. Set `OLLAMA_CONTEXT_LENGTH` if local roles need more.
- Cloud swap is just the model string: `google:gemini-3.5-flash-lite` did the same extraction in 6.4 s (257 in / 356 out tokens, about $0.001) and named the speaker correctly where the local model wrote "witness". `RunUsage.cost` reports cost directly, so we keep no price table. The prefix is `google:`, not `google-gla:`.

## Stage 3 implementation notes
- Default profile changed to **`cloud`** (Flash Lite for high-volume roles, Flash for analyst/argument/judge/debrief). On this CPU-only laptop a local call took 94-218 s, so `hybrid` (witness and IO on Ollama) only makes sense on a machine with a GPU. `local` stays fully offline and is forced for `local_only` cases.
- Every agent calls `app/llm/runner.py:run_role(role, ...)`, which is the only place a model is chosen, traced and billed.
- `build_model` passes the Ollama URL and provider API keys from `Settings` explicitly. A bare model string makes pydantic-ai read only process env vars, so keys in `.env` were silently ignored and `ollama:` failed without `OLLAMA_BASE_URL`.
- `config/models.yaml` is validated on load: unknown roles or profiles fail, and the `local` profile may contain only offline models (`ollama:*`, or `test` in tests).
- Tests use the offline `test` model via a test `models.yaml`, with no model overrides.

## Gemini key rotation
- `GEMINI_API_KEYS` (comma-separated) feeds a key pool (`app/llm/keys.py`). `run_role` leases a key per Gemini model per call; on a key-caused failure it marks the key and retries with the next one: invalid/expired (400/401/403 with an API-key reason) → disabled; 429 RESOURCE_EXHAUSTED → parked for that model until Google's RetryInfo delay (else midnight Pacific for daily quotas, else 60 s). If every key is parked but one resets within 60 s, it waits; otherwise it fails with `NoGeminiKey` naming the reset time.
- 429 is no longer retried inside the Gemini SDK (pointless for a daily quota); 5xx still is.
- Status is persisted in `data/gemini_keys.json` by fingerprint (hash + last 4 chars), never the key.
- `python -m app.llm.keys --check [--all-in-env] [--prune-env]` tests each key and can rewrite `.env` keeping only valid keys (backup `.env.bak`).
- Caveat: quotas are per Google Cloud project, so keys from one project share a quota; multiplying free-tier quota across projects may breach Google's terms. Rotation is for failover between keys you are entitled to use.

## Consequences
- Switching provider is a config change. Quality and cost differences are measured by evals per profile.
- We depend on a fast-moving library (v2.x), so it is pinned in `uv.lock`.

## Alternatives considered
- LangGraph: durable graphs and checkpointing are more than we need, since our flows are a fixed workflow and a code state machine.
- LiteLLM proxy: Pydantic AI already handles providers, so the proxy would be one more service.
- CrewAI: less control over typed outputs and testing.
