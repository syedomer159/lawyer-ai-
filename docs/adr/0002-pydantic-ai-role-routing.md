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

## Consequences
- Switching provider is a config change. Quality and cost differences are measured by evals per profile.
- We depend on a fast-moving library (v2.x), so it is pinned in `uv.lock`.

## Alternatives considered
- LangGraph: durable graphs and checkpointing are more than we need, since our flows are a fixed workflow and a code state machine.
- LiteLLM proxy: Pydantic AI already handles providers, so the proxy would be one more service.
- CrewAI: less control over typed outputs and testing.
