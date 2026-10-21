"""Runs the full analysis workflow on each sample case with real models and scores it against
samples/<case>/answer_key.yaml. Scoring is deterministic (no LLM judge):

- A citation "hits" an answer-key ref when it is the same document and page and shares at least
  half the words of the key's quote.
- A planted contradiction is found when ONE predicted conflict cites claims hitting >= 2 of
  its refs.
- A planted gap is found when a weak/missing element cites one of its refs (or, for gaps with no
  record to cite, its wording overlaps the key's).
- Predicted conflicts that match nothing are listed for a human to judge: they may be real
  findings the key does not list, so "matched share" is a precision proxy, not precision.
"""

import re
import tempfile
import time
from pathlib import Path
from typing import Any

from app.agents.analysis import analyse_case
from app.config import Settings
from app.contracts.analysis import Analysis, CitationView
from app.llm.embeddings import OllamaEmbedder
from app.store.analysis_store import finish_job, load_analysis, start_job
from app.store.registry import Registry
from evals.common import ingest_case, load_yaml, sample_cases, write_report

QUOTE_OVERLAP = 0.5


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0


def hits(ref: dict[str, Any], cit: CitationView) -> bool:
    return (
        cit.ref.filename == ref["doc"]
        and cit.ref.page == ref["page"]
        and overlap(ref["quote"], cit.quote) >= QUOTE_OVERLAP
    )


def score(analysis: Analysis, key: dict[str, Any]) -> dict[str, Any]:
    found_c, matched_pred = {}, set()
    for kc in key["contradictions"]:
        for f in analysis.conflicts:
            covered = {
                i for i, r in enumerate(kc["refs"]) if any(hits(r, c.citation) for c in f.claims)
            }
            if len(covered) >= 2:
                found_c[kc["id"]] = f
                matched_pred.add(f.id)

    open_elements = [e for e in analysis.elements if e.status != "supported"]
    found_g = {
        kg["id"]
        for kg in key["gaps"]
        for e in open_elements
        if any(hits(r, c) for r in kg["refs"] for c in e.citations)
        or overlap(kg["element"], f"{e.element} {e.explanation}") >= QUOTE_OVERLAP
    }
    found_h = {
        kh["id"]
        for kh in key["hurts"]
        for a in analysis.adverse
        if any(hits(r, c) for r in kh["refs"] for c in a.citations)
    }

    cites = [c for e in analysis.elements for c in e.citations]
    cites += [c for a in analysis.adverse for c in a.citations]
    cites += [c for i in analysis.issues for c in i.citations]
    n_c, n_pred = len(key["contradictions"]), len(analysis.conflicts)
    return {
        "contradiction_recall": round(len(found_c) / n_c, 3),
        "conflicts_predicted": n_pred,
        "matched_share": round(len(matched_pred) / n_pred, 3) if n_pred else None,
        "effect_correct": round(
            sum(
                f.effect == kc["effect"]
                for kc in key["contradictions"]
                if (f := found_c.get(kc["id"]))
            )
            / max(len(found_c), 1),
            3,
        ),
        "gap_recall": round(len(found_g) / len(key["gaps"]), 3),
        "adverse_recall": round(len(found_h) / len(key["hurts"]), 3),
        "citation_verified": round(sum(c.verified for c in cites) / len(cites), 3)
        if cites
        else None,
        "claims": len({c.id for f in analysis.conflicts for c in f.claims}),
        "issues": len(analysis.issues),
        "missed_contradictions": [
            f"{kc['id']} {kc['aspect']}" for kc in key["contradictions"] if kc["id"] not in found_c
        ],
        "missed_gaps": [
            f"{kg['id']} {kg['element']}" for kg in key["gaps"] if kg["id"] not in found_g
        ],
        "unmatched_conflicts": [
            f"[{f.severity}/{f.effect}] {f.aspect}: {f.explanation}"
            for f in analysis.conflicts
            if f.id not in matched_pred
        ],
    }


async def run(settings: Settings) -> Path:
    embedder = OllamaEmbedder(settings.embed_model, settings.ollama_base_url)
    results = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        registry = Registry(Path(tmp))
        for case_dir in sample_cases():
            case, store = await ingest_case(case_dir, registry, embedder, settings.embed_model)
            job_id = start_job(store, "analysis")
            t0 = time.perf_counter()
            await analyse_case(case, store, settings, job_id, embedder)
            finish_job(store, job_id)
            usage = store.usage_summary()
            row = {
                "case": case_dir.name,
                "profile": settings.model_profile,
                "seconds": round(time.perf_counter() - t0, 1),
                "llm_calls": usage.calls,
                "tokens": usage.input_tokens + usage.output_tokens,
                "cost_usd": round(usage.cost_usd, 4),
                **score(load_analysis(store), load_yaml(case_dir / "answer_key.yaml")),
            }
            results.append(row)
            print({k: v for k, v in row.items() if not isinstance(v, list)})
            store.close()
        registry.close()

    cols = [
        "case",
        "contradiction_recall",
        "matched_share",
        "effect_correct",
        "gap_recall",
        "adverse_recall",
        "citation_verified",
        "conflicts_predicted",
        "issues",
        "llm_calls",
        "cost_usd",
        "seconds",
    ]
    md = [
        f"# Eval report: analysis ({settings.model_profile} profile)",
        "",
        "Deterministic scoring against samples/*/answer_key.yaml; see evals/analysis_suite.py.",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in results]
    for r in results:
        for title, field in [
            ("missed contradictions", "missed_contradictions"),
            ("missed gaps", "missed_gaps"),
            ("predicted conflicts not in the key (review by hand)", "unmatched_conflicts"),
        ]:
            md += ["", f"## {r['case']}: {title}"]
            md += [f"- {x}" for x in r[field]] or ["- none"]
    return write_report(f"analysis-{settings.model_profile}", results, md)
