"""Moments: little stories the app finds in someone's library and offers back to them, like a photo app's memories.

Built on the fly from what each file already carries (date taken, place, tags, document text), so they appear as soon
as files are processed and change as the library grows. Two families, so a library of downloaded photos with no camera
data still gets moments:

  from dates and places  on this day, trips and events, a month or a year in review, places you keep returning to
  from content           themes from tags (by the sea, after dark, colour stories), document groups (ID cards, bills,
                         health records...), videos, what's new, and a daily rediscovery from the archive

Each moment has a stable id ("trip-2025-12-24-goa", "theme-sea", "docs-id") so it can be opened, played or saved.
"""
from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .models import Asset, AssetTag, Chunk, Tag
from .understanding import doc_types

MEDIA = ("photo", "video")


@dataclass
class Moment:
    id: str
    type: str            # on_this_day | trip | month | year | place | theme | documents | videos | recent | archive
    title: str
    subtitle: str
    asset_ids: list[str]
    score: float
    when: str | None = None  # date label, e.g. "24 - 27 Dec 2025"
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- helpers

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def _city(place: str | None) -> str | None:
    return place.split(",")[0].strip() if place else None


def _local(dt: datetime | None, tz: ZoneInfo) -> datetime | None:
    if not dt:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(tz)


def _range(a: date, b: date) -> str:
    if a == b:
        return f"{a.day} {a:%b %Y}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day} - {b.day} {a:%b %Y}"
    if a.year == b.year:
        return f"{a.day} {a:%b} - {b.day} {b:%b %Y}"
    return f"{a.day} {a:%b %Y} - {b.day} {b:%b %Y}"


def _count(assets: list[Asset]) -> str:
    c = Counter(a.kind for a in assets)
    parts = [f"{n} {k}{'s' if n != 1 else ''}" for k, n in (("photo", c["photo"]), ("video", c["video"]), ("document", c["document"])) if n]
    return ", ".join(parts)


def _best_first(assets: list[Asset]) -> list[Asset]:
    """Photos with previews first, bigger and wider first: the first item is the moment's cover."""
    return sorted(assets, key=lambda a: (not a.has_thumb, a.kind == "document", -((a.width or 0) * (a.height or 0)),
                                         -(1 if (a.width or 0) >= (a.height or 0) else 0)))


# ---------------------------------------------------------------- themes from tags

THEMES: list[tuple[str, str, set[str]]] = [
    ("sea", "By the sea", {"sea", "beach", "ocean", "shore", "seaside", "sand", "waves", "coast"}),
    ("sunset", "Golden hours", {"sunset", "sunrise", "golden hour", "dusk", "dawn"}),
    ("mountains", "Up in the hills", {"mountain", "mountains", "hills", "hill", "valley", "snow", "peak"}),
    ("nature", "Into the green", {"forest", "trees", "tree", "garden", "park", "grass", "nature", "green"}),
    ("night", "After dark", {"night", "dark", "lights", "city lights", "stars"}),
    ("food", "Food diary", {"food", "meal", "dinner", "lunch", "breakfast", "cake", "restaurant"}),
    ("people", "Faces you love", {"people", "person", "family", "friends", "group", "selfie", "face"}),
    ("celebration", "Celebrations", {"birthday", "wedding", "party", "festival", "diwali", "holi", "celebration"}),
    ("pets", "Furry friends", {"dog", "cat", "pet", "puppy", "kitten"}),
    ("sky", "Wide open skies", {"sky", "clouds", "outdoor", "outdoors"}),
    ("signatures", "Your signatures", {"signature", "handwritten signature", "autograph", "my sign", "sign"}),
]
COLOURS: list[tuple[str, str, set[str]]] = [
    ("pink", "Shades of pink", {"pink"}),
    ("blue", "Feeling blue", {"blue"}),
    ("warm", "Warm tones", {"orange", "yellow", "red"}),
    ("mono", "In black & white", {"monochrome", "black and white", "grayscale"}),
]
SCANNED = {"document", "scan", "paper", "id", "card", "pan card", "health card", "receipt", "bill", "certificate"}

DOC_GROUPS = {
    "id": ("Your ID cards", "Identity documents, ready when you need them"),
    "finance": ("Bills & money", "Bank, tax and payment papers"),
    "travel": ("Travel papers", "Tickets, passports and bookings"),
    "health": ("Health records", "Reports, prescriptions and health cards"),
    "education": ("Study & work", "Certificates, CVs and letters"),
    "legal": ("Home & legal", "Agreements and property papers"),
    "personal": ("Personal papers", "Letters and personal documents"),
}


