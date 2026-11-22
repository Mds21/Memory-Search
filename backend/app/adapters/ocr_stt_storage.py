import os
import re
import shutil
import subprocess
import tempfile
import threading
import logging
from pathlib import Path

from .base import OCREngine, ObjectStore, STT, Segment, Transcript


def _find_tesseract(explicit: str | None = None) -> str | None:
    """PATH first, then the usual install folders (the Windows installer does not add itself to PATH)."""
    if explicit and Path(explicit).exists():
        return explicit
    found = shutil.which("tesseract")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        p = Path(base) / "Tesseract-OCR" / "tesseract.exe"
        if p.exists():
            return str(p)
    for p in ("/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"):
        if Path(p).exists():
            return p
    return None


_WORDISH = re.compile(r"[A-Za-zऀ-෿]{3,}|\d{4,}")


def _quality(text: str) -> int:
    """Rough count of plausible words/numbers: used to keep good OCR passes and drop noise."""
    return len(_WORDISH.findall(text))


log = logging.getLogger(__name__)

class TesseractOCR(OCREngine):
    """Calls the tesseract CLI. Uses only the language packs actually installed."""

    def __init__(self, wanted: str = "eng+hin+mar+tam+spa", cmd: str | None = None):
        self.bin = _find_tesseract(cmd)
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

    def _run(self, img, psm: str) -> str:
        fd, name = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            img.save(name)
            r = subprocess.run([self.bin, name, "stdout", "-l", "+".join(self.langs), "--psm", psm],
                               capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120)
            return r.stdout
        except Exception:
            return ""
        finally:
            Path(name).unlink(missing_ok=True)

    def ocr_image(self, img, quick: bool = False) -> str:
        """Multi-pass OCR for photos of cards, screenshots and scans.

        Phone photos of ID cards have tinted/textured backgrounds and uneven light, which defeat plain OCR.
        Dividing the image by a blurred copy of itself flattens the background so the text stands out; small
        screenshots are upscaled first. Passes that read plausible words are kept and merged.
        """
        if not self.available:
            return ""
        import numpy as np
        from PIL import Image, ImageFilter
        g = img.convert("L")
        w, h = g.size
        scale = min(3.0, max(1.0, 1800 / max(w, h)))
        if scale > 1.05:
            g = g.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        elif max(w, h) > 2600:
            g.thumbnail((2600, 2600))
        a = np.asarray(g, dtype=np.float32)
        bg = np.asarray(g.filter(ImageFilter.GaussianBlur(max(8, int(max(g.size) / 70)))), dtype=np.float32) + 1.0
        flat = Image.fromarray(np.clip(a / bg * 235.0, 0, 255).astype(np.uint8))
        passes = [(flat, "3")] if quick else [(flat, "3"), (flat, "11"), (g, "3")]
        texts: list[str] = []
        best = 0
        for im, psm in passes:
            t = self._run(im, psm)
            q = _quality(t)
            if q >= 2:
                texts.append(t)
                best = max(best, q)
            if best >= 25 and len(texts) >= 2:
                break  # plenty of text already
        lines, seen = [], set()
        for t in texts:
            for ln in t.splitlines():
                key = " ".join(ln.split()).lower()
                if key and _quality(key) and key not in seen:
                    seen.add(key)
                    lines.append(" ".join(ln.split()))
        return "\n".join(lines)


class NoSTT(STT):
    def transcribe(self, audio_path, *, lang=None) -> Transcript:
        return Transcript(language=None, segments=[])


class FasterWhisperSTT(STT):
    """Offline speech-to-text. The model (base ~145 MB) downloads once, on the first video with sound, then runs locally."""

    def __init__(self, size: str = "base"):
        self.size, self._model, self._failed = size, None, False
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None and not self._failed:
                try:
                    from faster_whisper import WhisperModel  # optional dependency
                    self._model = WhisperModel(self.size, device="cpu", compute_type="int8")
                except Exception:
                    self._failed = True  # e.g. offline on first run: videos still index, just without speech
                    log.exception("speech model %s could not be loaded; videos will be indexed without speech", self.size)
        return self._model

    def transcribe(self, audio_path, *, lang=None) -> Transcript:
        model = self._load()
        if model is None:
            return Transcript(language=None, segments=[])
        with self._lock:  # one transcription at a time keeps CPU and memory predictable
            segs, info = model.transcribe(str(audio_path), language=lang, vad_filter=True, beam_size=1)
            out = [Segment(int(s.start * 1000), int(s.end * 1000), s.text.strip()) for s in segs if s.text.strip()]
        # very short or music-only clips: whisper's language guess is unreliable
        return Transcript(language=info.language if out and info.language_probability >= 0.5 else None, segments=out)


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

    def delete_prefix(self, prefix):
        p = self.path(prefix)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()
