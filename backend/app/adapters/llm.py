import json
import re
from typing import Iterator

import httpx

from .base import LLM


class ExtractiveLLM(LLM):
    """Offline stand-in: no generation. The RAG layer falls back to extractive answers (best matching sentences)."""
    name = "extractive"
    supports_json = False

    def complete(self, system, user, *, json_mode=False) -> str:
        raise NotImplementedError("ExtractiveLLM cannot generate text")

    def stream(self, system, user) -> Iterator[str]:
        raise NotImplementedError("ExtractiveLLM cannot generate text")


class OllamaLLM(LLM):
    supports_json = True
    can_chat = True

    def __init__(self, model: str, base_url: str):
        self.model, self.base = model, base_url.rstrip("/")
        self.name = f"ollama-{model}"

    def _payload(self, system, user, stream, json_mode):
        p = {"model": self.model, "stream": stream,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            p["format"] = "json"
        return p

    def complete(self, system, user, *, json_mode=False) -> str:
        r = httpx.post(f"{self.base}/api/chat", json=self._payload(system, user, False, json_mode), timeout=300)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def stream(self, system, user) -> Iterator[str]:
        with httpx.stream("POST", f"{self.base}/api/chat", json=self._payload(system, user, True, False), timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("message", {}).get("content"):
                    yield d["message"]["content"]
                if d.get("done"):
                    break


    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        with httpx.stream("POST", f"{self.base}/api/chat", json={"model": self.model, "stream": True, "messages": messages}, timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("message", {}).get("content"):
                    yield d["message"]["content"]
                if d.get("done"):
                    break


class GroqLLM(LLM):
    """Groq's hosted models (OpenAI-compatible API). Sends the prompt, including file excerpts, to Groq."""
    supports_json = True
    can_chat = True
    fast = True
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str, api_key: str):
        self.model, self.key = model, api_key
        self.name = f"groq-{model}"

    def _post(self, messages, *, stream: bool, json_mode: bool = False):
        body = {"model": self.model, "messages": messages, "stream": stream, "temperature": 0.3}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _headers(self):
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    def complete(self, system, user, *, json_mode=False) -> str:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        r = httpx.post(self.URL, headers=self._headers(), json=self._post(msgs, stream=False, json_mode=json_mode), timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def stream(self, system, user) -> Iterator[str]:
        return self.stream_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        with httpx.stream("POST", self.URL, headers=self._headers(), json=self._post(messages, stream=True), timeout=60) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta


_json_re = re.compile(r"\{.*\}", re.S)


def parse_json_loose(text: str) -> dict | None:
    m = _json_re.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
