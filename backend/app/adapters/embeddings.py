import hashlib
import math
import re
from typing import Literal

import httpx
import numpy as np

from .base import ImageEmbedder, TextEmbedder

# \w misses Indic combining vowel signs, so include the Indic blocks explicitly
_WORD = re.compile(r"[\w\u0900-\u0DFF\u200c\u200d]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class HashEmbedder(TextEmbedder):
    """Offline lexical embedder (hashing trick over words + character n-grams).

    Works for any script and needs no model download, so the whole app runs out of the box.
    It matches on shared words/sub-words, NOT on meaning across languages. For real multilingual
    semantic search set TEXT_EMBEDDER=st:BAAI/bge-m3 or ollama:bge-m3.
    """
    dim = 512
    name = "hash-512"

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for w in tokenize(text):
            self._add(v, "w:" + w, 1.0)
            padded = f"^{w}$"
            for n in (3, 4):
                for i in range(len(padded) - n + 1):
                    self._add(v, f"g{n}:" + padded[i:i + n], 0.35)
        norm = float(np.linalg.norm(v))
        return v / norm if norm else v

    def _add(self, v: np.ndarray, token: str, weight: float) -> None:
        h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "little")
        v[h % self.dim] += weight if (h >> 40) & 1 else -weight

    def embed(self, texts: list[str], *, kind: Literal["query", "passage"] = "passage") -> list[list[float]]:
        return [self._vec(t).tolist() for t in texts]


class OllamaEmbedder(TextEmbedder):
    def __init__(self, model: str, base_url: str):
        self.model, self.base = model, base_url.rstrip("/")
        self.name = f"ollama-{model}"
        self.dim = len(self.embed(["probe"])[0])

    def embed(self, texts, *, kind="passage"):
        r = httpx.post(f"{self.base}/api/embed", json={"model": self.model, "input": texts}, timeout=120)
        r.raise_for_status()
        return r.json()["embeddings"]


class SentenceTransformerEmbedder(TextEmbedder):
    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer  # optional dependency
        self.model = SentenceTransformer(model)
        self.name = f"st-{model.split('/')[-1]}"
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed(self, texts, *, kind="passage"):
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class OpenClipEmbedder(ImageEmbedder):
    def __init__(self, model: str = "xlm-roberta-base-ViT-B-32", pretrained: str = "laion5b_s13b_b90k"):
        import io  # noqa: F401
        import open_clip  # optional dependency
        import torch
        self.torch = torch
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model, pretrained=pretrained)
        self.tokenizer = open_clip.get_tokenizer(model)
        self.model.eval()
        self.name = f"openclip-{model}"
        self.dim = int(self.model.visual.output_dim)

    def embed_images(self, images):
        from io import BytesIO

        from PIL import Image
        batch = self.torch.stack([self.preprocess(Image.open(BytesIO(b)).convert("RGB")) for b in images])
        with self.torch.no_grad():
            f = self.model.encode_image(batch)
            f = f / f.norm(dim=-1, keepdim=True)
        return f.tolist()

    def embed_text(self, texts):
        with self.torch.no_grad():
            f = self.model.encode_text(self.tokenizer(texts))
            f = f / f.norm(dim=-1, keepdim=True)
        return f.tolist()


def to_blob(vec) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def cosine_matrix(q: np.ndarray, m: np.ndarray) -> np.ndarray:
    qn = q / (np.linalg.norm(q) or 1.0)
    mn = m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
    return mn @ qn


__all__ = ["HashEmbedder", "OllamaEmbedder", "SentenceTransformerEmbedder", "OpenClipEmbedder",
           "to_blob", "from_blob", "cosine_matrix", "tokenize", "math"]
