import re
import uuid
from datetime import datetime, timezone

from langdetect import DetectorFactory, detect
from sqlalchemy import delete, event
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
    """Writes nothing until the pipeline commits (see clear_derived): new tags get their id up front instead of a flush."""
    pending = db.info.setdefault("clear", {})
    have = {t.tag_id for t in db.query(AssetTag).filter_by(asset_id=asset.id).all()
            if asset.id not in pending or (pending[asset.id] and t.source != "auto")}  # rows about to be cleared don't count
    have |= {at.tag_id for at in db.new if isinstance(at, AssetTag) and at.asset_id == asset.id}
    new_tags = db.info.setdefault("new_tags", {})
    for raw in names:
        name = raw.strip().lower()[:60]
        if not name:
            continue
        key = (asset.owner_id, name)
        tag = new_tags.get(key) or db.query(Tag).filter_by(owner_id=asset.owner_id, name=name).first()
        if not tag:
            tag = Tag(id=uuid.uuid4().hex, owner_id=asset.owner_id, name=name)
            db.add(tag)
            new_tags[key] = tag
        if tag.id not in have:
            db.add(AssetTag(asset_id=asset.id, tag_id=tag.id, source=source))
            have.add(tag.id)


def clear_derived(db: Session, asset: Asset, keep_user_tags: bool = True) -> None:
    """Drop the asset's chunks and auto tags - when the pipeline commits, not now.

    SQLite allows one writer at a time. Deleting here would take the write lock and keep it through OCR, captioning and
    the image model (seconds to minutes per file), so other uploads and workers failed with "database is locked".
    The deletes run in the same short final write as the new rows (see _apply_pending_clears)."""
    db.info.setdefault("clear", {})[asset.id] = keep_user_tags


@event.listens_for(Session, "before_flush")
def _apply_pending_clears(session: Session, *_):
    pending = session.info.pop("clear", None)
    if not pending:
        return
    conn = session.connection()
    for asset_id, keep_user_tags in pending.items():
        conn.execute(delete(Chunk).where(Chunk.asset_id == asset_id))
        q = delete(AssetTag).where(AssetTag.asset_id == asset_id)
        conn.execute(q.where(AssetTag.source == "auto") if keep_user_tags else q)


@event.listens_for(Session, "after_rollback")
def _forget_pending(session: Session):
    session.info.pop("clear", None)
    session.info.pop("new_tags", None)


@event.listens_for(Session, "after_commit")
def _forget_new_tags(session: Session):
    session.info.pop("new_tags", None)