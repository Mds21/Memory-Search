"""Deep text extraction for office files, PDFs and web/markup files.

Each extractor returns an `Extracted`: one text block per page / slide / sheet (used for page-level citations),
plus plain-language facts about the file's structure (slide titles, headings, sheet columns, pictures found).
Pictures embedded inside documents (a scanned card pasted into Word, a photo on a slide, a chart image in a PDF)
are OCR'd so the words inside them become searchable too.
"""
from __future__ import annotations

import csv
import html
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from ..adapters import registry

MAX_PICTURES = 12          # OCR budget per document
MIN_PICTURE_BYTES = 6_000  # skip icons, bullets, logos
MIN_PICTURE_SIDE = 160
MAX_SHEET_ROWS = 2_000

TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".rtf", ".eml", ".log", ".json"}
MARKUP_EXT = {".html", ".htm", ".xml"}


@dataclass
class Extracted:
    pages: list[str]
    details: list[dict] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)   # slide titles / headings / sheet names
    pictures: int = 0                                   # embedded pictures seen
    picture_text: int = 0                               # of those, how many had readable text

    def detail(self, key: str, label: str, value) -> None:
        if value not in (None, "", 0):
            self.details.append({"key": key, "label": label, "value": str(value)[:160]})


class _PictureReader:
    """OCRs embedded pictures within a per-document budget."""

    def __init__(self, out: Extracted):
        self.out, self.done = out, 0
        self.ocr = registry.ocr()

    def read(self, blob: bytes) -> str:
        if len(blob) < MIN_PICTURE_BYTES:
            return ""
        try:
            img = Image.open(io.BytesIO(blob))
            img.load()
        except Exception:
            return ""
        if min(img.size) < MIN_PICTURE_SIDE:
            return ""
        self.out.pictures += 1
        if not self.ocr.available or self.done >= MAX_PICTURES:
            return ""
        self.done += 1
        try:
            text = " ".join((self.ocr.ocr_image(img.convert("RGB"), quick=True) or "").split())
        except Exception:
            return ""
        if len(re.findall(r"[A-Za-zऀ-ॿ]{3,}", text)) >= 2:  # real words, not OCR noise on a photo
            self.out.picture_text += 1
            return text
        return ""


def _clean(s: str | None) -> str:
    return re.sub(r"[ \t ]+", " ", s or "").strip()


# ---------------------------------------------------------------- PowerPoint
def _pptx(path: Path) -> Extracted:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(str(path))
    out = Extracted(pages=[])
    pics = _PictureReader(out)
    tables = charts = notes_n = 0

    def walk(shapes, lines: list[str]):
        nonlocal tables, charts
        for sh in shapes:
            try:
                if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                    walk(sh.shapes, lines)
                    continue
                if getattr(sh, "has_table", False) and sh.has_table:
                    tables += 1
                    for row in sh.table.rows:
                        lines.append(" | ".join(_clean(c.text) for c in row.cells))
                    continue
                if getattr(sh, "has_chart", False) and sh.has_chart:
                    charts += 1
                    ch = sh.chart
                    title = _clean(ch.chart_title.text_frame.text) if ch.has_title else ""
                    plot = ch.plots[0] if len(ch.plots) else None
                    cats = [str(c) for c in (plot.categories if plot else [])][:20]
                    series = [s.name for s in (plot.series if plot else [])][:10]
                    lines.append("Chart: " + "; ".join(x for x in (title, "categories " + ", ".join(cats) if cats else "",
                                                                  "series " + ", ".join(series) if series else "") if x))
                    continue
                if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    t = pics.read(sh.image.blob)
                    if t:
                        lines.append(f"Text in picture: {t}")
                    continue
                if sh.has_text_frame and sh.text_frame.text.strip():
                    lines.append(sh.text_frame.text.strip())
            except Exception:
                continue

    for i, slide in enumerate(prs.slides, 1):
        lines: list[str] = []
        title = ""
        try:
            if slide.shapes.title is not None:
                title = _clean(slide.shapes.title.text)
        except Exception:
            pass
        walk(slide.shapes, lines)
        if slide.has_notes_slide:
            note = _clean(slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else "")
            if note:
                notes_n += 1
                lines.append(f"Speaker notes: {note}")
        head = f"Slide {i}" + (f": {title}" if title else "")
        out.outline.append(title or "")
        out.pages.append(head + "\n" + "\n".join(l for l in lines if l != title))

    out.detail("slides", "Slides", len(prs.slides))
    named = [t for t in out.outline if t]
    if named:
        out.detail("outline", "Slide titles", " · ".join(dict.fromkeys(named[:8])))
    out.detail("tables", "Tables", tables)
    out.detail("charts", "Charts", charts)
    out.detail("notes", "Slides with notes", notes_n)
    return out


