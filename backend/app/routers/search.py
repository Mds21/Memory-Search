import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..adapters import registry
from ..db import SessionLocal, get_db
from ..models import Asset, Conversation, Message, User
from ..schemas import ChatIn, SearchIn
from ..search.answer import build_answer, fetch_answer
from ..search.query_parser import ParsedQuery, parse_query
from ..search.retrieval import search as run_search
from ..security import current_user
from .common import owned_asset  # noqa: F401

router = APIRouter(tags=["search"])
log = logging.getLogger("smriti.search")


def _people(db: Session, owner_id: str) -> list[str]:
    """First/last names printed on this user's documents, so "show rahul" works without "rahul's"."""
    names: set[str] = set()
    for (meta,) in db.query(Asset.meta).filter(Asset.owner_id == owner_id).all():
        p = (meta or {}).get("people") or {}
        for n in p.get("holder", []) + p.get("relatives", []):
            names.update(w.lower() for w in n.split() if len(w) >= 3)
    return sorted(names)


FETCH_LIKE = ("fetch", "ask_field", "count", "exists")


def _places(db: Session, owner_id: str) -> list[str]:
    return [p for (p,) in db.query(Asset.place_name).filter(Asset.owner_id == owner_id, Asset.place_name.isnot(None)).distinct().all()]


@router.post("/search")
def search(body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.parsed:  # chip edit: re-run without touching the LLM
        pq = ParsedQuery.from_dict(body.parsed)
    else:
        pq = parse_query(body.query or "", tz=user.timezone, places=_places(db, user.id), llm=None, lang=user.language,
                         people=_people(db, user.id))
    out = run_search(db, user.id, pq, limit=body.limit, offset=body.offset)
    res = {"parsed": pq.as_dict(), "results": out.cards, "total": out.total, "took_ms": out.took_ms}
    if pq.intent in FETCH_LIKE:
        res["answer"], res["primary"] = fetch_answer(pq, out, user.language)
    return res


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(current_user)):
    """One chat turn as an SSE stream: parsed -> results -> token* -> done (or error)."""
    uid, tz, ulang = user.id, user.timezone, user.language

    def stream():
        db = SessionLocal()  # own session: lives as long as the stream
        try:
            conv = db.get(Conversation, body.conversation_id) if body.conversation_id else None
            if conv and conv.owner_id != uid:
                conv = None
            if not conv:
                conv = Conversation(owner_id=uid, title=body.message[:60])
                db.add(conv)
                db.flush()
            conv.updated_at = datetime.now(timezone.utc)  # activity keeps a chat alive for another week
            prev = None
            last = db.query(Message).filter_by(conversation_id=conv.id, role="assistant").order_by(Message.created_at.desc()).first()
            if last and last.parsed_query:
                prev = last.parsed_query
            db.add(Message(conversation_id=conv.id, role="user", content=body.message, input_mode=body.input_mode, language=body.ui_language))
            db.commit()

            llm = registry.llm()
            if body.parsed_override:
                pq = ParsedQuery.from_dict(body.parsed_override)
                pq.raw = body.message
            else:
                pq = parse_query(body.message, tz=tz, places=_places(db, uid), prev=prev, llm=llm, lang=body.ui_language or ulang,
                                 people=_people(db, uid))
            yield _sse("parsed", {"parsed": pq.as_dict(), "conversation_id": conv.id})

            out = run_search(db, uid, pq, limit=30)
            yield _sse("results", {"results": out.cards, "total": out.total, "took_ms": out.took_ms})

            primary: list[str] = []
            if pq.intent in FETCH_LIKE:
                reply, primary = fetch_answer(pq, out, body.ui_language or ulang)
                tokens, cites = iter([reply]), []
            else:
                tokens, cites = build_answer(pq, out, body.ui_language or ulang, llm)
            text = []
            try:
                for tok in tokens:
                    text.append(tok)
                    yield _sse("token", {"text": tok})
            except Exception as e:  # LLM backend down: degrade to the plain summary
                from ..search.answer import summary_line
                fallback = summary_line(out, body.ui_language or "en")
                text = [fallback]
                yield _sse("token", {"text": " " + fallback})
            m = Message(conversation_id=conv.id, role="assistant", content="".join(text), language=body.ui_language, parsed_query=pq.as_dict(),
                        result_asset_ids=[c["asset_id"] for c in out.cards], citations=cites, primary_ids=primary)
            db.add(m)
            db.commit()
            yield _sse("done", {"message_id": m.id, "conversation_id": conv.id, "citations": cites, "primary": primary})
        except Exception:  # noqa: BLE001
            log.exception("chat turn failed")
            yield _sse("error", {"message": "Something went wrong while searching. Please try again."})
        finally:
            db.close()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- chat history ----------------

