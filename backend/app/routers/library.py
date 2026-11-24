import math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from .. import moments as moments_engine
from ..db import get_db
from ..models import Asset, Collection, CollectionItem, Conversation, Message, Tag, User
from ..search.query_parser import Filters
from ..search.retrieval import asset_card, candidate_assets, tags_for
from ..security import current_user

router = APIRouter(tags=["library"])


@router.get("/timeline")
def timeline(kind: str | None = None, period: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Counts per month (histogram, F7). With period=YYYY-MM returns per-day counts for that month."""
    rows = candidate_assets(db, user.id, Filters(kinds=[kind] if kind else []))
    buckets: dict[str, dict] = defaultdict(lambda: {"count": 0, "photo": 0, "video": 0, "document": 0})
    for a in rows:
        d = a.taken_at or a.created_at
        key = d.strftime("%Y-%m-%d") if period and d.strftime("%Y-%m") == period else d.strftime("%Y-%m")
        if period and not key.startswith(period):
            continue
        b = buckets[key]
        b["count"] += 1
        b[a.kind] += 1
    return {"granularity": "day" if period else "month", "items": [{"period": k, **v} for k, v in sorted(buckets.items())]}


@router.get("/map/clusters")
def map_clusters(min_lat: float = -90, min_lon: float = -180, max_lat: float = 90, max_lon: float = 180, zoom: int = Query(2, ge=0, le=20),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Grid clusters of geotagged assets for the viewport (F8)."""
    rows = [a for a in candidate_assets(db, user.id, Filters())
            if a.lat is not None and a.lon is not None and min_lat <= a.lat <= max_lat and min_lon <= a.lon <= max_lon]
    cell = 360 / (2 ** (zoom + 2))
    groups: dict[tuple[int, int], list[Asset]] = defaultdict(list)
    for a in rows:
        groups[(math.floor(a.lat / cell), math.floor(a.lon / cell))].append(a)
    out = []
    for members in groups.values():
        members.sort(key=lambda a: a.taken_at or a.created_at, reverse=True)
        first = members[0]
        out.append({"lat": sum(m.lat for m in members) / len(members), "lon": sum(m.lon for m in members) / len(members), "count": len(members),
                    "place": first.place_name, "asset": asset_card(first), "asset_ids": [m.id for m in members[:60]]})
    return {"clusters": out, "total": len(rows)}


@router.get("/on-this-day")
def on_this_day(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(ZoneInfo(user.timezone or "UTC"))
    rows = (db.query(Asset).filter(Asset.owner_id == user.id, Asset.kind.in_(["photo", "video"]), Asset.taken_at.isnot(None),
                                   extract("month", Asset.taken_at) == now.month, extract("day", Asset.taken_at) == now.day).all())
    rows = [a for a in rows if a.taken_at.year < now.year]
    rows.sort(key=lambda a: a.taken_at, reverse=True)
    tg = tags_for(db, [a.id for a in rows])
    return {"date": now.strftime("%B %d"), "items": [{**asset_card(a, tg.get(a.id)), "years_ago": now.year - a.taken_at.year} for a in rows[:24]]}


@router.get("/suggest")
def suggest(q: str = Query("", max_length=80), user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = q.strip().lower()
    out: list[dict] = []
    if len(q) < 1:
        recent = (db.query(Message.content).join(Conversation, Conversation.id == Message.conversation_id)
                  .filter(Conversation.owner_id == user.id, Message.role == "user").order_by(Message.created_at.desc()).limit(20).all())
        seen, items = set(), []
        for (c,) in recent:
            if c not in seen:
                seen.add(c)
                items.append({"text": c, "type": "recent"})
        return {"items": items[:6]}
    for (name,) in db.query(Tag.name).filter(Tag.owner_id == user.id, Tag.name.ilike(f"%{q}%")).limit(5):
        out.append({"text": name, "type": "tag"})
    places = {p.split(",")[0].strip() for (p,) in db.query(Asset.place_name).filter(Asset.owner_id == user.id, Asset.place_name.ilike(f"%{q}%")).distinct().limit(20)}
    out += [{"text": p, "type": "place"} for p in sorted(places)[:4]]
    for (fn,) in db.query(Asset.filename).filter(Asset.owner_id == user.id, Asset.kind == "document", Asset.filename.ilike(f"%{q}%")).limit(4):
        out.append({"text": fn, "type": "document"})
    for (m,) in (db.query(Message.content).join(Conversation, Conversation.id == Message.conversation_id)
                 .filter(Conversation.owner_id == user.id, Message.role == "user", Message.content.ilike(f"%{q}%")).limit(3)):
        out.append({"text": m, "type": "recent"})
    seen, uniq = set(), []
    for o in out:
        if o["text"].lower() not in seen:
            seen.add(o["text"].lower())
            uniq.append(o)
    return {"items": uniq[:8]}


# ---------------- moments ----------------

def _moment_out(db: Session, m, *, full: bool = False) -> dict:
    ids = m.asset_ids if full else m.asset_ids[:5]
    assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_(ids)).all()}
    tg = tags_for(db, ids)
    cards = [asset_card(assets[i], tg.get(i)) for i in ids if i in assets]
    out = {"id": m.id, "type": m.type, "title": m.title, "subtitle": m.subtitle, "when": m.when, "count": len(m.asset_ids),
           "cover": cards[0] if cards else None, "preview": cards[1:5], **m.extra}
    if full:
        out["items"] = cards
    return out


@router.get("/moments")
def list_moments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stories found in the library (trips, on this day, themes, document groups...), best first."""
    return {"items": [_moment_out(db, m) for m in moments_engine.build(db, user.id, user.timezone)]}


@router.get("/moments/{moment_id}")
def get_moment(moment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = moments_engine.find(db, user.id, moment_id, user.timezone)
    if not m:
        raise HTTPException(404, "This moment isn't available any more")
    return _moment_out(db, m, full=True)


@router.post("/moments/{moment_id}/save", status_code=201)
def save_moment(moment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Keeps a moment as a regular collection, so it stays even when the moment changes."""
    m = moments_engine.find(db, user.id, moment_id, user.timezone)
    if not m:
        raise HTTPException(404, "This moment isn't available any more")
    c = Collection(owner_id=user.id, name=m.title[:160], description=m.subtitle)
    db.add(c)
    db.flush()
    for i, aid in enumerate(m.asset_ids):
        db.add(CollectionItem(collection_id=c.id, asset_id=aid, position=i))
    db.commit()
    return {"collection_id": c.id, "name": c.name, "count": len(m.asset_ids)}
