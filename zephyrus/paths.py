"""Пути приложения.

* Папка установки (C:\\Program Files\\Zephyrus) — только для чтения.
* Все динамические данные живут в LOCALAPPDATA\\Zephyrus:
    bin\\       – рабочие копии yt-dlp / ffmpeg (их можно обновлять)
    data\\      – SQLite, ключ шифрования
    profiles\\  – зашифрованные cookie-профили
    cache\\     – временные файлы, favicon'ы
    logs\\      – журналы
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Zephyrus"
APP_VERSION = "1.0.0"
APP_AUTHOR = "RonovaDev"
# Впишите сюда ссылку на ваш репозиторий, например "https://github.com/RonovaDev/Zephyrus".
# Пока строка пустая, кнопка GitHub в «О программе» неактивна.
APP_GITHUB_URL = "https://github.com/RonovaMain/Zephyrus"

IS_WINDOWS = sys.platform.startswith("win")
IS_FROZEN = bool(getattr(sys, "frozen", False))
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""


def _data_root() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


DATA_DIR = _data_root()
BIN_DIR = DATA_DIR / "bin"
DB_DIR = DATA_DIR / "data"
DB_PATH = DB_DIR / "zephyrus.db"
KEY_PATH = DB_DIR / "vault.key"
PROFILES_DIR = DATA_DIR / "profiles"
CACHE_DIR = DATA_DIR / "cache"
LOG_DIR = DATA_DIR / "logs"

YTDLP_NAME = "yt-dlp" + EXE_SUFFIX
FFMPEG_NAME = "ffmpeg" + EXE_SUFFIX
FFPROBE_NAME = "ffprobe" + EXE_SUFFIX
ENGINE_FILES = (YTDLP_NAME, FFMPEG_NAME, FFPROBE_NAME)


def ensure_dirs() -> None:
    for d in (DATA_DIR, BIN_DIR, DB_DIR, PROFILES_DIR, CACHE_DIR, LOG_DIR, CACHE_DIR / "icons", CACHE_DIR / "ui"):
        d.mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    """Папка, где лежит Zephyrus.exe (или корень проекта при запуске из исходников)."""
    return Path(sys.executable).resolve().parent if IS_FROZEN else project_root()


def resource_dir() -> Path:
    """Корень ресурсов PyInstaller (_internal) либо корень проекта."""
    return Path(getattr(sys, "_MEIPASS", project_root()))


def bundled_bin_dirs() -> list[Path]:
    """Где искать «из коробки» yt-dlp/ffmpeg: рядом с exe и в _internal."""
    found: list[Path] = []
    for d in (install_dir() / "bin", resource_dir() / "bin"):
        if d.is_dir() and d not in found:
            found.append(d)
    return found
