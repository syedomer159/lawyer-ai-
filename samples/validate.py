"""Check that every answer-key and trial-script reference points at real text.

For each ref {doc, page, quote}: the doc exists, the page exists, and the quote appears on that
page (whitespace-normalised) in manifest.json and, for text PDFs, in the PDF's own text layer.
Scanned PDFs must have NO text layer (so ingestion has to OCR them).
Exits 1 on any problem.

Run:  uv run --directory backend python ../samples/validate.py
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import pymupdf
import yaml

SAMPLES = Path(__file__).parent


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def page_text(page: pymupdf.Page) -> str:
    text = page.get_text()  # default "text" mode always returns str
    assert isinstance(text, str)
    return norm(text)


def check_case(case_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    docs: dict[str, Any] = manifest["documents"]
    key = yaml.safe_load((case_dir / "answer_key.yaml").read_text(encoding="utf-8"))
    script = yaml.safe_load((case_dir / "trial_script.yaml").read_text(encoding="utf-8"))
    pdf_text: dict[str, list[str]] = {}

    for name, d in docs.items():
        path = case_dir / "files" / name
        if not path.exists():
            errors.append(f"missing file {name}")
            continue
        if d["kind"] in ("text_pdf", "scanned_pdf"):
            with pymupdf.open(path) as pdf:
                pdf_text[name] = [page_text(pdf[i]) for i in range(pdf.page_count)]
            if d["kind"] == "scanned_pdf" and any(pdf_text[name]):
                errors.append(f"{name}: scanned PDF has a text layer")

    def check_ref(where: str, ref: dict[str, Any]) -> None:
        doc, page, quote = ref["doc"], ref["page"], norm(ref["quote"])
        if doc not in docs:
            errors.append(f"{where}: unknown doc {doc}")
            return
        pages = docs[doc]["pages"]
        if not 1 <= page <= len(pages):
            errors.append(f"{where}: {doc} has no page {page}")
            return
        if quote not in norm(pages[page - 1]):
            errors.append(f"{where}: quote not on {doc} p{page}: {quote!r}")
        if docs[doc]["kind"] == "text_pdf" and quote not in pdf_text[doc][page - 1]:
            errors.append(f"{where}: quote missing from PDF text layer {doc} p{page}")

    for section in ("contradictions", "gaps", "hurts"):
        for item in key[section]:
            for ref in item["refs"]:
                check_ref(f"{section}.{item['id']}", ref)
    for c in key["contradictions"]:
        if len({(r["doc"], r["quote"]) for r in c["refs"]}) < 2:
            errors.append(f"contradiction {c['id']} needs at least 2 distinct refs")
    for i, r in enumerate(key["retrieval"]):
        check_ref(f"retrieval[{i}]", r)

    ids = {x["id"] for s in ("contradictions", "gaps", "hurts") for x in key[s]}
    names = {p["name"] for p in key["parties"]}
    for rnd in script["rounds"]:
        if rnd["witness"] not in names:
            errors.append(f"trial {rnd['id']}: witness {rnd['witness']!r} not in parties")
        for j, turn in enumerate(rnd["turns"]):
            where = f"trial {rnd['id']}.turns[{j}]"
            errors += [f"{where}: unknown target {t}" for t in turn["targets"] if t not in ids]
            if "grounded_in" in turn:
                check_ref(where, turn["grounded_in"])

    print(
        f"{key['case']}: {len(docs)} docs, {len(key['contradictions'])} contradictions, "
        f"{len(key['gaps'])} gaps, {len(key['retrieval'])} retrieval Qs, "
        f"{sum(len(r['turns']) for r in script['rounds'])} trial turns, {len(errors)} errors"
    )
    return errors


if __name__ == "__main__":
    keys = sorted(SAMPLES.glob("*/answer_key.yaml"))
    all_errors = [e for k in keys for e in check_case(k.parent)]
    for e in all_errors:
        print("  ERROR", e)
    sys.exit(1 if all_errors else 0)
