"""Decide what a file really is from its bytes, not just its extension.

Real-world files are messy: WhatsApp/Chrome save JPEGs as `.jfif`, sites serve WebP as `.jpeg`, phones produce
`.heic`, scanners produce `.tif`. The extension is only a hint; the magic bytes decide.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

PHOTO_EXT = {".jpg", ".jpeg", ".jpe", ".jfif", ".pjpeg", ".pjp", ".png", ".apng", ".webp", ".gif", ".bmp", ".dib",
             ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mpg", ".mpeg", ".3gp", ".3g2", ".wmv", ".flv", ".f4v", ".ts", ".mts",
             ".m2ts", ".ogv", ".vob"}
DOC_EXT = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xlsm", ".xls", ".odt", ".ods", ".odp", ".epub", ".rtf", ".eml",
           ".txt", ".md", ".markdown", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".ini", ".cfg", ".tex",
           ".xml", ".html", ".htm", ".xhtml", ".srt", ".vtt"}

# (offset, signature, kind, mime)
_MAGIC: list[tuple[int, bytes, str, str]] = [
    (0, b"\xff\xd8\xff", "photo", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "photo", "image/png"),
    (0, b"GIF87a", "photo", "image/gif"), (0, b"GIF89a", "photo", "image/gif"),
    (0, b"BM", "photo", "image/bmp"),
    (0, b"II*\x00", "photo", "image/tiff"), (0, b"MM\x00*", "photo", "image/tiff"),
    (0, b"\x00\x00\x01\x00", "photo", "image/x-icon"),
    (0, b"%PDF", "document", "application/pdf"),
    (0, b"{\\rtf", "document", "application/rtf"),
    (0, b"\x1aE\xdf\xa3", "video", "video/x-matroska"),  # mkv / webm
    (0, b"FLV", "video", "video/x-flv"),
    (0, b"\x00\x00\x01\xba", "video", "video/mpeg"), (0, b"\x00\x00\x01\xb3", "video", "video/mpeg"),
    (0, b"0&\xb2u\x8ef\xcf\x11", "video", "video/x-ms-wmv"),
    (0, b"OggS", "video", "video/ogg"),
]
_FTYP = {  # ISO-BMFF brands (bytes 8..12 after "ftyp")
    b"heic": ("photo", "image/heic"), b"heix": ("photo", "image/heic"), b"mif1": ("photo", "image/heif"), b"msf1": ("photo", "image/heif"),
    b"avif": ("photo", "image/avif"), b"avis": ("photo", "image/avif"),
    b"qt  ": ("video", "video/quicktime"), b"3gp4": ("video", "video/3gpp"), b"3gp5": ("video", "video/3gpp"), b"3g2a": ("video", "video/3gpp2"),
}
_OOXML = {"word/": ("document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
          "ppt/": ("document", "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
          "xl/": ("document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")}
# canonical extension per mime, so pipelines that switch on extension get the real format
CANON_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/bmp": ".bmp", "image/tiff": ".tif", "image/webp": ".webp",
             "image/heic": ".heic", "image/heif": ".heif", "image/avif": ".avif", "image/x-icon": ".ico", "application/pdf": ".pdf",
             "application/rtf": ".rtf", "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "video/x-matroska": ".mkv",
             "video/x-msvideo": ".avi", "video/3gpp": ".3gp", "video/mpeg": ".mpg", "video/x-flv": ".flv", "video/x-ms-wmv": ".wmv",
             "video/ogg": ".ogv", "video/mp2t": ".ts"}


def sniff(path: Path) -> tuple[str, str, str | None] | None:
    """Return (kind, mime, ooxml_ext) from file contents, or None if unrecognised."""
    try:
        with open(path, "rb") as f:
            head = f.read(400)
    except OSError:
        return None
    for off, sig, kind, mime in _MAGIC:
        if head[off:off + len(sig)] == sig:
            if mime == "video/x-matroska" and b"webm" in head:
                mime = "video/webm"
            return kind, mime, None
    for off in (0, 4):  # MPEG transport stream (.ts/.mts; .m2ts has a 4-byte timestamp first): sync byte every 188 bytes
        if len(head) > off + 188 and head[off] == 0x47 and head[off + 188] == 0x47:
            return "video", "video/mp2t", None
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "photo", "image/webp", None
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "video", "video/x-msvideo", None
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _FTYP:
            return (*_FTYP[brand], None)
        return "video", "video/mp4", None  # isom, mp42, M4V ...
    if head[:2] == b"PK":
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            for prefix, (kind, mime, ext) in _OOXML.items():
                if any(n.startswith(prefix) for n in names):
                    return kind, mime, ext
        except Exception:
            return None
    return None


def classify(path: Path, filename: str) -> tuple[str | None, str | None, str]:
    """(kind, mime, effective_ext). Content wins over extension; extension is the fallback for text formats."""
    ext = Path(filename).suffix.lower()
    s = sniff(path)
    if s:
        kind, mime, ooxml_ext = s
        if ext in DOC_EXT and not ooxml_ext and mime not in ("application/pdf",) and kind != "document":
            if mime in ("image/bmp", "image/x-icon", "video/mpeg"):  # 2-4 byte signatures: a text file can start with these
                return "document", None, ext
        if kind == "document" and ext in DOC_EXT and not ooxml_ext and mime != "application/pdf":
            return kind, mime, ext
        return kind, mime, ooxml_ext or CANON_EXT.get(mime, ext)
    if ext in DOC_EXT:
        return "document", None, ext
    if ext in PHOTO_EXT or ext in VIDEO_EXT:
        return None, None, ext  # claims to be media but the bytes aren't: reject rather than crash a pipeline
    return None, None, ext
