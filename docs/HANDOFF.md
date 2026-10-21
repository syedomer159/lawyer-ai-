# Handoff — Lawyer AI case prep

| Version | Updated | Describes commit | Written by | Status |
|---|---|---|---|---|
| 1 | 2026-10-21 | `13fbc97` | Claude Code session `local_25698c00-0c6e-4fa3-8830-aaa4313d2078` (Stages 0–6 build) | Stages 0–6 done, Stage 7 not started · 52 backend tests passing |

> Living document: update this file in place (bump the version, set the commit) at the start and end of every stage. If the commit above is older than `git log -1`, check the status sections against the code before trusting them. Rules: `CLAUDE.md` → "Session handoff".

Change log: v1 (2026-10-21) first handoff after Stages 0–6 and key rotation.

Read first: [README](../README.md) (run it), [CLAUDE.md](../CLAUDE.md) (rules for working in the repo), [plan](plan.md) (original staged plan), [design](design.md) (requirements, cost, agents), [ADRs](adr/) (decisions, with implementation notes per stage).

---

## 1. Where we are

| Stage | What it delivers | Status | Commit | How it was verified |
|---|---|---|---|---|
| 0 Foundation | Repo, FastAPI + React skeleton, OpenAPI→TS contract, CI file, hook, ADRs, risk spikes | ✅ Done | `4d7eb52` | lint/types/build green; spikes for Ollama, Gemini, OCR, PyMuPDF, Phoenix |
| 1 Sample data | 2 synthetic BNS/BNSS cases (21 files), answer keys, scripted trial rounds | ✅ Done | `c063b66` | `samples/validate.py` (runs in CI), negative test of the validator |
| 2 Core | Cases, upload, OCR, chunks with page+box, hybrid search, page viewer | ✅ Done | `412fbb0` | tests (incl. case isolation); browser check of search → viewer highlight; ingest eval |
| 3 LLM layer | Role→model routing, `run_role`, usage rows, Phoenix tracing, usage line in UI | ✅ Done | `c761a96` | tests; real call on cloud + local, traces checked in Phoenix |
| 4 Analysis | Contradictions, gaps, adverse evidence, arguments with citations; Analysis + Arguments tabs | ✅ Done | `8d8938d` | tests; analysis eval (3 runs, see §2); Analysis tab empty/progress/failure states in browser |
| 5 Mock trial | Judge / counsel / IO / witness agents, objections, debrief; Courtroom tab | ✅ Done | `d849133` | tests (phases, scoping, full offline trial); trial eval case 1 only |
| 6 Case assistant | Tool-calling chat over one case, cited answers; Ask tab | ✅ Done | `e90c980` | tests (offline round trip, tool isolation) |
| — Key rotation | Gemini key pool: rotate, park out-of-quota keys until reset, disable invalid keys | ✅ Done | `13fbc97` | tests; live `--check` of 10 keys (8 ok, 2 invalid, pruned from `.env`) |
| 7 Hardening & deploy | Auth, Docker Compose, CI run, final README + eval summary | ⬜ Not started | — | — |

## 2. Measured results (synthetic sample cases, `cloud` profile)

| Eval | Case 1 (Arjun Verma) | Case 2 (Kavita Rao) | Report |
|---|---|---|---|
| OCR similarity / retrieval recall@5 | 0.988 / 1.0 | 0.988 / 1.0 | `backend/evals/reports/2026-10-21-ingest.md` |
| Contradictions found (of planted) | 6/7 | 5/6 | `…-analysis-cloud.md` (run 3; runs 1–2 kept for comparison) |
| Gaps found / "hurts us" found | 6/6 · 1/2 | 3/4 · 2/2 | same |
| Citations verified | 100% | 100% | same |
| Analysis cost / time | $0.061 / 4.3 min | $0.058 / 5.3 min | same |
| Trial: objections right / witness consistent / answers inventing a fact | 8/9 · 9/9 · 1/9 | not run (quota) | report not saved (see §3, Stage 5) |
| Trial cost / time | $0.025 / 2 min | — | — |

Caveat: two clean synthetic cases; real scans and longer files will score lower. Run-to-run variance is about ±1 contradiction per case.

## 3. What was left out or differs from the plan (checklist)

Tick these off as they are done. **P1** = needed for a reliable demo, **P2** = should do, **P3** = later.

### Stage 0–1
- [ ] P2 CI has never run on GitHub (no remote yet). Push and confirm the `ci.yml` jobs pass.
- [ ] P3 Spike scripts in `scripts/spikes/` are not lint/type-checked (throwaway; delete or leave).
- [ ] P2 Only 2 synthetic cases, one scripted trial round each. Add a third case of a different kind (e.g. a civil-flavoured or document-heavy case) before trusting the numbers.
- [ ] P2 Unverified legal references (marked `verified: false` in `backend/app/legal_refs/*.yaml`): BNS 106(1), BNS 281, the BNSS test-identification provision, the BSA electronic-record certificate section. Have a lawyer confirm.