def purge_old_conversations(owner_id: str | None = None) -> int:
    """Delete chats with no activity for `chat_retention_days` days. Pinned chats are kept forever."""
    from datetime import timedelta
    from ..config import get_settings
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().chat_retention_days)
    db = SessionLocal()
    try:
        q = db.query(Conversation).filter(Conversation.pinned.isnot(True), Conversation.updated_at < cutoff)
        if owner_id:
            q = q.filter(Conversation.owner_id == owner_id)
        old = q.all()
        for c in old:
            db.delete(c)
        db.commit()
        return len(old)
    finally:
        db.close()


def _own_conversation(db: Session, cid: str, user: User) -> Conversation:
    from fastapi import HTTPException
    c = db.get(Conversation, cid)
    if not c or c.owner_id != user.id:
        raise HTTPException(404, "This chat no longer exists.")
    return c


@router.get("/conversations")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..config import get_settings
    purge_old_conversations(user.id)
    rows = (db.query(Conversation).filter_by(owner_id=user.id)
            .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()).limit(100).all())
    items = []
    for c in rows:
        last = next((m for m in reversed(c.messages) if m.role == "assistant"), None)
        items.append({"id": c.id, "title": c.title, "pinned": bool(c.pinned), "updated_at": c.updated_at,
                      "messages": sum(1 for m in c.messages if m.role == "user"), "preview": (last.content[:120] if last else "")})
    return {"items": items, "retention_days": get_settings().chat_retention_days}


@router.get("/conversations/{cid}")
def conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A saved chat with everything needed to show it again: messages, their result cards and handed-over files."""
    from ..search.retrieval import asset_card, tags_for
    c = _own_conversation(db, cid, user)
    ids: list[str] = []
    for m in c.messages:
        for i in (m.result_asset_ids or [])[:30] + (m.primary_ids or []):
            if i not in ids:
                ids.append(i)
    assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_(ids), Asset.owner_id == user.id).all()} if ids else {}
    tg = tags_for(db, list(assets))
    cards = {i: {**asset_card(a, tg.get(i)), "score": None, "snippet": "", "match": None, "matches": [], "why": []} for i, a in assets.items()}
    return {"id": c.id, "title": c.title, "pinned": bool(c.pinned), "updated_at": c.updated_at, "assets": cards, "messages": [
        {"id": m.id, "role": m.role, "content": m.content, "parsed_query": m.parsed_query, "citations": m.citations,
         "result_asset_ids": [i for i in (m.result_asset_ids or []) if i in cards], "primary_ids": [i for i in (m.primary_ids or []) if i in cards],
         "created_at": m.created_at} for m in c.messages]}


@router.patch("/conversations/{cid}")
def update_conversation(cid: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _own_conversation(db, cid, user)
    if "pinned" in body:
        c.pinned = bool(body["pinned"])
    if isinstance(body.get("title"), str) and body["title"].strip():
        c.title = body["title"].strip()[:200]
    db.commit()
    return {"id": c.id, "title": c.title, "pinned": bool(c.pinned)}


@router.delete("/conversations", status_code=204)
def clear_conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Clear chat history; pinned chats are kept."""
    for c in db.query(Conversation).filter(Conversation.owner_id == user.id, Conversation.pinned.isnot(True)).all():
        db.delete(c)
    db.commit()


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if c and c.owner_id == user.id:
        db.delete(c)
        db.commit()
