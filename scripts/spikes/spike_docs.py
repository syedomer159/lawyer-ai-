"""Spike c/d: PyMuPDF text blocks + bboxes + page render, RapidOCR on a rendered "scan".

Run from backend/:  uv run python ../scripts/spikes/spike_docs.py
Writes throwaway files to scripts/spikes/out/.
"""

import time
from pathlib import Path

import pymupdf
from rapidocr import RapidOCR

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

TEXT = (
    "FIRST INFORMATION REPORT\n"
    "P.S. Civil Lines, FIR No. 112/2026\n"
    "Date of occurrence: 12-03-2026 at about 21:15 hrs\n"
    "Informant: Sunita Sharma. Accused wore a blue jacket."
)

# d) build a text PDF, read blocks with bboxes, render page to PNG
doc = pymupdf.open()
page = doc.new_page()
page.insert_text((72, 72), TEXT, fontsize=12)
pdf_path = OUT / "fir.pdf"
doc.save(pdf_path)

doc = pymupdf.open(pdf_path)
for block in doc[0].get_text("blocks"):
    x0, y0, x1, y1, text, *_ = block
    print(f"block bbox=({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}) text={text.strip()[:60]!r}")
png_path = OUT / "fir_p1.png"
doc[0].get_pixmap(dpi=150).save(png_path)
print("rendered", png_path)

# c) OCR the rendered page as if it were a scanned image
engine = RapidOCR()
t0 = time.perf_counter()
result = engine(str(png_path))
print(f"OCR in {time.perf_counter() - t0:.1f}s")
assert result.txts is not None and result.boxes is not None and result.scores is not None
for box, txt, score in zip(result.boxes, result.txts, result.scores, strict=True):
    print(f"  {score:.2f} box0={box[0].tolist()} {txt!r}")
