from app.contracts.documents import BBox
from app.ingest.parse import Block, ParsedDoc
from app.store.case_store import ParsedChunk

MAX_CHARS = 700  # small chunks keep citations precise; one case has few, so count is no issue


def _union(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _split_long(block: Block) -> list[Block]:
    text, parts = block.text, []
    while len(text) > MAX_CHARS:
        cut = text.rfind(" ", 0, MAX_CHARS)
        cut = cut if cut > 0 else MAX_CHARS
        parts.append(Block(text[:cut].strip(), block.bbox))
        text = text[cut:]
    return [*parts, Block(text.strip(), block.bbox)] if text.strip() else parts


def chunk_page(page_no: int, blocks: list[Block]) -> list[ParsedChunk]:
    """Greedily merge consecutive blocks on ONE page. Chunks never cross pages, so a citation
    to a chunk is always a citation to an exact page."""
    chunks: list[ParsedChunk] = []
    texts: list[str] = []
    boxes: list[BBox] = []

    def flush() -> None:
        if texts:
            chunks.append(ParsedChunk(page_no, "\n".join(texts), _union(boxes)))
            texts.clear()
            boxes.clear()

    for block in (piece for b in blocks for piece in _split_long(b)):
        if texts and len("\n".join(texts)) + len(block.text) + 1 > MAX_CHARS:
            flush()
        texts.append(block.text)
        if block.bbox:
            boxes.append(block.bbox)
    flush()
    return chunks


def chunk_document(doc: ParsedDoc) -> list[ParsedChunk]:
    return [c for page, blocks in zip(doc.pages, doc.blocks, strict=True)
            for c in chunk_page(page.page_no, blocks)]  # fmt: skip
