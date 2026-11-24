"""Locate the command-line tools the pipelines use (tesseract, pdftoppm, ffmpeg).

PATH first. On Windows, also the usual install folders: a server started before a tool was installed doesn't see the
updated PATH, and winget puts some tools under the user's WinGet folder rather than on PATH. TESSERACT_CMD and
PDFTOPPM_CMD in the environment or .env point at a specific executable.
"""
from __future__ import annotations

import glob
import os
import shutil
from functools import lru_cache
from pathlib import Path

_WIN_DIRS = {
    "tesseract": [r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR",
                  r"%LOCALAPPDATA%\Programs\Tesseract-OCR"],
    "pdftoppm": [r"%LOCALAPPDATA%\Microsoft\WinGet\Links",
                 r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\oschwartz10612.Poppler*\poppler-*\Library\bin",
                 r"C:\Program Files\poppler*\Library\bin", r"C:\Program Files\poppler*\bin"],
    "ffmpeg": [r"%LOCALAPPDATA%\Microsoft\WinGet\Links", r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin"],
}


@lru_cache
def find(name: str) -> str | None:
    """Full path of a tool, or None if it isn't installed."""
    from .app_settings import _env_value
    override = _env_value(f"{name.upper()}_CMD")
    if override and Path(override).exists():
        return override
    hit = shutil.which(name)
    if hit:
        return hit
    if os.name == "nt":
        for pattern in _WIN_DIRS.get(name, []):
            for d in sorted(glob.glob(os.path.expandvars(pattern)), reverse=True):  # newest version first
                exe = Path(d) / f"{name}.exe"
                if exe.exists():
                    return str(exe)
    return None
