"""Build the synthetic sample cases from samples/<case>/case.yaml.

Writes samples/<case>/files/* (what a lawyer would upload) and samples/<case>/manifest.json
(the true text of every page, used as ground truth by validate.py and the OCR evals).
Deterministic: same yaml -> same files.

Run:  uv run --directory backend python ../samples/generate.py
"""

import io
import json
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pymupdf
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SAMPLES = Path(__file__).parent
PAGE_BREAK = "---PAGE---"
WRAP = 92  # chars per line for 10pt Helvetica inside A4 margins


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def wrap_page(text: str) -> str:
    lines: list[str] = []
    for line in text.strip("\n").splitlines():
        lines.extend(textwrap.wrap(line, WRAP) or [""])
    return "\n".join(lines)


def split_pages(body: str) -> list[str]:
    return [wrap_page(p) for p in body.split(PAGE_BREAK)]


def text_pdf(pages: list[str]) -> pymupdf.Document:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)  # A4
        overflow = page.insert_textbox(pymupdf.Rect(56, 56, 539, 800), text, fontsize=10)
        assert overflow >= 0, "page text overflows; add a ---PAGE--- break"
    return doc


def degrade(img: Image.Image, seed: int, angle: float, noise: float = 12) -> Image.Image:
    """Make a clean render look like a phone photo / scan: grey, tilted, noisy, soft.
    Use noise=0 for PNG output: pixel noise makes PNGs ~10x larger."""
    rng = np.random.default_rng(seed)
    grey = img.convert("L").rotate(angle, expand=True, fillcolor=235)
    arr = np.asarray(grey, dtype=np.int16) + rng.normal(0, noise, (grey.height, grey.width))
    noisy = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return noisy.filter(ImageFilter.GaussianBlur(0.6))


def scanned_pdf(pages: list[str], seed: int) -> pymupdf.Document:
    clean = text_pdf(pages)
    out = pymupdf.open()
    for i in range(clean.page_count):
        pix = clean[i].get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        buf = io.BytesIO()
        degrade(img, seed + i, angle=0.8).save(buf, format="JPEG", quality=70)
        new = out.new_page(width=595, height=842)
        new.insert_image(new.rect, stream=buf.getvalue())  # image only: no text layer
    return out


def save_pdf(doc: pymupdf.Document, path: Path) -> None:
    doc.set_metadata({"creator": "lawyer-ai samples", "creationDate": "", "modDate": ""})
    doc.save(path, garbage=4, deflate=True, no_new_id=True)


def draw_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    lines: list[str],
    size: int,
    fill: int | tuple[int, int, int],
    gap: int = 14,
) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font(size), fill=fill)
        y += size + gap


def document_photo(texts: list[str], seed: int) -> Image.Image:
    paper = Image.new("RGB", (1100, 120 + 52 * len(texts)), (250, 248, 240))
    draw_lines(ImageDraw.Draw(paper), (60, 60), texts, size=30, fill=(20, 20, 20), gap=22)
    canvas = Image.new("RGB", (paper.width + 160, paper.height + 160), (92, 64, 44))
    canvas.paste(paper, (80, 80))
    return degrade(canvas, seed, angle=2.0).convert("RGB")


