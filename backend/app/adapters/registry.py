"""Builds adapter instances from settings. The only place that knows concrete classes."""
from functools import lru_cache

from ..config import get_settings
from .base import ImageEmbedder, LLM, STT, TextEmbedder, VisionLanguageModel
from .embeddings import HashEmbedder, OllamaEmbedder, OpenClipEmbedder, SentenceTransformerEmbedder
from .llm import ExtractiveLLM, OllamaLLM
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


@lru_cache
def llm() -> LLM:
    s = get_settings()
    kind, arg = _split(s.llm)
    return OllamaLLM(arg, s.ollama_base_url) if kind == "ollama" else ExtractiveLLM()


def _whisper_installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


@lru_cache
def stt() -> STT:
    kind, arg = _split(get_settings().stt)
    if kind == "auto":  # speech in videos becomes searchable as soon as the add-on is installed
        return FasterWhisperSTT("base") if _whisper_installed() else NoSTT()
    return FasterWhisperSTT(arg or "base") if kind == "faster_whisper" else NoSTT()


@lru_cache
def ocr() -> TesseractOCR:
    return TesseractOCR(cmd=get_settings().tesseract_cmd or None)


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
