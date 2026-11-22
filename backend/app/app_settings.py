"""Settings the server owner can change from inside the app (no .env editing, no restart).

Stored as a small JSON file in the data folder. Environment variables still win when set, so deployments that
configure everything through the environment keep working.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from .config import get_settings

_lock = threading.Lock()
GOOGLE_ID_RE = re.compile(r"^[0-9]+-[a-z0-9_]+\.apps\.googleusercontent\.com$")


def _path() -> Path:
    return get_settings().data_path / "app_settings.json"


def load() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(**changes) -> dict:
    with _lock:
        data = {**load(), **changes}
        data = {k: v for k, v in data.items() if v not in (None, "")}
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(_path())
        return data


def _env_value(name: str) -> str:
    """Current value from the process environment or the .env file, read fresh each time.

    Settings are cached at startup and the dev server only reloads on code changes, so an edited .env would
    otherwise keep serving the old value until a manual restart."""
    import os
    if name in os.environ:  # set explicitly (even to empty) wins over the file
        return os.environ[name].strip()
    env_file = Path(get_settings().model_config.get("env_file") or ".env")
    found = ""
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, val = line.partition("=")
            if sep and key.strip() == name:
                found = val.split("#", 1)[0].strip().strip('"').strip("'")  # last one wins, like .env loaders
    except OSError:
        pass
    return found


def google_client_id() -> str:
    return _env_value("GOOGLE_CLIENT_ID") or str(load().get("google_client_id") or "").strip()


def google_source() -> str | None:
    """Where the active client id comes from: 'env', 'app' or None (not set up)."""
    if _env_value("GOOGLE_CLIENT_ID"):
        return "env"
    return "app" if load().get("google_client_id") else None
