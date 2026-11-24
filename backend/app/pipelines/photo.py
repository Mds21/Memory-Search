import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from .. import geo
from ..adapters import registry
from ..config import get_settings
from ..models import Asset
from ..adapters.embeddings import from_blob
from ..understanding import clip_labels, understand, visual
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
    img_chunk = add_image_chunk(db, asset, data, chunk_type="video_frame" if chunk_type == "video_frame" else "image", **kw)

    raw_text = desc.visible_text or ""
    if not raw_text and cfg.ocr_photos and registry.ocr().available:
        # own temp file per call (workers run in parallel); confident words only, so plain photos add no noise
        raw_text = registry.ocr().ocr_image(img, min_conf=cfg.ocr_min_conf)
    visible = " ".join(raw_text.split())

    # What the picture shows: the image model's labels ("a handwritten signature", "a robot"), else pixel heuristics
    found = clip_labels.labels(from_blob(img_chunk.image_embedding), registry.image_embedder()) if img_chunk is not None else []
    cues = clip_labels.as_cues(found) if found else visual.analyze(img, ocr_text=raw_text).scores
    shows = [clip_labels.LABELS[k][3] if k in clip_labels.LABELS else visual.CUE_TEXT[k][1] for k in cues
             if k in clip_labels.LABELS or k in visual.CUE_TEXT]
    label_tags = [t for k in cues for t in (clip_labels.LABELS[k][1] if k in clip_labels.LABELS else visual.CUE_TEXT.get(k, ([],))[0])]
    desc.tags = list(dict.fromkeys([*label_tags, *desc.tags]))
    if "id_card" in cues:
        cues.setdefault("document", cues["id_card"])  # document types keyed on "document" apply to cards too

    parts = [f"Shows {', '.join(dict.fromkeys(shows))}." if shows else "", desc.caption]
    if asset.place_name:
        parts.append(f"Taken in {asset.place_name}.")
    if asset.taken_at:
        parts.append(f"Date: {asset.taken_at:%B %Y}.")
    if desc.objects:
        parts.append("Objects: " + ", ".join(desc.objects) + ".")
    text = " ".join(p for p in parts if p)
    add_chunk(db, asset, chunk_type, text, embed_text=text + " " + " ".join(desc.tags), meta={"tags": desc.tags}, **kw)
    if len(visible) >= 8:
        add_chunk(db, asset, "ocr_text", visible, language=detect_lang(visible), **kw)

    if chunk_type == "caption":  # the photo itself (not a video frame): what it is and whose
        asset.meta = {**(asset.meta or {}), "labels": list(cues), "shows": list(dict.fromkeys(shows))}
        understand(db, asset, text=raw_text, visual_scores=cues)
    return desc


def ingest_photo(db: Session, asset: Asset, src: Path) -> None:
    store = registry.store()
    base = f"{asset.owner_id}/{asset.id}"
    try:
        img = Image.open(src)
        exif = img.getexif()
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise ValueError(f"Cannot read image ({e}). HEIC needs pillow-heif installed.") from e

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
    if asset.place_name:
        upsert_tags(db, asset, [asset.place_name.split(",")[0]])
