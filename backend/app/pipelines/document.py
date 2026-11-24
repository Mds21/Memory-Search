import csv
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from email import policy as email_policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from ..adapters import registry
from ..tools import find as find_tool
from ..models import Asset
from ..understanding import understand
from .common import add_chunk, clear_derived, detect_lang, upsert_tags
from .photo import describe_and_index, make_thumbs  # noqa: F401

TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".ini", ".cfg", ".tex"}
MARKUP_EXT = {".html", ".htm", ".xhtml", ".xml", ".svg"}
ODF_EXT = {".odt", ".ods", ".odp"}
SUBTITLE_EXT = {".srt", ".vtt"}


class _Text(HTMLParser):
    """Visible text of HTML/XML: drops tags, scripts and styles, keeps line breaks at block ends."""
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "title",
             "text:p", "text:h", "table:table-row", "draw:page"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag == "table:table-cell":
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", "".join(self.parts))).strip()


def _markup_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    return p.text()


def _decode(b: bytes) -> str:
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16", errors="replace")
    try:
        return b.decode("utf-8-sig")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace")


def _rtf_text(raw: str) -> str:
    """Plain text of an RTF file (good enough for search: drops control words, font/colour tables, hex escapes)."""
    raw = re.sub(r"\{\\\*[^{}]*\}", "", raw)
    for name in ("fonttbl", "colortbl", "stylesheet", "info", "pict"):
        raw = re.sub(r"\{\\" + name + r"(?:[^{}]|\{[^{}]*\})*\}", "", raw)
    raw = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes.fromhex(m[1]).decode("cp1252", errors="replace"), raw)
    raw = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m[1]) % 65536), raw)
    raw = re.sub(r"\\(par|line|row|cell)\b ?", "\n", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?|\\[^a-zA-Z]|[{}]", "", raw)
    return re.sub(r"\n\s*\n+", "\n", raw).strip()


def _eml_text(path: Path) -> str:
    with path.open("rb") as f:
        msg = BytesParser(policy=email_policy.default).parse(f)
    head = "\n".join(f"{k}: {msg[k]}" for k in ("From", "To", "Cc", "Date", "Subject") if msg[k])
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body is not None else ""
    if body is not None and body.get_content_type() == "text/html":
        text = _markup_text(text)
    names = [part.get_filename() for part in msg.iter_attachments() if part.get_filename()]
    return head + "\n\n" + text + (("\n\nAttachments: " + ", ".join(names)) if names else "")



def _ocr_pdf_page(path: Path, page: int) -> str:
    if not find_tool("pdftoppm") or not registry.ocr().available:
        return ""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([find_tool("pdftoppm"), "-f", str(page), "-l", str(page), "-r", "150", "-png", str(path), f"{td}/p"],
                       capture_output=True, timeout=120)
        imgs = sorted(Path(td).glob("p*.png"))
        return registry.ocr().ocr(imgs[0]) if imgs else ""


RICH_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".xlsm"}


def _pages(path: Path, ext: str) -> list[str]:
    if ext in RICH_EXT:  # slides with notes/charts/tables, Word tables, sheet columns, text inside embedded pictures
        from .extractors import extract
        return extract(path, ext, _ocr_pdf_page).pages
    if ext == ".xls":
        import xlrd
        book = xlrd.open_workbook(str(path))
        return [f"Sheet: {sh.name}\n" + "\n".join(" | ".join(str(v) for v in sh.row_values(i)) for i in range(sh.nrows))
                for sh in book.sheets()]
    if ext in ODF_EXT:  # OpenDocument: the text lives in content.xml (one page per slide for .odp)
        with zipfile.ZipFile(path) as z:
            xml = z.read("content.xml").decode("utf-8", errors="replace")
        if ext == ".odp":
            return [_markup_text(pg) for pg in re.findall(r"<draw:page\b.*?</draw:page>", xml, re.S)] or [_markup_text(xml)]
        return [_markup_text(xml)]
    if ext == ".epub":
        with zipfile.ZipFile(path) as z:
            names = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
            return [t for t in (_markup_text(_decode(z.read(n))) for n in names) if t.strip()] or [""]
    if ext in (".doc", ".ppt"):
        raise ValueError(f"Old Office {ext} files can't be read yet. Save it as {ext}x and upload that.")
    if ext in TEXT_EXT or ext in MARKUP_EXT or ext in SUBTITLE_EXT or ext in (".rtf", ".eml"):
        raw = _eml_text(path) if ext == ".eml" else _decode(path.read_bytes())
        if ext in (".csv", ".tsv"):
            raw = "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(raw), delimiter="\t" if ext == ".tsv" else ","))
        elif ext in MARKUP_EXT:
            raw = _markup_text(raw)
        elif ext == ".rtf":
            raw = _rtf_text(raw)
        elif ext in SUBTITLE_EXT:  # keep the spoken lines, drop cue numbers and timings
            raw = "\n".join(l for l in raw.splitlines() if l.strip() and "-->" not in l and not l.strip().isdigit() and l.strip() != "WEBVTT")
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
    if not find_tool("pdftoppm"):
        return None
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([find_tool("pdftoppm"), "-f", "1", "-l", "1", "-r", "70", "-png", str(path), f"{td}/t"], capture_output=True, timeout=60)
        f = sorted(Path(td).glob("t*.png"))
        return Image.open(f[0]).convert("RGB") if f else None


def summarize(title: str, pages: list[str]) -> str:
    body = " ".join(" ".join(pages).split())
    sentences = re.split(r"(?<=[.!?।])\s+", body)
    return (f"{title}. " + " ".join(sentences[:3]))[:700]


def ingest_document(db: Session, asset: Asset, src: Path) -> None:
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    ext = src.suffix.lower() or Path(asset.filename).suffix.lower()  # stored under its real type (filetypes.classify)
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
    summary = summarize(title, pages)
    add_chunk(db, asset, "doc_text", summary, meta={"is_summary": True}, language=asset.language)
    upsert_tags(db, asset, [ext.lstrip("."), "document"])
    understand(db, asset, text=full[:20000], summary=summary)  # what kind of document, whose, key facts
