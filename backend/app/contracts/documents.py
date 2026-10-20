from typing import Literal, get_args

from pydantic import BaseModel

DocumentKind = Literal["pdf", "image", "text"]
DocumentStatus = Literal["queued", "processing", "ready", "failed"]
DOCUMENT_KINDS: tuple[str, ...] = get_args(DocumentKind)
DOCUMENT_STATUSES: tuple[str, ...] = get_args(DocumentStatus)

# Box on a page as fractions of page width/height: (x0, y0, x1, y1), each 0..1.
# The same for PDF points and image pixels, so the viewer can overlay it on any render size.
BBox = tuple[float, float, float, float]


class Document(BaseModel):
    id: str
    filename: str
    kind: DocumentKind
    status: DocumentStatus
    n_pages: int
    error: str | None = None


class SourceRef(BaseModel):
    """Where a piece of text lives in the case. Every citation resolves to one of these."""

    chunk_id: int
    doc_id: str
    filename: str
    page: int
    bbox: BBox | None


class ChunkView(BaseModel):
    id: int
    bbox: BBox | None
    text: str


class PageDetail(BaseModel):
    doc_id: str
    page: int
    n_pages: int
    ocr: bool
    text: str
    chunks: list[ChunkView]


class SearchHit(BaseModel):
    ref: SourceRef
    text: str
    score: float
