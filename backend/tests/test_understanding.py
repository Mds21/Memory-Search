"""Document understanding: file sniffing, doc-type classification, names, visual cues, query parsing, fetch answers.

Uses synthetic files only (no real ID documents in the repo). OCR-dependent tests skip when Tesseract is absent.
"""
import io
import time
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.adapters import registry
from app.filetypes import classify as classify_file
from app.search.query_parser import rule_parse
from app.understanding.doc_types import _verhoeff_ok, classify, find_in_query
from app.understanding.entities import extract_names
from app.understanding.visual import analyze

from .conftest import API

TODAY = date(2026, 11, 21)
needs_ocr = pytest.mark.skipif(not registry.ocr().available, reason="Tesseract not installed")


# ---------- synthetic images ----------

def signature_img(color=(30, 30, 140)) -> Image.Image:
    im = Image.new("RGB", (740, 370), "white")
    d = ImageDraw.Draw(im)
    pts = [(80, 260), (140, 120), (200, 250), (260, 140), (320, 240), (380, 130), (440, 230), (650, 160)]
    d.line(pts, fill=color, width=6, joint="curve")
    d.arc([120, 90, 260, 280], 200, 340, fill=color, width=6)
    return im


def beach_img() -> Image.Image:
    im = Image.new("RGB", (300, 200))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 300, 70], fill=(60, 140, 230))     # sky
    d.rectangle([0, 70, 300, 135], fill=(40, 200, 200))   # turquoise sea
    d.rectangle([0, 135, 300, 200], fill=(235, 220, 180))  # sand
    return im


def card_img(lines: list[str], size=(1100, 700), bg=(205, 225, 245)) -> Image.Image:
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    y = 40
    for ln in lines:
        d.text((50, y), ln, fill="black", font_size=40)
        y += 62
    return im


def save(im: Image.Image, path: Path, fmt: str) -> Path:
    im.save(path, fmt)
    return path


# ---------- file types ----------

def test_sniff_handles_wrong_and_odd_extensions(tmp_path):
    jfif = save(signature_img(), tmp_path / "images (1).jfif", "JPEG")
    assert classify_file(jfif, jfif.name)[:2] == ("photo", "image/jpeg")
    webp_as_jpeg = save(beach_img(), tmp_path / "pan.jpeg", "WEBP")
    kind, mime, ext = classify_file(webp_as_jpeg, webp_as_jpeg.name)
    assert (kind, mime, ext) == ("photo", "image/webp", ".webp")
    txt = tmp_path / "notes.txt"
    txt.write_text("BMW service notes")  # starts with "BM" like a bitmap header
    assert classify_file(txt, txt.name)[0] == "document"
    fake = tmp_path / "broken.jpg"
    fake.write_text("not really an image")
    assert classify_file(fake, fake.name)[0] is None


# ---------- classification from text ----------

@pytest.mark.parametrize("text,fname,expected", [
    ("INCOME TAX DEPARTMENT GOVT OF INDIA Permanent Account Number Card ABCPK1234F Name RAVI SHARMA", "scan001.jpg", "pan_card"),
    ("Unique Identification Authority of India  Aadhaar  2345 6789 0124", "IMG_1.jpg", "aadhaar_card"),
    ("Ayushman Bharat Health Account (ABHA) Abha Number 91-1234-5678-9012 priya@abdm", "x.png", "abha_card"),
    ("ELECTION COMMISSION OF INDIA Elector Photo Identity Card ABC1234567", "card.jpg", "voter_id"),
    ("TAX INVOICE  Invoice No 4471  GSTIN 27AAACB  CGST SGST Total", "doc.pdf", "invoice"),
    ("", "my_signature.png", "signature"),
])
def test_doc_type_classification(text, fname, expected):
    assert classify(text, fname).type_id == expected


def test_aadhaar_checksum_rejects_random_numbers():
    assert _verhoeff_ok("2345 6789 0124") and not _verhoeff_ok("2345 6789 0123")
    assert classify("Order 2345 6789 0123 shipped", "order.txt").type_id is None


def test_unrelated_text_is_not_a_document_type():
    assert classify("Grocery list: lemonade, sandwiches and a blanket for the picnic", "notes.txt").type_id is None


# ---------- names ----------

def test_extract_names_handles_noisy_labels():
    pan = "INCOME TAX DEPARTMENT\n@-Permanent Account Number Card\nAIVPU0924A\n| Mame\nUPPULA VARUN KUMAR\nfer WT / Father's Name\nMAHESH KUMAR UPPULA"
    n = extract_names(pan)
    assert n["holder"] == ["Uppula Varun Kumar"] and n["relatives"] == ["Mahesh Kumar Uppula"]
    abha = "Name/ .\nTEA HAR 1 LC.\nName/ acy . a\nRAHUL KUMAR aoe\nAbha Number/\nName/\nRAHUL KUMAR"
    assert extract_names(abha)["holder"] == ["Rahul Kumar"]


