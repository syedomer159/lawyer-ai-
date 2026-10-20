# ADR-0003: Analysis is a workflow, the trial is a state machine, and only the assistant is a free agent

- Status: accepted
- Date: 2026-10-20

## Context
"Multi-agent" can mean an LLM supervisor that decides everything, which makes the system expensive, unpredictable and hard to evaluate. Court-simulation research (AgentCourt, AgentsCourt, civil-court simulation) uses fixed procedural stages. Contradiction-detection research (LegalWiz) found a pure LLM judge hallucinates and is overconfident.

## Decision
- **Analysis** is a code-ordered workflow of single-purpose typed agents: extractor → aspect grouper → contradiction analyst (one call per aspect, not pairwise N²) → gap analyst → argument builder → deterministic citation validator.
- **Mock trial** has phases (charge, openings, examination-in-chief, cross, re-examination, final arguments, judgment, debrief) in a Python state machine. Role agents (judge, opposing counsel, IO, witnesses) only produce their own turn. Each agent sees only its own knowledge: a witness sees only their own statement, and the judge sees only the transcript.
- **Case assistant** is the only open-ended tool-calling agent, and its tools are read-only.

## Consequences
- Each step can be tested and evaluated on its own, and cost per case is predictable.
- Changing trial procedure means changing code, not prompts.

## Alternatives considered
- LLM supervisor/orchestrator: more calls, nondeterministic turn order, harder evals.
- One big agent with all tools: no knowledge scoping, so a witness could "know" police documents.
