"""Hybrid retrieval: dense text + keyword(BM25) + image-text + metadata, fused with Reciprocal Rank Fusion.

Storage-agnostic note: vectors live in SQL blobs and are scored with numpy. For large libraries swap the
dense step for a `VectorStore` backed by pgvector/Qdrant; the fusion code stays the same.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timezone

import numpy as np
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..adapters import registry
from ..adapters.embeddings import cosine_matrix, from_blob, tokenize
from ..config import get_settings
from ..models import Asset, AssetTag, Chunk, CollectionItem, Tag
from ..security import media_url
from .query_parser import STOP, Filters, ParsedQuery

RRF_K = 60
WEIGHTS = {"dense": 1.0, "keyword": 1.0, "image": 1.0, "meta": 0.6}


@dataclass
class SearchOutput:
    cards: list[dict]
    total: int
    took_ms: int
    rag_chunks: list[dict] = field(default_factory=list)


def _day_bounds(f: Filters):
    lo = hi = None
    if f.date_from:
        lo = datetime.combine(datetime.fromisoformat(f.date_from).date(), dtime.min, tzinfo=timezone.utc)
    if f.date_to:
        hi = datetime.combine(datetime.fromisoformat(f.date_to).date(), dtime.max, tzinfo=timezone.utc)
    return lo, hi


def candidate_assets(db: Session, owner_id: str, f: Filters):
    """SQL pre-filter shared by every retriever (owner isolation is enforced here, always)."""
    when = func.coalesce(Asset.taken_at, Asset.created_at)
    q = select(Asset).where(Asset.owner_id == owner_id, Asset.status != "failed")
    if f.kinds:
        q = q.where(Asset.kind.in_(f.kinds))
    lo, hi = _day_bounds(f)
    if lo:
        q = q.where(when >= lo)
    if hi:
        q = q.where(when <= hi)
    if f.place:
        q = q.where(Asset.place_name.ilike(f"%{f.place}%"))
    if f.language:
        q = q.where(Asset.language == f.language)
    if f.collection_id:
        q = q.where(Asset.id.in_(select(CollectionItem.asset_id).where(CollectionItem.collection_id == f.collection_id)))
    for t in f.tags:
        q = q.where(Asset.id.in_(select(AssetTag.asset_id).join(Tag, Tag.id == AssetTag.tag_id).where(Tag.name == t.lower(), Tag.owner_id == owner_id)))
    return db.execute(q).scalars().all()


def _terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOP and len(t) > 1]


def _bm25(rows: list[tuple[str, str]], terms: list[str], k1=1.5, b=0.75) -> list[tuple[str, float]]:
    if not rows or not terms:
        return []
    docs = [(cid, tokenize(txt or "")) for cid, txt in rows]
    n = len(docs)
    avgdl = sum(len(d) for _, d in docs) / n or 1
    df = {t: sum(1 for _, d in docs if t in d) for t in set(terms)}
    out = []
    for cid, d in docs:
        if not d:
            continue
        tf: dict[str, int] = defaultdict(int)
        for w in d:
            tf[w] += 1
        s = 0.0
        for t in set(terms):
            if df[t] == 0:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            f = tf.get(t, 0)
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / avgdl))
        if s > 0:
            out.append((cid, s))
    return sorted(out, key=lambda x: -x[1])


def _snippet(text: str | None, terms: list[str], width: int = 240) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    s = text[start:start + width]
    return ("…" if start else "") + s + ("…" if start + width < len(text) else "")


def asset_card(a: Asset, tags: list[str] | None = None) -> dict:
    return {
        "asset_id": a.id, "kind": a.kind, "title": a.filename, "status": a.status, "status_detail": a.status_detail,
        "thumb_url": media_url(a.id, "thumb") if a.has_thumb else None,
        "preview_url": media_url(a.id, "preview") if a.has_thumb else None,
        "taken_at": a.taken_at.isoformat() if a.taken_at else None,
        "added_at": a.created_at.isoformat() if a.created_at else None,
        "place": a.place_name, "lat": a.lat, "lon": a.lon, "width": a.width, "height": a.height,
        "duration_ms": a.duration_ms, "page_count": a.page_count, "language": a.language,
        "tags": tags or [], "caption_user": a.caption_user,
    }


def tags_for(db: Session, asset_ids: list[str]) -> dict[str, list[str]]:
    if not asset_ids:
        return {}
    rows = db.execute(select(AssetTag.asset_id, Tag.name).join(Tag, Tag.id == AssetTag.tag_id).where(AssetTag.asset_id.in_(asset_ids))).all()
    out: dict[str, list[str]] = defaultdict(list)
    for aid, n in rows:
        out[aid].append(n)
    return out


def search(db: Session, owner_id: str, pq: ParsedQuery, *, limit: int = 40, offset: int = 0) -> SearchOutput:
    t0 = time.time()
    cfg = get_settings()
    assets = candidate_assets(db, owner_id, pq.filters)
    by_id = {a.id: a for a in assets}
    sq = (pq.semantic_query or "").strip()
    terms = _terms(sq + " " + (pq.semantic_query_en or ""))

    # Browse mode (filters only): newest first
    if not terms:
        ordered = sorted(assets, key=lambda a: a.taken_at or a.created_at, reverse=True)
        page = ordered[offset:offset + limit]
        tg = tags_for(db, [a.id for a in page])
        cards = [{**asset_card(a, tg.get(a.id)), "score": None, "snippet": "", "match": None, "matches": []} for a in page]
        return SearchOutput(cards, len(ordered), int((time.time() - t0) * 1000))

    if not by_id:
        return SearchOutput([], 0, int((time.time() - t0) * 1000))

    rows = db.execute(select(Chunk.id, Chunk.asset_id, Chunk.chunk_type, Chunk.content, Chunk.page, Chunk.start_ms, Chunk.end_ms,
                             Chunk.text_embedding, Chunk.emb_model, Chunk.image_embedding, Chunk.img_model, Chunk.meta)
                      .where(Chunk.owner_id == owner_id, Chunk.asset_id.in_(list(by_id)))).all()
    chunks = {r.id: r for r in rows}
    lists: dict[str, list[str]] = {}

    # R2 dense text
    te = registry.text_embedder()
    dense_rows = [r for r in rows if r.text_embedding is not None and r.emb_model == te.name]
    dense_sims: dict[str, float] = {}
    if dense_rows:
        qtext = sq + (" " + pq.semantic_query_en if pq.semantic_query_en else "")
        qv = np.array(te.embed([qtext], kind="query")[0], dtype=np.float32)
        m = np.vstack([from_blob(r.text_embedding) for r in dense_rows])
        sims = cosine_matrix(qv, m)
        for r, s in zip(dense_rows, sims):
            if s >= cfg.dense_min:
                dense_sims[r.id] = float(s)
        lists["dense"] = [c for c, _ in sorted(dense_sims.items(), key=lambda x: -x[1])][:cfg.search_top_k]

    # R3 keyword (BM25 over chunk text)
    kw = _bm25([(r.id, r.content) for r in rows if r.content], terms)
    lists["keyword"] = [c for c, _ in kw][:cfg.search_top_k]

    # R1 image-text (only when an image embedder is configured)
    ie = registry.image_embedder()
    if ie:
        img_rows = [r for r in rows if r.image_embedding is not None and r.img_model == ie.name]
        if img_rows:
            texts = [t for t in [sq, pq.semantic_query_en] if t]
            qv = np.mean(np.array(ie.embed_text(texts), dtype=np.float32), axis=0)
            sims = cosine_matrix(qv, np.vstack([from_blob(r.image_embedding) for r in img_rows]))
            ranked = sorted(((r.id, float(s)) for r, s in zip(img_rows, sims) if s >= 0.18), key=lambda x: -x[1])
            lists["image"] = [c for c, _ in ranked][:cfg.search_top_k]

    # R4 metadata (tags, place, filename, user caption) -> asset level
    tagmap = tags_for(db, list(by_id))
    meta_scores: dict[str, float] = {}
    for a in assets:
        hay = set(tokenize(" ".join([a.filename, a.place_name or "", a.caption_user or "", " ".join(tagmap.get(a.id, []))])))
        hit = sum(1 for t in set(terms) if t in hay)
        if hit:
            meta_scores[a.id] = hit / len(set(terms))
    meta_rank = [a for a, _ in sorted(meta_scores.items(), key=lambda x: -x[1])]

    # Reciprocal Rank Fusion
    fused: dict[str, float] = defaultdict(float)
    for name, ids in lists.items():
        for rank, cid in enumerate(ids):
            fused[cid] += WEIGHTS[name] / (RRF_K + rank + 1)
    asset_bonus: dict[str, float] = defaultdict(float)
    for rank, aid in enumerate(meta_rank):
        asset_bonus[aid] += WEIGHTS["meta"] / (RRF_K + rank + 1)

    per_asset: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for cid, sc in fused.items():
        per_asset[chunks[cid].asset_id].append((cid, sc))
    for aid in asset_bonus:
        per_asset.setdefault(aid, [])
    scored = []
    for aid, lst in per_asset.items():
        lst.sort(key=lambda x: -x[1])
        best = lst[0][1] if lst else 0.0
        scored.append((aid, best + asset_bonus.get(aid, 0.0), lst[:3]))
    scored.sort(key=lambda x: -x[1])
    top = scored[0][1] if scored else 1.0
    total = len(scored)
    scored = scored[offset:offset + limit]

    cards, rag = [], []
    for aid, sc, lst in scored:
        a = by_id[aid]
        if not lst:  # metadata-only hit: show its caption/first chunk
            first = next((r for r in rows if r.asset_id == aid), None)
            lst = [(first.id, 0.0)] if first else []
        matches = []
        for cid, _ in lst:
            r = chunks[cid]
            matches.append({"chunk_id": r.id, "type": r.chunk_type, "page": r.page, "start_ms": r.start_ms, "end_ms": r.end_ms,
                            "snippet": _snippet(r.content, terms)})
            if r.chunk_type in ("doc_text", "transcript", "ocr_text") and r.content and not (r.meta or {}).get("is_summary"):
                rag.append({"asset_id": aid, "title": a.filename, "chunk_id": r.id, "page": r.page, "start_ms": r.start_ms,
                            "text": r.content, "score": fused.get(cid, 0.0)})
        best = matches[0] if matches else None
        cards.append({**asset_card(a, tagmap.get(aid)), "score": round(sc / top, 3) if top else None,
                      "snippet": best["snippet"] if best else "", "match": best, "matches": matches})
    rag.sort(key=lambda x: -x["score"])
    return SearchOutput(cards, total, int((time.time() - t0) * 1000), rag[:8])