# ---------- visual cues ----------

def test_visual_cues_signature_and_beach():
    assert analyze(signature_img()).has("signature")
    b = analyze(beach_img())
    assert b.has("beach") and "beach" in b.tags and not b.has("signature")
    assert not analyze(Image.new("RGB", (400, 300), (128, 128, 128))).scores  # flat grey: nothing


# ---------- query understanding ----------

@pytest.mark.parametrize("q,intent,action,docs,person,self_ref,place", [
    ("share my pan card", "fetch", "share", ["pan_card"], None, True, None),
    ("share my signature", "fetch", "share", ["signature"], None, True, None),
    ("share the beach image which i have taken in Goa", "fetch", "share", [], None, False, "Goa"),
    ("my aadhaar card", "fetch", None, ["aadhaar_card"], None, True, None),
    ("rahul's abha card", "fetch", None, ["abha_card"], "rahul", False, None),
    ("send rahul ka aadhar", "fetch", "share", ["aadhaar_card"], "rahul", False, None),
    ("मेरा आधार कार्ड भेजो", "fetch", "share", ["aadhaar_card"], None, True, None),
    ("open passport of priya", "fetch", "open", ["passport"], "priya", False, None),
    ("photos from Goa", "find_media", None, [], None, False, "Goa"),
])
def test_query_parsing(q, intent, action, docs, person, self_ref, place):
    p = rule_parse(q, today=TODAY)
    assert (p.intent, p.action, p.filters.doc_types, p.filters.person, p.filters.self_ref, p.filters.place) == \
        (intent, action, docs, person, self_ref, place)


def test_capture_phrase_and_filler_removed():
    assert rule_parse("share the beach image which i have taken in Goa", today=TODAY).semantic_query == "beach"
    assert rule_parse("find the picture of my dog", today=TODAY).semantic_query == "dog"
    assert find_in_query("can you send my driving licence")[0] == ["driving_licence"]


# ---------- end to end through the API ----------

