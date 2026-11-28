"""Memory assistant: replies from the person's files only, shows exactly the files it found, masks ID numbers,
keeps context, and still works when the model is down. Uses a scripted stand-in model (no network)."""
import json

import pytest

from app.adapters import registry
from app.search.converse import CITE, FULLWIDTH, build_sources, converse, mask_ids, shared_files

from .conftest import API


class FakeLLM:
    supports_json = True
    name = "fake"

    def __init__(self, reply: str, fail: bool = False):
        self.reply, self.fail, self.seen = reply, fail, []

    def stream_chat(self, messages, **_):
        self.seen.append(messages)
        if self.fail:
            raise RuntimeError("down")
        for i in range(0, len(self.reply), 7):  # arrives in small pieces, like a real stream
            yield self.reply[i:i + 7]

    def complete(self, system, user, *, json_mode=False):
        return "{}"

    def stream(self, system, user):
        return iter([self.reply])


class Out:
    def __init__(self, cards=None, chunks=None):
        self.cards, self.rag_chunks, self.total, self.took_ms = cards or [], chunks or [], len(cards or []), 1


def events(text: str):
    out = []
    for block in text.strip().split("\n\n"):
        d = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in d:
            out.append((d["event"], json.loads(d["data"])))
    return out


CHUNK = {"asset_id": "a1", "title": "lease.pdf", "chunk_id": "c1", "page": 2, "start_ms": None, "text": "Deposit Rs 75,000"}


def run(reply, **kw):
    kw.setdefault("out", Out(chunks=[CHUNK]))
    return list(converse(FakeLLM(reply), message="q", history=[], who="Kavya", total_files=1, **kw))


def test_reply_streams_and_cites_only_what_it_used():
    ev = run("The deposit is Rs 75,000 [S1].")
    assert "".join(v for k, v in ev if k == "token") == "The deposit is Rs 75,000 [S1]."
    assert [c["asset_id"] for c in dict(ev)["cites"]] == ["a1"]


def test_no_citation_means_no_files():
    assert dict(run("I couldn't find a passport in your library."))["cites"] == []


def test_old_routing_tags_and_odd_brackets_are_cleaned():
    ev = run("<<FILES>>\nHere it is 【S1】")
    text = "".join(v for k, v in ev if k == "token")
    assert text == "Here it is [S1]" and dict(ev)["cites"][0]["label"] == "S1"
    assert CITE.findall("a [ S2 ] b [​S3]".translate(FULLWIDTH)) == ["2", "3"]


def test_confirmed_match_is_the_first_source():
    cards = [{"asset_id": "x", "kind": "photo", "title": "x.jpg"}, {"asset_id": "pan", "kind": "photo", "display_title": "PAN card", "doc_label": "PAN card"}]
    ctx, cites = build_sources(Out(cards=cards), first=["pan"])
    assert ctx.startswith("[S1] PAN card (photo)") and cites[0]["asset_id"] == "pan"


def test_media_cards_become_sources():
    out = Out(cards=[{"asset_id": "p1", "kind": "photo", "display_title": "Beach in Goa", "place": "Goa, India", "taken_at": "2024-12-24T10:00:00",
                      "auto_caption": "a sandy beach at sunset", "tags": ["beach", "sunset"]}])
    ctx, cites = build_sources(out)
    assert "[S1] Beach in Goa (photo)" in ctx and "place: Goa, India" in ctx and cites[0]["chunk_id"] == "card-p1"


def test_id_numbers_are_masked_unless_asked():
    assert mask_ids("PAN ABCDE1234F, Aadhaar 1234 5678 9012, passport K1234567") == "PAN XXXXXX234F, Aadhaar XXXX XXXX 9012, passport XXXX4567"
    assert mask_ids("Rs 75,000 on 14/02/1994, flat 4B, year 2024") == "Rs 75,000 on 14/02/1994, flat 4B, year 2024"
    llm = FakeLLM("ok")
    out = Out(cards=[{"asset_id": "p", "kind": "photo", "title": "pan.jpg", "facts": [{"label": "Number", "value": "ABCDE1234F"}]}])
    list(converse(llm, message="share my pan", history=[], out=out, who="", total_files=1))
    assert "ABCDE1234F" not in llm.seen[0][-1]["content"] and "XXXXXX234F" in llm.seen[0][-1]["content"]
    list(converse(llm, message="what is my pan number", history=[], out=out, who="", total_files=1, reveal_ids=True))
    assert "ABCDE1234F" in llm.seen[1][-1]["content"]


