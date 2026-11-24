import json
import time
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
    """Groq's hosted models (OpenAI-compatible API). Sends the prompt, including file excerpts, to Groq.

    Free Groq accounts have a per-model tokens-per-minute limit. Quick JSON jobs (rewriting the search query) go to a
    small model so they don't use up the main model's budget, and a 429 "rate limited" answer is retried on the next
    model in FALLBACKS (each model has its own limit) instead of dropping to the offline answer."""
    supports_json = True
    can_chat = True
    fast = True
    URL = "https://api.groq.com/openai/v1/chat/completions"
    SMALL = "openai/gpt-oss-20b"
    FALLBACKS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    def __init__(self, model: str, api_key: str):
        self.model, self.key = model, api_key
        self.name = f"groq-{model}"

    def _models(self, first: str) -> list[str]:
        return list(dict.fromkeys([first, *self.FALLBACKS]))

    def _post(self, messages, *, model: str, stream: bool, json_mode: bool = False):
        body = {"model": model, "messages": messages, "stream": stream, "temperature": 0.3}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _headers(self):
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    @staticmethod
    def _wait(r) -> float:
        try:
            return float(r.headers.get("retry-after", "0"))
        except ValueError:
            return 0.0

    def complete(self, system, user, *, json_mode=False) -> str:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last = None
        for model in self._models(self.SMALL if json_mode else self.model):
            r = httpx.post(self.URL, headers=self._headers(), json=self._post(msgs, model=model, stream=False, json_mode=json_mode), timeout=60)
            if r.status_code == 429:
                last = r
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        last.raise_for_status()
        return ""

    def stream(self, system, user) -> Iterator[str]:
        return self.stream_chat([{"role": "system", "content": system}, {"role": "user", "content": user}])

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        models = self._models(self.model)
        for i, model in enumerate(models):
            with httpx.stream("POST", self.URL, headers=self._headers(), json=self._post(messages, model=model, stream=True), timeout=60) as r:
                if r.status_code == 429 and i + 1 < len(models):
                    wait = self._wait(r)
                    if 0 < wait <= 3:  # about to free up: wait for the better model rather than switching
                        r.close()
                        time.sleep(wait)
                        yield from self._stream_once(messages, model)
                        return
                    continue
                r.raise_for_status()
                yield from self._read(r)
                return

    def _stream_once(self, messages, model):
        with httpx.stream("POST", self.URL, headers=self._headers(), json=self._post(messages, model=model, stream=True), timeout=60) as r:
            r.raise_for_status()
            yield from self._read(r)

    @staticmethod
    def _read(r) -> Iterator[str]:
        think = False
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
            if not delta:
                continue
            # some fallback models think out loud in <think>...</think> before answering: don't show that
            if "<think>" in delta:
                before, delta = delta.split("<think>", 1)
                if before:
                    yield before
                think = True
            if think:
                if "</think>" not in delta:
                    continue
                think, delta = False, delta.split("</think>", 1)[1]
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
