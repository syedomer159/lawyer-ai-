# ADR-0003: Analysis is a workflow, the trial is a state machine, and only the assistant is a free agent

- Status: accepted
- Date: 2026-10-20

## Context
"Multi-agent" can mean an LLM supervisor that decides everything, which makes the system expensive, unpredictable and hard to evaluate. Court-simulation research (AgentCourt, AgentsCourt, civil-court simulation) uses fixed procedural stages. Contradiction-detection research (LegalWiz) found a pure LLM judge hallucinates and is overconfident.

## Decision
- **Analysis** is a code-ordered workflow of single-purpose typed agents: extractor → aspect grouper → contradiction analyst (one call per aspect, not pairwise N²) → gap analyst → argument builder → deterministic citation validator.
- **Mock trial** has phases (charge, openings, examination-in-chief, cross, re-examination, final arguments, judgment, debrief) in a Python state machine. Role agents (judge, opposing counsel, IO, witnesses) only produce their own turn. Each agent sees only its own knowledge: a witness sees only their own statement, and the judge sees only the transcript.
- **Case assistant** is the only open-ended tool-calling agent, and its tools are read-only.

## Stage 4 implementation notes
- `app/agents/analysis.py` runs: extractor (per document) → aspect grouper (1 call) → contradiction analyst (1 call per aspect with claims from at least 2 documents) → assessment (elements of each charge + procedure checklist + evidence that hurts us, 1 call) → argument builder (1 call per issue, max 12) → one-transaction save. About 30 calls per case. It runs as a background job with progress, and as ONE Phoenix trace (`analysis` span with every role call nested).
- Grouping claims for comparison: first version asked one LLM call to cluster ~100 claims; Phoenix traces showed it silently dropped whole topics (speed, side of impact, distance), differently each run (case 2 contradiction recall 0.33 → 0.17). Now the LLM only names the 8-20 factual questions, and code assigns every claim to its 2 closest questions by local embedding similarity, so no claim can be dropped. Claims may sit in several aspects; duplicate conflicts are merged by claim set.
- Grounding: claims whose quote is not in the cited chunk are **dropped**. Other citations get one corrective retry via pydantic-ai's `ModelRetry` (`run_role(check=...)`), then are kept but flagged `verified: false`, shown amber in the UI and never as fact.
- Domain knowledge lives in `app/legal_refs/*.yaml` (elements per BNS section, procedure checklist), each marked verified or not, rather than in model memory.
- Resilience: Gemini calls retry 429/5xx with backoff (SDK `retry_options`). Heavy roles use a fallback chain (Flash → Flash Lite) via `FallbackModel`, and the usage row records the model that actually answered. The first real eval run hit Gemini 503 "high demand", which is how this was found (via the error span in Phoenix).

## Consequences
- Each step can be tested and evaluated on its own, and cost per case is predictable.
- Changing trial procedure means changing code, not prompts.

## Alternatives considered
- LLM supervisor/orchestrator: more calls, nondeterministic turn order, harder evals.
- One big agent with all tools: no knowledge scoping, so a witness could "know" police documents.