def test_shared_files_keeps_order_and_dedupes():
    assert shared_files([{"asset_id": "b"}, {"asset_id": "a"}, {"asset_id": "b"}]) == ["b", "a"]


@pytest.fixture
def fake_llm(monkeypatch):
    def use(reply, fail=False):
        llm = FakeLLM(reply, fail)
        monkeypatch.setattr(registry, "llm", lambda: llm)
        return llm
    return use


def test_chat_shows_only_cited_files(client, alice, library, fake_llm):
    fake_llm("I found your rental agreement - the refund clause is on page 1 [S1].")
    ev = events(client.post(f"{API}/chat", headers=alice, json={"message": "security deposit refund"}).text)
    done = next(d for e, d in ev if e == "done")
    assert [f["title"] for f in done["files"]] == ["rental_agreement.pdf"]  # only what the reply cited


def test_chat_small_talk_shows_nothing(client, alice, library, fake_llm):
    fake_llm("Hi! Tell me what you'd like to find.")
    done = next(d for e, d in events(client.post(f"{API}/chat", headers=alice, json={"message": "hello"}).text) if e == "done")
    assert done["files"] == []


def test_chat_remembers_earlier_turns(client, alice, library, fake_llm):
    fake_llm("The refund clause is on page 1 [S1].")
    done = next(d for e, d in events(client.post(f"{API}/chat", headers=alice, json={"message": "security deposit refund"}).text) if e == "done")
    llm = fake_llm("It's refundable within 30 days.")
    client.post(f"{API}/chat", headers=alice, json={"message": "when do I get it back?", "conversation_id": done["conversation_id"]})
    assert any(m["role"] == "assistant" and "refund clause" in m["content"] for m in llm.seen[0])


def test_chat_survives_model_outage(client, alice, library, fake_llm):
    fake_llm("", fail=True)
    ev = events(client.post(f"{API}/chat", headers=alice, json={"message": "security deposit refund"}).text)
    done = next(d for e, d in ev if e == "done")
    assert done["files"] and "".join(d["text"] for e, d in ev if e == "token")


def test_library_documents_tab_includes_scanned_cards(client, alice, library):
    docs = client.get(f"{API}/assets?kind=document", headers=alice).json()["items"]
    photos = client.get(f"{API}/assets?kind=photo", headers=alice).json()["items"]
    doc_ids = {a["asset_id"] for a in docs}
    assert not doc_ids & {a["asset_id"] for a in photos}  # nothing is in both tabs
    assert all(a["kind"] == "document" or a.get("doc_type") for a in docs)


def test_small_talk_gets_no_file_context():
    llm = FakeLLM("Hi! What shall I find?")
    history = [{"role": "user", "content": "any robot photos?"}, {"role": "assistant", "content": "I found a robot photo [S1]."}]
    ev = list(converse(llm, message="hi", history=history, out=Out(), who="Asha", total_files=3, small_talk=True))
    sent = llm.seen[0][-1]["content"]
    assert "<file_sources>" not in sent and "no search was run" in sent and dict(ev)["cites"] == []


def test_chat_files_can_be_viewed_and_downloaded(client, alice, library, fake_llm):
    fake_llm("Here is your rental agreement [S1].")
    done = next(d for e, d in events(client.post(f"{API}/chat", headers=alice, json={"message": "rental agreement"}).text) if e == "done")
    f = done["files"][0]
    assert f["original_url"].startswith("/api/v1/media/")
    inline = client.get(f["original_url"])
    assert inline.status_code == 200 and inline.headers["content-disposition"] == "inline"
    saved = client.get(f["original_url"] + "&dl=1")
    assert saved.headers["content-disposition"].startswith('attachment; filename="rental_agreement.pdf"')


