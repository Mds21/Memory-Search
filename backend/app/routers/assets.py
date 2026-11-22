import os
import time
import hashlib
import mimetypes
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import registry
from ..adapters.embeddings import cosine_matrix, from_blob
from ..config import get_settings
from ..db import get_db
from ..models import Asset, AssetTag, Chunk, Tag
from ..pipelines import runner
from ..pipelines.common import add_chunk, upsert_tags
from ..schemas import AssetPatch
from ..search.query_parser import Filters
from ..search.retrieval import asset_card, candidate_assets, tags_for
from ..security import current_user, media_url, verify_media
from .common import owned_asset

router = APIRouter(tags=["assets"])

from ..filetypes import DOC_EXT as DOC, PHOTO_EXT as PHOTO, VIDEO_EXT as VIDEO, classify as classify_file  # noqa: E402


def kind_of(filename: str) -> str | None:
    """Extension-only guess (used where no bytes are available). Uploads use `classify_file`, which sniffs content."""
    e = Path(filename).suffix.lower()
    return "photo" if e in PHOTO else "video" if e in VIDEO else "document" if e in DOC else None


def detail(db: Session, a: Asset) -> dict:
    c = asset_card(a, tags_for(db, [a.id]).get(a.id))
    c["original_url"] = media_url(a.id, "original")
    c["video_url"] = media_url(a.id, "video") if a.kind == "video" else None
    c["size_bytes"] = a.size_bytes
    c["mime_type"] = a.mime_type
    return c


def ingest_file(db: Session, user_id: str, src: Path, filename: str, sha: str, size: int) -> tuple[str, Asset | None, str | None]:
    kind, mime, ext = classify_file(src, filename)
    if not kind:
        return "rejected", None, "This type of file isn't supported yet."
    dup = db.query(Asset).filter_by(owner_id=user_id, sha256=sha).first()
    if dup:
        return "duplicate", dup, None
    a = Asset(owner_id=user_id, kind=kind, filename=filename[:500], mime_type=mime or mimetypes.guess_type("x" + ext)[0] or "application/octet-stream",
              size_bytes=size, sha256=sha, status="queued", meta={"ext": ext})
    db.add(a)
    db.flush()
    registry.store().put_file(a.original_key, src)
    db.commit()
    runner.enqueue(a.id)
    return "queued", a, None


def _spool(upload: UploadFile) -> tuple[Path, str, int]:
    limit = get_settings().max_upload_mb * 1024 * 1024
    h, size = hashlib.sha256(), 0
    fd, name = tempfile.mkstemp(dir=get_settings().data_path, prefix="up_")
    os.close(fd)  # mkstemp leaves the descriptor open; on Windows that blocks the later unlink
    tmp = Path(name)
    with open(tmp, "wb") as f:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                tmp.unlink(missing_ok=True)
                raise HTTPException(413, f"File larger than {get_settings().max_upload_mb} MB")
            h.update(chunk)
            f.write(chunk)
    return tmp, h.hexdigest(), size


