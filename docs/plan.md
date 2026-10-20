# Lawyer Case-Prep AI — MVP Plan (India BNS/BNSS)

## Context
AI-architect workshop project. A lawyer uploads all material for ONE case (text notes, PDFs, images), and the system:
1. Runs a **mock trial** with role-playing agents (judge, public prosecutor / opposing counsel, investigating officer, witnesses).
2. **Finds conflicting testimony** and evidence contradictions, weak/missing evidence, and what helps/hurts the client.
3. **Prepares arguments** and counter-arguments per issue, every claim cited back to the exact page/image region.
4. Keeps every case **isolated** (confidential material).

Constraints from you: not over-engineered, multi-agent done sensibly, evals + observability, runs locally first then deployable, cheap, Ollama **and** cloud APIs switchable (heavier model allowed for judge etc.), 2 synthetic sample cases with planted issues, Indian procedure.

Project folder `lawyer ai/` is **empty, no git, no CLAUDE.md** → Stage 0 uses the `project-setup` skill.
Machine: 16 GB RAM, Intel UHD 620 (no GPU), Ollama has `qwen3.5:4b`, `qwen2.5:1.5b`, `nomic-embed-text`; Python 3.13, Node 22, uv, Docker present.
→ Local models are CPU-only: fine for embeddings, extraction and witness role-play; judge / contradiction analyst / argument builder should default to a cloud model in the `hybrid` profile.