def cctv(texts: list[str], seed: int) -> Image.Image:
    img = Image.new("RGB", (1280, 720), (18, 20, 24))
    d = ImageDraw.Draw(img)
    d.polygon([(400, 720), (880, 720), (700, 330), (580, 330)], fill=(40, 42, 46))  # road
    d.rectangle([980, 260, 1180, 520], fill=(55, 50, 40))  # tea stall
    d.ellipse([612, 400, 652, 440], fill=(120, 110, 100))  # running figure, colour unclear
    d.rectangle([606, 440, 658, 530], fill=(70, 75, 90))
    d.line([(620, 530), (600, 600)], fill=(60, 60, 60), width=10)
    d.line([(645, 530), (675, 595)], fill=(60, 60, 60), width=10)
    d.text((24, 20), texts[0], font=font(30), fill=(255, 255, 255))
    d.rectangle([0, 660, 1280, 720], fill=(0, 0, 0))
    d.text((24, 672), texts[1], font=font(28), fill=(255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(0.8))


def site_plan(texts: list[str], seed: int) -> Image.Image:
    img = Image.new("RGB", (1400, 1100), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 30), texts[0], font=font(30), fill=(0, 0, 0))
    d.line([(500, 100), (500, 760)], fill=(0, 0, 0), width=4)  # road edges
    d.line([(900, 100), (900, 760)], fill=(0, 0, 0), width=4)
    d.line([(700, 100), (700, 760)], fill=(120, 120, 120), width=6)  # divider
    d.text((710, 110), "N ^", font=font(26), fill=(0, 0, 0))
    d.text((560, 470), "X", font=font(48), fill=(200, 0, 0))
    d.text((560, 150), "A", font=font(40), fill=(0, 0, 160))
    d.text((400, 470), "B", font=font(40), fill=(0, 0, 160))
    d.rectangle([520, 560, 640, 700], outline=(0, 0, 0), width=3)
    d.text((565, 610), "C", font=font(40), fill=(0, 0, 160))
    d.text((920, 400), "Station Road", font=font(26), fill=(0, 0, 0))
    draw_lines(d, (40, 800), texts[1:], size=26, fill=(0, 0, 0), gap=12)
    return degrade(img, seed, angle=0.0, noise=0).convert("RGB")


def vehicle(texts: list[str], seed: int) -> Image.Image:
    img = Image.new("RGB", (1280, 800), (150, 150, 150))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([240, 220, 1040, 560], radius=60, fill=(240, 240, 236))  # body
    d.rectangle([380, 140, 900, 260], fill=(200, 210, 220))  # windscreen
    d.ellipse([300, 520, 440, 660], fill=(30, 30, 30))
    d.ellipse([840, 520, 980, 660], fill=(30, 30, 30))
    for dx, dy in [(0, 0), (30, 20), (60, -10), (15, 45)]:  # cracks on front-left
        d.line([(270 + dx, 300 + dy), (330 + dx, 360 + dy)], fill=(40, 40, 40), width=5)
    d.ellipse([255, 280, 345, 340], outline=(60, 60, 60), width=6)  # broken headlight
    d.rectangle([0, 700, 1280, 800], fill=(255, 255, 255))
    draw_lines(d, (30, 710), texts, size=28, fill=(0, 0, 0), gap=10)
    return degrade(img, seed, angle=1.0).convert("RGB")


IMAGE_STYLES = {
    "document_photo": document_photo,
    "cctv": cctv,
    "site_plan": site_plan,
    "vehicle": vehicle,
}


def build_case(case_dir: Path) -> None:
    spec: dict[str, Any] = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    files = case_dir / "files"
    files.mkdir(exist_ok=True)
    manifest: dict[str, Any] = {"case": spec["id"], "documents": {}}

    for i, d in enumerate(spec["documents"]):
        path, kind, seed = files / d["file"], d["kind"], 1000 * (i + 1)
        if kind == "text_pdf":
            pages = split_pages(d["body"])
            save_pdf(text_pdf(pages), path)
        elif kind == "scanned_pdf":
            pages = split_pages(d["body"])
            save_pdf(scanned_pdf(pages, seed), path)
        elif kind == "txt":
            pages = [d["body"].strip()]
            path.write_text(pages[0] + "\n", encoding="utf-8")
        elif kind == "image":
            pages = ["\n".join(d["texts"])]
            img = IMAGE_STYLES[d["style"]](d["texts"], seed)
            img.save(path, quality=85) if path.suffix == ".jpg" else img.save(path)
        else:
            raise ValueError(f"unknown kind {kind!r} in {d['file']}")
        manifest["documents"][d["file"]] = {"kind": kind, "title": d["title"], "pages": pages}

    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{spec['id']}: {len(spec['documents'])} documents -> {files}")


if __name__ == "__main__":
    for case_yaml in sorted(SAMPLES.glob("*/case.yaml")):
        build_case(case_yaml.parent)
