"""Human titles and one-line descriptions for files people never named.

"8cc134c17728ba2bd33b99345f69552f.jpg" -> "Aadhaar card"; "images.jfif" -> "Beach"; "IMG_20251224.jpg" -> "Beach · Goa · Dec 2025";
"scan001.pdf" -> the heading printed on its first page. Used for display and indexed for search; the user's own
caption always wins.
"""
from __future__ import annotations

import re
from pathlib import Path

SCENE_TITLE = {"signature": "Signature", "beach": "Beach", "sunset": "Sunset", "snow": "Snowy scene", "greenery": "Greenery",
               "night": "Night scene", "sea": "Sea view", "sky": "Sky", "screenshot": "Screenshot", "document": "Document"}
SCENE_PHRASE = {"signature": "a handwritten signature", "beach": "a beach with sea and sand", "sunset": "a sunset sky",
                "snow": "a snowy scene", "greenery": "trees and greenery", "night": "a night-time scene", "sea": "open water",
                "sky": "open sky", "screenshot": "a screenshot", "document": "a document or card with printed text"}
for _key, (_prompts, _tags, _title, _phrase) in __import__("app.understanding.clip_labels", fromlist=["LABELS"]).LABELS.items():
    SCENE_TITLE.setdefault(_key, _title)  # what the image model can name (signature, robot, ID card ...)
    SCENE_PHRASE.setdefault(_key, _phrase)
JUNK = {"img", "image", "images", "photo", "pic", "dsc", "dscn", "pxl", "vid", "video", "mov", "whatsapp", "screenshot", "download",
        "downloads", "file", "files", "scan", "scanned", "untitled", "new", "document", "doc", "copy", "final", "edited", "optimized",
        "compressed", "resized", "scaled", "thumbnail", "unsplash", "pexels", "pixabay", "original", "export", "camera", "wa", "at", "pm", "am"}
KIND_WORD = {"photo": "Photo", "video": "Video", "document": "Document"}


SPECIFIC = ["signature", "beach", "sunset", "snow", "greenery", "night", "sea", "screenshot", "sky", "document"]


def ranked(cues: dict[str, float]) -> list[str]:
    """Strongest cue first; on a near-tie the more specific scene wins ("beach" over "sky")."""
    return sorted(cues, key=lambda k: (-round(cues[k], 1), SPECIFIC.index(k) if k in SPECIFIC else 99))


def meaningful_name(filename: str) -> str | None:
    """A readable title from the filename, or None when it's just a camera/hash/download name."""
    stem = Path(filename).stem
    words = []
    for w in re.split(r"[\s_\-.()\[\]]+", stem):
        lw = w.lower()
        if not w or lw in JUNK or w.isdigit():
            continue
        if re.fullmatch(r"[0-9a-f]{8,}", lw) or (re.search(r"\d", w) and re.search(r"[A-Za-z]", w) and len(w) >= 6):
            continue  # hashes and random ids ("8cc134c1...", "OobcCeOAH1k")
        if len(w) < 2:
            continue
        words.append(w if not w.islower() else w.capitalize())
    title = " ".join(words).strip()
    return title if len(title) >= 3 and sum(c.isalpha() for c in title) >= 3 else None


def _month(dt) -> str | None:
    return f"{dt:%b %Y}" if dt else None


def make_title(asset, *, doc_label: str | None, holder: str | None, cues: dict[str, float], details: list[dict]) -> str:
    if doc_label:
        return f"{doc_label} · {holder}" if holder else doc_label
    detail = {d["key"]: d["value"] for d in details or []}
    if asset.kind == "document":
        return detail.get("title") or meaningful_name(asset.filename) or "Document"
    scene = next((k for k in ranked(cues) if k in SCENE_TITLE and cues[k] >= 0.5 and k != "document"), None)
    name = meaningful_name(asset.filename)
    head = SCENE_TITLE[scene] if scene else (name or KIND_WORD.get(asset.kind, "File"))
    downloaded = re.search(r"[0-9a-f]{8,}|unsplash|pexels|pixabay|shutterstock|freepik|(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z\d]{8,}",
                           Path(asset.filename).stem, re.I)
    if name and scene and SCENE_TITLE[scene].lower() not in name.lower() and not downloaded:
        head = name  # a real name the person gave the file beats a guessed scene (not a stock-site download name)
    extras = [x for x in ((asset.place_name or "").split(",")[0] or None, _month(asset.taken_at)) if x and x.lower() not in head.lower()]
    return " · ".join([head, *extras])


def make_caption(asset, *, doc_label: str | None, holder: str | None, cues: dict[str, float], summary: str | None = None,
                 text: str = "") -> str:
    parts: list[str] = []
    if doc_label:
        parts.append(f"{doc_label}{f' of {holder}' if holder else ''}.")
    elif asset.kind == "document" and summary:
        s = re.split(r"(?<=[.!?।])\s+", summary.strip())
        parts.append((s[1] if len(s) > 1 and len(s[0]) < 40 else s[0])[:200])
    else:
        seen = [SCENE_PHRASE[k] for k in ranked(cues) if k in SCENE_PHRASE and cues[k] >= 0.5]
        if "beach" in cues:
            seen = [p for p in seen if p not in (SCENE_PHRASE["sea"], SCENE_PHRASE["sky"])]
        if seen:
            kind = "video" if asset.kind == "video" else "photo"
            parts.append(f"A {kind} showing {' and '.join(seen[:2])}.")
        elif text and len(text.split()) >= 4:
            parts.append(f"Contains the text “{' '.join(text.split()[:10])}…”.")
    when = f"{asset.taken_at:%d %b %Y}" if asset.taken_at else None
    where = (asset.place_name or "").split(",")[0] or None
    if asset.kind != "document" and (when or where):
        parts.append("Taken" + (f" on {when}" if when else "") + (f" in {where}" if where else "") + ".")
    return " ".join(parts)
