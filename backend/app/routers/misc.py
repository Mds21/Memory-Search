import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..adapters import registry
from ..db import SessionLocal, get_db
from ..models import Asset, Collection, CollectionItem, Feedback, SavedSearch, User
from ..pipelines import runner
from ..schemas import CollectionIn, CollectionItemsIn, FeedbackIn, ReindexIn, SavedSearchIn
from ..search.retrieval import asset_card, tags_for
from ..security import admin_user, current_user
from .common import owned_collection

router = APIRouter()


# ---------- collections (F10) ----------
def _coll_out(db: Session, c: Collection) -> dict:
    ids = [r.asset_id for r in db.query(CollectionItem).filter_by(collection_id=c.id).order_by(CollectionItem.position).all()]
    covers = [asset_card(a) for a in db.query(Asset).filter(Asset.id.in_(ids[:4]))] if ids else []
    return {"id": c.id, "name": c.name, "description": c.description, "count": len(ids), "covers": covers}


@router.get("/collections", tags=["collections"])
def list_collections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"items": [_coll_out(db, c) for c in db.query(Collection).filter_by(owner_id=user.id).order_by(Collection.created_at.desc())]}


@router.post("/collections", status_code=201, tags=["collections"])
def create_collection(body: CollectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = Collection(owner_id=user.id, name=body.name.strip(), description=body.description)
    db.add(c)
    db.commit()
    return _coll_out(db, c)


@router.get("/collections/{cid}", tags=["collections"])
def get_collection(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = owned_collection(db, user, cid)
    ids = [r.asset_id for r in db.query(CollectionItem).filter_by(collection_id=c.id).order_by(CollectionItem.position).all()]
    assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_(ids), Asset.owner_id == user.id)} if ids else {}
    tg = tags_for(db, ids)
    return {**_coll_out(db, c), "items": [asset_card(assets[i], tg.get(i)) for i in ids if i in assets]}


@router.patch("/collections/{cid}", tags=["collections"])
def patch_collection(cid: str, body: CollectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = owned_collection(db, user, cid)
    c.name, c.description = body.name.strip(), body.description
    db.commit()
    return _coll_out(db, c)


@router.delete("/collections/{cid}", status_code=204, tags=["collections"])
def delete_collection(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_collection(db, user, cid))
    db.commit()


@router.post("/collections/{cid}/items", tags=["collections"])
def add_items(cid: str, body: CollectionItemsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = owned_collection(db, user, cid)
    valid = {a.id for a in db.query(Asset.id).filter(Asset.id.in_(body.asset_ids), Asset.owner_id == user.id)}  # never add other users' assets
    have = {r.asset_id for r in db.query(CollectionItem).filter_by(collection_id=c.id)}
    pos = db.query(func.coalesce(func.max(CollectionItem.position), -1)).filter_by(collection_id=c.id).scalar() + 1
    for aid in body.asset_ids:
        if aid in valid and aid not in have:
            db.add(CollectionItem(collection_id=c.id, asset_id=aid, position=pos))
            pos += 1
    db.commit()
    return _coll_out(db, c)


@router.delete("/collections/{cid}/items/{asset_id}", status_code=204, tags=["collections"])
def remove_item(cid: str, asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = owned_collection(db, user, cid)
    db.query(CollectionItem).filter_by(collection_id=c.id, asset_id=asset_id).delete()
    db.commit()


# ---------- saved searches (F13) ----------
@router.get("/saved-searches", tags=["saved"])
def list_saved(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(SavedSearch).filter_by(owner_id=user.id).order_by(SavedSearch.pinned.desc(), SavedSearch.created_at.desc()).all()
    return {"items": [{"id": r.id, "name": r.name, "query": r.query, "pinned": r.pinned} for r in rows]}


@router.post("/saved-searches", status_code=201, tags=["saved"])
def create_saved(body: SavedSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = SavedSearch(owner_id=user.id, name=body.name, query=body.query, pinned=body.pinned)
    db.add(r)
    db.commit()
    return {"id": r.id, "name": r.name, "query": r.query, "pinned": r.pinned}


@router.patch("/saved-searches/{sid}", tags=["saved"])
def patch_saved(sid: str, body: SavedSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(SavedSearch, sid)
    if not r or r.owner_id != user.id:
        raise HTTPException(404)
    r.name, r.pinned = body.name, body.pinned
    db.commit()
    return {"id": r.id, "name": r.name, "query": r.query, "pinned": r.pinned}


@router.delete("/saved-searches/{sid}", status_code=204, tags=["saved"])
def delete_saved(sid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(SavedSearch, sid)
    if r and r.owner_id == user.id:
        db.delete(r)
        db.commit()


# ---------- feedback (F12) ----------
@router.post("/feedback", status_code=201, tags=["feedback"])
def feedback(body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.value == 0:
        raise HTTPException(422, "value must be -1 or 1")
    db.add(Feedback(owner_id=user.id, message_id=body.message_id, asset_id=body.asset_id, value=body.value, comment=body.comment))
    db.commit()
    return {"ok": True}


# ---------- processing events (F16) ----------
@router.get("/events", tags=["events"])
def events(request: Request, user: User = Depends(current_user)):
    """SSE: emits an `asset` event whenever one of the user's assets changes status. Auth via ?access_token=."""
    uid = user.id

    def gen():
        seen: dict[str, tuple] = {}
        started = time.time()
        yield "retry: 3000\n\n"
        while time.time() - started < 300:  # EventSource reconnects automatically
            db = SessionLocal()
            try:
                for a in db.query(Asset).filter(Asset.owner_id == uid).order_by(Asset.updated_at.desc()).limit(300):
                    state = (a.status, a.status_detail)
                    if seen.get(a.id) != state:
                        if a.id in seen or a.status != "ready" or not seen:  # skip replaying the whole library on connect
                            yield f"event: asset\ndata: {json.dumps({'asset_id': a.id, 'status': a.status, 'detail': a.status_detail, 'filename': a.filename}, ensure_ascii=False)}\n\n"
                        seen[a.id] = state
            finally:
                db.close()
            yield ": ping\n\n"
            time.sleep(1.2)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- admin ----------
@router.get("/admin/stats", tags=["admin"])
def admin_stats(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    by = db.query(Asset.kind, Asset.status, func.count(Asset.id), func.coalesce(func.sum(Asset.size_bytes), 0)).group_by(Asset.kind, Asset.status).all()
    return {"users": db.query(User).count(), "assets": [{"kind": k, "status": s, "count": c, "bytes": int(b)} for k, s, c, b in by],
            "adapters": registry.describe_adapters()}


@router.post("/admin/reindex", tags=["admin"])
def admin_reindex(body: ReindexIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    q = db.query(Asset)
    if body.asset_ids:
        q = q.filter(Asset.id.in_(body.asset_ids))
    if body.only_failed:
        q = q.filter(Asset.status == "failed")
    ids = [a.id for a in q.all()]
    for a in q.all():
        a.status, a.status_detail = "queued", None
    db.commit()
    for i in ids:
        runner.enqueue(i)
    return {"queued": len(ids)}


@router.get("/me/storage", tags=["me"])
def my_storage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Asset.kind, func.count(Asset.id), func.coalesce(func.sum(Asset.size_bytes), 0)).filter_by(owner_id=user.id).group_by(Asset.kind).all()
    return {"items": [{"kind": k, "count": c, "bytes": int(b)} for k, c, b in rows], "adapters": registry.describe_adapters()}
