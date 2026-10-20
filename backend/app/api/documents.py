import hashlib
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import EmbedderDep, SettingsDep, StoreDep
from app.contracts.documents import Document, DocumentKind, PageDetail, SearchHit
from app.ingest.pipeline import ingest_in_background
from app.retrieval.search import search

router = APIRouter(prefix="/api/cases/{case_id}", tags=["documents"])

KIND_BY_EXT: dict[str, DocumentKind] = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".txt": "text",
    ".md": "text",
}


@router.post("/documents", status_code=201)
async def upload_documents(
    files: list[UploadFile],
    background: BackgroundTasks,
    store: StoreDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
) -> list[Document]:
    """Store the files and queue ingestion. Identical bytes return the existing document."""
    result: list[Document] = []
    new_docs: list[Document] = []
    for f in files:
        name = Path(f.filename or "upload").name
        kind = KIND_BY_EXT.get(Path(name).suffix.lower())
        if kind is None:
            raise HTTPException(415, f"{name}: unsupported type (use {', '.join(KIND_BY_EXT)})")
        data = await f.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"{name}: larger than {settings.max_upload_mb} MB")
        sha = hashlib.sha256(data).hexdigest()
        if existing := store.find_by_sha(sha):
            result.append(existing)
            continue
        doc = store.add_document(name, kind, sha)
        store.file_path(doc).write_bytes(data)
        result.append(doc)
        new_docs.append(doc)
    if new_docs:
        background.add_task(ingest_in_background, store.dir, new_docs, embedder)
    return result


@router.get("/documents")
def list_documents(store: StoreDep) -> list[Document]:
    return store.list_documents()


@router.get("/documents/{doc_id}/pages/{page}")
def get_page(doc_id: str, page: int, store: StoreDep) -> PageDetail:
    detail = store.get_page(doc_id, page)
    if detail is None:
        raise HTTPException(404, "page not found")
    return detail


@router.get("/documents/{doc_id}/pages/{page}/image", response_class=FileResponse)
def get_page_image(doc_id: str, page: int, store: StoreDep) -> FileResponse:
    if store.get_document(doc_id) is None:  # doc_id comes from the URL: only serve known docs
        raise HTTPException(404, "document not found")
    path = store.page_image_path(doc_id, page)
    if not path.exists():
        raise HTTPException(404, "page image not found")
    return FileResponse(path, media_type="image/png")


@router.get("/search")
async def search_case(
    q: str, store: StoreDep, embedder: EmbedderDep, k: int = 8
) -> list[SearchHit]:
    return await search(store, embedder, q, k)