def test_reopened_chat_brings_back_its_files(client, alice, library, fake_llm):
    fake_llm("Here is your rental agreement [S1].")
    done = next(d for e, d in events(client.post(f"{API}/chat", headers=alice, json={"message": "rental agreement"}).text) if e == "done")
    chats = client.get(f"{API}/conversations", headers=alice).json()["items"]
    assert chats[0]["id"] == done["conversation_id"]  # most recently active first
    conv = client.get(f"{API}/conversations/{done['conversation_id']}", headers=alice).json()
    answer = [m for m in conv["messages"] if m["role"] == "assistant"][-1]
    assert [f["title"] for f in answer["files"]] == ["rental_agreement.pdf"]
    assert client.get(answer["files"][0]["original_url"] + "&dl=1").status_code == 200


def test_original_found_when_stored_under_its_real_extension(client, alice, library):
    """Files kept by an earlier version: photo.jfif stored as original.jpg must still open and download."""
    from pathlib import Path

    from app.db import SessionLocal
    from app.models import Asset
    db = SessionLocal()
    a = db.query(Asset).filter(Asset.filename.like("%.jpg"), Asset.size_bytes > 1).first()  # a real upload, with a stored file
    store = registry.store()
    base = f"{a.owner_id}/{a.id}"
    a.filename = Path(a.filename).stem + ".jfif"
    db.commit()
    detail = client.get(f"{API}/assets/{a.id}", headers=alice).json()
    r = client.get(detail["original_url"] + "&dl=1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/jpeg")
    assert r.headers["content-disposition"].startswith(f'attachment; filename="{a.filename}"')  # exactly as uploaded
    assert store.original_key(base, ".jfif").endswith("original.jpg")
    a.filename = Path(a.filename).stem + ".jpg"
    db.commit()
    db.close()


def test_download_as_other_formats(client, alice, library):
    import io

    from PIL import Image
    items = client.get(f"{API}/assets?limit=50", headers=alice).json()["items"]
    photo = next(i for i in items if i["kind"] == "photo" and i["title"].endswith(".jpg"))
    doc = next(i for i in items if i["title"] == "rental_agreement.pdf")
    assert photo["download_formats"] == ["png", "webp", "gif", "bmp", "tif", "pdf"] and doc["download_formats"] == ["txt", "docx"]
    url = client.get(f"{API}/assets/{photo['asset_id']}", headers=alice).json()["original_url"]
    stem = photo["title"].rsplit(".", 1)[0]
    for fmt, pil, mime in [("png", "PNG", "image/png"), ("webp", "WEBP", "image/webp")]:
        r = client.get(f"{url}&dl=1&fmt={fmt}")
        assert r.status_code == 200 and r.headers["content-type"] == mime and Image.open(io.BytesIO(r.content)).format == pil
        assert r.headers["content-disposition"].startswith(f'attachment; filename="{stem}.{fmt}"')
    pdf = client.get(f"{url}&dl=1&fmt=pdf")
    assert pdf.content.startswith(b"%PDF")
    assert client.get(f"{url}&dl=1&fmt=jpg").status_code == 400  # that's the original's own format
    assert client.get(f"{url}&dl=1&fmt=exe").status_code == 400
    durl = client.get(f"{API}/assets/{doc['asset_id']}", headers=alice).json()["original_url"]
    txt = client.get(f"{durl}&dl=1&fmt=txt")
    assert txt.headers["content-disposition"].startswith('attachment; filename="rental_agreement.txt"') and b"deposit" in txt.content.lower()


def test_text_read_from_a_photo_reaches_the_model():
    out = Out(cards=[{"asset_id": "logo", "kind": "photo", "title": "logo.png", "ocr_text": "STAR ART WORKS INTERIOR CIVIL CONTRACTOR"}])
    ctx, _ = build_sources(out)
    assert "text in the image: STAR ART WORKS INTERIOR CIVIL CONTRACTOR" in ctx


def test_follow_ups_are_split_off_and_never_shown():
    ev = run("The deposit is Rs 75,000 [S1].\n**FOLLOW-UPS:** when does it end? | download the agreement")
    assert "".join(v for k, v in ev if k == "token") == "The deposit is Rs 75,000 [S1]."
    assert dict(ev)["followups"] == ["when does it end?", "download the agreement"]
    assert [c["asset_id"] for c in dict(ev)["cites"]] == ["a1"]
