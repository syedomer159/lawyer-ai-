# ADR-0004: OpenTelemetry traces to Arize Phoenix

- Status: accepted
- Date: 2026-10-20

## Context
We need to see each agent call (prompt, output, tokens, latency) per case and job, locally and at no cost.

## Decision
- Pydantic AI's built-in OpenTelemetry instrumentation exports over OTLP/HTTP to a self-hosted Phoenix container (`:6006/v1/traces`). No vendor SDK is needed. The Stage 0 spike confirmed spans arrive with `gen_ai.usage.*` token counts.
- Spans carry `case_id`, `role`, `job_id` and the prompt version.
- `TRACE_CONTENT=false` (deployment) sets `include_content=False`: tokens and latency are kept, confidential text is dropped.
- Token usage and cost are also stored per job and session in the case DB, so the UI can show cost without Phoenix.

## Stage 3 implementation notes
- Traces go to the Phoenix project `lawyer-ai` (resource attribute `openinference.project.name`). Each LLM call is `role.<role>` (case.id, llm.role, llm.profile, llm.model_name, prompt.name/version, job.id, session.id, llm.cost_usd) → `invoke_agent` → `chat <model>` with token counts. Embedding calls are instrumented too.
- Every call also gets an `llm_calls` row in the case DB (tokens, cost, latency, prompt version, **trace_id**), so any number in the UI can be followed to its Phoenix trace. `GET /api/cases/{id}/usage` sums them by role and model.
- Cost is `None` (unknown) when a provider can't price a call, and 0 only for local/offline models.
- `TRACING=false` turns export off (tests set it). Tests capture spans in memory to assert attributes.
- agent-lab (the workshop's suggested reference) holds only a README so far, so nothing was adopted from it.

## Consequences
- Moving to Langfuse or another OTLP backend is an endpoint change.
- Local traces contain case text, which is acceptable because Phoenix runs on the same machine.

## Alternatives considered
- Langfuse self-hosted: needs Postgres, ClickHouse, Redis and S3. Too heavy for an MVP.
- Logfire: hosted SaaS, which sends case text off the machine.
