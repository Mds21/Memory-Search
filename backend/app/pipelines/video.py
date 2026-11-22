import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from .. import geo
from ..adapters import registry
from ..config import get_settings
from ..models import Asset
from .common import add_chunk, clear_derived, date_from_filename, detect_lang, upsert_tags
from .photo import describe_and_index, make_thumbs


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: Path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise ValueError("We couldn't open this video. It may be damaged or in a format we can't read yet.")
    return json.loads(r.stdout)


def _iso6709(s: str) -> tuple[float, float] | None:
    import re
    m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", s or "")
    return (float(m[1]), float(m[2])) if m else None


def frame_at(path: Path, t: float) -> Image.Image | None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "f.jpg"
        _run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-q:v", "3", str(out)], 120)
        return Image.open(out).convert("RGB") if out.exists() else None


def _length(ms: int) -> str:
    s = round(ms / 1000)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h} h {m} min" if h else f"{m} min {s} s" if m else f"{s} s"


def video_details(asset: Asset, tags: dict, has_audio: bool, has_speech: bool, screen_text: list[str]) -> list[dict]:
    """Plain-language facts: when, where, how long, what device, whether it has sound, speech or on-screen text."""
    out = []
    if asset.taken_at:
        out.append({"key": "taken_on", "label": "Recorded on", "value": f"{asset.taken_at:%d %b %Y}"})
    if asset.place_name:
        out.append({"key": "place", "label": "Place", "value": asset.place_name})
    if asset.duration_ms:
        out.append({"key": "length", "label": "Length", "value": _length(asset.duration_ms)})
    dev = " ".join(x for x in (tags.get("com.apple.quicktime.make") or tags.get("make") or "",
                               tags.get("com.apple.quicktime.model") or tags.get("model") or "") if x).strip()
    if dev:
        out.append({"key": "camera", "label": "Camera", "value": dev})
    if asset.width and asset.height:
        out.append({"key": "orientation", "label": "Shape", "value": "Portrait" if asset.height > asset.width else "Landscape"})
    out.append({"key": "sound", "label": "Sound", "value": ("Has speech" if has_speech else "Yes") if has_audio else "No sound"})
    if screen_text:
        out.append({"key": "has_text", "label": "Text on screen", "value": "Yes"})
    return out


def ingest_video(db: Session, asset: Asset, src: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise ValueError("Videos can't be processed on this server right now.")
    cfg = get_settings()
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    info = probe(src)
    vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not vs:
        raise ValueError("This file doesn't contain any video.")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    dur = float(info["format"].get("duration") or vs.get("duration") or 0)
    tags = {k.lower(): v for k, v in (info["format"].get("tags") or {}).items()}

    asset.duration_ms = int(dur * 1000)
    asset.width, asset.height = vs.get("width"), vs.get("height")
    ct = tags.get("creation_time")
    if ct:
        try:
            asset.taken_at = datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    asset.taken_at = asset.taken_at or date_from_filename(asset.filename)
    loc = _iso6709(tags.get("location") or tags.get("com.apple.quicktime.location.iso6709", ""))
    if loc:
        asset.lat, asset.lon = loc
        asset.place_name = geo.reverse(*loc)

    poster = frame_at(src, min(1.0, dur / 2))
    if poster:
        make_thumbs(poster, base, store)
        asset.has_thumb = True

    # Browser-playable proxy (H.264/AAC MP4) when the source is not already
    web_ok = vs.get("codec_name") == "h264" and src.suffix.lower() in {".mp4", ".m4v", ".mov"} and \
        all(s.get("codec_name") == "aac" for s in info["streams"] if s["codec_type"] == "audio")
    if not web_ok:
        asset.status_detail = "transcoding"
        db.commit()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "proxy.mp4"
            r = _run(["ffmpeg", "-y", "-i", str(src), "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
                      "-crf", "28", "-c:a", "aac", "-movflags", "+faststart", str(out)], 3600)
            if r.returncode == 0 and out.exists():
                store.put_file(f"{base}/proxy.mp4", out)
                asset.has_proxy = True
    asset.status_detail = "indexing"
    db.commit()

    clear_derived(db, asset)
    # Keyframes: evenly spaced, at most MAX_KEYFRAMES, at least every 30 s
    n = max(1, min(cfg.max_keyframes, int(dur // 5) + 1))
    step = dur / n if dur > 0 else 0
    times = [step * i + step / 2 for i in range(n)] if dur > 0 else [0]
    all_tags: list[str] = []
    cues: dict[str, float] = {}
    screen_text: list[str] = []
    spoken = ""
    for i, t in enumerate(times):
        fr = frame_at(src, t)
        if fr is None:
            continue
        end = int((times[i + 1] if i + 1 < len(times) else dur) * 1000)
        d = describe_and_index(db, asset, fr, chunk_type="video_frame", start_ms=int(t * 1000), end_ms=end)
        all_tags += d.tags
        flat = " ".join((d.visible_text or "").split())
        if len(flat) >= 8 and flat not in screen_text:
            screen_text.append(flat)
        for k, v in (d.cues or {}).items():
            cues[k] = max(cues.get(k, 0.0), v)
    # Speech (when an STT adapter is configured)
    if has_audio:
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "a.wav"
            _run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)], 1800)
            if wav.exists():
                tr = registry.stt().transcribe(wav)
                spoken = " ".join(s.text for s in tr.segments)
                asset.language = tr.language
                win: list = []
                for seg in tr.segments:
                    win.append(seg)
                    if seg.end_ms - win[0].start_ms >= 30000:
                        txt = " ".join(s.text for s in win)
                        add_chunk(db, asset, "transcript", txt, start_ms=win[0].start_ms, end_ms=win[-1].end_ms, language=detect_lang(txt))
                        win = win[-1:]  # one-segment overlap
                if len(win) > 1 or (win and not tr.segments[:-1]):
                    txt = " ".join(s.text for s in win)
                    add_chunk(db, asset, "transcript", txt, start_ms=win[0].start_ms, end_ms=win[-1].end_ms, language=detect_lang(txt))
    top = [t for t, _ in sorted(((t, all_tags.count(t)) for t in set(all_tags)), key=lambda x: -x[1])][:8]
    upsert_tags(db, asset, [*top, "video"])
    from ..understanding import understand
    understand(db, asset, text="\n".join(screen_text)[:20000], visual_scores=cues, extra_text=spoken[:5000],
               file_facts=video_details(asset, tags, has_audio, bool(spoken), screen_text))