### Stage 2 (documents)
- [ ] P1 The **Upload** button itself was never clicked in a browser (the test tool cannot open a file picker); upload was tested through the same API. Do it manually (§5).
- [ ] P2 Ingestion and analysis run as in-process background tasks: a server restart mid-job leaves a document "processing" forever (analysis jobs time out after 30 min). Fix: mark stale jobs failed on startup, or a small job queue.
- [ ] P2 No delete / re-ingest of a single document.
- [ ] P3 Photos with no text get no description (the `vision` role exists in config but is unused).
- [ ] P3 Password-protected PDFs and very large files (>25 MB) are rejected without a friendly path.

### Stage 3 (models, tracing)
- [ ] P1 Your `.env` has `MODEL_PROFILE=hybrid`: witness and IO turns then run on local Ollama (20–30+ s each on this CPU). Set `MODEL_PROFILE=cloud` for demos.
- [ ] P2 `TRACE_CONTENT=true` by default: Phoenix stores case text. Fine locally; set `false` for any shared deployment.
- [ ] P3 Usage is shown as a case total only, not per analysis job or trial session (the data is there: `llm_calls.job_id / session_id`).

### Stage 4 (analysis)
- [ ] P1 A full analysis **started from the UI** has not completed since the last fixes (first try hit a network drop + the migration race, both fixed). The same workflow passes in the evals. Verify manually (§5).
- [ ] P2 The model sometimes flags a consistent account as a "contradiction", or labels helps/hurts wrongly. The lawyer can dismiss; a second "verify conflict" pass would reduce this.
- [ ] P2 Arguments can't be edited (plan said "dismiss/edit"); only conflicts can be dismissed.
- [ ] P2 Dismissed conflicts come back on re-run (results are replaced as a whole).
- [ ] P3 The `local` profile has never been evaluated on analysis (too slow on CPU: ~30+ min per case).

### Stage 5 (mock trial)
- [ ] P1 Trial eval for case 2 never ran (Gemini free-tier quota). Re-run: `uv run python -m evals.run --suite trial --profile cloud` (now writes a report even if one case fails).
- [ ] P1 A trial has not been driven in the browser yet (Courtroom tab built and type-checked only).
- [ ] P2 Every move waits for the model (5–30 s), no streaming; the AI asks only 2 questions per examination.
- [ ] P2 No re-examination phase; all witnesses are treated as prosecution witnesses (no defence evidence); you can object to opposing counsel's questions/arguments but not to a witness's answer.
- [ ] P2 Opposing counsel works from the analysis brief, not a live case search (design doc listed a search tool).
- [ ] P3 Memory is a window of the last turns, not a rolling summary; long trials lose early detail.
- [ ] P3 The witness list comes from the case analysis, so a trial needs the analysis run first.

### Stage 6 (assistant)
- [ ] P1 Never asked a question with a real model. Verify manually (§5).
- [ ] P2 No assistant eval (plan: gold Q&A correctness + citation validity; the 20 retrieval questions in the answer keys can be reused).
- [ ] P3 It is an "Ask" tab, not a side panel on every tab; the conversation can't be cleared.

### Key rotation
- [ ] P2 Rotation under real quota exhaustion has only been tested with simulated errors.
- [ ] P2 Quotas are per Google Cloud project: keys from the same project share one quota. Using many projects to multiply the free tier may breach Google's terms; consider billing on one key for the workshop.

## 4. Remaining plan

### Stage 7 — Hardening & deploy (next)
1. **Auth**: one bearer token (`API_TOKEN` in `.env`) checked by a FastAPI dependency on every `/api` route except `/api/health`; the frontend client sends it (stored after a one-field login screen). Test: 401 without token.
2. **Startup recovery**: on app start, mark `processing` documents and `running` jobs as failed with "interrupted by restart" (closes the P2 item in Stage 2).
3. **Docker Compose**: `backend` (uv image, data volume), `frontend` (built static files served by nginx, proxying `/api`), `phoenix`; Ollama stays on the host (`OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`). Test: `docker compose up` on a clean checkout runs the §5 checklist.
4. **CI**: push to GitHub, confirm the two jobs pass (lint, types, tests with the offline model, sample validation, contract drift).
5. **Docs**: README run/deploy section, final eval summary table (from §2 after re-running the trial eval), update this handoff.

Done when: a fresh machine can `docker compose up`, log in with the token, and pass §5 end to end.

### After Stage 7 (pick by priority from §3)
- P1 items in §3 not covered above (manual verification runs).
- Conflict "verify" pass + editable arguments.
- Streaming trial turns; defence witnesses; re-examination.
- Assistant eval suite.
- Out of scope for the MVP (from the plan): multi-user accounts/roles, encryption at rest (SQLCipher or disk), voice, statute/case-law search, DMS integration.

