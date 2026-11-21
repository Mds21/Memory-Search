import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..adapters import registry
from ..db import SessionLocal, get_db
from ..models import Asset, Conversation, Message, User
from ..schemas import ChatIn, SearchIn
from ..search.answer import build_answer
from ..search.query_parser import ParsedQuery, parse_query
from ..search.retrieval import search as run_search
from ..security import current_user
from .common import owned_asset  # noqa: F401

router = APIRouter(tags=["search"])


def _places(db: Session, owner_id: str) -> list[str]:
    return [p for (p,) in db.query(Asset.place_name).filter(Asset.owner_id == owner_id, Asset.place_name.isnot(None)).distinct().all()]


@router.post("/search")
def search(body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.parsed:  # chip edit: re-run without touching the LLM
        pq = ParsedQuery.from_dict(body.parsed)
    else:
        pq = parse_query(body.query or "", tz=user.timezone, places=_places(db, user.id), llm=None, lang=user.language)
    out = run_search(db, user.id, pq, limit=body.limit, offset=body.offset)
    return {"parsed": pq.as_dict(), "results": out.cards, "total": out.total, "took_ms": out.took_ms}


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
                pq = parse_query(body.message, tz=tz, places=_places(db, uid), prev=prev, llm=llm, lang=body.ui_language or ulang)
            yield _sse("parsed", {"parsed": pq.as_dict(), "conversation_id": conv.id})

            out = run_search(db, uid, pq, limit=30)
            yield _sse("results", {"results": out.cards, "total": out.total, "took_ms": out.took_ms})

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
                        result_asset_ids=[c["asset_id"] for c in out.cards], citations=cites)
            db.add(m)
            db.commit()
            yield _sse("done", {"message_id": m.id, "conversation_id": conv.id, "citations": cites})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"message": f"{type(e).__name__}: {e}"})
        finally:
            db.close()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).filter_by(owner_id=user.id).order_by(Conversation.updated_at.desc()).limit(50).all()
    return {"items": [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]}


@router.get("/conversations/{cid}")
def conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException
    c = db.get(Conversation, cid)
    if not c or c.owner_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return {"id": c.id, "title": c.title, "messages": [
        {"id": m.id, "role": m.role, "content": m.content, "parsed_query": m.parsed_query, "citations": m.citations,
         "result_asset_ids": m.result_asset_ids, "created_at": m.created_at} for m in c.messages]}


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if c and c.owner_id == user.id:
        db.delete(c)
        db.commit()
