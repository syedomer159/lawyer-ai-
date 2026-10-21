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

## Stage 5 implementation notes
- `app/agents/trial/phases.py` is a pure state machine: opening → (examination-in-chief → cross-examination) per prosecution witness → final arguments → judge's observations → closed. Prosecution examines in chief, defence cross-examines; the AI counsel plays whichever side the lawyer is not on.
- `orchestrator.py` runs the AI side until the lawyer must act (AI examinations are 2 questions per witness to keep a demo short and cheap). Lawyer questions first go to an objection check by AI counsel; if it objects, the judge rules, and a sustained objection strikes the question. The lawyer can object to AI counsel; a sustained objection strikes that turn and the answer it drew.
- Knowledge scoping (`roles.py`): a witness/IO gets only their own documents (documents where the analysis found them speaking, else documents naming them in full) and their own examination; the judge gets the transcript only; AI counsel gets the analysis brief + transcript. Every call carries `session.id`.
- Witness and objection turns run synchronously inside the request (a few model calls, ~5-30 s on cloud). A streaming UI is a later improvement.

## Consequences
- Each step can be tested and evaluated on its own, and cost per case is predictable.
- Changing trial procedure means changing code, not prompts.

## Alternatives considered
- LLM supervisor/orchestrator: more calls, nondeterministic turn order, harder evals.
- One big agent with all tools: no knowledge scoping, so a witness could "know" police documents.
