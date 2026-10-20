"""Eval runner. Scores the pipeline against samples/<case>/{manifest.json, answer_key.yaml}.

Suites:
  ingest - OCR accuracy (vs the true page text) and retrieval recall@5 / MRR on the answer-key
           questions. Uses the real local embedder (Ollama), so it costs nothing.

Run from backend/:  uv run python -m evals.run --suite ingest
Writes evals/reports/<date>-<suite>.{md,json}.
"""

import argparse
import asyncio
import difflib
import json
import re
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT, settings
from app.contracts.cases import CaseCreate
from app.contracts.documents import DocumentKind
from app.ingest.pipeline import ingest_document
from app.llm.embeddings import OllamaEmbedder
from app.retrieval.search import search
from app.store.case_store import CaseStore
from app.store.registry import Registry

SAMPLES = REPO_ROOT / "samples"
REPORTS = Path(__file__).parent / "reports"
KIND: dict[str, DocumentKind] = {"text_pdf": "pdf", "scanned_pdf": "pdf", "image": "image",
                                 "txt": "text"}  # fmt: skip
TOP_K = 5
SUMMARY_COLS = ["case", "ocr_mean_similarity", "recall_at_5", "mrr", "quote_in_top_5",
                "ingest_seconds"]  # fmt: skip


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


async def ingest_case(case_dir: Path, registry: Registry, embedder: OllamaEmbedder) -> CaseStore:
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    case = registry.create(CaseCreate(title=manifest["case"], client="eval"), settings.embed_model)
    store = CaseStore(registry.case_dir(case.id))
    for name, meta in manifest["documents"].items():
        doc = store.add_document(name, KIND[meta["kind"]], sha256=name)
        shutil.copy(case_dir / "files" / name, store.file_path(doc))
        await ingest_document(store, doc, embedder)
    return store


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
    key = yaml.safe_load((case_dir / "answer_key.yaml").read_text(encoding="utf-8"))
    rows = []
    for item in key["retrieval"]:
        hits = await search(store, embedder, item["q"], k=TOP_K)
        rank = next(
            (r for r, h in enumerate(hits, start=1)
             if h.ref.filename == item["doc"] and h.ref.page == item["page"]),
            None,
        )  # fmt: skip
        quote_found = any(norm(item["quote"]) in norm(h.text) for h in hits)
        rows.append({"q": item["q"], "expected": f"{item['doc']} p{item['page']}", "rank": rank,
                     "quote_in_top_k": quote_found})  # fmt: skip
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


def write_report(suite: str, results: list[dict]) -> Path:
    REPORTS.mkdir(exist_ok=True)
    stem = REPORTS / f"{date.today().isoformat()}-{suite}"
    stem.with_suffix(".json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    lines = [f"# Eval report: {suite} ({date.today().isoformat()})", "",
             f"Embedder: `{settings.embed_model}` (local). Retrieval: hybrid BM25 + cosine, RRF, "
             f"top {TOP_K}.", "",
             "| case | OCR similarity | recall@5 | MRR | quote in top 5 | ingest s |",
             "|---|---|---|---|---|---|"]  # fmt: skip
    for r in results:
        lines.append("| " + " | ".join(str(r[c]) for c in SUMMARY_COLS) + " |")
    for r in results:
        misses = [x for x in r["retrieval"] if x["rank"] is None]
        lines += ["", f"## {r['case']}: retrieval misses ({len(misses)})"]
        lines += [f"- {m['q']} (expected {m['expected']})" for m in misses] or ["- none"]
        lines += ["", f"## {r['case']}: OCR per page"]
        lines += [f"- {o['doc']} p{o['page']}: {o['similarity']}" for o in r["ocr"]]
    stem.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stem.with_suffix(".md")


async def run_ingest_suite() -> list[dict]:
    embedder = OllamaEmbedder(settings.embed_model, settings.ollama_base_url)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        registry = Registry(Path(tmp))
        for case_dir in sorted(SAMPLES.glob("case*/")):
            t0 = time.perf_counter()
            store = await ingest_case(case_dir, registry, embedder)
            secs = time.perf_counter() - t0
            ret = await retrieval_scores(case_dir, store, embedder)
            results.append(summarise(case_dir.name, ocr_scores(case_dir, store), ret, secs))
            store.close()
        registry.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["ingest"], required=True)
    args = parser.parse_args()
    results = asyncio.run(run_ingest_suite())
    for r in results:
        print({k: v for k, v in r.items() if k not in ("ocr", "retrieval")})
    print("report:", write_report(args.suite, results))


if __name__ == "__main__":
    main()
