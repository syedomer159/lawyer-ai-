"""Shared by the eval suites: sample-case paths, ingestion into a throwaway store, reports."""

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT
from app.contracts.cases import Case, CaseCreate
from app.contracts.documents import DocumentKind
from app.ingest.pipeline import ingest_document
from app.llm.embeddings import CaseEmbedder
from app.store.case_store import CaseStore
from app.store.registry import Registry

SAMPLES = REPO_ROOT / "samples"
REPORTS = Path(__file__).parent / "reports"
KIND: dict[str, DocumentKind] = {
    "text_pdf": "pdf",
    "scanned_pdf": "pdf",
    "image": "image",
    "txt": "text",
}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def sample_cases() -> list[Path]:
    return sorted(SAMPLES.glob("case*/"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def ingest_case(
    case_dir: Path, registry: Registry, embedder: CaseEmbedder, embed_model: str
) -> tuple[Case, CaseStore]:
    """Create the sample case (with its real charges and side) and ingest every file."""
    spec = load_yaml(case_dir / "case.yaml")
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    case = registry.create(
        CaseCreate(
            title=spec["title"],
            client=spec["client"],
            user_side=spec["user_side"],
            charges=spec["charges"],
        ),
        embed_model,
    )
    store = CaseStore(registry.case_dir(case.id))
    for name, meta in manifest["documents"].items():
        doc = store.add_document(name, KIND[meta["kind"]], sha256=name)
        shutil.copy(case_dir / "files" / name, store.file_path(doc))
        await ingest_document(store, doc, embedder)
    return case, store


def write_report(name: str, results: Any, markdown: list[str]) -> Path:
    REPORTS.mkdir(exist_ok=True)
    stem = REPORTS / f"{date.today().isoformat()}-{name}"
    stem.with_suffix(".json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return stem.with_suffix(".md")