## 5. Manual test verification checklist

Run before a demo and after Stage 7. Expected values come from the sample answer keys (`samples/*/answer_key.yaml`).

### Setup
- [ ] `.env` from `.env.example`: `MODEL_PROFILE=cloud`, `GEMINI_API_KEYS=` set.
- [ ] `cd backend && uv run python -m app.llm.keys --check` → at least one key `active`, none needed `invalid`.
- [ ] Ollama running with `nomic-embed-text` (`ollama list`), Phoenix running (`http://localhost:6006`).
- [ ] Backend on :8010 and frontend on :5173 start without errors; header shows `models: cloud`.

### Case and documents
- [ ] Create case "State v. Arjun Verma", client "Arjun Verma", side defence, charge "BNS 304(2)". It appears in the list.
- [ ] Upload all 11 files from `samples/case1_state_v_arjun_verma/files/` with the **Upload** button. All reach `ready` (about 1–2 min); FIR shows 2 pages.
- [ ] Open `04_Statement_Mohd_Irfan_PW3_scanned.pdf`: page image shows, **OCR** badge visible.
- [ ] Re-upload one file: no duplicate appears.
- [ ] Search "was the streetlight working": top results are the municipal letter, Irfan's statement, Ramesh's statement. Clicking a result opens the page with a yellow highlight on the right text.

### Analysis (Analysis + Arguments tabs)
- [ ] Click **Analyse case**: progress bar moves through reading → grouping → contradictions → assessing → arguments, and finishes in about 4–6 min. The usage line shows calls and a few cents.
- [ ] Contradictions include most of: time of incident (21:15 vs 8:30 pm vs CCTV 20:41), jacket colour (blue vs red vs dark), street light (on vs not working, municipal letter), injury (bleeding elbow vs MLC "no injury"), panch presence at recovery (memo vs affidavit), arrest date.
- [ ] Every citation chip opens the cited page; none are amber "unverified" (a few are acceptable; they must not be shown as plain fact).
- [ ] Procedure checklist marks missing: test identification parade, video recording of search/seizure; weak: FIR delay.
- [ ] Dismiss one conflict: it greys out; "show dismissed" brings it back.
- [ ] Arguments tab: ~12 issues, each with our argument / they will say / our reply / cross-examination questions / citations.

### Mock trial (Courtroom tab)
- [ ] Start a trial with Ramesh Kumar (cooperative). Judge opens, Public Prosecutor opens and asks 2 questions in chief, then the hint says it's your cross-examination (about 20–40 s).
- [ ] Ask "At what time did you see the incident?": witness answers consistent with "about 8:30 pm", no invented facts.
- [ ] Ask "Isn't it true you were drunk that evening?": prosecutor objects, judge sustains, your question is struck through.
- [ ] Object to opposing counsel (any ground): judge rules with a reason.
- [ ] **No further questions** → final arguments: prosecutor argues; type your argument; **Proceed** → judge's observations; phase shows Closed.
- [ ] **Debrief**: score 1–10, strengths, missed contradictions (should name ones you didn't use), better questions.

### Case assistant (Ask tab)
- [ ] "What time does the CCTV still show?" → 20:41:07, citing `08_CCTV_Still_CAM03.png`.
- [ ] "What are the strongest contradictions?" → answer drawn from the analysis, with citations.
- [ ] "What did the accused have for breakfast?" → says the case material does not say (no guessing).

### Isolation and confidentiality
- [ ] Create a second case, upload `samples/case2_state_v_kavita_rao/files/`. In case 2, search "Sunita Sharma gold chain" and ask the assistant about it: nothing from case 1 appears.
- [ ] Create a case with **local models only** ticked, ask one assistant question: Phoenix / the usage line shows only `ollama:` models (slow is expected).
- [ ] Delete a case: it disappears and its folder under `data/cases/` is gone.

### Observability
- [ ] Phoenix project `lawyer-ai`: an `analysis` trace with nested `role.*` spans (tokens, cost, prompt version); trial calls carry `session.id`.
- [ ] `data/gemini_keys.json` contains fingerprints only (no `AIza…` strings).

## 6. Gotchas for whoever picks this up
- Paths contain spaces: quote them in shell commands.
- Never edit generated sample files; edit `samples/*/case.yaml` and run `samples/generate.py` + `validate.py`.
- After changing a backend contract run `npm run gen:api` in `frontend/` and commit `schema.d.ts`.
- `qwen3.5:4b` must be called with reasoning off (handled in the registry); local runs are ~4 tokens/s on this laptop.
- Gemini free tier: ~500 requests/day per model per project. One analysis ≈ 35 calls, one trial ≈ 40.
- The guardrail hook rejects `type: ignore` / `noqa` without a reason: fix the type instead.
