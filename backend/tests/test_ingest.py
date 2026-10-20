from pathlib import Path

from app.contracts.documents import BBox
from app.ingest.chunk import MAX_CHARS, chunk_document, chunk_page
from app.ingest.parse import Block, parse_document
from tests.conftest import CASE1, norm


def _in_unit_square(b: BBox) -> bool:
    return all(0 <= v <= 1 for v in b) and b[0] < b[2] and b[1] < b[3]


def test_text_pdf_keeps_pages_and_boxes(tmp_path: Path) -> None:
    doc = parse_document("pdf", CASE1 / "01_FIR_112-2026.pdf", lambda n: tmp_path / f"{n}.png")
    assert [p.page_no for p in doc.pages] == [1, 2]
    assert not any(p.ocr for p in doc.pages)
    assert (tmp_path / "1.png").exists() and (tmp_path / "2.png").exists()

    chunks = chunk_document(doc)
    page1 = [c for c in chunks if c.page_no == 1]
    assert any("Occurrence: 12-03-2026 at about 21:15 hrs" in norm(c.text) for c in page1)
    assert any("No purchase bill furnished" in norm(c.text) for c in chunks if c.page_no == 2)
    assert all(c.bbox and _in_unit_square(c.bbox) for c in chunks)


def test_scanned_pdf_is_ocred(tmp_path: Path) -> None:
    path = CASE1 / "04_Statement_Mohd_Irfan_PW3_scanned.pdf"
    doc = parse_document("pdf", path, lambda n: tmp_path / f"{n}.png")
    assert doc.pages[0].ocr
    assert "streetlight was not working that week" in norm(doc.pages[0].text)
    assert all(b.bbox and _in_unit_square(b.bbox) for b in doc.blocks[0])


def test_image_is_ocred(tmp_path: Path) -> None:
    path = CASE1 / "09_Municipal_Letter_Streetlight.jpg"
    doc = parse_document("image", path, lambda n: tmp_path / f"{n}.png")
    assert (tmp_path / "1.png").exists()
    assert "non-functional from 08-03-2026" in norm(doc.pages[0].text)


def test_text_file_paragraphs_have_no_boxes(tmp_path: Path) -> None:
    doc = parse_document("text", CASE1 / "11_Client_Interview_Notes.txt", lambda n: tmp_path)
    assert len(doc.pages) == 1
    assert all(b.bbox is None for b in doc.blocks[0])
    assert any("cousin's sangeet function" in norm(b.text) for b in doc.blocks[0])


def test_chunks_respect_size_and_union_boxes() -> None:
    long = Block("word " * 400, (0.1, 0.1, 0.9, 0.2))
    small = Block("tail", (0.1, 0.5, 0.3, 0.6))
    chunks = chunk_page(3, [long, small])
    assert all(len(c.text) <= MAX_CHARS for c in chunks)
    assert all(c.page_no == 3 for c in chunks)
    assert chunks[-1].bbox == (0.1, 0.1, 0.9, 0.6)  # last piece of the long block + "tail"
