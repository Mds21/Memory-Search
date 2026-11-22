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
    default_timezone: str = "Asia/Kolkata"

    text_embedder: str = "hash"
    image_embedder: str = "none"
    vlm: str = "basic"
    llm: str = "extractive"
    stt: str = "auto"  # auto = faster-whisper "base" when installed | none | faster_whisper:<size>
    ollama_base_url: str = "http://localhost:11434"

    max_upload_mb: int = 2048
    max_keyframes: int = 40
    worker_concurrency: int = 2
    search_top_k: int = 50
    dense_min: float = 0.22      # min cosine for a dense-only hit (hash embedder scale)
    ocr_photos: bool = True
    chat_retention_days: int = 7
    signups_per_hour: int = 10      # new accounts allowed per IP address per hour
    admin_username: str = "admin"   # the owner account created on first start (one-time password in data/admin-credentials.txt)
    # "Forgot password" is switched off until OTP delivery is added; admins can give temporary passwords meanwhile.
    password_reset_enabled: bool = False
    # Email delivery for reset codes (used only when password_reset_enabled). Without it, codes go to the server log.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    google_client_id: str = ""   # OAuth client id from Google Cloud Console; empty = Google sign-in hidden  # chats untouched for longer are deleted, unless pinned
    tesseract_cmd: str = ""      # optional full path; auto-detected from PATH / Program Files otherwise
    doc_types_file: str = ""     # optional JSON with extra document types (see app/understanding/doc_types.py)

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
