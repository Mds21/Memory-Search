import csv
import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from ..adapters import registry
from ..models import Asset
from .common import add_chunk, clear_derived, detect_lang, upsert_tags
from .photo import describe_and_index, make_thumbs  # noqa: F401

TEXT_EXT = {".txt", ".md", ".csv", ".rtf", ".eml", ".log", ".json"}


def _pdf_pages(path: Path) -> tuple[list[str], int]:
    from pypdf import PdfReader
    r = PdfReader(str(path))
    return [(p.extract_text() or "") for p in r.pages], len(r.pages)


def _ocr_pdf_page(path: Path, page: int) -> str:
    if not shutil.which("pdftoppm") or not registry.ocr().available:
        return ""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "150", "-png", str(path), f"{td}/p"],
                       capture_output=True, timeout=120)
        imgs = sorted(Path(td).glob("p*.png"))
        return registry.ocr().ocr(imgs[0]) if imgs else ""


def _pages(path: Path, ext: str) -> list[str]:
    if ext == ".pdf":
        pages, _ = _pdf_pages(path)
        out = []
        for i, t in enumerate(pages, 1):
            if len(t.strip()) < 30:  # scanned page: OCR fallback
                t = _ocr_pdf_page(path, i) or t
            out.append(t)
        return out
    if ext == ".docx":
        from docx import Document
        d = Document(str(path))
        lines = [p.text for p in d.paragraphs]
        for tb in d.tables:
            for row in tb.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return ["\n".join(lines)]
    if ext == ".pptx":
        from pptx import Presentation
        out = []
        for slide in Presentation(str(path)).slides:
            out.append("\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame))
        return out
    if ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(str(path), read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            rows = [" | ".join("" if c is None else str(c) for c in r) for r in ws.iter_rows(values_only=True)]
            out.append(f"Sheet: {ws.title}\n" + "\n".join(rows))
        return out
    if ext in TEXT_EXT:
        raw = path.read_bytes().decode("utf-8", errors="replace")
        if ext == ".csv":
            raw = "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(raw)))
        # split long plain text into pseudo-pages of ~3000 chars for page-level citations
        return [raw[i:i + 3000] for i in range(0, max(len(raw), 1), 3000)]
    raise ValueError(f"Unsupported document type: {ext}")


def chunk_text(text: str, target_words: int = 220, overlap_words: int = 35) -> list[str]:
    """Paragraph-aware sliding window (~target_words, ~15% overlap). Never splits inside a line of a table row."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks, cur, n = [], [], 0
    for line in lines:
        w = len(line.split())
        if cur and n + w > target_words:
            chunks.append("\n".join(cur))
            tail, tn = [], 0
            for prev in reversed(cur):
                tn += len(prev.split())
                tail.insert(0, prev)
                if tn >= overlap_words:
                    break
            cur, n = (tail if tn < target_words else []), (tn if tn < target_words else 0)
        cur.append(line)
        n += w
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def text_thumbnail(title: str, text: str) -> Image.Image:
    img = Image.new("RGB", (480, 640), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 480, 56], fill="#1f3a5f")
    d.text((18, 20), title[:48], fill="#ffffff")
    y = 78
    words, line = re.sub(r"\s+", " ", text).strip().split(" "), ""
    for w in words:
        if len(line) + len(w) > 52:
            d.text((18, y), line, fill="#33475f")
            y, line = y + 16, ""
            if y > 610:
                break
        line += w + " "
    return img


def _pdf_thumb(path: Path) -> Image.Image | None:
    if not shutil.which("pdftoppm"):
        return None
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "70", "-png", str(path), f"{td}/t"], capture_output=True, timeout=60)
        f = sorted(Path(td).glob("t*.png"))
        return Image.open(f[0]).convert("RGB") if f else None


def summarize(title: str, pages: list[str]) -> str:
    body = " ".join(" ".join(pages).split())
    sentences = re.split(r"(?<=[.!?।])\s+", body)
    return (f"{title}. " + " ".join(sentences[:3]))[:700]


def ingest_document(db: Session, asset: Asset, src: Path) -> None:
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    ext = Path(asset.filename).suffix.lower()
    title = Path(asset.filename).stem.replace("_", " ")

    if asset.mime_type.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}:
        raise ValueError("Image files are ingested as photos")

    pages = _pages(src, ext)
    asset.page_count = len(pages)
    full = "\n".join(pages)
    asset.language = detect_lang(full)

    thumb = _pdf_thumb(src) if ext == ".pdf" else None
    thumb = thumb or text_thumbnail(title, full)
    make_thumbs(thumb, base, store)
    asset.has_thumb = True
    asset.status_detail = "indexing"
    db.commit()

    clear_derived(db, asset)
    empty = 0
    for pno, text in enumerate(pages, 1):
        if not text.strip():
            empty += 1
            continue
        lang = detect_lang(text)
        for part in chunk_text(text):
            add_chunk(db, asset, "doc_text", part, embed_text=f"{title} > page {pno}\n{part}", page=pno, language=lang)
    if empty == len(pages):
        raise ValueError("No readable text found (scan too poor for OCR, or OCR language pack missing).")
    add_chunk(db, asset, "doc_text", summarize(title, pages), meta={"is_summary": True}, language=asset.language)
    upsert_tags(db, asset, [ext.lstrip("."), "document"])
