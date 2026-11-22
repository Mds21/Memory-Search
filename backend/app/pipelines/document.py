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
from ..understanding import understand
from .common import add_chunk, clear_derived, detect_lang, upsert_tags
from .photo import describe_and_index, make_thumbs  # noqa: F401

from .extractors import TEXT_EXT  # noqa: F401,E402


def _pdf_pages(path: Path) -> tuple[list[str], int]:
    from pypdf import PdfReader
    r = PdfReader(str(path))
    return [(p.extract_text() or "") for p in r.pages], len(r.pages)


def _embedded_page_image(path: Path, page: int) -> Image.Image | None:
    """Largest picture stored on a PDF page. A scanned page is just one big image, so this works without Poppler."""
    try:
        from pypdf import PdfReader
        imgs = PdfReader(str(path)).pages[page - 1].images
        best = max(imgs, key=lambda im: len(im.data), default=None)
        return Image.open(io.BytesIO(best.data)) if best else None
    except Exception:
        return None


def _ocr_pdf_page(path: Path, page: int) -> str:
    if not registry.ocr().available:
        return ""
    if not shutil.which("pdftoppm"):
        img = _embedded_page_image(path, page)
        return registry.ocr().ocr_image(img) if img else ""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "150", "-png", str(path), f"{td}/p"],
                       capture_output=True, timeout=120)
        imgs = sorted(Path(td).glob("p*.png"))
        return registry.ocr().ocr_image(Image.open(imgs[0])) if imgs else ""


def _extract(path: Path, ext: str):
    from .extractors import extract
    return extract(path, ext, _ocr_pdf_page)


def _pages(path: Path, ext: str) -> list[str]:
    return _extract(path, ext).pages


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


LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "es": "Spanish", "te": "Telugu", "kn": "Kannada",
              "bn": "Bengali", "gu": "Gujarati", "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu", "fr": "French", "de": "German"}


def doc_properties(path: Path, ext: str) -> dict:
    """Title / author / created date stored inside the file by the app that made it."""
    out: dict = {}
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            m = PdfReader(str(path)).metadata or {}
            out = {"title": m.get("/Title"), "author": m.get("/Author"), "subject": m.get("/Subject")}
            try:
                out["created"] = m.creation_date
            except Exception:
                pass
        elif ext in (".docx", ".pptx"):
            if ext == ".docx":
                from docx import Document
                cp = Document(str(path)).core_properties
            else:
                from pptx import Presentation
                cp = Presentation(str(path)).core_properties
            out = {"title": cp.title, "author": cp.author, "subject": cp.subject, "created": cp.created}
        elif ext in (".xlsx", ".xlsm"):
            from openpyxl import load_workbook
            p = load_workbook(str(path), read_only=True).properties
            out = {"title": p.title, "author": p.creator, "subject": p.subject, "created": p.created}
    except Exception:
        return {}
    from datetime import timezone
    c = out.get("created")
    if c is not None and getattr(c, "year", 0) >= 1990:
        out["created"] = c if c.tzinfo else c.replace(tzinfo=timezone.utc)
    else:
        out.pop("created", None)
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in out.items() if v}


def document_details(asset: Asset, props: dict, pages: list[str], title: str, ex=None) -> list[dict]:
    out = []
    head = next((ln.strip() for p in pages for ln in p.splitlines() if 4 <= len(ln.strip()) <= 90), None)
    if ex is not None and asset.ext == ".pptx":
        head = next((t for t in ex.outline if t), head)
    real_title = props.get("title") or head
    if real_title and real_title.lower() != title.lower():
        out.append({"key": "title", "label": "Title", "value": real_title[:90]})
    if props.get("author"):
        out.append({"key": "author", "label": "Author", "value": str(props["author"])[:80]})
    if props.get("created"):
        out.append({"key": "created", "label": "Created", "value": f"{props['created']:%d %b %Y}"})
    if asset.page_count and asset.page_count > 1 and asset.ext == ".pdf":
        out.append({"key": "pages", "label": "Pages", "value": str(asset.page_count)})
    words = sum(len(p.split()) for p in pages)
    if words >= 50:
        out.append({"key": "words", "label": "Length", "value": f"About {words:,} words" if words < 1000 else f"About {round(words / 1000, 1):g}k words"})
    if ex is not None:
        seen = {d["key"] for d in out}
        out += [d for d in ex.details if d["key"] not in seen]
        if ex.pictures:
            out.append({"key": "pictures", "label": "Pictures inside", "value": str(ex.pictures) + (f" ({ex.picture_text} with text)" if ex.picture_text else "")})
    if asset.language and asset.language in LANG_NAMES:
        out.append({"key": "language", "label": "Language", "value": LANG_NAMES[asset.language]})
    return out


def summarize(title: str, pages: list[str]) -> str:
    body = " ".join(" ".join(pages).split())
    sentences = re.split(r"(?<=[.!?।])\s+", body)
    return (f"{title}. " + " ".join(sentences[:3]))[:700]


def ingest_document(db: Session, asset: Asset, src: Path) -> None:
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    ext = asset.ext
    title = Path(asset.filename).stem.replace("_", " ")

    if asset.mime_type.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}:
        raise ValueError("This file is a picture, not a document.")

    ex = _extract(src, ext)
    pages = ex.pages
    asset.page_count = len(pages)
    props = doc_properties(src, ext)
    if props.get("created") and not asset.taken_at:
        asset.taken_at = props["created"]  # lets "documents from 2023" work for files without a date in the name
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
            where = f"slide {pno}" if ext == ".pptx" else f"sheet {ex.outline[pno - 1]}" if ext in (".xlsx", ".xlsm") and pno <= len(ex.outline) else f"page {pno}"
            add_chunk(db, asset, "doc_text", part, embed_text=f"{title} > {where}\n{part}", page=pno, language=lang)
    if empty == len(pages):
        raise ValueError("We couldn't find any readable text in this document. If it's a photo or scan, try a clearer copy.")
    summary = summarize(title, pages)
    add_chunk(db, asset, "doc_text", summary, meta={"is_summary": True}, language=asset.language)
    named = [t for t in ex.outline if t]
    if named:  # structure is searchable too: "the deck with a slide about pricing"
        add_chunk(db, asset, "doc_text", f"{title} contents: " + "; ".join(dict.fromkeys(named[:40])), meta={"is_outline": True})
    kind_tags = {".pptx": ["presentation", "slides"], ".xlsx": ["spreadsheet"], ".xlsm": ["spreadsheet"], ".csv": ["spreadsheet"],
                 ".docx": ["word"], ".pdf": ["pdf"]}.get(ext, [])
    upsert_tags(db, asset, [ext.lstrip("."), "document", *kind_tags])
    understand(db, asset, text=full[:20000], file_facts=document_details(asset, props, pages, title, ex), summary=summary)  # e.g. an e-Aadhaar PDF or a scanned PAN becomes "aadhaar_card"/"pan_card"