def _doc_category(db: Session, a: Asset, tags: set[str]) -> str | None:
    """What kind of document a file is (id, finance, health...), classified once and remembered in asset.meta."""
    meta = a.meta or {}
    if "doc_cat" in meta:
        return meta["doc_cat"] or None
    if a.kind != "document" and not (tags & SCANNED):
        return None
    text = " ".join(c for (c,) in db.query(Chunk.content).filter(
        Chunk.asset_id == a.id, Chunk.chunk_type.in_(("doc_text", "ocr_text", "caption"))).limit(20).all() if c)[:6000]
    text = f"{text} {' '.join(tags)}"
    got = doc_types.classify(text, a.filename)
    cat = doc_types.registry()[got.type_id].category if got.type_id else ("personal" if a.kind == "document" else None)
    a.meta = {**meta, "doc_type": got.type_id or "", "doc_cat": cat or ""}
    return cat


# ---------------------------------------------------------------- the engine

def build(db: Session, owner_id: str, tz_name: str = "UTC", today: date | None = None) -> list[Moment]:
    tz = ZoneInfo(tz_name or "UTC")
    now = datetime.now(tz)
    today = today or now.date()
    assets = db.query(Asset).filter(Asset.owner_id == owner_id, Asset.status == "ready").all()
    if not assets:
        return []
    by_id = {a.id: a for a in assets}
    tags: dict[str, set[str]] = defaultdict(set)
    for aid, name in db.query(AssetTag.asset_id, Tag.name).join(Tag, Tag.id == AssetTag.tag_id).filter(Tag.owner_id == owner_id).all():
        tags[aid].add(name.lower())

    media = [a for a in assets if a.kind in MEDIA]
    dated = sorted([(a, _local(a.taken_at, tz)) for a in media if a.taken_at], key=lambda x: x[1])
    out: list[Moment] = []

    def add(mid, typ, title, subtitle, items, score, when=None, **extra):
        items = _best_first(items)
        if items:
            out.append(Moment(mid, typ, title, subtitle, [a.id for a in items], score, when, extra))

    # On this day: same date in earlier years; else the same week
    otd = [(a, t) for a, t in dated if t.year < today.year and (t.month, t.day) == (today.month, today.day)]
    label = "On this day"
    if not otd:
        week = {(today + timedelta(days=d)).timetuple()[1:3] for d in range(-3, 4)}
        otd = [(a, t) for a, t in dated if t.year < today.year and (t.month, t.day) in week]
        label = "This week, years ago"
    if otd:
        years = sorted({today.year - t.year for _, t in otd})
        ago = f"{years[0]} year{'s' if years[0] > 1 else ''} ago" if len(years) == 1 else f"{years[0]}-{years[-1]} years ago"
        add(f"day-{today:%m-%d}", "on_this_day", label, f"{ago} · {_count([a for a, _ in otd])}", [a for a, _ in otd], 100,
            when=f"{today.day} {today:%B}")

    # Trips and events: bursts of photos with no gap longer than 36 hours
    home = Counter(_city(a.place_name) for a, _ in dated if a.place_name).most_common(1)
    home_city = home[0][0] if home else None
    burst: list[tuple[Asset, datetime]] = []
    bursts: list[list[tuple[Asset, datetime]]] = []
    for a, t in dated:
        if burst and t - burst[-1][1] > timedelta(hours=36):
            bursts.append(burst)
            burst = []
        burst.append((a, t))
    if burst:
        bursts.append(burst)
    trip_ids: set[str] = set()
    for b in bursts:
        if len(b) < 4:
            continue
        items = [a for a, _ in b]
        start, end = b[0][1].date(), b[-1][1].date()
        city = Counter(_city(a.place_name) for a in items if a.place_name).most_common(1)
        city = city[0][0] if city else None
        if city and city != home_city:
            title, typ = f"Trip to {city}", "trip"
        elif city:
            title, typ = f"{start:%A} in {city}" if start == end else f"Days in {city}", "event"
        else:
            title, typ = (f"A {start:%A} to remember" if start == end else f"{start:%B} getaway"), "event"
        recency = max(0, 30 - (today - end).days / 30)
        add(f"trip-{start.isoformat()}-{_slug(city or 'days')}", typ, title, _count(items), items, 70 + min(len(items), 30) + recency,
            when=_range(start, end), place=city)
        trip_ids.update(a.id for a in items)

    # A month in review (recent months, and this month in earlier years)
    months: dict[tuple[int, int], list[Asset]] = defaultdict(list)
    for a, t in dated:
        months[(t.year, t.month)].append(a)
    for (y, m), items in months.items():
        if len(items) < 6 or (y, m) == (today.year, today.month):
            continue
        age = (today.year - y) * 12 + today.month - m
        if age <= 6 or m == today.month:
            add(f"month-{y}-{m:02d}", "month", f"{date(y, m, 1):%B %Y}", f"Month in review · {_count(items)}", items,
                45 + (10 if m == today.month else 0) - age / 2, when=f"{date(y, m, 1):%B %Y}")

    # A year in review
    years: dict[int, list[Asset]] = defaultdict(list)
    for a, t in dated:
        years[t.year].append(a)
    for y, items in years.items():
        if len(items) >= 12 and (y < today.year or today.month >= 11):
            add(f"year-{y}", "year", f"{y} in review", _count(items), items, 55 if today.month in (12, 1) else 30, when=str(y))

    # Places you keep coming back to (several different days)
    places: dict[str, list[Asset]] = defaultdict(list)
    for a in media:
        if a.place_name:
            places[_city(a.place_name)].append(a)
    for city, items in places.items():
        days = {_local(a.taken_at, tz).date() for a in items if a.taken_at}
        if len(items) >= 5 and len(days) >= 2:
            add(f"place-{_slug(city)}", "place", f"Memories from {city}", _count(items), items, 35 + min(len(items), 20), place=city)

    # Themes and colour stories from tags
    for key, title, words in THEMES + COLOURS:
        items = [a for a in media if tags[a.id] & words and not (key != "signatures" and tags[a.id] & SCANNED)]
        if key == "mono":
            items = [a for a in media if {"gray", "black", "white"} <= tags[a.id] and not tags[a.id] & SCANNED] or items
        need = 2 if key == "signatures" else 3
        if len(items) >= need:
            add(f"theme-{key}", "theme", title, _count(items), items, 30 + min(len(items), 15) + (5 if key in ("sea", "sunset", "people") else 0))

    # Documents (and scanned documents among photos) grouped by what they are
    groups: dict[str, list[Asset]] = defaultdict(list)
    for a in assets:
        cat = _doc_category(db, a, tags[a.id])
        if cat in DOC_GROUPS:
            groups[cat].append(a)
    for cat, items in groups.items():
        title, blurb = DOC_GROUPS[cat]
        add(f"docs-{cat}", "documents", title, f"{blurb} · {len(items)} file{'s' if len(items) != 1 else ''}", items,
            40 + (10 if cat in ("id", "health") else 0) + min(len(items), 10))

    # Videos
    videos = [a for a in media if a.kind == "video"]
    if len(videos) >= 3:
        add("videos", "videos", "Moving pictures", _count(videos), sorted(videos, key=lambda a: a.taken_at or a.created_at, reverse=True), 32)

    # What's new: added in the last two weeks
    since = now - timedelta(days=14)
    fresh = [a for a in assets if _local(a.created_at, tz) and _local(a.created_at, tz) >= since]
    if len(fresh) >= 4:
        add("recent", "recent", "Fresh in your library", f"Added in the last two weeks · {_count(fresh)}", fresh, 38)

    # Rediscover: a different handful of older photos every day
    older = [a for a in media if a.kind == "photo" and a.id not in trip_ids
             and (_local(a.taken_at, tz) or _local(a.created_at, tz)) < now - timedelta(days=30)]
    if len(older) >= 6:
        rnd = random.Random(int(hashlib.sha256(f"{owner_id}{today}".encode()).hexdigest()[:8], 16))
        pick = rnd.sample(older, min(12, len(older)))
        add("archive", "archive", "From your archive", f"Rediscover · {_count(pick)}", pick, 36)

    db.commit()  # remembers document categories worked out above
    out.sort(key=lambda m: -m.score)
    seen, unique = set(), []
    for m in out:  # drop near-duplicates (same files as a higher-ranked moment)
        sig = frozenset(m.asset_ids)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(m)
    unique = unique[:24]
    covers: set[str] = set()  # each moment gets a cover no higher-ranked moment already uses, when it has one to spare
    for m in unique:
        pick = next((i for i in m.asset_ids if i not in covers and by_id[i].has_thumb), m.asset_ids[0])
        m.asset_ids.remove(pick)
        m.asset_ids.insert(0, pick)
        covers.add(pick)
    return unique


def find(db: Session, owner_id: str, moment_id: str, tz_name: str = "UTC") -> Moment | None:
    return next((m for m in build(db, owner_id, tz_name) if m.id == moment_id), None)
