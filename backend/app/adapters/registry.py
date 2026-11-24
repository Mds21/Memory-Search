"""Builds adapter instances from settings. The only place that knows concrete classes."""
import time
from functools import lru_cache

import httpx

from ..config import get_settings
from .base import ImageEmbedder, LLM, STT, TextEmbedder, VisionLanguageModel
from .embeddings import HashEmbedder, OllamaEmbedder, OpenClipEmbedder, SentenceTransformerEmbedder
from .llm import ExtractiveLLM, GroqLLM, OllamaLLM
from .ocr_stt_storage import FasterWhisperSTT, LocalStore, NoSTT, TesseractOCR
from .vlm import BasicVLM, OllamaVLM


def _split(spec: str) -> tuple[str, str]:
    kind, _, arg = spec.partition(":")
    return kind.strip(), arg.strip()


@lru_cache
def text_embedder() -> TextEmbedder:
    s = get_settings()
    kind, arg = _split(s.text_embedder)
    if kind == "ollama":
        return OllamaEmbedder(arg or "bge-m3", s.ollama_base_url)
    if kind == "st":
        return SentenceTransformerEmbedder(arg or "BAAI/bge-m3")
    return HashEmbedder()


@lru_cache
def image_embedder() -> ImageEmbedder | None:
    kind, _ = _split(get_settings().image_embedder)
    return OpenClipEmbedder() if kind == "openclip" else None


@lru_cache
def vlm() -> VisionLanguageModel:
    s = get_settings()
    kind, arg = _split(s.vlm)
    return OllamaVLM(arg, s.ollama_base_url) if kind == "ollama" else BasicVLM()


_NOT_CHAT = ("embed", "bge", "nomic", "minilm", "llava", "vl", "vision", "moondream")
_auto: dict = {"at": 0.0, "pick": None}


def _local_chat_model(base_url: str) -> str | None:
    """First chat model the local Ollama server has (skips embedding and vision models), or None if it isn't running."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=1.5)
        names = [m["name"] for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001 - not installed / not running
        return None
    return next((n for n in names if not any(x in n.lower() for x in _NOT_CHAT)), None)


def _groq_key() -> tuple[str, str]:
    from ..app_settings import _env_value
    return _env_value("GROQ_API_KEY"), _env_value("GROQ_MODEL") or "openai/gpt-oss-120b"


def llm() -> LLM:
    """LLM=ollama:<model> | groq:<model> | extractive | auto. "auto" prefers the local Ollama model (files stay on this
    machine), then Groq when GROQ_API_KEY is set, else offline extractive answers. Re-checked every minute."""
    s = get_settings()
    kind, arg = _split(s.llm)
    if kind == "ollama":
        return OllamaLLM(arg, s.ollama_base_url)
    if kind == "groq":
        key, model = _groq_key()
        return GroqLLM(arg or model, key) if key else ExtractiveLLM()
    if kind != "auto":
        return ExtractiveLLM()
    if time.monotonic() - _auto["at"] > 60 or _auto["pick"] is None:
        local = _local_chat_model(s.ollama_base_url)
        key, model = _groq_key()
        _auto["pick"] = ("ollama", local) if local else ("groq", model) if key else ("extractive", "")
        _auto["at"] = time.monotonic()
    kind, arg = _auto["pick"]
    if kind == "ollama":
        return OllamaLLM(arg, s.ollama_base_url)
    if kind == "groq":
        return GroqLLM(arg, _groq_key()[0])
    return ExtractiveLLM()


@lru_cache
def stt() -> STT:
    kind, arg = _split(get_settings().stt)
    return FasterWhisperSTT(arg or "small") if kind == "faster_whisper" else NoSTT()


@lru_cache
def ocr() -> TesseractOCR:
    return TesseractOCR()


@lru_cache
def store() -> LocalStore:
    return LocalStore(get_settings().data_path / "objects")


def describe_adapters() -> dict:
    ie = image_embedder()
    return {
        "text_embedder": text_embedder().name,
        "image_embedder": ie.name if ie else "none",
        "vlm": vlm().name,
        "llm": llm().name,
        "stt": type(stt()).__name__,
        "ocr": ",".join(ocr().langs) if ocr().available else "unavailable",
    }
