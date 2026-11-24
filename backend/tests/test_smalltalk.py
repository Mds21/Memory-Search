"""Small talk skips file search and gets the assistant's persona, even with no language model running."""
import json

import pytest

from app.search.smalltalk import asks_for_number, detect, reply

from .conftest import API


@pytest.mark.parametrize("msg,kind", [
    ("hi", "greet"), ("Hello there!", "greet"), ("hey 👋", "greet"), ("good morning", "greet"), ("नमस्ते", "greet"), ("vanakkam", "greet"),
    ("how are you?", "how"), ("thank you so much", "thanks"), ("thanks!", "thanks"), ("bye", "bye"),
    ("who are you", "identity"), ("what's your name?", "identity"), ("what can you do?", "help"), ("help", "help"),
])
def test_detects_small_talk(msg, kind):
    assert detect(msg) == kind


@pytest.mark.parametrize("msg", ["hi, show my beach photos", "hello kitty birthday photos", "beach photos from Goa",
                                 "what does my rental agreement say about the deposit?", "thanks receipt from amazon"])
def test_searches_are_not_small_talk(msg):
    assert detect(msg) is None


def test_persona_replies_use_first_name_and_language():
    assert reply("greet", "en", "Asha Rao").startswith("Hi Asha! I'm Memory Search")
    assert reply("greet", "hi", "").startswith("नमस्ते!")
    assert reply("help", "ta").startswith("I find your photos")  # no Tamil text yet: English


def test_number_requests_reveal_ids():
    assert asks_for_number("what is my PAN number") and not asks_for_number("share my PAN card")


def test_chat_greeting_skips_search(client, alice, library):
    text = client.post(f"{API}/chat", headers=alice, json={"message": "hello!"}).text
    ev = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in text.strip().split("\n\n")]
    assert [e for e, _ in ev][0] == "parsed" and not any(e == "results" for e, _ in ev)
    assert "Memory Search" in "".join(d["text"] for e, d in ev if e == "token")
    assert next(d for e, d in ev if e == "done")["files"] == []


def test_slow_model_falls_back_to_persona(client, alice, monkeypatch):
    import time

    from app.adapters import registry
    from app.routers import search as chat_router

    class Slow:
        name, can_chat, fast, supports_json = "slow", True, False, False

        def stream_chat(self, messages):
            time.sleep(1.5)
            yield "too late"

    monkeypatch.setattr(registry, "llm", lambda: Slow())
    monkeypatch.setattr(chat_router, "FIRST_TOKEN_SECONDS", 0.3)
    text = client.post(f"{API}/chat", headers=alice, json={"message": "who are you?"}).text
    assert "I'm Memory Search" in text and "too late" not in text
