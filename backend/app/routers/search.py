import json
from datetime import datetime, timezone
import queue
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..adapters import registry
from ..adapters.llm import ExtractiveLLM
from ..db import SessionLocal, get_db
from ..models import Asset, Conversation, Message, User
from ..schemas import ChatIn, SearchIn
from ..search import smalltalk
from ..search.answer import build_answer, summary_line
from ..search.converse import converse, history_messages, shared_files
from ..search.query_parser import ParsedQuery, parse_query
from ..search.retrieval import SearchOutput, asset_card, tags_for
from ..search.retrieval import search as run_search
from ..security import current_user, media_url
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


FIRST_TOKEN_SECONDS = 25  # a model that hasn't started replying by then is too slow: answer offline instead


class ModelTimeout(Exception):
    pass


def _with_deadline(items, first_wait: float, next_wait: float = 120):
    """Runs a model stream in a thread and re-yields its items; raises ModelTimeout if the first item (or a later
    one) takes too long, so a slow or stuck local model never leaves the chat hanging."""
    q: queue.Queue = queue.Queue()

    def run():
        try:
            for it in items:
                q.put(("item", it))
            q.put(("end", None))
        except Exception as e:  # noqa: BLE001
            q.put(("err", e))

    threading.Thread(target=run, daemon=True).start()
    wait = first_wait
    while True:
        try:
            kind, val = q.get(timeout=wait)
        except queue.Empty:
            raise ModelTimeout() from None
        if kind == "end":
            return
        if kind == "err":
            raise val
        wait = next_wait
        yield val


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(current_user)):
    """One chat turn as an SSE stream: parsed -> results -> token* -> done (or error).

    Small talk ("hi", "who are you") skips file search and gets the assistant's persona. Everything else searches the
    library, then the model replies from the matching files only (converse.py); "done" lists the files it shared.
    With no model, or when it fails, the reply falls back to the offline extractive answer."""
    uid, tz, ulang, who = user.id, user.timezone, user.language, user.display_name or ""

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
            earlier = db.query(Message).filter_by(conversation_id=conv.id).order_by(Message.created_at).all()
            history = history_messages(earlier)
            prev = next((m.parsed_query for m in reversed(earlier) if m.role == "assistant" and m.parsed_query), None)
            db.add(Message(conversation_id=conv.id, role="user", content=body.message, input_mode=body.input_mode, language=body.ui_language))
            conv.updated_at = datetime.now(timezone.utc)  # recent chats are ordered by last activity
            db.commit()

            lang = body.ui_language or ulang
            llm = registry.llm()
            can_chat = getattr(llm, "can_chat", hasattr(llm, "stream_chat"))
            total_files = db.query(Asset).filter_by(owner_id=uid).count()
            talk = None if body.parsed_override else smalltalk.detect(body.message)

            pq, out = None, SearchOutput(cards=[], total=0, took_ms=0)
            if talk:
                yield _sse("parsed", {"parsed": None, "conversation_id": conv.id})
            else:
                if body.parsed_override:
                    pq = ParsedQuery.from_dict(body.parsed_override)
                    pq.raw = body.message
                else:  # a slow local model would double the wait if it also parsed every query
                    pq = parse_query(body.message, tz=tz, places=_places(db, uid), prev=prev, llm=llm if getattr(llm, "fast", False) else None, lang=lang)
                yield _sse("parsed", {"parsed": pq.as_dict(), "conversation_id": conv.id})
                out = run_search(db, uid, pq, limit=30)
                yield _sse("results", {"results": out.cards, "total": out.total, "took_ms": out.took_ms})

            text, cites, model_replied = [], [], False
            if can_chat:
                try:
                    reply = converse(llm, message=body.message, history=history, out=out, who=who, total_files=total_files,
                                     reveal_ids=smalltalk.asks_for_number(body.message), small_talk=bool(talk))
                    for kind, val in _with_deadline(reply, FIRST_TOKEN_SECONDS):
                        if kind == "token":
                            text.append(val)
                            yield _sse("token", {"text": val})
                        else:
                            cites = val
                    model_replied = bool(text)
                except Exception:  # noqa: BLE001 - model down or unreachable: answer offline below
                    if text:
                        yield _sse("token", {"text": " …"})
            if not text:
                if talk:
                    text = [smalltalk.reply(talk, lang, who)]
                    yield _sse("token", {"text": text[0]})
                else:
                    tokens, cites = build_answer(pq, out, lang, ExtractiveLLM())
                    try:
                        for tok in tokens:
                            text.append(tok)
                            yield _sse("token", {"text": tok})
                    except Exception:  # noqa: BLE001
                        text = [summary_line(out, lang)]
                        yield _sse("token", {"text": text[0]})

            by_id = {c["asset_id"]: c for c in out.cards}
            files = [by_id[i] for i in shared_files(cites) if i in by_id]
            if not files and not talk and not model_replied:  # offline answer: still show the best matches
                files = out.cards[:6]
            files = [{**f, "original_url": media_url(f["asset_id"], "original"),  # view and download right from the chat
                      "video_url": media_url(f["asset_id"], "video") if f.get("kind") == "video" else None} for f in files]
            m = Message(conversation_id=conv.id, role="assistant", content="".join(text), language=body.ui_language,
                        parsed_query=pq.as_dict() if pq else None, result_asset_ids=[c["asset_id"] for c in out.cards], citations=cites)
            db.add(m)
            db.commit()
            yield _sse("done", {"message_id": m.id, "conversation_id": conv.id, "citations": cites, "files": files})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"message": f"{type(e).__name__}: {e}"})
        finally:
            db.close()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).filter_by(owner_id=user.id).order_by(Conversation.updated_at.desc()).limit(50).all()
    return {"items": [{"id": c.id, "title": c.title, "updated_at": c.updated_at, "messages": len(c.messages)} for c in rows]}


@router.get("/conversations/{cid}")
def conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException
    c = db.get(Conversation, cid)
    if not c or c.owner_id != user.id:
        raise HTTPException(404, "Conversation not found")
    # Each answer comes back with the files it shared (fresh signed links), so a reopened chat can view and download them.
    shared = {m.id: shared_files(m.citations or []) for m in c.messages if m.role == "assistant"}
    ids = sorted({i for v in shared.values() for i in v})
    assets = {a.id: a for a in db.query(Asset).filter(Asset.owner_id == user.id, Asset.id.in_(ids)).all()} if ids else {}
    tags = tags_for(db, list(assets))

    def card(aid: str) -> dict:
        a = assets[aid]
        return {**asset_card(a, tags.get(aid)), "original_url": media_url(aid, "original"),
                "video_url": media_url(aid, "video") if a.kind == "video" else None}

    return {"id": c.id, "title": c.title, "messages": [
        {"id": m.id, "role": m.role, "content": m.content, "parsed_query": m.parsed_query, "citations": m.citations,
         "result_asset_ids": m.result_asset_ids, "created_at": m.created_at,
         "files": [card(i) for i in shared.get(m.id, []) if i in assets]} for m in c.messages]}


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if c and c.owner_id == user.id:
        db.delete(c)
        db.commit()
