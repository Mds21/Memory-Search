"""Vision-language adapters. `BasicVLM` is an offline heuristic describer (colour/brightness/shape);
for real captions use VLM=ollama:qwen2.5vl:3b."""
import base64
import io
import json

import httpx
from PIL import Image, ImageStat

from .base import ImageDescription, VisionLanguageModel

_COLORS = {
    "red": (200, 40, 40), "orange": (230, 130, 30), "yellow": (230, 210, 50), "green": (60, 160, 70),
    "blue": (50, 100, 210), "purple": (130, 70, 170), "pink": (235, 130, 170), "brown": (120, 80, 50),
    "white": (240, 240, 240), "gray": (128, 128, 128), "black": (20, 20, 20),
}


def _nearest(rgb):
    return min(_COLORS, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, _COLORS[k])))


class BasicVLM(VisionLanguageModel):
    name = "basic"

    def describe(self, image: bytes, *, hint: str = "") -> ImageDescription:
        im = Image.open(io.BytesIO(image)).convert("RGB")
        w, h = im.size
        small = im.resize((48, 48))
        q = small.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()[:12]
        counts = sorted(q.getcolors(), reverse=True)
        names: list[str] = []
        for _, idx in counts:
            n = _nearest(tuple(pal[idx * 3:idx * 3 + 3]))
            if n not in names:
                names.append(n)
        lum = ImageStat.Stat(small.convert("L")).mean[0]
        tone = "bright" if lum > 170 else "dark" if lum < 70 else "balanced"
        shape = "landscape" if w > h * 1.15 else "portrait" if h > w * 1.15 else "square"
        colors = names[:3]
        caption = f"A {tone} {shape} photo with mostly {' and '.join(colors)} tones."
        if hint:
            caption = f"{hint}. {caption}"
        return ImageDescription(caption=caption, tags=[*colors, tone, shape], objects=[])


class OllamaVLM(VisionLanguageModel):
    PROMPT = ('Describe this image for a photo search index. Reply ONLY with JSON: '
              '{"caption": "one or two sentences", "tags": ["up to 10 short tags"], '
              '"objects": ["visible objects"], "visible_text": "text visible in the image or empty"}')

    def __init__(self, model: str, base_url: str):
        self.model, self.base = model, base_url.rstrip("/")
        self.name = f"ollama-{model}"

    def describe(self, image: bytes, *, hint: str = "") -> ImageDescription:
        im = Image.open(io.BytesIO(image)).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        r = httpx.post(f"{self.base}/api/chat", timeout=300, json={
            "model": self.model, "stream": False, "format": "json",
            "messages": [{"role": "user", "content": self.PROMPT, "images": [base64.b64encode(buf.getvalue()).decode()]}],
        })
        r.raise_for_status()
        try:
            d = json.loads(r.json()["message"]["content"])
        except Exception:
            return ImageDescription(caption=r.json()["message"]["content"][:400])
        return ImageDescription(caption=str(d.get("caption", ""))[:600], tags=[str(t) for t in d.get("tags", [])][:12],
                                objects=[str(t) for t in d.get("objects", [])][:12],
                                visible_text=(d.get("visible_text") or None))
