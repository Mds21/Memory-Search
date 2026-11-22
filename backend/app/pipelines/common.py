import re
from datetime import datetime, timezone

from langdetect import DetectorFactory, detect
from sqlalchemy.orm import Session

from ..adapters import registry
from ..adapters.embeddings import to_blob
from ..models import Asset, AssetTag, Chunk, Tag

DetectorFactory.seed = 0
_FN_DATE = re.compile(r"(?<!\d)(20\d{2}|19\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)")


def date_from_filename(name: str) -> datetime | None:
    m = _FN_DATE.search(name)
    if not m:
        return None
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
    except ValueError:
        return None


def detect_lang(text: str) -> str | None:
    t = (text or "").strip()
    if len(t) < 20:
        return None
    try:
        return detect(t[:2000])
    except Exception:
        return None


def add_chunk(db: Session, asset: Asset, chunk_type: str, content: str | None, *, embed: bool = True,
              embed_text: str | None = None, **kw) -> Chunk:
    c = Chunk(asset_id=asset.id, owner_id=asset.owner_id, chunk_type=chunk_type, content=content, **kw)
    if embed and (embed_text or content):
        te = registry.text_embedder()
        c.text_embedding = to_blob(te.embed([embed_text or content], kind="passage")[0])
        c.emb_model = te.name
    db.add(c)
    return c


def add_image_chunk(db: Session, asset: Asset, image_bytes: bytes, chunk_type: str = "image", **kw):
    ie = registry.image_embedder()
    if not ie:
        return None
    c = Chunk(asset_id=asset.id, owner_id=asset.owner_id, chunk_type=chunk_type, content=None, **kw)
    c.image_embedding = to_blob(ie.embed_images([image_bytes])[0])
    c.img_model = ie.name
    db.add(c)
    return c


def upsert_tags(db: Session, asset: Asset, names: list[str], source: str = "auto") -> None:
    db.flush()  # sessions don't autoflush: make tags added by an earlier call in this ingest visible to the query below
    have = {t.tag_id for t in db.query(AssetTag).filter_by(asset_id=asset.id).all()}
    for raw in names:
        name = raw.strip().lower()[:60]
        if not name:
            continue
        tag = db.query(Tag).filter_by(owner_id=asset.owner_id, name=name).first()
        if not tag:
            tag = Tag(owner_id=asset.owner_id, name=name)
            db.add(tag)
            db.flush()
        if tag.id not in have:
            db.add(AssetTag(asset_id=asset.id, tag_id=tag.id, source=source))
            have.add(tag.id)


def clear_derived(db: Session, asset: Asset, keep_user_tags: bool = True) -> None:
    db.query(Chunk).filter_by(asset_id=asset.id).delete()
    q = db.query(AssetTag).filter_by(asset_id=asset.id)
    if keep_user_tags:
        q = q.filter(AssetTag.source == "auto")
    q.delete()
    db.flush()
