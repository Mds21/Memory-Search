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
    assert [c["asset_id"] for c in ev[-1][1]] == ["a1"]


def test_no_citation_means_no_files():
    assert run("I couldn't find a passport in your library.")[-1] == ("cites", [])


def test_old_routing_tags_and_odd_brackets_are_cleaned():
    ev = run("<<FILES>>\nHere it is 【S1】")
    text = "".join(v for k, v in ev if k == "token")
    assert text == "Here it is [S1]" and ev[-1][1][0]["label"] == "S1"
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
    assert [f["title"] for f in done["files"]] == ["rental_agreement.pdf"]
    assert not any(e == "results" for e, _ in ev)  # no list of loose matches


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