@router.post("/assets", status_code=201)
def upload(files: list[UploadFile] = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    items = []
    for up in files:
        tmp, sha, size = _spool(up)
        try:
            status, a, err = ingest_file(db, user.id, tmp, up.filename or "file", sha, size)
        finally:
            tmp.unlink(missing_ok=True)
        items.append({"filename": up.filename, "status": status, "error": err, "asset": detail(db, a) if a else None})
    return {"items": items}


@router.post("/imports/zip", status_code=201)
def import_zip(file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    """Upload a ZIP of photos/videos/documents; each supported file becomes an asset."""
    tmp, _, _ = _spool(file)
    items = []
    try:
        with zipfile.ZipFile(tmp) as z, tempfile.TemporaryDirectory(dir=get_settings().data_path) as td:
            for info in z.infolist():
                name = Path(info.filename).name
                if info.is_dir() or name.startswith(".") or "__MACOSX" in info.filename:
                    continue
                out = Path(td) / f"{len(items)}_{name}"
                with z.open(info) as src, open(out, "wb") as dst:
                    h, n = hashlib.sha256(), 0
                    while b := src.read(1024 * 1024):
                        h.update(b)
                        dst.write(b)
                        n += len(b)
                status, a, err = ingest_file(db, user.id, out, name, h.hexdigest(), n)
                items.append({"filename": name, "status": status, "error": err, "asset": detail(db, a) if a else None})
    except zipfile.BadZipFile:
        raise HTTPException(400, "Not a valid ZIP file")
    finally:
        tmp.unlink(missing_ok=True)
    return {"items": items}


@router.get("/assets")
def list_assets(kind: str | None = None, date_from: str | None = None, date_to: str | None = None, place: str | None = None,
                tag: str | None = None, status: str | None = None, collection_id: str | None = None,
                limit: int = Query(60, ge=1, le=200), offset: int = Query(0, ge=0),
                user=Depends(current_user), db: Session = Depends(get_db)):
    f = Filters(kinds=[kind] if kind else [], date_from=date_from, date_to=date_to, place=place, tags=[tag] if tag else [], collection_id=collection_id)
    if status == "failed":
        rows = db.query(Asset).filter_by(owner_id=user.id, status="failed").all()
    else:
        rows = candidate_assets(db, user.id, f)  # excludes failed assets
        if status:
            rows = [a for a in rows if a.status == status]
        elif not (place or tag or date_from or date_to or collection_id):  # unfiltered library view also shows failed uploads
            rows += [a for a in db.query(Asset).filter_by(owner_id=user.id, status="failed").all() if not kind or a.kind == kind]
    rows.sort(key=lambda a: a.taken_at or a.created_at, reverse=True)
    page = rows[offset:offset + limit]
    tg = tags_for(db, [a.id for a in page])
    return {"total": len(rows), "items": [asset_card(a, tg.get(a.id)) for a in page]}


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return detail(db, owned_asset(db, user, asset_id))


@router.get("/assets/{asset_id}/chunks")
def asset_chunks(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    """Readable text/moments for the viewer: document pages, video frames (captions) and transcript segments."""
    a = owned_asset(db, user, asset_id)
    rows = db.query(Chunk).filter_by(asset_id=a.id).order_by(Chunk.page, Chunk.start_ms).all()
    return {"items": [{"id": c.id, "type": c.chunk_type, "page": c.page, "start_ms": c.start_ms, "end_ms": c.end_ms, "content": c.content,
                       "is_summary": bool((c.meta or {}).get("is_summary"))} for c in rows if c.content]}


@router.patch("/assets/{asset_id}")
def patch_asset(asset_id: str, body: AssetPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    a = owned_asset(db, user, asset_id)
    if body.caption_user is not None:
        a.caption_user = body.caption_user.strip() or None
        for c in db.query(Chunk).filter_by(asset_id=a.id).all():  # replace the previous user caption chunk
            if (c.meta or {}).get("user_caption"):
                db.delete(c)
        db.flush()
        if a.caption_user:
            add_chunk(db, a, "caption", a.caption_user, meta={"user_caption": True})  # searchable immediately
    if body.place_name is not None:
        a.place_name = body.place_name.strip() or None
    if body.taken_at is not None:
        try:
            a.taken_at = datetime.fromisoformat(body.taken_at).replace(tzinfo=timezone.utc) if body.taken_at else None
        except ValueError:
            raise HTTPException(422, "taken_at must be an ISO date")
    if body.tags is not None:
        want = {t.strip().lower()[:60] for t in body.tags if t.strip()}
        rows = db.execute(select(AssetTag, Tag.name).join(Tag, Tag.id == AssetTag.tag_id).where(AssetTag.asset_id == a.id)).all()
        have = set()
        for link, name in rows:
            if name not in want:
                db.delete(link)
            else:
                have.add(name)
        upsert_tags(db, a, sorted(want - have), source="user")
    db.commit()
    return detail(db, a)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    a = owned_asset(db, user, asset_id)
    registry.store().delete_prefix(f"{a.owner_id}/{a.id}")
    db.delete(a)  # cascades to chunks, tags links, jobs, collection items
    db.commit()


@router.post("/assets/{asset_id}/reindex")
def reindex(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    a = owned_asset(db, user, asset_id)
    a.status, a.status_detail = "queued", None
    db.commit()
    runner.enqueue(a.id)
    return detail(db, a)


@router.get("/assets/{asset_id}/similar")
def similar(asset_id: str, limit: int = Query(12, ge=1, le=40), user=Depends(current_user), db: Session = Depends(get_db)):
    """More like this: nearest assets by caption/text embedding (and image embedding when enabled)."""
    a = owned_asset(db, user, asset_id)
    te, ie = registry.text_embedder(), registry.image_embedder()
    rows = db.query(Chunk.asset_id, Chunk.text_embedding, Chunk.emb_model, Chunk.image_embedding, Chunk.img_model, Chunk.meta).filter(Chunk.owner_id == user.id).all()
    scores: dict[str, float] = {}
    for kind_col, model_col, model in (("text_embedding", "emb_model", te.name), ("image_embedding", "img_model", ie.name if ie else None)):
        if model is None:
            continue
        mine = [from_blob(getattr(r, kind_col)) for r in rows if r.asset_id == a.id and getattr(r, kind_col) is not None and getattr(r, model_col) == model]
        others = [r for r in rows if r.asset_id != a.id and getattr(r, kind_col) is not None and getattr(r, model_col) == model]
        if not mine or not others:
            continue
        q = np.mean(np.vstack(mine), axis=0)
        sims = cosine_matrix(q, np.vstack([from_blob(getattr(r, kind_col)) for r in others]))
        for r, s in zip(others, sims):
            scores[r.asset_id] = max(scores.get(r.asset_id, -1), float(s))
    # tag overlap as a gentle tiebreaker so results are never empty for tagged libraries
    mytags = set(tags_for(db, [a.id]).get(a.id, []))
    alltags = tags_for(db, [x for x in scores] or [])
    ranked = sorted(scores, key=lambda i: -(scores[i] + 0.05 * len(mytags & set(alltags.get(i, [])))))[:limit]
    assets = {x.id: x for x in db.query(Asset).filter(Asset.id.in_(ranked), Asset.owner_id == user.id)}
    tg = tags_for(db, ranked)
    return {"items": [{**asset_card(assets[i], tg.get(i)), "score": round(scores[i], 3)} for i in ranked if i in assets]}


@router.get("/media/{asset_id}/{variant}", include_in_schema=False)
def media(asset_id: str, variant: str, exp: int, sig: str, db: Session = Depends(get_db)):
    if not verify_media(asset_id, variant, exp, sig):
        raise HTTPException(403, "Link expired or invalid")
    a = db.get(Asset, asset_id)
    if not a:
        raise HTTPException(404)
    base = f"{a.owner_id}/{a.id}"
    store = registry.store()
    if variant in ("thumb", "preview"):
        key, mt = f"{base}/{variant}.webp", "image/webp"
    elif variant == "video":
        key, mt = (f"{base}/proxy.mp4", "video/mp4") if a.has_proxy else (a.original_key, a.mime_type)
    elif variant == "original":
        key, mt = a.original_key, a.mime_type
    else:
        raise HTTPException(404)
    if not store.exists(key):
        raise HTTPException(404, "File not available")
    # Cache until the signed link expires (thumbnails/previews are immutable for a given URL).
    max_age = max(0, min(exp - int(time.time()), 86400))
    return FileResponse(store.path(key), media_type=mt, headers={"Cache-Control": f"private, max-age={max_age}", "Content-Disposition": "inline"})
