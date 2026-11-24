from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/smriti.db"
    data_dir: str = "./data"
    jwt_secret: str = "dev-secret-change-me"
    allowed_origins: str = "http://localhost:3000"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30
    media_url_ttl_s: int = 3600
    doc_types_file: str = ""  # optional JSON with extra or overriding document types (understanding/doc_types.py)
    default_timezone: str = "Asia/Kolkata"

    text_embedder: str = "hash"
    image_embedder: str = "none"
    vlm: str = "basic"
    llm: str = "extractive"
    stt: str = "none"
    ollama_base_url: str = "http://localhost:11434"

    max_upload_mb: int = 2048
    max_keyframes: int = 40
    worker_concurrency: int = 2
    search_top_k: int = 50
    dense_min: float = 0.22      # min cosine for a dense-only hit (hash embedder scale)
    image_min: float = 0.16     # CLIP text-to-image similarity below this is noise (unrelated ~0.1, matches 0.2+)
    image_window: float = 0.06  # keep image matches within this of the best one
    ocr_photos: bool = True
    ocr_min_conf: float = 60  # photos: keep OCR words Tesseract is at least this sure of (0-100)

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
