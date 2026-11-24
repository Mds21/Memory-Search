"""Turns raw signals (OCR text, visual cues, filename, VLM caption) into what a file *is* and *whose* it is.

The result lives in `asset.meta` (doc_type, doc_label, doc_confidence, people, fields), in tags, and in one
searchable "doc_profile" chunk, so every retriever (keyword, dense, metadata) can find
"my pan card" / "rahul's abha" without special cases.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Asset
from .doc_types import classify, registry
from .entities import extract_names, person_tokens
from .facts import extract_facts, facts_sentence
from .titles import make_caption, make_title


def understand(db: Session, asset: Asset, *, text: str, visual_scores: dict[str, float] | None = None, extra_text: str = "",
               file_facts: list[dict] | None = None, summary: str | None = None) -> dict:
    from ..pipelines.common import add_chunk, upsert_tags  # local import: pipelines import this module

    visual_scores = visual_scores or {}
    c = classify(f"{text}\n{extra_text}", asset.filename, visual_scores)
    is_doc = bool(c.type_id) or visual_scores.get("document", 0) >= 0.5 or asset.kind == "document"
    names = extract_names(text) if is_doc and text else {"holder": [], "relatives": []}

    meta = dict(asset.meta or {})
    for k in ("doc_type", "doc_label", "doc_category", "doc_confidence", "doc_fields", "people", "doc_scores", "facts", "details",
              "auto_title", "auto_caption"):
        meta.pop(k, None)
    if c.type_id:
        t = registry()[c.type_id]
        meta.update(doc_type=t.id, doc_label=t.label, doc_category=t.category, doc_confidence=c.confidence, doc_fields=c.fields)
    if names["holder"] or names["relatives"]:
        meta["people"] = names
    if c.scores:
        meta["doc_scores"] = dict(sorted(c.scores.items(), key=lambda x: -x[1])[:4])
    facts = extract_facts(text, fields=c.fields, names=names) if text and is_doc else []
    if c.type_id and registry()[c.type_id].category == "id":
        for fct in facts:  # identity cards carry one personal date: the holder's birth date
            if fct["key"] == "date" and not any(x["key"] == "date_of_birth" for x in facts):
                fct.update(key="date_of_birth", label="Date of birth")
    if facts:
        meta["facts"] = facts
    if file_facts:
        meta["details"] = file_facts  # about the file itself: taken on, camera, place, author ...
    # a readable name and description for files nobody named or captioned
    label = registry()[c.type_id].label if c.type_id else None
    holder = names["holder"][0] if names["holder"] else None
    meta["auto_title"] = make_title(asset, doc_label=label, holder=holder, cues=visual_scores, details=file_facts or [])
    meta["auto_caption"] = make_caption(asset, doc_label=label, holder=holder, cues=visual_scores, summary=summary, text=text)
    asset.meta = meta

    tags: list[str] = []
    parts: list[str] = []
    if c.type_id:
        t = registry()[c.type_id]
        tags += [t.label.lower(), *[a for a in t.aliases[:4] if a.isascii()], t.category]
        parts.append(f"{t.label} ({t.category} document). Also called: {', '.join(t.aliases[:8])}.")
        if c.fields:
            parts.append("Numbers: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in c.fields.items()) + ".")
    if names["holder"]:
        parts.append(f"Belongs to: {', '.join(names['holder'])}.")
        tags += [n.split()[0].lower() for n in names["holder"]]
    if names["relatives"]:
        parts.append(f"Related people: {', '.join(names['relatives'])}.")
    if facts:
        parts.append(facts_sentence(facts))
    if file_facts:
        parts.append(" ".join(f"{f['label']}: {f['value']}." for f in file_facts))
    parts.append(f"{meta['auto_title']}. {meta['auto_caption']}")
    if tags:
        upsert_tags(db, asset, tags)
    if parts:
        add_chunk(db, asset, "doc_profile", " ".join(parts), meta={"people": person_tokens(names)})
    return meta
