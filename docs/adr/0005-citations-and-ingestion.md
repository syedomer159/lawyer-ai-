# ADR-0005: Every chunk carries a source reference, and citations are verified in code

- Status: accepted
- Date: 2026-10-20

## Context
Lawyers need every finding traced to the exact page or image region, and LLMs invent citations.

## Decision
- Ingestion: text PDFs use PyMuPDF text blocks with bboxes. Scanned pages and images are rendered and run through RapidOCR (ONNX, pip-only, returns line boxes). `.txt` files are split into paragraphs. Every chunk stores `{doc_id, page, bbox}`, and every page has a rendered PNG for the viewer.
- Agents return citations as `{chunk_id, quote}`. `app/citations.py` checks that the chunk exists in this case and that the quote fuzzy-matches the chunk text (≥ 0.9). On failure we retry once, then mark the citation `unverified` in the UI.
- Photos without text get an optional vision-model caption (cloud only; too slow locally), stored as a chunk that points at the image.

## Spike results (Stage 0)
- PyMuPDF returned block bboxes and rendered a page at 150 dpi.
- RapidOCR read a rendered page line by line at 0.99–1.00 confidence and returned boxes. The first call takes about 10 s, mostly model warm-up.

## Consequences
- The UI can highlight the exact region, and evals can score citation validity in code instead of with an LLM.

## Alternatives considered
- Docling: better layout on complex documents, but heavier models. Our documents are simple statements and memos.
- Tesseract: needs a system install on Windows. RapidOCR is pip-only.
- Local vision LLM for OCR: far too slow on this CPU.
