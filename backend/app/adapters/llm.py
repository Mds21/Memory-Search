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


_json_re = re.compile(r"\{.*\}", re.S)


def parse_json_loose(text: str) -> dict | None:
    m = _json_re.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
