import json

from .conftest import API


def by_name(lib, name):
    return next(a for a in lib["assets"] if a["title"] == name)


def sse(resp_text: str):
    events = []
    for block in resp_text.strip().split("\n\n"):
        ev = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in ev:
            events.append((ev["event"], json.loads(ev["data"])))
    return events


def test_auth_flow(client, alice):  # alice first, so she is the first user (= admin)
    r = client.post(f"{API}/auth/register", json={"email": "carol@example.com", "password": "longenough1"})
    assert r.status_code == 201 and r.json()["user"]["is_admin"] is False
    assert client.post(f"{API}/auth/register", json={"email": "CAROL@example.com", "password": "longenough1"}).status_code == 409
    assert client.post(f"{API}/auth/login", json={"email": "carol@example.com", "password": "wrong-pass"}).status_code == 401
    t = client.post(f"{API}/auth/login", json={"email": "carol@example.com", "password": "longenough1"}).json()
    assert client.get(f"{API}/me", headers={"Authorization": "Bearer " + t["access_token"]}).json()["email"] == "carol@example.com"
    assert client.get(f"{API}/me").status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 200
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t["access_token"]}).status_code == 401  # wrong token type


def test_upload_and_ingestion(library):
    names = {a["title"]: a for a in library["assets"]}
    for n in ["IMG_20251224_101200.jpg", "sunset_delhi.jpg", "rental_agreement.pdf", "notes.txt", "clip_20240615.mp4", "scanned_invoice.pdf"]:
        assert names[n]["status"] == "ready", (n, names[n]["status_detail"])
    rejected = [i for i in library["upload"] if i["status"] == "rejected"]
    assert len(rejected) == 1 and rejected[0]["filename"] == "bad.xyz"


def test_photo_metadata(library):
    a = by_name(library, "IMG_20251224_101200.jpg")
    assert a["taken_at"].startswith("2025-12-24")
    assert "Goa" in a["place"]
    assert a["kind"] == "photo" and a["thumb_url"]


