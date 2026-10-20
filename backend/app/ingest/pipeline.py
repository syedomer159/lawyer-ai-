import asyncio
import logging
from pathlib import Path

from app.contracts.documents import Document
from app.ingest.chunk import chunk_document
from app.ingest.parse import parse_document
from app.llm.embeddings import CaseEmbedder
from app.store.case_store import CaseStore

log = logging.getLogger(__name__)


async def ingest_document(store: CaseStore, doc: Document, embedder: CaseEmbedder) -> None:
    """Parse -> chunk -> embed, then write everything in one transaction (all or nothing)."""
    store.set_status(doc.id, "processing")
    try:
        # Parsing and OCR are CPU-bound: keep them off the event loop.
        parsed = await asyncio.to_thread(
            parse_document,
            doc.kind,
            store.file_path(doc),
            lambda n: store.page_image_path(doc.id, n),
        )
        chunks = chunk_document(parsed)
        vectors = await embedder.embed_documents([c.text for c in chunks])
        store.save_ingest(doc.id, parsed.pages, chunks, vectors)
    except Exception as exc:
        # Boundary of a background job: record the failure on the document so the UI shows it,
        # then re-raise so the traceback is logged.
        store.set_status(doc.id, "failed", f"{type(exc).__name__}: {exc}")
        raise


async def ingest_in_background(
    case_dir: Path, docs: list[Document], embedder: CaseEmbedder
) -> None:
    """Runs after the upload response, so it opens its own store (the request's is closed)."""
    store = CaseStore(case_dir)
    try:
        for doc in docs:
            try:
                await ingest_document(store, doc, embedder)
            except Exception:
                log.exception("ingest failed for %s (%s)", doc.filename, doc.id)
    finally:
        store.close()
