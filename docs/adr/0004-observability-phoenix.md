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

## Consequences
- Moving to Langfuse or another OTLP backend is an endpoint change.
- Local traces contain case text, which is acceptable because Phoenix runs on the same machine.

## Alternatives considered
- Langfuse self-hosted: needs Postgres, ClickHouse, Redis and S3. Too heavy for an MVP.
- Logfire: hosted SaaS, which sends case text off the machine.