## What research says (and what we take from it)
- Court-sim research ([AgentCourt](https://arxiv.org/abs/2408.08089v2), [AgentsCourt](https://www.themoonlight.io/de/review/agentscourt-building-judicial-decision-making-agents-with-court-debate-simulation-and-legal-knowledge-augmentation), [Civil Court Simulation](https://arxiv.org/pdf/2606.09632)) all use **fixed procedural stages** with role agents, and the civil paper found staging "claims → evidence → disputed issues" before judging is needed. Hackathon demos (LeetCourt, ACTS) use a code-driven turn controller. → **Phases are a code state machine; agents only speak.** No LLM "supervisor" (cheaper, predictable, testable).
- Contradiction detection ([LegalWiz, NeurIPS'25](https://arxiv.org/pdf/2510.03418)): pure LLM-judge suffers hallucination/overconfidence; structured + verified pipeline works better. → **Extract structured claims → group by aspect → LLM compares only within a group → deterministic citation check.** Avoids N² comparisons.
- Isolation ([Harvey on ethical walls](https://www.harvey.ai/blog/long-horizon-agents-and-ethical-walls), [BBD](https://bbdsoftware.com/case-studies/leveraging-ai-for-legal-analysis/)): matter = hard boundary, not a metadata filter; fail closed. → **One SQLite file + one folder per case.**
- Agent framework ([Pydantic AI vs LangGraph](https://pydantic.dev/docs/ai/comparisons/vs-langchain-langgraph/)): for typed outputs + simple delegation, Pydantic AI is lighter; LangGraph only if we need durable graphs. → **Pydantic AI** (model-agnostic: Ollama, Anthropic, OpenAI, Gemini; built-in `TestModel` for LLM-free tests; OpenTelemetry built in).
- Observability ([Langfuse vs Phoenix](https://langfuse.com/compare/arize-phoenix)): Phoenix = one process, OTel-native; Langfuse self-host needs Postgres+ClickHouse+Redis+S3. → **Arize Phoenix** (local container), swap OTLP endpoint later if needed.
- PDFs ([PyMuPDF4LLM](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm)): fast, gives per-block bounding boxes, no built-in OCR. → **PyMuPDF** for text/bboxes/page rendering + **RapidOCR** (pip-only ONNX, Windows-friendly, returns boxes) for scanned pages/images. Photos with no text: optional cloud vision caption.
- Evals ([promptfoo vs deepeval](https://qaskills.sh/blog/promptfoo-vs-deepeval-vs-ragas-2026)): our metrics are domain-specific (contradiction recall vs answer key, citation validity). → **Small pytest-style eval runner + answer keys**, LLM-as-judge only for soft rubrics. No eval framework dependency.

## Architecture (one picture in words)
```
React UI ──(typed client generated from OpenAPI)──► FastAPI
                                                     │
          ┌──────────── per-request CaseContext(case_id) ────────────┐
          │  CaseStore = data/cases/<id>/case.db + files/  (only this │
          │  case is ever opened; no global index, no shared memory)  │
          └───────────────────────────────────────────────────────────┘
 Ingest (deterministic): parse → OCR → chunk(SourceRef) → embed → FTS5
 Analysis WORKFLOW (code-ordered agents): Extractor → Aspect grouper →
   Contradiction analyst → Gap analyst → Argument builder → Citation validator
 Mock trial: Phase state machine (code) → Judge / Opposing counsel / IO /
   Witness agents (each with its OWN knowledge scope) → Debrief coach
 Case assistant: one tool-using agent (search, conflicts, timeline, arguments)
 LLM registry: role → model per profile (local | hybrid | cloud), case.local_only
 Observability: OTel → Phoenix; token+cost per job/session saved in case DB
```
Two kinds of "agentic": **workflow** (analysis — fixed order, typed outputs, cheap, evaluable) and **role agents** (trial — conversational). Only the case assistant is a free tool-calling agent. This is the main design message for the workshop.

### Key design decisions (each becomes a short ADR in `docs/adr/`)
1. **Per-case SQLite + folder isolation.** `registry.db` holds case list only. Retrieval = SQLite FTS5 (BM25) + numpy cosine over that case's embeddings (a case is hundreds–few thousand chunks; no vector DB needed), fused with RRF. Delete case = delete folder. Isolation test: query case A can never return case B content.
2. **Citations are data, not prose.** Every chunk has `SourceRef{doc_id, page, bbox, chunk_id}`. Agents must return `citations: [{chunk_id, quote}]`; a deterministic validator checks the chunk exists in this case and the quote appears in it (fuzzy ≥ 0.9). Fails → one retry → else marked `unverified` in UI. Never trust LLM citations unchecked.
3. **Role → model routing** in `config/models.yaml` with profiles `local`, `hybrid` (default), `cloud`. Roles: `extractor, analyst, argument, judge, opposing_counsel, io, witness, assistant, debrief, vision, eval_judge`, plus embeddings (always local `nomic-embed-text`; embed model pinned per case). Per-case `local_only` flag forces the `local` profile (confidential matters never leave the machine).
4. **Knowledge scoping in the trial.** Witness agent sees only its own statement(s) (whole text in system prompt — small, cache-friendly) and must say "I don't recall" beyond it. IO sees police documents. Opposing counsel sees case summary + analysis + search tool. Judge sees procedure rules + transcript only (decides on what is presented, like a real court).
5. **Prompt-injection hygiene.** Case text is wrapped as quoted data; all agent tools are read-only and case-scoped.
6. **Trace content toggle.** `TRACE_CONTENT=true` locally; `false` in deployment (Phoenix gets spans, tokens, latency, case_id — not confidential text).

## Repo layout
```
lawyer-ai/
  CLAUDE.md  README.md  .env.example  docker-compose.yml
  docs/adr/0001-case-isolation.md ... 
  config/models.yaml
  backend/                      (uv, FastAPI, Pydantic AI)
    app/main.py config.py observability.py
    app/contracts/              Pydantic request/response models (the single API contract)
    app/api/                    cases.py documents.py analysis.py trial.py assistant.py
    app/store/                  registry.py case_store.py (schema + migrations) files.py
    app/ingest/                 pdf.py image_ocr.py text.py chunk.py embed.py
    app/retrieval/search.py     FTS5 + cosine + RRF
    app/llm/                    registry.py (role→model), usage.py (tokens/cost)
    app/prompts/*.md            one prompt file per role
    app/agents/                 extractor.py contradictions.py gaps.py arguments.py assistant.py debrief.py
    app/agents/trial/           phases.py (state machine) roles.py orchestrator.py
    app/citations.py            validator
    app/legal_refs/*.yaml       small curated element checklists (BNS 303/309/106/281 + procedural checks)
    tests/
  frontend/                     Vite + React + TS + Tailwind + TanStack Query + openapi-fetch
  samples/generate.py  samples/case1_*/  samples/case2_*/  (files + answer_key.yaml + trial_script.yaml)
  evals/run.py metrics.py reports/
```

## Data model (per-case `case.db`)
`documents(id, filename, kind[pdf|image|text], sha256, n_pages, status)` · `pages(doc_id, page_no, image_path, text, ocr_conf)` · `chunks(id, doc_id, page_no, bbox_json, text, embedding BLOB)` + `chunks_fts` · `parties(id, name, role[accused|complainant|witness|io|doctor|panch|other], doc_ids)` · `claims(id, party_id, aspect, statement, time, place, chunk_id, quote)` · `conflicts(id, claim_a, claim_b, type, severity, explanation, effect[helps|hurts], status[open|dismissed])` · `gaps(id, element, status[supported|weak|missing], explanation, citations)` · `issues(id, title, our_argument, opposing_argument, rebuttal, cross_questions, citations)` · `trial_sessions(id, user_side, phase, witness_queue, summary)` · `trial_turns(id, session_id, speaker_role, party_id, text, citations, objection)` · `jobs(id, kind, status, progress, error, tokens_in, tokens_out, cost)`.
`registry.db`: `cases(id, title, client, user_side[defence|prosecution], charges, local_only, embed_model, created_at)`.

## Stages (each stage = backend + contract + UI tab + tests + evals, so nothing is left unconnected)

### Stage 0 — Foundation & risk spikes
- `project-setup` skill: git init, CLAUDE.md, structure above, ruff + pyright, eslint + tsc, pre-commit.
- OpenAPI → TS pipeline: `npm run gen:api` (openapi-typescript) so the frontend never hand-copies types.
- Spikes (throwaway, in `scripts/spikes/`) to kill risks before building:
  a. Pydantic AI + Ollama `qwen3.5:4b` returns a typed output on CPU; measure latency.
  b. Same agent on a cloud model via config string swap.
  c. RapidOCR reads a sample image with boxes on Windows.
  d. PyMuPDF block bboxes + page PNG render.
  e. One trace with tokens visible in Phoenix (`docker run arizephoenix/phoenix`).
- ADRs 0001–0005 written (isolation, Pydantic AI + routing, workflow-vs-agents, Phoenix, citations).
- **Exit:** `uv run pytest`, `ruff`, `pyright`, `npm run build`, `npm run lint` all green; spike notes recorded in ADRs.

### Stage 1 — Sample cases + answer keys (data before features)
`samples/generate.py` builds both cases reproducibly (reportlab/PyMuPDF for PDFs, Pillow for "scanned" images with skew/noise), so the ground truth text is known.
- **Case 1 – State v. Arjun Verma (robbery, BNS 309)**: FIR (text PDF), complainant's police statement, 2 eyewitness statements (one as scanned image-only PDF), IO seizure/recovery memo, arrest memo, MLC, CCTV still (image with timestamp overlay), municipal letter on streetlight, lawyer's client-interview notes (.txt). Planted: time-of-incident mismatch, jacket colour mismatch, "clear view" vs streetlight not working, CCTV timestamp vs FIR time, panch witness says not present at recovery, no TIP, 2-day unexplained FIR delay.
- **Case 2 – State v. Kavita Rao (death by negligence, BNS 106 + rash driving 281)**: FIR, 3 eyewitness statements, post-mortem report, mechanical inspection report, site-plan sketch (image), vehicle-damage photos, driver's licence record, notes. Planted: who was driving, vehicle colour, injury side vs claimed impact direction, site-plan distance vs witness position, speed estimate inconsistent with skid marks, missing CCTV request.
- Each case: `answer_key.yaml` (expected parties, ~7 contradictions with source refs, ~5 gaps, helps/hurts labels, 10 retrieval Q&A with expected page) and `trial_script.yaml` (a scripted lawyer cross-examination round + final argument lines for eval runs).
- Verify statute/section references once with a quick source check; legal_refs YAML marks anything uncertain.
- **Exit:** validator script checks every answer-key ref points to a real doc/page; files open correctly.

### Stage 2 — Core: cases, upload, ingest, retrieval, document viewer
- Backend: cases CRUD, upload (type/size checks, sha256 dedupe), ingest job (BackgroundTasks + `jobs` row): text PDF → PyMuPDF blocks; image/scanned page → RapidOCR; .txt → paragraphs; chunk with SourceRef; embed; FTS5. Page PNG endpoint.
- Frontend: Cases list/create (client, side, charges, local_only), Case workspace shell with tabs, Documents tab (upload, status, viewer with highlighted bbox).
- Tests: parsers, chunker, RRF, **isolation test**, API tests.
- Evals: OCR char-accuracy on generated images; retrieval recall@5 on gold Q&A.
- **Exit:** upload case1 in the UI → search returns the right page highlighted; eval report saved.

### Stage 3 — LLM layer + observability (shared by all agents)
- `llm/registry.py`: `get_model(role, case)` from `models.yaml` + profile + `local_only`. `usage.py`: tokens/cost per job/session from pydantic-ai's `RunUsage.cost` (built-in price table; no prices file to maintain).
- `observability.py`: OTel → Phoenix, spans tagged `case_id`, `role`, `job_id`; `TRACE_CONTENT` toggle.
- Prompt files loaded from `app/prompts/`, with version string recorded on each span.
- Default cloud models (Gemini, key in `.env`): `google:gemini-3.5-flash-lite` for high-volume roles (extractor, witness, IO, objection check, eval_judge) and `google:gemini-3.5-flash` for judge, contradiction analyst, argument builder. Use Flash Lite for dev/testing runs.
- Reference for the tracing/eval dashboard: `C:/Users/hp/Desktop/mfird workshop/agent-lab` (look at it when building Stage 3 and the Stage 7 eval report; don't copy it wholesale).
- **Exit:** smoke agent call per profile shows in Phoenix with tokens; usage row written; unit tests with `TestModel`.

### Stage 4 — Analysis workflow (Find conflicts + Prepare arguments)
Sub-steps, each its own agent file with a typed output model:
- 4a **Extractor** (per document): parties + claims `{speaker, aspect_hint, statement, time, place, chunk_id, quote}`.
- 4b **Aspect grouper**: one call proposes case aspects ("time of incident", "attacker clothing", "lighting"...), assigns claims.
- 4c **Contradiction analyst**: one call per aspect with ≥2 sources → conflicting pairs + type (testimony↔testimony, testimony↔document, testimony↔physical evidence) + severity + helps/hurts for the client side.
- 4d **Gap analyst**: maps evidence to each element of the charged offence and procedural checklist (from `legal_refs/*.yaml`) → supported / weak / missing.
- 4e **Argument builder**: per issue (high-severity conflicts + gaps): our argument, likely opposing argument, rebuttal, suggested cross-examination questions, citations.
- 4f **Citation validator** runs on every output; failures retried once then flagged.
- Frontend: Analysis tab (timeline, conflicts side-by-side with source snippets, gaps checklist, helps/hurts), Arguments tab (issue cards, citation chips open the doc viewer at the exact region, lawyer can dismiss/edit).
- Evals: contradiction precision/recall vs answer key (match by source refs, LLM-judge fallback for wording), gap recall, citation validity %, cost and latency per profile.
- **Exit:** both sample cases analysed end-to-end from the UI; eval report per profile (target on `hybrid`: contradiction recall ≥ 0.7, citation validity ≥ 0.95; `local` baseline recorded honestly).

### Stage 5 — Mock trial (multi-agent role-play)
- Session setup: user side (defence default), pick witnesses from extracted parties, demeanour per witness (cooperative / nervous / hostile).
- `phases.py` state machine (simplified sessions trial): `charge → prosecution opening → per witness [examination-in-chief → cross-examination → re-examination] → defence evidence (optional) → final arguments → judge observations → debrief`. Symmetric "examining side / cross side" so user can also play prosecution. "Skip to phase" to save time/cost.
- Turn loop: user message → (cheap) opposing-counsel `ObjectionDecision` → judge rules if objected → addressed agent replies → turn stored with citations. User can also object; judge rules with reason.
- Memory: last N turns + rolling summary per session (keeps context and cost bounded).
- **Debrief coach**: scores the lawyer's round, lists contradictions from Stage 4 they could have used but didn't, suggests better questions.
- Frontend: Courtroom tab (role-labelled transcript, phase bar, Object button with grounds, witness picker, per-session token/cost meter, debrief view).
- Evals: run `trial_script.yaml` for both cases; deterministic: witness answers only cite own docs, phase order respected; LLM-judge rubric: witness consistency with statement (no invented facts), stays in role, judge rulings sensible.
- **Exit:** scripted round completes for both cases via API and is playable in the UI.

### Stage 6 — Case assistant chat (the one free tool-using agent)
- Tools (read-only, case-scoped): `search_case`, `list_conflicts`, `get_timeline`, `get_issue`, `get_gaps`. Answers must carry validated citations.
- Frontend: Assistant side panel available on every tab.
- Evals: gold Q&A answer correctness (LLM-judge) + citation validity.
- **Exit:** gold questions answered with valid citations on both cases.

### Stage 7 — Hardening & deploy
- Simple bearer-token auth (single user/firm MVP), upload limits, CORS, structured error responses.
- `docker-compose.yml`: backend, frontend (static via nginx), phoenix; Ollama stays on host (`OLLAMA_BASE_URL`). Data volume for `data/`.
- CI (GitHub Actions): lint, typecheck, unit/API tests using `TestModel` (no LLM, no cost). Evals run manually: `uv run python -m evals.run --profile hybrid --case all`.
- README: local run, profile switching, eval run, deploy steps; final eval report comparing `local` vs `hybrid` (quality, tokens, cost, latency).
- **Exit:** `docker compose up` on a clean machine runs the full flow with sample cases.

## Cost control (built in, not bolted on)
Role routing (cheap model for high-volume roles: extractor, witness, IO, objection check; stronger only for judge, contradiction analyst, argument builder), per-aspect grouping instead of pairwise compares, whole witness statement in a stable system prompt (prompt caching on cloud providers), transcript windowing + summary, `MAX_TURNS` per session, token/cost shown in UI per job and session, CI never calls an LLM.

## Out of scope for MVP (mentioned so it is a choice, not an omission)
Multi-user RBAC and firm-level tenancy, encryption at rest (SQLCipher — noted in ADR as next step), voice, real statute/case-law search, DMS integration, local vision LLM (too slow on this CPU).

## Verification (end-to-end)
1. `uv run pytest` + `ruff check` + `pyright` (backend); `npm run lint && npm run build` (frontend) — green at every stage.
2. `uv run python samples/generate.py && uv run python samples/validate.py`.
3. `docker compose up` → open UI → create case → upload `samples/case1_*` → wait for ingest + analysis → check conflicts/arguments and click citations → run a mock-trial round → read debrief.
4. Open Phoenix (`http://localhost:6006`) → see the analysis job and trial turns as traces with tokens per role.
5. `uv run python -m evals.run --profile hybrid --case all` and `--profile local` → `evals/reports/<date>.md` with OCR accuracy, retrieval recall@5, contradiction P/R, gap recall, citation validity, trial rubric scores, tokens/cost/latency.
6. Isolation check: two cases loaded; assistant in case 2 asked about case 1's facts finds nothing.
