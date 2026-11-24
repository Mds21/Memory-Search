"""Uploads are recognised by their bytes and every supported format ends up searchable."""
import email.message
import io
import zipfile

import pytest
from PIL import Image

from .conftest import API, wait_ready


def _jpeg(color=(200, 60, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(buf, "JPEG")
    return buf.getvalue()


def _odt(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", '<?xml version="1.0"?><office:document-content xmlns:office="o" xmlns:text="t">'
                                  f"<office:body><office:text><text:p>{text}</text:p></office:text></office:body></office:document-content>")
    return buf.getvalue()


def _eml() -> bytes:
    m = email.message.EmailMessage()
    m["From"], m["To"], m["Subject"] = "landlord@example.com", "me@example.com", "Rent receipt"
    m.set_content("Received the marigold deposit of 40000 rupees.")
    return m.as_bytes()


@pytest.fixture(scope="module")
def dave(client, alice, bob):  # after alice and bob, so alice stays the admin
    r = client.post(f"{API}/auth/register", json={"email": "dave@example.com", "password": "formats galore"})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="module")
def uploaded(client, dave):
    heif = io.BytesIO()
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        Image.new("RGB", (64, 64), (10, 120, 60)).save(heif, "HEIF")
    except Exception:
        heif = None
    files = {
        "whatsapp.jfif": _jpeg(),
        "lying.png": _jpeg((20, 20, 200)),  # really a JPEG
        "notes.html": b"<html><head><style>x{}</style></head><body><h1>Trip plan</h1><p>Visit the zephyr lighthouse</p></body></html>",
        "letter.rtf": rb"{\rtf1\ansi{\fonttbl{\f0 Arial;}}\f0 Dear quokka society,\par thanks for the visit.}",
        "report.odt": _odt("Quarterly tamarind harvest report"),
        "receipt.eml": _eml(),
        "table.tsv": b"item\tprice\nnarwhal plush\t499\n",
        "talk.srt": b"1\n00:00:01,000 --> 00:00:03,000\nWelcome to the pangolin talk\n",
        "fake.jpg": b"this is not an image at all",
        "virus.exe": b"MZ",
    }
    if heif:
        files["iphone.heic"] = heif.getvalue()
    r = client.post(f"{API}/assets", headers=dave, files=[("files", (n, b)) for n, b in files.items()])
    assert r.status_code == 201, r.text
    return {"upload": {i["filename"]: i for i in r.json()["items"]}, "assets": {a["title"]: a for a in wait_ready(client, dave)}}


def test_uploads_classified_by_content(uploaded):
    up = uploaded["upload"]
    assert up["whatsapp.jfif"]["status"] == "queued" and up["whatsapp.jfif"]["asset"]["kind"] == "photo"
    assert up["lying.png"]["asset"]["mime_type"] == "image/jpeg"
    assert up["fake.jpg"]["status"] == "rejected" and "damaged" in up["fake.jpg"]["error"]
    assert up["virus.exe"]["status"] == "rejected" and "Unsupported" in up["virus.exe"]["error"]


def test_every_format_ingests(uploaded):
    failed = {n: a["status_detail"] for n, a in uploaded["assets"].items() if a["status"] != "ready"}
    assert not failed, failed
    if "iphone.heic" in uploaded["upload"]:
        assert uploaded["assets"]["iphone.heic"]["kind"] == "photo"


@pytest.mark.parametrize("word,name", [("zephyr", "notes.html"), ("quokka", "letter.rtf"), ("tamarind", "report.odt"),
                                       ("marigold", "receipt.eml"), ("narwhal", "table.tsv"), ("pangolin", "talk.srt")])
def test_document_text_is_searchable(client, dave, uploaded, word, name):
    r = client.post(f"{API}/search", headers=dave, json={"query": word}).json()
    assert name in [c["title"] for c in r["results"]], (word, [c["title"] for c in r["results"]])


def test_jfif_view_and_download_keep_name(client, dave, uploaded):
    a = uploaded["assets"]["whatsapp.jfif"]
    d = client.get(f"{API}/assets/{a['asset_id']}", headers=dave).json()
    view = client.get(d["original_url"])
    assert view.status_code == 200 and view.headers["content-type"].startswith("image/jpeg")
    saved = client.get(d["original_url"] + "&dl=1")
    assert "whatsapp.jfif" in saved.headers["content-disposition"]


def test_more_download_formats(client, dave, uploaded):
    photo = client.get(f"{API}/assets/{uploaded['assets']['whatsapp.jfif']['asset_id']}", headers=dave).json()
    assert "jpg" not in photo["download_formats"] and {"png", "tif", "bmp", "gif"} <= set(photo["download_formats"])
    tif = client.get(photo["original_url"] + "&dl=1&fmt=tif")
    assert tif.status_code == 200 and tif.headers["content-type"] == "image/tiff" and "whatsapp.tif" in tif.headers["content-disposition"]
    doc = client.get(f"{API}/assets/{uploaded['assets']['notes.html']['asset_id']}", headers=dave).json()
    word = client.get(doc["original_url"] + "&dl=1&fmt=docx")
    assert word.status_code == 200 and word.content[:2] == b"PK" and "notes.docx" in word.headers["content-disposition"]
    if "iphone.heic" in uploaded["assets"]:
        heic = client.get(f"{API}/assets/{uploaded['assets']['iphone.heic']['asset_id']}", headers=dave).json()
        assert client.get(heic["original_url"] + "&dl=1&fmt=jpg").content[:3] == b"\xff\xd8\xff"


def test_reingest_replaces_chunks_and_keeps_db_writable(uploaded):
    """clear_derived only deletes at commit: re-running a pipeline replaces rows, and nothing is written meanwhile."""
    import threading

    from app.db import SessionLocal
    from app.models import AssetTag, Chunk
    from app.pipelines import runner

    aid = uploaded["assets"]["notes.html"]["asset_id"]
    db = SessionLocal()
    before = db.query(Chunk).filter_by(asset_id=aid).count()
    tags_before = db.query(AssetTag).filter_by(asset_id=aid).count()
    db.close()

    from app.pipelines import common
    real = common.add_chunk
    seen_write = {}

    def slow_add_chunk(db, *a, **kw):  # while the pipeline "works", another session must be able to write
        if "checked" not in seen_write:
            seen_write["checked"] = True
            other = SessionLocal()
            done = threading.Event()

            def write():
                other.execute(Chunk.__table__.update().where(Chunk.id == "none").values(content="x"))
                other.commit()
                done.set()
            t = threading.Thread(target=write)
            t.start()
            t.join(5)
            seen_write["ok"] = done.is_set()
            other.close()
        return real(db, *a, **kw)

    import app.pipelines.document as document
    document.add_chunk = slow_add_chunk
    try:
        runner.run_ingest(aid)
    finally:
        document.add_chunk = real
    db = SessionLocal()
    assert seen_write.get("ok"), "another writer was blocked while the pipeline ran"
    assert db.query(Chunk).filter_by(asset_id=aid).count() == before
    assert db.query(AssetTag).filter_by(asset_id=aid).count() == tags_before
    db.close()
