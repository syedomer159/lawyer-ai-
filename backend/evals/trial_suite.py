"""Replays samples/<case>/trial_script.yaml (a scripted defence cross-examination) against the
real models and scores the courtroom agents:

- objections: questions marked expect_objection must be blocked (objection sustained); all other
  scripted questions must get through.
- witnesses: an LLM judge (role eval_judge) checks each answer against the witness's own
  statements: consistent, and no invented facts (incl. the script's must_not_invent list).
"""

import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agents.trial import orchestrator
from app.agents.trial.roles import TrialContext, witness_statements
from app.config import Settings
from app.contracts.trial import TrialWitness, UserTurn
from app.llm.embeddings import OllamaEmbedder
from app.llm.prompts import load_prompt
from app.llm.runner import run_role
from app.store import trial_store
from app.store.registry import Registry
from evals.common import ingest_case, load_yaml, sample_cases, write_report


class WitnessCheck(BaseModel):
    consistent: bool
    invented: list[str]


async def run_case(
    case_dir: Path, settings: Settings, registry: Registry, embedder: OllamaEmbedder
) -> dict[str, Any]:
    script = load_yaml(case_dir / "trial_script.yaml")
    roles = {p["name"]: p["role"] for p in load_yaml(case_dir / "answer_key.yaml")["parties"]}
    case, store = await ingest_case(case_dir, registry, embedder, settings.embed_model)
    witnesses = [
        TrialWitness(name=r["witness"], role=roles[r["witness"]]) for r in script["rounds"]
    ]
    session_id = trial_store.create_session(store, case.user_side, witnesses)
    ctx = TrialContext(case, store, settings, session_id)
    t0 = time.perf_counter()
    await orchestrator.start(ctx, witnesses)

    objection_ok, answers = [], []
    for i, rnd in enumerate(script["rounds"]):
        if i > 0:
            await orchestrator.advance(ctx)  # next witness: AI chief, then our cross
        for turn in rnd["turns"]:
            before = len(trial_store.get_turns(store, session_id))
            await orchestrator.user_turn(ctx, UserTurn(kind="question", text=turn["say"]))
            new = trial_store.get_turns(store, session_id)[before:]
            blocked = any(t.kind == "ruling" and t.text.startswith("Sustained") for t in new)
            objection_ok.append(blocked == bool(turn.get("expect_objection")))
            answer = next((t.text for t in new if t.speaker == "witness"), None)
            if answer:
                answers.append((rnd["witness"], turn["say"], answer))
    await orchestrator.advance(ctx)  # to final arguments
    await orchestrator.user_turn(
        ctx, UserTurn(kind="argument", text=" ".join(script["final_argument"]))
    )
    await orchestrator.advance(ctx)  # judge's observations
    await orchestrator.run_debrief(ctx)
    seconds = time.perf_counter() - t0

    checks = []
    for name, question, answer in answers:
        check = await run_role(
            "eval_judge",
            case=case,
            store=store,
            settings=settings,
            prompt=load_prompt("eval_witness"),
            output_type=WitnessCheck,
            user_prompt=f"STATEMENTS\n{witness_statements(store, name)}\n\nQUESTION: {question}"
            f"\nANSWER: {answer}",
            prompt_vars={"must_not_invent": "; ".join(script["must_not_invent"])},
        )
        checks.append((name, question, answer, check))
    rec = trial_store.get_session(store, session_id)
    usage = store.usage_summary()
    store.close()
    return {
        "case": case_dir.name,
        "objection_accuracy": round(sum(objection_ok) / len(objection_ok), 3),
        "witness_consistent": round(sum(c.consistent for *_, c in checks) / len(checks), 3),
        "answers_with_invention": round(sum(bool(c.invented) for *_, c in checks) / len(checks), 3),
        "debrief_score": rec.debrief.score if rec and rec.debrief else None,
        "phase_reached": rec.phase if rec else None,
        "llm_calls": usage.calls,
        "cost_usd": round(usage.cost_usd, 4),
        "seconds": round(seconds, 1),
        "problems": [
            f"{n}: Q: {q} | A: {a} | invented: {c.invented}"
            for n, q, a, c in checks
            if not c.consistent or c.invented
        ],
    }


async def run(settings: Settings) -> Path:
    embedder = OllamaEmbedder(settings.embed_model, settings.ollama_base_url)
    results = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        registry = Registry(Path(tmp))
        for case_dir in sample_cases():
            row = await run_case(case_dir, settings, registry, embedder)
            results.append(row)
            print({k: v for k, v in row.items() if k != "problems"})
        registry.close()
    cols = [
        "case",
        "objection_accuracy",
        "witness_consistent",
        "answers_with_invention",
        "debrief_score",
        "phase_reached",
        "llm_calls",
        "cost_usd",
        "seconds",
    ]
    md = [
        f"# Eval report: mock trial ({settings.model_profile} profile)",
        "",
        "Scripted cross-examination from samples/*/trial_script.yaml; see evals/trial_suite.py.",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in results]
    for r in results:
        md += ["", f"## {r['case']}: answers flagged by the judge"]
        md += [f"- {p}" for p in r["problems"]] or ["- none"]
    return write_report(f"trial-{settings.model_profile}", results, md)
