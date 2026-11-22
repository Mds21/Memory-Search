import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from .. import geo
from ..adapters import registry
from ..config import get_settings
from ..models import Asset
from ..understanding import understand
from ..understanding.visual import analyze
from .common import add_chunk, add_image_chunk, clear_derived, date_from_filename, detect_lang, upsert_tags

try:  # optional HEIC support
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass


def _rational(v) -> float:
    try:
        return float(v)
    except Exception:
        return float(v[0]) / float(v[1])


def _gps(exif) -> tuple[float, float] | None:
    try:
        g = exif.get_ifd(0x8825)
        if not g or 2 not in g or 4 not in g:
            return None
        lat = sum(_rational(x) / 60 ** i for i, x in enumerate(g[2]))
        lon = sum(_rational(x) / 60 ** i for i, x in enumerate(g[4]))
        if g.get(1) == "S":
            lat = -lat
        if g.get(3) == "W":
            lon = -lon
        return lat, lon
    except Exception:
        return None


def _taken(exif) -> datetime | None:
    try:
        raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if raw:
            return datetime.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def make_thumbs(img: Image.Image, base: str, store) -> None:
    for name, size in (("thumb", 256), ("preview", 1000)):
        t = img.copy()
        t.thumbnail((size, size))
        buf = io.BytesIO()
        t.convert("RGB").save(buf, "WEBP", quality=80)
        store.put_bytes(f"{base}/{name}.webp", buf.getvalue())


def describe_and_index(db: Session, asset: Asset, img: Image.Image, *, chunk_type: str = "caption", **kw):
    """VLM describe + OCR + embeddings for one image (photo or video keyframe)."""
    cfg = get_settings()
    buf = io.BytesIO()
    small = img.copy()
    small.thumbnail((1024, 1024))
    small.convert("RGB").save(buf, "JPEG", quality=85)
    data = buf.getvalue()

    hint = ""
    if chunk_type == "caption":
        stem = Path(asset.filename).stem.replace("_", " ").replace("-", " ")
        hint = "" if stem.replace(" ", "").isdigit() or stem.upper().startswith(("IMG", "DSC", "PXL")) else stem
    desc = registry.vlm().describe(data, hint=hint)

    # OCR first: the visual cues use it (a signature has no text, a card has lots)
    visible = desc.visible_text or ""
    if not visible and cfg.ocr_photos and registry.ocr().available:
        visible = registry.ocr().ocr_image(img, quick=chunk_type != "caption")  # keyframes: one fast pass
    cues = analyze(img, ocr_text=visible)
    desc.tags = list(dict.fromkeys([*desc.tags, *cues.tags]))
    desc.visible_text = visible
    desc.cues = cues.scores

    parts = [desc.caption]
    if cues.sentence:
        parts.append(cues.sentence)
    if asset.place_name:
        parts.append(f"Taken in {asset.place_name}.")
    if asset.taken_at:
        parts.append(f"Date: {asset.taken_at:%B %Y}.")
    if desc.objects:
        parts.append("Objects: " + ", ".join(desc.objects) + ".")
    text = " ".join(parts)
    add_chunk(db, asset, chunk_type, text, embed_text=text + " " + " ".join(desc.tags), meta={"tags": desc.tags}, **kw)
    add_image_chunk(db, asset, data, chunk_type="video_frame" if chunk_type == "video_frame" else "image", **kw)

    flat = " ".join(visible.split())
    if len(flat) >= 8:
        add_chunk(db, asset, "ocr_text", flat, language=detect_lang(flat), **kw)
    return desc


SCENE_NAMES = {"beach": "Beach", "sea": "Sea", "sky": "Sky", "greenery": "Greenery", "snow": "Snow", "sunset": "Sunset",
               "night": "Night", "signature": "Signature", "document": "Document or card", "screenshot": "Screenshot"}


def _camera(exif) -> str | None:
    make, model = str(exif.get(271, "") or "").strip(" \x00"), str(exif.get(272, "") or "").strip(" \x00")
    if model.lower().startswith(make.lower()):
        make = ""
    cam = " ".join(x for x in (make.title() if make.isupper() else make, model) if x)
    return cam or None


def photo_details(asset: Asset, exif, desc) -> list[dict]:
    """Plain-language facts about a photo (no pixel counts or formats): when, where, what device, what's in it."""
    out = []
    if asset.taken_at:
        out.append({"key": "taken_on", "label": "Taken on", "value": f"{asset.taken_at:%d %b %Y}"})
    if asset.place_name:
        out.append({"key": "place", "label": "Place", "value": asset.place_name})
    cam = _camera(exif)
    if cam:
        out.append({"key": "camera", "label": "Camera", "value": cam})
    scene = [SCENE_NAMES[k] for k in sorted(desc.cues, key=lambda k: -desc.cues[k]) if k in SCENE_NAMES]
    if scene:
        out.append({"key": "scene", "label": "Looks like", "value": ", ".join(scene[:3])})
    if desc.cues.get("document", 0) >= 0.5 or desc.cues.get("screenshot", 0) >= 0.5:  # real text, not OCR noise on art/texture
        out.append({"key": "has_text", "label": "Contains text", "value": "Yes"})
    return out


def ingest_photo(db: Session, asset: Asset, src: Path) -> None:
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    try:
        img = Image.open(src)
        exif = img.getexif()
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise ValueError("We couldn't open this picture. It may be damaged or in a format we can't read yet.") from e

    asset.width, asset.height = img.size
    asset.taken_at = _taken(exif) or date_from_filename(asset.filename) or asset.taken_at
    gps = _gps(exif)
    if gps:
        asset.lat, asset.lon = gps
        asset.place_name = geo.reverse(*gps)
    asset.meta = {**(asset.meta or {}), "camera": str(exif.get(272, "") or "") + " " + str(exif.get(271, "") or "")}
    make_thumbs(img, base, store)
    asset.has_thumb = True
    asset.status_detail = "indexing"
    db.commit()  # progressive availability: browsable now, searchable once indexing completes

    clear_derived(db, asset)
    desc = describe_and_index(db, asset, img)
    upsert_tags(db, asset, desc.tags)
    understand(db, asset, text=desc.visible_text or "", visual_scores=desc.cues,
               extra_text=" ".join([desc.caption, *desc.tags]) if registry.vlm().name != "basic" else "",
               file_facts=photo_details(asset, exif, desc))
    if asset.place_name:
        upsert_tags(db, asset, [asset.place_name.split(",")[0]])
