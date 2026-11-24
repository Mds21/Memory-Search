import shutil
import subprocess
from pathlib import Path

from .base import OCREngine, ObjectStore, STT, Segment, Transcript


class TesseractOCR(OCREngine):
    """Calls the tesseract CLI. Uses only the language packs actually installed."""

    def __init__(self, wanted: str = "eng+hin+mar+tam+spa"):
        self.bin = shutil.which("tesseract")
        have: set[str] = set()
        if self.bin:
            out = subprocess.run([self.bin, "--list-langs"], capture_output=True, text=True).stdout.split()
            have = set(out)
        self.langs = [l for l in wanted.split("+") if l in have] or (["eng"] if "eng" in have else [])

    @property
    def available(self) -> bool:
        return bool(self.bin and self.langs)

    def ocr(self, image_path: Path, langs: list[str] | None = None) -> str:
        if not self.available:
            return ""
        use = "+".join(langs or self.langs)
        try:
            r = subprocess.run([self.bin, str(image_path), "stdout", "-l", use, "--psm", "3"],
                               capture_output=True, text=True, timeout=120)
            return r.stdout.strip()
        except Exception:
            return ""


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