def _wait_ready(client, headers, ids, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        st = {i: client.get(f"{API}/assets/{i}", headers=headers).json()["status"] for i in ids}
        if all(s in ("ready", "failed") for s in st.values()):
            return st
        time.sleep(0.5)
    raise AssertionError(f"not processed: {st}")


@pytest.fixture(scope="module")
def carol(client):
    r = client.post(f"{API}/auth/register", json={"email": "ravi.docs@example.com", "password": "password123", "display_name": "Ravi Sharma"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def carol_library(client, carol, tmp_path_factory):
    d = tmp_path_factory.mktemp("carol")
    files = [save(signature_img(), d / "images (1).jfif", "JPEG"), save(beach_img(), d / "images.jfif", "JPEG")]
    if registry.ocr().available:
        files.append(save(card_img(["INCOME TAX DEPARTMENT", "Permanent Account Number Card", "ABCPK1234F", "Name", "RAVI SHARMA",
                                    "Father's Name", "MOHAN SHARMA"]), d / "pan.jpeg", "WEBP"))
        files.append(save(card_img(["Ayushman Bharat Health Account (ABHA)", "Name", "RAHUL KUMAR", "Abha Number", "91-0000-1111-2222",
                                    "Abha Address", "rahul.demo@abdm"], bg=(250, 250, 250)), d / "IMG_4412.png", "PNG"))
    ids = []
    for p in files:
        with open(p, "rb") as fh:
            r = client.post(f"{API}/assets", headers=carol, files=[("files", (p.name, fh))]).json()
        ids.append(r["items"][0]["asset"]["asset_id"])
    st = _wait_ready(client, carol, ids)
    assert all(s == "ready" for s in st.values()), st
    return ids


def _ask(client, headers, q):
    return client.post(f"{API}/search", headers=headers, json={"query": q}).json()


def test_share_signature_and_beach(client, carol, carol_library):
    r = _ask(client, carol, "share my signature")
    assert r["results"][0]["title"] == "images (1).jfif" and r["results"][0]["doc_type"] == "signature"
    assert r["primary"] == [r["results"][0]["asset_id"]] and "signature" in r["answer"].lower()
    r = _ask(client, carol, "share the beach image which i have taken in Goa")
    assert r["results"][0]["title"] == "images.jfif"
    assert "can't confirm it was taken in Goa" in r["answer"]


@needs_ocr
def test_share_id_cards_by_type_and_person(client, carol, carol_library):
    r = _ask(client, carol, "share my pan card")
    assert r["results"][0]["title"] == "pan.jpeg" and "PAN card" in r["answer"] and "Ravi Sharma" in r["answer"]
    r = _ask(client, carol, "rahul's abha card")
    assert r["results"][0]["title"] == "IMG_4412.png" and "Rahul Kumar" in r["answer"]
    r = _ask(client, carol, "abha card of priya")
    assert "not Priya" in r["answer"] and r["primary"] == []
    r = _ask(client, carol, "show my voter id")
    assert "couldn't find a Voter ID card" in r["answer"] and r["primary"] == []


def test_chat_stream_returns_primary_file(client, carol, carol_library):
    from .test_app import sse
    ev = sse(client.post(f"{API}/chat", headers=carol, json={"message": "share my signature"}).text)
    done = ev[-1][1]
    assert ev[-1][0] == "done" and len(done["primary"]) == 1
    assert "signature" in "".join(d["text"] for e, d in ev if e == "token").lower()


# ---------- details inside files and questions about them ----------

def test_extract_facts_from_card_text():
    from app.understanding.facts import extract_facts
    text = ("Ayushman Bharat Health Account (ABHA)\nName/\nRAHUL KUMAR\nAbha Number/\n91-0000-1111-2222\nAbha Address/\nrahul.demo@abdm\n"
            "Gender/ Date Of Birth/ Mobile/\nMALE 15-08-1994 98XXXXXX10")
    facts = {f["key"]: f["value"] for f in extract_facts(text, fields={"abha_number": "91-0000-1111-2222", "abha_address": "rahul.demo@abdm"},
                                                         names={"holder": ["Rahul Kumar"], "relatives": []})}
    assert facts["date_of_birth"] == "15-08-1994" and facts["gender"] == "Male" and facts["abha_number"] == "91-0000-1111-2222"
    assert "address" not in facts  # "ABHA Address" is a handle, not a postal address


@pytest.mark.parametrize("q,intent,fields", [
    ("what is my pan number?", "ask_field", ["id_number"]),
    ("what is my father's name on my pan card?", "ask_field", ["father_name"]),
    ("when was rahul born?", "ask_field", ["date_of_birth"]),
    ("how many id proofs do i have?", "count", []),
    ("do i have a voter id?", "exists", []),
    ("show my voter id", "fetch", []),
])
def test_question_kinds(q, intent, fields):
    p = rule_parse(q, today=TODAY, people=["rahul"])
    assert p.intent == intent and p.ask_fields[:len(fields)] == fields
    assert p.filters.person != "father"


def test_typos_groups_and_synonyms():
    assert find_in_query("share my adhar")[0] == ["aadhaar_card"]
    assert find_in_query("send my signture")[0] == ["signature"]
    assert "passport" in find_in_query("show my id proofs")[0]
    assert find_in_query("nature photos")[0] == []
    from app.understanding.concepts import expand
    assert "beach" in expand(["ocean"])


@needs_ocr
def test_answers_details_counts_and_existence(client, carol, carol_library):
    r = _ask(client, carol, "what is my pan number?")
    assert r["answer"] == "Your PAN number is ABCPK1234F (from your PAN card)."
    r = _ask(client, carol, "what is rahul's abha number")
    assert "91-0000-1111-2222" in r["answer"]
    r = _ask(client, carol, "how many id proofs do i have?")
    assert r["answer"] == "You have 1 document: PAN card (Ravi Sharma)."
    r = _ask(client, carol, "do i have a passport?")
    assert r["answer"].startswith("No") and r["primary"] == []
    r = _ask(client, carol, "pictures of the ocean")
    assert r["results"][0]["title"] == "images.jfif"


def test_no_technical_details_in_user_api(client, carol):
    assert "adapters" not in client.get(f"{API}/me/storage", headers=carol).json()


# ---------- titles, file types, chat history ----------

def test_auto_titles_for_unnamed_files(client, carol, carol_library):
    cards = {c["title"]: c for c in client.get(f"{API}/assets?limit=50", headers=carol).json()["items"]}
    assert cards["images.jfif"]["display_title"] == "Beach" and "beach" in cards["images.jfif"]["auto_caption"]
    assert cards["images (1).jfif"]["display_title"] == "Signature"
    assert cards["images.jfif"]["file_type"] == "Photo"


def test_meaningful_names():
    from app.understanding.titles import meaningful_name
    assert meaningful_name("8cc134c17728ba2bd33b99345f69552f.jpg") is None
    assert meaningful_name("IMG_20251224_101200.jpg") is None
    assert meaningful_name("Goa trip with dad.jpg") == "Goa Trip With Dad"


def test_chat_history_pin_resume_and_cleanup(client, carol, carol_library):
    from datetime import datetime, timedelta, timezone
    from app.db import SessionLocal
    from app.models import Conversation
    from app.routers.search import purge_old_conversations
    from .test_app import sse
    ev = sse(client.post(f"{API}/chat", headers=carol, json={"message": "share my signature"}).text)
    keep = ev[-1][1]["conversation_id"]
    ev = sse(client.post(f"{API}/chat", headers=carol, json={"message": "beach photos"}).text)
    old = ev[-1][1]["conversation_id"]
    # resume: messages come back with the files they showed
    c = client.get(f"{API}/conversations/{keep}", headers=carol).json()
    assert c["messages"][-1]["primary_ids"] and c["messages"][-1]["primary_ids"][0] in c["assets"]
    assert client.patch(f"{API}/conversations/{keep}", headers=carol, json={"pinned": True}).json()["pinned"] is True
    # both chats go quiet for 8 days: the pinned one survives the clean-up
    db = SessionLocal()
    for cid in (keep, old):
        db.get(Conversation, cid).updated_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.commit(); db.close()
    purge_old_conversations()
    ids = [x["id"] for x in client.get(f"{API}/conversations", headers=carol).json()["items"]]
    assert keep in ids and old not in ids


# ---------- Google sign-in ----------

class _Resp:
    def __init__(self, status, data):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


def _google(monkeypatch, claims, status=200):
    import time as _t
    from app.config import get_settings
    import app.routers.auth as auth_mod
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    base = {"aud": "test-client.apps.googleusercontent.com", "iss": "https://accounts.google.com", "email_verified": "true", "exp": str(int(_t.time()) + 600)}
    monkeypatch.setattr(auth_mod.httpx, "get", lambda *a, **k: _Resp(status, {**base, **claims}))


def test_google_sign_up_link_and_reject(client, monkeypatch):
    pv = client.get(f"{API}/auth/providers").json()
    assert pv["google"] is True and pv["google_ready"] is False  # button always offered; works once the owner sets it up
    _google(monkeypatch, {"sub": "g-111", "email": "Meera@Example.com", "name": "Meera Iyer"})
    r = client.post(f"{API}/auth/google", json={"credential": "x" * 40})
    assert r.status_code == 200 and r.json()["user"]["display_name"] == "Meera Iyer" and r.json()["user"]["google"]
    uid = r.json()["user"]["id"]
    assert client.post(f"{API}/auth/google", json={"credential": "x" * 40}).json()["user"]["id"] == uid  # same Google account -> same user
    # a Google-only account can't use a password
    assert "Google" in client.post(f"{API}/auth/login", json={"email": "meera@example.com", "password": "whatever1"}).json()["detail"]
    # existing password account with the same verified email gets linked, not duplicated
    pw = client.post(f"{API}/auth/register", json={"email": "arjun@example.com", "password": "password123"}).json()["user"]["id"]
    _google(monkeypatch, {"sub": "g-222", "email": "arjun@example.com"})
    assert client.post(f"{API}/auth/google", json={"credential": "x" * 40}).json()["user"]["id"] == pw
    assert client.post(f"{API}/auth/login", json={"email": "arjun@example.com", "password": "password123"}).status_code == 200
    # tokens for another app, or unverified emails, are refused
    _google(monkeypatch, {"sub": "g-333", "email": "x@example.com", "aud": "someone-else"})
    assert client.post(f"{API}/auth/google", json={"credential": "x" * 40}).status_code == 401
    _google(monkeypatch, {"sub": "g-444", "email": "y@example.com", "email_verified": "false"})
    assert client.post(f"{API}/auth/google", json={"credential": "x" * 40}).status_code == 401
    _google(monkeypatch, {}, status=400)
    assert client.post(f"{API}/auth/google", json={"credential": "x" * 40}).status_code == 401


def test_admin_sets_google_client_id_from_the_app(client, admin, carol):
    from app import app_settings
    bad = client.put(f"{API}/admin/settings/google", headers=admin, json={"client_id": "not-an-id"})
    assert bad.status_code == 422
    assert client.put(f"{API}/admin/settings/google", headers=carol, json={"client_id": "1-x.apps.googleusercontent.com"}).status_code == 403
    ok = client.put(f"{API}/admin/settings/google", headers=admin, json={"client_id": "123456-abc.apps.googleusercontent.com"}).json()
    assert ok["source"] == "app" and client.get(f"{API}/auth/providers").json()["google_ready"] is True
    client.put(f"{API}/admin/settings/google", headers=admin, json={"client_id": ""})
    assert app_settings.google_client_id() == ""
