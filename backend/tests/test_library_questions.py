"""Questions about what is in pictures and about the library as a whole (signature, robot, "how many photos")."""
from types import SimpleNamespace

import numpy as np

from app.search.answer import build_answer
from app.search.converse import _card_line, converse
from app.search.query_parser import ParsedQuery, _scripts, llm_enrich
from app.search.retrieval import SearchOutput
from app.understanding import clip_labels
from app.understanding.entities import extract_names


def test_names_survive_ocr_misreads_of_relative_labels():
    pan = "INCOME TAX DEPARTMENT\ne-Permanent Account Number Card\nAIVPU0924A\nUPPULA VARUN KUMAR\nfonTa/Faher's Nae\nMAHESH KUMAR UPPULA\n15/11/1999"
    assert extract_names(pan) == {"holder": ["Uppula Varun Kumar"], "relatives": ["Mahesh Kumar Uppula"]}
    hindi = "नाम / Name\nRAHUL KUMAR\nपिता का नाम / Father's Name\nSURESH KUMAR"
    assert extract_names(hindi) == {"holder": ["Rahul Kumar"], "relatives": ["Suresh Kumar"]}


class _FakeClip:
    """Embeds texts as one-hot vectors so a test image can 'look like' exactly one description."""
    name = "fake-clip"

    def embed_text(self, texts):
        out = np.zeros((len(texts), len(texts)), dtype=np.float32)
        np.fill_diagonal(out, 1)
        self.texts = list(texts)
        return out


def test_clip_labels_name_the_picture():
    clip = _FakeClip()
    keys, m = clip_labels._label_matrix(clip)
    sig = m[keys.index("signature")]  # an image whose fingerprint matches the signature description
    found = clip_labels.labels(sig, clip)
    assert found[0][0] == "signature" and found[0][1] > 0.4
    assert clip_labels.as_cues(found)["signature"] >= 0.5
    assert clip_labels.labels(np.ones(len(keys), dtype=np.float32), clip) == []  # looks like everything: no label


def test_parser_keeps_users_language():
    assert _scripts("공유된 서명") == {"cjk"} and _scripts("share signature") == {"latin"}

    class Reply:
        supports_json = True

        def __init__(self, text):
            self.text = text

        def complete(self, *_a, **_k):
            return self.text

    q = ParsedQuery(raw="share signature", semantic_query="share signature")
    llm_enrich(q, Reply('{"semantic_query": "공유된 서명", "semantic_query_en": "shared signature"}'))
    assert q.semantic_query == "share signature" and q.semantic_query_en == "shared signature"
    q = ParsedQuery(raw="do i have any robot image?", semantic_query="robot image")
    llm_enrich(q, Reply('{"semantic_query": "robot", "semantic_query_en": "robot"}'))
    assert q.semantic_query == "robot"


def _card(**kw):
    base = {"asset_id": "a1", "kind": "photo", "title": "images (1).jfif", "display_title": "Signature", "shows": ["a handwritten signature"],
            "tags": [], "facts": [], "people": []}
    return {**base, **kw}


def test_chat_model_is_told_what_pictures_show_and_library_totals():
    line = _card_line(_card())
    assert "shows: a handwritten signature" in line and line.startswith("Signature (photo)")

    seen = {}

    class LLM:
        def stream_chat(self, msgs):
            seen["msgs"] = msgs
            yield "You have 6 photos [LIBRARY OVERVIEW]."

    out = SearchOutput(cards=[_card()], total=1, took_ms=1)
    tokens = [v for k, v in converse(LLM(), message="how many photos do I have?", history=[], out=out, who="Asha", total_files=6,
                                     overview="6 files in total: 6 photos, 0 videos, 0 documents.") if k == "token"]
    user = seen["msgs"][-1]["content"]
    assert "<library_overview>" in user and "6 photos" in user and "shows: a handwritten signature" in user
    assert "LIBRARY OVERVIEW" in seen["msgs"][0]["content"]
    assert "[LIBRARY OVERVIEW]" not in "".join(tokens)


def test_offline_answer_uses_understood_facts_and_masks_numbers():
    card = _card(title="pan.jpeg", display_title="PAN card · Uppula Varun Kumar", shows=["an identity card"], doc_label="PAN card",
                 facts=[{"key": "pan", "label": "PAN number", "value": "AIVPU0924A"}, {"key": "date_of_birth", "label": "Date of birth", "value": "15/11/1999"}])
    out = SearchOutput(cards=[card], total=1, took_ms=1)
    pq = ParsedQuery(raw="whose pan card is this", semantic_query="pan card", intent="find_document")
    text = "".join(build_answer(pq, out, "en", SimpleNamespace())[0])
    assert "PAN card · Uppula Varun Kumar" in text and "AIVPU0924A" not in text
    pq = ParsedQuery(raw="what is the pan number", semantic_query="pan number", intent="answer_question")
    assert "AIVPU0924A" in "".join(build_answer(pq, out, "en", SimpleNamespace())[0])


def test_library_overview_counts(client, alice, library):
    from app.db import SessionLocal
    from app.models import User
    from app.search.library_stats import overview
    db = SessionLocal()
    uid = db.query(User).filter_by(email="alice@example.com").one().id
    text = overview(db, uid)
    db.close()
    total = client.get("/api/v1/assets?limit=1", headers=alice).json()["total"]  # other test modules add files too
    assert text.startswith(f"{total} files in total:") and "photos" in text and "By year:" in text
