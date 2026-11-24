"""Download a file in another format. The default download is always the original, byte for byte, under the name it
was uploaded with; these are optional conversions offered next to it.

photo    -> jpg, png, webp, gif, bmp, tif, pdf (Pillow, HEIC/AVIF in too; EXIF rotation applied, transparency flattened onto white where needed)
document -> txt, docx (the text Smriti extracted: document text, OCR and transcripts, in page order)
video    -> mp4 (the browser-friendly copy made during processing, when there is one)
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from .models import Asset, Chunk

IMAGE_FORMATS = {"jpg": ("JPEG", "image/jpeg"), "png": ("PNG", "image/png"), "webp": ("WEBP", "image/webp"),
                 "gif": ("GIF", "image/gif"), "bmp": ("BMP", "image/bmp"), "tif": ("TIFF", "image/tiff"), "pdf": ("PDF", "application/pdf")}
DOC_FORMATS = {"txt": "text/plain; charset=utf-8", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
SAME = {"jpeg": "jpg", "jfif": "jpg", "jpe": "jpg", "pjpeg": "jpg", "pjp": "jpg", "tiff": "tif", "dib": "bmp", "htm": "html"}


def _ext(filename: str) -> str:
    e = Path(filename).suffix.lower().lstrip(".")
    return SAME.get(e, e)


def formats_for(a: Asset) -> list[str]:
    """Extra formats this file can be downloaded in (never its own format: that's the original)."""
    own = _ext(a.filename)
    if a.kind == "photo":
        opts = list(IMAGE_FORMATS)
    elif a.kind == "document":
        opts = list(DOC_FORMATS)
    elif a.kind == "video":
        opts = ["mp4"] if a.has_proxy else []
    else:
        opts = []
    return [f for f in opts if f != own]


def download_name(a: Asset, fmt: str | None = None) -> str:
    name = Path(a.filename).name or "file"
    return f"{Path(name).stem}.{fmt}" if fmt else name


def convert_image(src: Path, fmt: str) -> tuple[bytes, str]:
    pil_fmt, mime = IMAGE_FORMATS[fmt]
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if pil_fmt in ("JPEG", "PDF", "BMP") and (im.mode in ("RGBA", "LA", "P") or "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, "white")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        elif pil_fmt in ("JPEG", "PDF", "BMP") and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        opts = {"quality": 92} if pil_fmt in ("JPEG", "WEBP") else {}
        im.save(buf, pil_fmt, **opts)
    return buf.getvalue(), mime


def extracted_text(db: Session, a: Asset) -> bytes:
    rows = (db.query(Chunk).filter(Chunk.asset_id == a.id, Chunk.chunk_type.in_(("doc_text", "ocr_text", "transcript")))
            .order_by(Chunk.page.is_(None), Chunk.page, Chunk.start_ms).all())
    parts, last_page = [], None
    for c in rows:
        if not (c.content or "").strip():
            continue
        if c.page and c.page != last_page and a.page_count and a.page_count > 1:
            parts.append(f"\n--- Page {c.page} ---\n")
            last_page = c.page
        parts.append(c.content.strip())
    return ("\n\n".join(parts).strip() + "\n").encode("utf-8")


def extracted_docx(db: Session, a: Asset) -> bytes:
    """The extracted text as a Word document: a heading per page, a paragraph per block."""
    from docx import Document
    d = Document()
    d.add_heading(Path(a.filename).stem, level=1)
    for block in extracted_text(db, a).decode("utf-8").split("\n\n"):
        block = block.strip()
        if block.startswith("--- Page ") and block.endswith("---"):
            d.add_heading(block.strip("- "), level=2)
        elif block:
            d.add_paragraph(block)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
