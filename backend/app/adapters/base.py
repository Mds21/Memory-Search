"""Adapter interfaces. Business logic imports ONLY these; implementations are chosen by env config.

Swap a model or a paid service by adding a class and changing the env value. All methods are
synchronous (the API runs in a thread pool and ingestion runs in worker threads).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal


@dataclass
class ImageDescription:
    caption: str
    tags: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    visible_text: str | None = None
    cues: dict = field(default_factory=dict)  # visual cue scores (signature, beach, document, ...)


@dataclass
class Segment:
    start_ms: int
    end_ms: int
    text: str


@dataclass
class Transcript:
    language: str | None
    segments: list[Segment]


class TextEmbedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str], *, kind: Literal["query", "passage"] = "passage") -> list[list[float]]: ...


class ImageEmbedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed_images(self, images: list[bytes]) -> list[list[float]]: ...

    @abstractmethod
    def embed_text(self, texts: list[str]) -> list[list[float]]: ...  # same space as images


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, passages: list[str], top_k: int) -> list[tuple[int, float]]: ...


class VisionLanguageModel(ABC):
    name: str

    @abstractmethod
    def describe(self, image: bytes, *, hint: str = "") -> ImageDescription: ...


class LLM(ABC):
    name: str
    supports_json: bool = False

    @abstractmethod
    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str: ...

    @abstractmethod
    def stream(self, system: str, user: str) -> Iterator[str]: ...


class OCREngine(ABC):
    @abstractmethod
    def ocr(self, image_path: Path, langs: list[str] | None = None) -> str: ...


class STT(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, *, lang: str | None = None) -> Transcript: ...


class TTS(ABC):  # Phase 2
    @abstractmethod
    def speak(self, text: str, lang: str) -> bytes: ...


class ObjectStore(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None: ...
    @abstractmethod
    def put_file(self, key: str, src: Path) -> None: ...
    @abstractmethod
    def path(self, key: str) -> Path: ...
    @abstractmethod
    def exists(self, key: str) -> bool: ...
    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...