def test_video_metadata(client, alice, library):
    v = by_name(library, "clip_20240615.mp4")
    assert v["kind"] == "video" and v["duration_ms"] >= 3000
    d = client.get(f"{API}/assets/{v['asset_id']}", headers=alice).json()
    chunks = client.get(f"{API}/assets/{v['asset_id']}/chunks", headers=alice).json()["items"]
    assert any(c["type"] == "video_frame" and c["start_ms"] is not None for c in chunks)
    r = client.get(d["video_url"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("video/")


def test_scanned_pdf_ocr(client, alice, library):
    a = by_name(library, "scanned_invoice.pdf")
    text = " ".join(c["content"] for c in client.get(f"{API}/assets/{a['asset_id']}/chunks", headers=alice).json()["items"]).lower()
    assert "invoice" in text and "plumbing" in text


def test_search_place_and_date_filters(client, alice, library):
    r = client.post(f"{API}/search", headers=alice, json={"query": "photos from Goa"}).json()
    assert r["parsed"]["filters"]["place"] == "Goa" and r["parsed"]["filters"]["kinds"] == ["photo"]
    assert [x["title"] for x in r["results"]] == ["IMG_20251224_101200.jpg"]
    r = client.post(f"{API}/search", headers=alice, json={"query": "photos from 2023"}).json()
    assert [x["title"] for x in r["results"]] == ["sunset_delhi.jpg"]


def test_search_documents_and_snippet(client, alice, library):
    r = client.post(f"{API}/search", headers=alice, json={"query": "security deposit refund"}).json()
    top = r["results"][0]
    assert top["title"] == "rental_agreement.pdf" and top["match"]["page"] == 2
    assert "deposit" in top["snippet"].lower()


def test_search_blue_photo_by_vlm_caption(client, alice, library):
    r = client.post(f"{API}/search", headers=alice, json={"query": "blue photo"}).json()
    assert r["results"][0]["title"] == "IMG_20251224_101200.jpg"


def test_chunk_edit_chips_no_llm(client, alice, library):
    parsed = client.post(f"{API}/search", headers=alice, json={"query": "photos"}).json()["parsed"]
    parsed["filters"]["place"] = "Delhi"
    r = client.post(f"{API}/search", headers=alice, json={"parsed": parsed}).json()
    assert [x["title"] for x in r["results"]] == ["sunset_delhi.jpg"]


def test_chat_stream_order_and_citation(client, alice, library):
    r = client.post(f"{API}/chat", headers=alice, json={"message": "What is the security deposit amount?", "ui_language": "en"})
    ev = sse(r.text)
    kinds = [e for e, _ in ev]
    assert kinds[0] == "parsed" and kinds[1] == "results" and "token" in kinds and kinds[-1] == "done"
    answer = "".join(d["text"] for e, d in ev if e == "token")
    assert "75000" in answer and "[S1]" in answer
    done = ev[-1][1]
    assert done["citations"][0]["title"] == "rental_agreement.pdf" and done["citations"][0]["page"] == 2


def test_chat_not_found_message(client, alice, library):
    ev = sse(client.post(f"{API}/chat", headers=alice, json={"message": "What is the warranty on my washing machine?"}).text)
    assert "couldn't find" in "".join(d["text"] for e, d in ev if e == "token")
    assert ev[-1][1]["citations"] == []


def test_chat_followup_keeps_context(client, alice, library):
    ev = sse(client.post(f"{API}/chat", headers=alice, json={"message": "photos from Goa"}).text)
    cid = ev[-1][1]["conversation_id"]
    ev2 = sse(client.post(f"{API}/chat", headers=alice, json={"message": "only 2023", "conversation_id": cid}).text)
    p = ev2[0][1]["parsed"]
    assert p["followup"] and p["filters"]["place"] == "Goa" and p["filters"]["date_from"] == "2023-01-01"


def test_hindi_ui_language_summary(client, alice, library):
    ev = sse(client.post(f"{API}/chat", headers=alice, json={"message": "बीच फोटो", "ui_language": "hi"}).text)
    assert any(e == "token" for e, _ in ev)


def test_isolation_between_users(client, alice, bob, library):
    aid = by_name(library, "rental_agreement.pdf")["asset_id"]
    assert client.get(f"{API}/assets/{aid}", headers=bob).status_code == 404
    assert client.delete(f"{API}/assets/{aid}", headers=bob).status_code == 404
    assert client.get(f"{API}/assets/{aid}/chunks", headers=bob).status_code == 404
    assert client.patch(f"{API}/assets/{aid}", headers=bob, json={"caption_user": "x"}).status_code == 404
    assert client.get(f"{API}/assets", headers=bob).json()["total"] == 0
    assert client.post(f"{API}/search", headers=bob, json={"query": "security deposit"}).json()["results"] == []
    ev = sse(client.post(f"{API}/chat", headers=bob, json={"message": "What is the security deposit amount?"}).text)
    assert ev[-1][1]["citations"] == []
    c = client.post(f"{API}/collections", headers=bob, json={"name": "mine"}).json()
    client.post(f"{API}/collections/{c['id']}/items", headers=bob, json={"asset_ids": [aid]})
    assert client.get(f"{API}/collections/{c['id']}", headers=bob).json()["count"] == 0  # cannot add alice's asset
    assert client.get(f"{API}/collections/{c['id']}", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_collections_and_search_within(client, alice, library):
    ids = [by_name(library, "sunset_delhi.jpg")["asset_id"]]
    c = client.post(f"{API}/collections", headers=alice, json={"name": "Trips"}).json()
    assert client.post(f"{API}/collections/{c['id']}/items", headers=alice, json={"asset_ids": ids}).json()["count"] == 1
    parsed = client.post(f"{API}/search", headers=alice, json={"query": "photos"}).json()["parsed"]
    parsed["filters"]["collection_id"] = c["id"]
    assert [x["title"] for x in client.post(f"{API}/search", headers=alice, json={"parsed": parsed}).json()["results"]] == ["sunset_delhi.jpg"]
    assert client.delete(f"{API}/collections/{c['id']}/items/{ids[0]}", headers=alice).status_code == 204


def test_edit_caption_and_tags_searchable_immediately(client, alice, library):
    aid = by_name(library, "sunset_delhi.jpg")["asset_id"]
    r = client.patch(f"{API}/assets/{aid}", headers=alice, json={"caption_user": "Grandma's zebra cake at the festival", "tags": ["festival", "family"]})
    assert r.status_code == 200 and set(r.json()["tags"]) == {"festival", "family"}
    res = client.post(f"{API}/search", headers=alice, json={"query": "zebra cake"}).json()["results"]
    assert res and res[0]["asset_id"] == aid
    res = client.post(f"{API}/search", headers=alice, json={"query": "family"}).json()["results"]
    assert any(x["asset_id"] == aid for x in res)


def test_timeline_map_on_this_day_suggest_similar(client, alice, library):
    t = client.get(f"{API}/timeline", headers=alice).json()["items"]
    assert {"2025-12", "2023-03"} <= {x["period"] for x in t}
    m = client.get(f"{API}/map/clusters?zoom=2", headers=alice).json()
    assert m["total"] == 2 and sum(c["count"] for c in m["clusters"]) == 2
    assert client.get(f"{API}/on-this-day", headers=alice).status_code == 200
    s = client.get(f"{API}/suggest?q=go", headers=alice).json()["items"]
    assert any("panaji" in x["text"].lower() or "goa" in x["text"].lower() for x in s)
    a = by_name(library, "rental_agreement.pdf")["asset_id"]
    sim = client.get(f"{API}/assets/{a}/similar", headers=alice).json()["items"]
    assert all(x["asset_id"] != a for x in sim)


def test_saved_search_feedback_conversations(client, alice, library):
    s = client.post(f"{API}/saved-searches", headers=alice, json={"name": "Goa", "query": {"query": "photos from Goa"}, "pinned": True}).json()
    assert client.get(f"{API}/saved-searches", headers=alice).json()["items"][0]["id"] == s["id"]
    assert client.post(f"{API}/feedback", headers=alice, json={"value": 1, "asset_id": "x"}).status_code == 201
    assert client.get(f"{API}/conversations", headers=alice).json()["items"]


def test_signed_media_url_rules(client, alice, library):
    a = by_name(library, "IMG_20251224_101200.jpg")
    assert client.get(a["thumb_url"]).status_code == 200
    assert client.get(a["thumb_url"].split("sig=")[0] + "sig=bad").status_code == 403


def test_admin_and_roles(client, alice, bob):
    assert client.get(f"{API}/admin/stats", headers=alice).status_code == 200  # first user = admin
    assert client.get(f"{API}/admin/stats", headers=bob).status_code == 403


def test_delete_removes_everything(client, alice, library):
    from app.adapters import registry
    from app.db import SessionLocal
    from app.models import Chunk, AssetTag
    a = by_name(library, "notes.txt")
    uid = client.get(f"{API}/me", headers=alice).json()["id"]
    prefix = registry.store().path(f"{uid}/{a['asset_id']}")
    assert prefix.exists()
    assert client.delete(f"{API}/assets/{a['asset_id']}", headers=alice).status_code == 204
    assert not prefix.exists()
    assert client.get(f"{API}/assets/{a['asset_id']}", headers=alice).status_code == 404
    db = SessionLocal()
    try:
        assert db.query(Chunk).filter_by(asset_id=a["asset_id"]).count() == 0
        assert db.query(AssetTag).filter_by(asset_id=a["asset_id"]).count() == 0
    finally:
        db.close()


def test_duplicate_upload_detected(client, alice, library, files):
    r = client.post(f"{API}/assets", headers=alice, files=[("files", ("copy.jpg", (files / "sunset_delhi.jpg").read_bytes()))]).json()
    assert r["items"][0]["status"] == "duplicate"


def test_account_deletion(client):
    r = client.post(f"{API}/auth/register", json={"email": "dave@example.com", "password": "longenough1"})
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.get(f"{API}/me/export", headers=h).status_code == 200
    assert client.delete(f"{API}/me", headers=h).status_code == 204
    assert client.get(f"{API}/me", headers=h).status_code == 401


def test_photo_ocr_keeps_only_confident_words():
    from PIL import Image, ImageDraw, ImageFont

    from app.adapters import registry
    ocr = registry.ocr()
    if not ocr.available:
        import pytest
        pytest.skip("tesseract not installed")
    img = Image.new("RGB", (1200, 300), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    d.text((40, 100), "Permanent Account Number ABCDE1234F", fill="black", font=font)
    assert "ABCDE1234F" in ocr.ocr_image(img, min_conf=60)
    assert ocr.ocr_image(Image.effect_noise((600, 400), 80).convert("RGB"), min_conf=60) == ""  # a photo with no writing
