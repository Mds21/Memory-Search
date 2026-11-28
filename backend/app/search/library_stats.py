"""A short factual overview of someone's whole library, for questions about the library itself.

"How many photos do I have?", "what ID cards have I saved?", "do I have anything from Goa?" are about the whole
library, not about the handful of files a search returns. The chat model gets this overview with every message so it
can answer them from real counts instead of saying it couldn't find anything.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from ..models import Asset

KIND_WORDS = {"photo": ("photo", "photos"), "video": ("video", "videos"), "document": ("document", "documents")}


def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def overview(db: Session, owner_id: str, *, limit: int = 20000) -> str:
    rows = (db.query(Asset.kind, Asset.status, Asset.taken_at, Asset.created_at, Asset.place_name, Asset.meta)
            .filter(Asset.owner_id == owner_id).limit(limit).all())
    if not rows:
        return "Their library is empty so far."
    kinds, doc_types, shows, holders, places, years = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    processing = failed = 0
    for kind, status, taken, created, place, meta in rows:
        kinds[kind] += 1
        processing += status in ("queued", "processing")
        failed += status == "failed"
        m = meta or {}
        if m.get("doc_label"):
            doc_types[m["doc_label"]] += 1
        for s in m.get("shows") or []:
            shows[s] += 1
        for h in ((m.get("people") or {}).get("holder") or [])[:2]:
            holders[h.title()] += 1
        if place:
            places[place.split(",")[0].strip()] += 1
        when = taken or created
        if when:
            years[when.year] += 1

    total = sum(kinds.values())
    lines = [f"{_n(total, 'file', 'files')} in total: " + ", ".join(_n(kinds[k], *KIND_WORDS[k]) for k in ("photo", "video", "document"))
             + "."]
    if doc_types:
        lines.append("Identified documents: " + ", ".join(f"{label} ×{c}" for label, c in doc_types.most_common(15)) + ".")
    if shows:
        lines.append("Pictures showing: " + ", ".join(f"{s} ×{c}" for s, c in shows.most_common(15)) + ".")
    if holders:
        lines.append("Documents belong to: " + ", ".join(f"{h} ×{c}" for h, c in holders.most_common(8)) + ".")
    if places:
        lines.append("Places: " + ", ".join(f"{p} ×{c}" for p, c in places.most_common(8)) + ".")
    if years:
        lines.append("By year: " + ", ".join(f"{y}: {c}" for y, c in sorted(years.items())) + ".")
    if processing:
        lines.append(f"{_n(processing, 'file is', 'files are')} still being processed.")
    if failed:
        lines.append(f"{_n(failed, 'file', 'files')} could not be processed.")
    return "\n".join(lines)


def starters(db: Session, owner_id: str, *, limit: int = 6) -> list[str]:
    """Conversation starters that fit this library: its documents, what its pictures show, places and years."""
    from ..understanding.clip_labels import LABELS
    rows = db.query(Asset.kind, Asset.taken_at, Asset.created_at, Asset.place_name, Asset.meta).filter(Asset.owner_id == owner_id).limit(5000).all()
    if not rows:
        return ["What can you do?", "How do I add my photos?", "What kinds of files can I upload?"]
    docs, labels, places, years, kinds = Counter(), Counter(), Counter(), Counter(), Counter()
    for kind, taken, created, place, meta in rows:
        m = meta or {}
        kinds[kind] += 1
        if m.get("doc_label") and m["doc_label"] != "Signature":
            docs[m["doc_label"]] += 1
        for k in m.get("labels") or []:
            if k in LABELS and k not in ("document", "id_card", "screenshot", "receipt", "qr_code", "chart", "handwriting"):
                labels[k] += 1
        if place:
            places[place.split(",")[0].strip()] += 1
        if taken or created:
            years[(taken or created).year] += 1
    out: list[str] = []
    out += [f"Show my {d}" for d, _ in docs.most_common(2)]
    out += [f"{LABELS[k][2]} photos" if k != "signature" else "Share my signature" for k, _ in labels.most_common(2)]
    out += [f"Photos from {p}" for p, _ in places.most_common(1)]
    if kinds["photo"]:
        out.append("How many photos do I have?")
    if len(years) > 1:
        out.append(f"What did I save in {max(years)}?")
    if sum(docs.values()) > 1:
        out.append("Which documents have I saved?")
    out.append("What can you do?")
    return list(dict.fromkeys(out))[:limit]
