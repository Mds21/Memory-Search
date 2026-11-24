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

    @property
    def available(self) -> bool:
        return bool(self.bin and self.langs)

    def ocr(self, image_path: Path, langs: list[str] | None = None, psm: int = 3, min_conf: float = 0) -> str:
        """Text in an image. min_conf > 0 keeps only words Tesseract is at least that sure of (0-100), so an ordinary
        photo with no writing yields nothing instead of stray characters."""
        if not self.available:
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
        """OCR a PIL image (e.g. a picture inside a Word file or slide). quick: English plus Hindi only, smaller image."""
        if not self.available:
            return ""
        import tempfile
        img = img.convert("L")
        img.thumbnail((1400, 1400) if quick else (2400, 2400))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "page.png"
            img.save(p)
            use = langs or ([l for l in ("eng", "hin") if l in self.langs] or self.langs if quick else None)
            return self.ocr(p, use, min_conf=min_conf)


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
