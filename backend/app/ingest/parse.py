"""Turn an uploaded file into pages of text blocks with normalised boxes (ADR-0005).

- PDF: PyMuPDF text blocks; a page with (almost) no text layer is a scan -> OCR its render.
- Image: OCR.
- Text: paragraphs, no boxes.
Every PDF page and image is also saved as a PNG so the viewer can show it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image
from rapidocr import RapidOCR
from rapidocr.utils.output import RapidOCROutput

from app.contracts.documents import BBox, DocumentKind
from app.store.case_store import ParsedPage

VIEW_DPI = 110  # page PNGs for the viewer
OCR_DPI = 200  # renders of scanned PDF pages for OCR
MIN_TEXT_LAYER = 25  # fewer chars than this on a PDF page -> treat as scanned
TEXT_PAGE_LINES = 60  # .txt files are split into "pages" of this many lines

# Where to save the viewer PNG for page n (a callable keeps parsing independent of the store).
PagePngPath = Callable[[int], Path]


@dataclass
class Block:
    text: str
    bbox: BBox | None


@dataclass
class ParsedDoc:
    pages: list[ParsedPage]
    blocks: list[list[Block]]  # blocks[i] belongs to pages[i]


@cache
def _ocr_engine() -> RapidOCR:
    return RapidOCR()  # loads ONNX models once (~10 s), then reused


def ocr_image(img: Image.Image) -> list[Block]:
    out = _ocr_engine()(np.asarray(img.convert("RGB")))
    if not isinstance(out, RapidOCROutput) or out.boxes is None or out.txts is None:
        return []  # no text found
    w, h = img.size
    blocks = []
    for quad, text in zip(out.boxes, out.txts, strict=True):
        xs, ys = quad[:, 0], quad[:, 1]
        bbox = (float(xs.min() / w), float(ys.min() / h), float(xs.max() / w), float(ys.max() / h))
        blocks.append(Block(text=text, bbox=bbox))
    return blocks


def _render(page: pymupdf.Page, dpi: int) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def parse_pdf(path: Path, page_png: PagePngPath) -> ParsedDoc:
    pages: list[ParsedPage] = []
    all_blocks: list[list[Block]] = []
    with pymupdf.open(path) as pdf:
        for i in range(pdf.page_count):
            page, page_no = pdf[i], i + 1
            _render(page, VIEW_DPI).save(page_png(page_no))
            w, h = page.rect.width, page.rect.height
            blocks = [
                Block(text=b[4].strip(), bbox=(b[0] / w, b[1] / h, b[2] / w, b[3] / h))
                for b in page.get_text("blocks")
                if b[6] == 0 and b[4].strip()  # type 0 = text block
            ]
            ocr = sum(len(b.text) for b in blocks) < MIN_TEXT_LAYER
            if ocr:
                blocks = ocr_image(_render(page, OCR_DPI))
            pages.append(ParsedPage(page_no, "\n".join(b.text for b in blocks), ocr))
            all_blocks.append(blocks)
    return ParsedDoc(pages, all_blocks)


def parse_image(path: Path, page_png: PagePngPath) -> ParsedDoc:
    with Image.open(path) as img:
        img.convert("RGB").save(page_png(1))
        blocks = ocr_image(img)
    return ParsedDoc([ParsedPage(1, "\n".join(b.text for b in blocks), True)], [blocks])


def parse_text(path: Path) -> ParsedDoc:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pages, all_blocks = [], []
    for start in range(0, max(len(lines), 1), TEXT_PAGE_LINES):
        page_lines = lines[start : start + TEXT_PAGE_LINES]
        paragraphs = "\n".join(page_lines).split("\n\n")
        blocks = [Block(text=p.strip(), bbox=None) for p in paragraphs if p.strip()]
        page_no = len(pages) + 1
        pages.append(ParsedPage(page_no, "\n".join(page_lines), False))
        all_blocks.append(blocks)
    return ParsedDoc(pages, all_blocks)


def parse_document(kind: DocumentKind, path: Path, page_png: PagePngPath) -> ParsedDoc:
    if kind == "pdf":
        return parse_pdf(path, page_png)
    if kind == "image":
        return parse_image(path, page_png)
    return parse_text(path)