# ---------------------------------------------------------------- Word
def _docx(path: Path) -> Extracted:
    from docx import Document

    d = Document(str(path))
    out = Extracted(pages=[])
    pics = _PictureReader(out)
    lines: list[str] = []
    headings: list[str] = []
    # body in document order: paragraphs and tables interleaved
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            txt = _clean(p.text)
            if not txt:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            if style.lower().startswith(("heading", "title")):
                headings.append(txt)
            lines.append(txt)
        elif tag == "tbl":
            for row in Table(el, d).rows:
                cells = list(dict.fromkeys(_clean(c.text) for c in row.cells))  # merged cells repeat
                lines.append(" | ".join(cells))
    extra: list[str] = []
    for sec in d.sections:
        for part in (sec.header, sec.footer):
            try:
                t = " ".join(_clean(p.text) for p in part.paragraphs if p.text.strip())
                if t and t not in extra:
                    extra.append(t)
            except Exception:
                pass
    if extra:
        lines.append("Header/footer: " + " · ".join(extra))
    for rel in d.part.rels.values():
        if "image" in rel.reltype:
            try:
                t = pics.read(rel.target_part.blob)
            except Exception:
                t = ""
            if t:
                lines.append(f"Text in picture: {t}")
    # pseudo-pages of ~600 words so citations point somewhere useful in long documents
    page, n = [], 0
    for ln in lines:
        page.append(ln)
        n += len(ln.split())
        if n >= 600:
            out.pages.append("\n".join(page))
            page, n = [], 0
    if page or not out.pages:
        out.pages.append("\n".join(page))
    out.outline = headings
    if headings:
        out.detail("outline", "Headings", " · ".join(dict.fromkeys(headings[:8])))
    out.detail("tables", "Tables", len(d.tables))
    return out


# ---------------------------------------------------------------- Excel
def _xlsx(path: Path) -> Extracted:
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True, data_only=True)
    out = Extracted(pages=[])
    summary = []
    for ws in wb.worksheets:
        rows = []
        for r in ws.iter_rows(values_only=True):
            if len(rows) >= MAX_SHEET_ROWS:
                break
            vals = ["" if c is None else str(c).strip() for c in r]
            if any(vals):
                rows.append(vals)
        header = rows[0] if rows and sum(1 for v in rows[0] if v and not re.fullmatch(r"[\d.,\-]+", v)) >= max(1, len([v for v in rows[0] if v]) // 2) else None
        lines = [f"Sheet: {ws.title}"]
        if header:
            cols = [h for h in header if h]
            lines.append("Columns: " + ", ".join(cols))
            for r in rows[1:]:  # "Column: value" makes rows answerable ("what's the amount for March?")
                lines.append("; ".join(f"{h}: {v}" for h, v in zip(header, r) if h and v))
        else:
            lines += [" | ".join(r) for r in rows]
        out.pages.append("\n".join(lines))
        out.outline.append(ws.title)
        n = max(0, len(rows) - (1 if header else 0))
        summary.append(f"{ws.title} ({n} rows" + (f": {', '.join([h for h in header if h][:5])}" if header else "") + ")")
    out.detail("sheets", "Sheets", " · ".join(summary[:6]))
    return out


# ---------------------------------------------------------------- PDF
def _pdf(path: Path, ocr_page) -> Extracted:
    from pypdf import PdfReader

    r = PdfReader(str(path))
    out = Extracted(pages=[])
    pics = _PictureReader(out)
    scanned = 0
    for i, page in enumerate(r.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if len(text.strip()) < 30:  # scanned page: OCR the whole page
            scanned += 1
            text = ocr_page(path, i) or text
        else:  # text page that also carries pictures (a photo of a card, a chart): read those too
            try:
                for im in page.images:
                    t = pics.read(im.data)
                    if t and t[:40] not in text:
                        text += f"\nText in picture: {t}"
            except Exception:
                pass
        out.pages.append(text)
    try:
        outline = [o.title for o in r.outline if hasattr(o, "title")][:12]
    except Exception:
        outline = []
    out.outline = outline
    if outline:
        out.detail("outline", "Sections", " · ".join(outline[:8]))
    try:
        fields = r.get_form_text_fields() or {}
        filled = {k: v for k, v in fields.items() if v}
        if filled:
            out.pages.append("Form fields:\n" + "\n".join(f"{k}: {v}" for k, v in list(filled.items())[:60]))
            out.detail("form", "Filled form fields", len(filled))
    except Exception:
        pass
    if scanned and scanned == len(r.pages):
        out.detail("scanned", "Scanned", "Yes, text read from the images")
    return out


# ---------------------------------------------------------------- text & markup
def _markup_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|section|article)>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return html.unescape(re.sub(r"[ \t]+", " ", raw))


def _text(path: Path, ext: str) -> Extracted:
    raw = path.read_bytes().decode("utf-8", errors="replace")
    title = None
    if ext in MARKUP_EXT:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        title = _clean(html.unescape(m[1])) if m else None
        raw = _markup_to_text(raw)
    elif ext in (".csv", ".tsv"):
        rows = list(csv.reader(io.StringIO(raw), delimiter="\t" if ext == ".tsv" else ","))[:MAX_SHEET_ROWS]
        if rows and len(rows) > 1:
            header = rows[0]
            raw = "Columns: " + ", ".join(header) + "\n" + "\n".join("; ".join(f"{h}: {v}" for h, v in zip(header, r) if h and v) for r in rows[1:])
        else:
            raw = "\n".join(" | ".join(r) for r in rows)
    elif ext == ".rtf":
        raw = re.sub(r"\\'[0-9a-f]{2}|\\[a-z]+-?\d* ?|[{}]", " ", raw)
    out = Extracted(pages=[raw[i:i + 3000] for i in range(0, max(len(raw), 1), 3000)])
    if title:
        out.detail("title", "Title", title)
    return out


def extract(path: Path, ext: str, ocr_page) -> Extracted:
    if ext == ".pdf":
        return _pdf(path, ocr_page)
    if ext == ".docx":
        return _docx(path)
    if ext == ".pptx":
        return _pptx(path)
    if ext in (".xlsx", ".xlsm"):
        return _xlsx(path)
    if ext in TEXT_EXT or ext in MARKUP_EXT:
        return _text(path, ext)
    raise ValueError("This kind of document isn't supported yet.")
