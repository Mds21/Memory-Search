"""Moments: stories found in a library. Built on a made-up library written straight to the database (no processing)."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app import moments
from app.db import SessionLocal
from app.models import Asset, AssetTag, Chunk, Tag

from .conftest import API

TODAY = date(2026, 11, 24)


@pytest.fixture(scope="module")
def kavya(client, alice, bob):  # after the shared users, so the first account (the admin) stays alice
    r = client.post(f"{API}/auth/register", json={"email": f"kavya-{uuid.uuid4().hex[:6]}@example.com", "password": "moments rock"})
    d = r.json()
    db = SessionLocal()
    uid = d["user"]["id"]
    tags: dict[str, Tag] = {}

    def add(kind="photo", taken=None, place=None, tagnames=(), text=None, name=None, created=None):
        a = Asset(owner_id=uid, kind=kind, filename=name or f"{uuid.uuid4().hex[:8]}.jpg", mime_type="image/jpeg", size_bytes=1,
                  sha256=uuid.uuid4().hex, status="ready", taken_at=taken, place_name=place, has_thumb=True, width=1600, height=1067, meta={})
        if created:
            a.created_at = created
        db.add(a)
        db.flush()
        for n in tagnames:
            if n not in tags:
                tags[n] = Tag(owner_id=uid, name=n)
                db.add(tags[n])
                db.flush()
            db.add(AssetTag(asset_id=a.id, tag_id=tags[n].id))
        if text:
            db.add(Chunk(asset_id=a.id, owner_id=uid, chunk_type="doc_text", content=text))
        return a

    old = datetime(2025, 1, 5, tzinfo=timezone.utc)
    for i in range(6):  # a trip: 6 photos over 3 days in Goa, far from home (Pune)
        add(taken=datetime(2025, 12, 24, 10, tzinfo=timezone.utc) + timedelta(hours=11 * i), place="Goa, India", tagnames=["sea"] if i < 3 else [], created=old)
    for i in range(5):  # home town photos on different days
        add(taken=datetime(2025, 9, 1 + i * 6, 9, tzinfo=timezone.utc), place="Pune, India", created=old)
    for y in (2023, 2024):  # on this day, in earlier years
        add(taken=datetime(y, 11, 24, 18, tzinfo=timezone.utc), place="Pune, India", created=old)
    for _ in range(3):  # after dark
        add(tagnames=["night", "lights"], created=old)
    add(kind="document", name="pan_card.pdf", text="INCOME TAX DEPARTMENT Permanent Account Number Card ABCDE1234F", created=old)
    add(kind="document", name="aadhaar.pdf", text="Government of India Aadhaar unique identification authority 1234 5678 9012", created=old)
    db.commit()
    db.close()
    return {"Authorization": "Bearer " + d["access_token"], "id": uid}


def titles(ms):
    return {m.title: m for m in ms}


def test_engine_finds_the_stories(kavya):
    db = SessionLocal()
    ms = titles(moments.build(db, kavya["id"], "Asia/Kolkata", today=TODAY))
    db.close()
    assert "Trip to Goa" in ms and len(ms["Trip to Goa"].asset_ids) == 6 and ms["Trip to Goa"].when == "24 - 26 Dec 2025"
    assert ms["On this day"].subtitle.startswith("2-3 years ago") and len(ms["On this day"].asset_ids) == 2
    assert "Memories from Pune" in ms
    assert "After dark" in ms and "By the sea" in ms
    assert len(ms["Your ID cards"].asset_ids) == 2
    ranked = list(ms)
    assert ranked[0] == "On this day"  # best first


def test_document_category_is_remembered(kavya):
    db = SessionLocal()
    moments.build(db, kavya["id"], "UTC", today=TODAY)
    pan = db.query(Asset).filter(Asset.owner_id == kavya["id"], Asset.filename == "pan_card.pdf").one()
    assert pan.meta["doc_type"] == "pan_card" and pan.meta["doc_cat"] == "id"
    db.close()


def test_moments_api_open_and_save(client, kavya):
    h = {"Authorization": kavya["Authorization"]}
    items = client.get(f"{API}/moments", headers=h).json()["items"]
    trip = next(m for m in items if m["type"] == "trip")
    assert trip["cover"]["asset_id"] and trip["count"] == 6 and len(trip["preview"]) == 4
    full = client.get(f"{API}/moments/{trip['id']}", headers=h).json()
    assert len(full["items"]) == 6
    saved = client.post(f"{API}/moments/{trip['id']}/save", headers=h).json()
    col = client.get(f"{API}/collections/{saved['collection_id']}", headers=h).json()
    assert col["name"] == "Trip to Goa" and len(col["items"]) == 6
    assert client.get(f"{API}/moments/nope", headers=h).status_code == 404


def test_other_people_cannot_see_moments(client, kavya, bob):
    assert client.get(f"{API}/moments", headers=bob).json()["items"] == [] or all(
        m["title"] != "Trip to Goa" for m in client.get(f"{API}/moments", headers=bob).json()["items"])
