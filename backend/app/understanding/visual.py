"""Offline visual cues from pixel statistics (no model download).

Recognises things a colour-only describer can't: handwritten signatures, scanned/ID-card-like documents,
screenshots, and broad outdoor scenes (beach/sea, sky, greenery, snow, sunset, night). Each cue has a score
in 0..1; callers keep cues above a threshold. When a real VLM is configured its tags are merged on top.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image


@dataclass
class VisualCues:
    scores: dict[str, float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    sentence: str = ""

    def has(self, cue: str, at: float = 0.5) -> bool:
        return self.scores.get(cue, 0.0) >= at


# cue -> (tags added to the asset, phrase used in the caption)
CUE_TEXT = {
    "signature": (["signature", "handwritten signature", "sign", "autograph"], "a handwritten signature on a plain background"),
    "document": (["document", "scan", "paper"], "a document or card with printed text"),
    "screenshot": (["screenshot"], "a phone or computer screenshot"),
    "beach": (["beach", "sea", "ocean", "coast", "sand", "shore", "seaside"], "a beach with sea and sand"),
    "sea": (["sea", "ocean", "water"], "open water"),
    "sky": (["sky", "outdoor"], "open sky"),
    "greenery": (["greenery", "nature", "trees", "plants", "outdoor"], "trees or greenery"),
    "snow": (["snow", "winter", "mountains"], "snow"),
    "sunset": (["sunset", "sunrise", "golden hour", "evening sky"], "a sunset or sunrise sky"),
    "night": (["night", "dark"], "a night or low-light scene"),
}


def _hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """rgb float 0..1 (H,W,3) -> hue degrees, saturation, value."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn + 1e-6
    h = np.where(mx == r, (g - b) / d % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx


def _frac(mask: np.ndarray) -> float:
    return float(mask.mean()) if mask.size else 0.0


def analyze(img: Image.Image, *, ocr_text: str = "") -> VisualCues:
    im = img.convert("RGB")
    im.thumbnail((256, 256))
    a = np.asarray(im, dtype=np.float32) / 255.0
    H, W = a.shape[:2]
    h, s, v = _hsv(a)
    gray = a.mean(-1)
    sc: dict[str, float] = {}
    words = len([w for w in ocr_text.split() if sum(c.isalnum() for c in w) >= 3])
    # OCR invents short junk words on textures/art; real text comes as lines of several words
    text_lines = sum(1 for ln in ocr_text.splitlines() if len([w for w in ln.split() if sum(c.isalnum() for c in w) >= 2]) >= 3)

    # --- signature: bright, near-uniform background + a small amount of thin, single-coloured ink ---
    bg = float(np.median(gray))
    ink = np.abs(gray - bg) > 0.25
    ink_frac = _frac(ink)
    bg_px = ~ink
    bg_flat = float(gray[bg_px].std()) if bg_px.any() else 1.0
    if bg > 0.78 and bg_flat < 0.06 and 0.003 < ink_frac < 0.15:
        ink_rgb = a[ink]
        # ink is one colour (blue/black pen), not a multi-coloured graphic
        colour_spread = float(ink_rgb.std(0).mean()) if len(ink_rgb) > 10 else 1.0
        rows, cols = np.where(ink)
        span_w = (cols.max() - cols.min() + 1) / W if len(cols) else 0
        span_h = (rows.max() - rows.min() + 1) / H if len(rows) else 0
        fill = ink_frac / max(span_w * span_h, 1e-3)  # strokes cover little of their own bounding box
        score = 0.35
        score += 0.2 if colour_spread < 0.12 else 0
        score += 0.2 if fill < 0.25 else 0
        score += 0.1 if span_w > span_h else 0
        score += 0.15 if words <= 2 else (-0.3 if words > 6 else 0)
        sc["signature"] = min(1.0, score)

    # --- document / card: lots of printed text ---
    if text_lines >= 4 and words >= 12:
        sc["document"] = min(1.0, 0.4 + text_lines / 20)

    # --- screenshot: status-bar-like dark band on a tall image, very flat regions ---
    if H > W * 1.5:
        top = gray[: max(2, H // 30)]
        if float(top.std()) < 0.12 and (float(top.mean()) < 0.25 or float(top.mean()) > 0.9):
            sc["screenshot"] = 0.6

    # --- outdoor scenes (skip for near-greyscale images: art, scans) ---
    if float(s.mean()) > 0.12:
        top, mid, bot = slice(0, H // 3), slice(H // 3, 2 * H // 3), slice(2 * H // 3, H)
        blue = (h >= 185) & (h <= 250) & (s > 0.2) & (v > 0.45)
        turq = (h >= 160) & (h <= 210) & (s > 0.25) & (v > 0.4)
        sand = (h >= 20) & (h <= 55) & (s > 0.06) & (s < 0.5) & (v > 0.62)
        white_sand = (s < 0.12) & (v > 0.85)
        green = (h >= 70) & (h <= 165) & (s > 0.2) & (v > 0.15)
        warm = ((h <= 45) | (h >= 330)) & (s > 0.45) & (v > 0.45)
        sky = _frac(blue[top]) + 0.5 * _frac(((s < 0.15) & (v > 0.85))[top]) * _frac(blue[top] | turq[top])
        water = max(_frac(turq[mid]), _frac(blue[mid]))
        shore = max(_frac(sand[bot]), _frac(white_sand[bot]) * 0.8, _frac(sand[mid]) * 0.7)
        if sky > 0.25:
            sc["sky"] = min(1.0, sky * 1.4)
        if water > 0.2:
            sc["sea"] = min(1.0, water * 1.5)
        if water > 0.15 and shore > 0.12:
            sc["beach"] = min(1.0, 0.45 + water + shore * 0.8 + (0.1 if sky > 0.2 else 0))
        if _frac(green) > 0.3:
            sc["greenery"] = min(1.0, _frac(green) * 1.3)
        if _frac(warm[top]) > 0.3 and float(v.mean()) < 0.75:
            sc["sunset"] = min(1.0, _frac(warm[top]) * 1.4)
        if _frac(((s < 0.1) & (v > 0.88))[bot]) > 0.55 and _frac(blue[top] | ((s < 0.1) & (v > 0.8))[top]) > 0.4 and water < 0.15:
            sc["snow"] = 0.55
    if float(v.mean()) < 0.18:
        sc["night"] = 0.6

    kept = {k: round(x, 2) for k, x in sc.items() if x >= 0.5}
    tags: list[str] = []
    for k in sorted(kept, key=lambda k: -kept[k]):
        for t in CUE_TEXT[k][0]:
            if t not in tags:
                tags.append(t)
    phrases = [CUE_TEXT[k][1] for k in sorted(kept, key=lambda k: -kept[k]) if k not in ("sky", "sea") or "beach" not in kept]
    sentence = ("Looks like " + ", ".join(phrases[:3]) + ".") if phrases else ""
    return VisualCues(scores=kept, tags=tags, sentence=sentence)
