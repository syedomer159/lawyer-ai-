"""OCR accuracy (vs the true page text) and retrieval recall@5 / MRR on the answer-key questions.
Uses the real local embedder (Ollama), so it costs nothing."""

import difflib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from app.config import Settings
from app.llm.embeddings import OllamaEmbedder
from app.retrieval.search import search
from app.store.case_store import CaseStore
from app.store.registry import Registry
from evals.common import ingest_case, load_yaml, norm, sample_cases, write_report

TOP_K = 5
SUMMARY_COLS = [
    "case",
    "ocr_mean_similarity",
    "recall_at_5",
    "mrr",
    "quote_in_top_5",
    "ingest_seconds",
]


def ocr_scores(case_dir: Path, store: CaseStore) -> list[dict[str, Any]]:
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for doc in store.list_documents():
        meta = manifest["documents"][doc.filename]
        if meta["kind"] not in ("scanned_pdf", "image"):
            continue
        for i, truth in enumerate(meta["pages"], start=1):
            page = store.get_page(doc.id, i)
            got = page.text if page else ""
            ratio = difflib.SequenceMatcher(None, norm(truth), norm(got)).ratio()
            rows.append({"doc": doc.filename, "page": i, "similarity": round(ratio, 3)})
    return rows


async def retrieval_scores(
    case_dir: Path, store: CaseStore, embedder: OllamaEmbedder
) -> list[dict[str, Any]]:
    rows = []
    for item in load_yaml(case_dir / "answer_key.yaml")["retrieval"]:
        hits = await search(store, embedder, item["q"], k=TOP_K)
        rank = next(
            (
                r
                for r, h in enumerate(hits, start=1)
                if h.ref.filename == item["doc"] and h.ref.page == item["page"]
            ),
            None,
        )
        quote_found = any(norm(item["quote"]) in norm(h.text) for h in hits)
        rows.append(
            {
                "q": item["q"],
                "expected": f"{item['doc']} p{item['page']}",
                "rank": rank,
                "quote_in_top_k": quote_found,
            }
        )
    return rows


def summarise(case: str, ocr: list[dict[str, Any]], ret: list[dict[str, Any]], secs: float) -> dict:
    ranks = [r["rank"] for r in ret]
    return {
        "case": case,
        "ocr_mean_similarity": round(sum(o["similarity"] for o in ocr) / len(ocr), 3),
        "recall_at_5": round(sum(r is not None for r in ranks) / len(ranks), 3),
        "mrr": round(sum(1 / r for r in ranks if r) / len(ranks), 3),
        "quote_in_top_5": round(sum(r["quote_in_top_k"] for r in ret) / len(ret), 3),
        "ingest_seconds": round(secs, 1),
        "ocr": ocr,
        "retrieval": ret,
    }


async def run(settings: Settings) -> Path:
    embedder = OllamaEmbedder(settings.embed_model, settings.ollama_base_url)
    results = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        registry = Registry(Path(tmp))
        for case_dir in sample_cases():
            t0 = time.perf_counter()
            _, store = await ingest_case(case_dir, registry, embedder, settings.embed_model)
            secs = time.perf_counter() - t0
            ret = await retrieval_scores(case_dir, store, embedder)
            results.append(summarise(case_dir.name, ocr_scores(case_dir, store), ret, secs))
            store.close()
        registry.close()

    md = [
        "# Eval report: ingest",
        "",
        f"Embedder: `{settings.embed_model}` (local). Retrieval: hybrid BM25 + cosine, RRF, "
        f"top {TOP_K}.",
        "",
        "| case | OCR similarity | recall@5 | MRR | quote in top 5 | ingest s |",
        "|---|---|---|---|---|---|",
    ]
    md += ["| " + " | ".join(str(r[c]) for c in SUMMARY_COLS) + " |" for r in results]
    for r in results:
        misses = [x for x in r["retrieval"] if x["rank"] is None]
        md += ["", f"## {r['case']}: retrieval misses ({len(misses)})"]
        md += [f"- {m['q']} (expected {m['expected']})" for m in misses] or ["- none"]
        md += ["", f"## {r['case']}: OCR per page"]
        md += [f"- {o['doc']} p{o['page']}: {o['similarity']}" for o in r["ocr"]]
    for r in results:
        print({k: v for k, v in r.items() if k not in ("ocr", "retrieval")})
    return write_report("ingest", results, md)
