import shutil
import subprocess
from pathlib import Path

from .base import OCREngine, ObjectStore, STT, Segment, Transcript


class TesseractOCR(OCREngine):
    """Calls the tesseract CLI. Uses only the language packs actually installed.

    Language data in <DATA_DIR>/tessdata (eng, hin, mar, tam, spa...) is preferred when present, so extra languages
    don't need admin rights or a reinstall. Output is read as UTF-8 so Devanagari and Tamil survive on Windows."""

    def __init__(self, wanted: str = "eng+hin+mar+tam+spa"):
        from ..config import get_settings
        from ..tools import find
        self.bin = find("tesseract")
        local = get_settings().data_path / "tessdata"
        self.extra = ["--tessdata-dir", str(local)] if (local / "eng.traineddata").exists() else []
        have: set[str] = set()
        if self.bin:
            out = self._run([self.bin, *self.extra, "--list-langs"], timeout=30).split()
            have = set(out)
        self.langs = [l for l in wanted.split("+") if l in have] or (["eng"] if "eng" in have else [])

    @staticmethod
    def _run(cmd: list[str], timeout: int) -> str:
        try:
            r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
            return r.stdout or ""
        except Exception:
            return ""

    def ocr(self, image_path: Path, langs: list[str] | None = None, psm: int = 3, min_conf: float = 0) -> str:
        """Tesseract on an image file (scanned PDF pages). min_conf > 0 keeps only words Tesseract is at least that sure
        of (0-100), so an ordinary photo with no writing yields nothing instead of stray characters."""
        if not (self.bin and self.langs):
            return ""
        use = "+".join(langs or self.langs)
        if not min_conf:
            return self._run([self.bin, str(image_path), "stdout", *self.extra, "-l", use, "--psm", str(psm)], timeout=120).strip()
        tsv = self._run([self.bin, str(image_path), "stdout", *self.extra, "-l", use, "--psm", str(psm), "-c", "tessedit_create_tsv=1"], timeout=120)
        lines: dict[tuple, list[str]] = {}
        for row in tsv.splitlines()[1:]:
            f = row.split(chr(9))  # tab-separated
            if len(f) < 12 or not f[11].strip():
                continue
            try:
                conf = float(f[10])
            except ValueError:
                continue
            word = f[11].strip()
            if conf >= min_conf and any(ch.isalnum() for ch in word):
                lines.setdefault((f[2], f[3], f[4]), []).append(word)
        kept = [" ".join(ws) for ws in lines.values()]
        words = [w for ln in kept for w in ln.split()]
        # a real piece of writing has a few proper words, not a couple of fragments
        if sum(1 for w in words if sum(ch.isalpha() for ch in w) >= 3) < 2:
            return ""
        return chr(10).join(kept)

    def ocr_image(self, img, quick: bool = False, langs: list[str] | None = None, min_conf: float = 0) -> str:
        """OCR a PIL image (a photo, or a picture inside a Word file or slide). quick: English plus Hindi only, smaller.

        Tesseract reads clean scans well but often finds nothing in phone photos of cards (small text on patterned
        backgrounds). RapidOCR, when installed, reads those; Tesseract still supplies Hindi/Marathi/Tamil lines, which
        RapidOCR's models don't cover. The longer Latin reading wins."""
        tess = ""
        if self.bin and self.langs:
            import tempfile
            g = img.convert("L")
            g.thumbnail((1400, 1400) if quick else (2400, 2400))
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "page.png"
                g.save(p)
                use = langs or ([l for l in ("eng", "hin") if l in self.langs] or self.langs if quick else None)
                tess = self.ocr(p, use, min_conf=min_conf)
        rapid = _rapid_text(img, min_score=0.6 if min_conf else 0.5)
        return _merge_readings(tess, rapid)

    @property
    def available(self) -> bool:  # either engine is enough for photos
        return bool(self.bin and self.langs) or _rapid() is not None


_RAPID: dict = {}
_RAPID_LOCK = __import__("threading").Lock()


def _rapid():
    """Shared RapidOCR engine (onnxruntime sessions are thread-safe), or None when it isn't installed."""
    if "e" not in _RAPID:
        with _RAPID_LOCK:
            if "e" not in _RAPID:
                try:
                    import logging
                    from rapidocr_onnxruntime import RapidOCR
                    logging.getLogger("RapidOCR").setLevel(logging.ERROR)
                    _RAPID["e"] = RapidOCR()
                except Exception:  # noqa: BLE001 - optional dependency
                    _RAPID["e"] = None
    return _RAPID["e"]


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x3000 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF or 0xAC00 <= o <= 0xD7AF


def _real_words(text: str) -> int:
    return sum(1 for w in text.split() if sum(ch.isalpha() for ch in w) >= 3)


def _rapid_text(img, min_score: float) -> str:
    eng = _rapid()
    if eng is None:
        return ""
    try:
        import numpy as np
        im = img.convert("RGB")
        im.thumbnail((1600, 1600))
        res, _ = eng(np.asarray(im))
    except Exception:  # noqa: BLE001
        return ""
    lines = []
    for _box, text, score in res or []:
        # its models are English/Chinese: Devanagari comes out as stray Chinese characters, so drop those
        text = "".join(" " if _is_cjk(ch) else ch for ch in str(text)).strip()
        if float(score) >= min_score and sum(ch.isalnum() for ch in text) >= 2:
            lines.append(" ".join(text.split()))
    out = chr(10).join(lines)
    return out if _real_words(out) >= 2 else ""


def _merge_readings(tess: str, rapid: str) -> str:
    if not rapid:
        return tess
    latin_tess = " ".join(w for w in tess.split() if all(ord(ch) < 0x250 for ch in w))
    if _real_words(latin_tess) > _real_words(rapid) * 1.2:
        return tess
    indic = [ln for ln in tess.splitlines() if any(0x0900 <= ord(ch) <= 0x0DFF for ch in ln)]
    return chr(10).join([rapid, *indic]) if indic else rapid


class NoSTT(STT):
    def transcribe(self, audio_path, *, lang=None) -> Transcript:
        return Transcript(language=None, segments=[])


class FasterWhisperSTT(STT):
    def __init__(self, size: str = "small"):
        from faster_whisper import WhisperModel  # optional dependency
        self.model = WhisperModel(size, compute_type="int8")

    def transcribe(self, audio_path, *, lang=None) -> Transcript:
        segs, info = self.model.transcribe(str(audio_path), language=lang, vad_filter=True)
        out = [Segment(int(s.start * 1000), int(s.end * 1000), s.text.strip()) for s in segs if s.text.strip()]
        return Transcript(language=info.language, segments=out)


class LocalStore(ObjectStore):
    """Filesystem object store. Replace with an S3/MinIO implementation of ObjectStore for production."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("bad key")
        return p

    def put_bytes(self, key, data):
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_file(self, key, src):
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(src), p)

    def exists(self, key):
        return self.path(key).exists()

    def original_key(self, base: str, ext: str) -> str:
        """Key of an asset's original file. Usually "<base>/original<ext of its filename>", but files stored by an
        earlier version may carry their real type's extension instead (photo.jfif -> original.jpg, a WebP named
        .jpeg -> original.webp), so fall back to whatever original.* is there."""
        exact = f"{base}/original{ext}"
        if self.exists(exact):
            return exact
        folder = self.path(base)
        found = sorted(folder.glob("original.*")) if folder.is_dir() else []
        return f"{base}/{found[0].name}" if found else exact

    def delete_prefix(self, prefix):
        p = self.path(prefix)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()
