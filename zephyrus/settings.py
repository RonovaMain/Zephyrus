"""Типизированные настройки поверх таблицы settings (SQLite)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal

from .database import Database


def _default_download_dir() -> str:
    d = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return str(Path(d or Path.home() / "Downloads") / "Zephyrus")


class Settings(QObject):
    changed = pyqtSignal(str)

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self.DEFAULTS: dict[str, Any] = {
            "download_dir": _default_download_dir(),
            "theme_mode": "light",          # light | dark | system
            "accent": "sakura",
            "accent_custom": "#FF8FB8",
            "format_mode": "video",         # video | audio
            "video_quality": "best",
            "audio_quality": "192",
            "video_container": "mp4",
            "audio_format": "mp3",
            "embed_thumbnail": True,
            "embed_metadata": True,
            "embed_subs": False,
            "subs_langs": "ru,en",
            "sponsorblock": False,
            "playlist": False,
            "filename_template": "%(title).150B [%(id)s].%(ext)s",
            "rate_limit": "",
            "fragments": 4,
            "proxy": "",
            "notifications": True,
            "language": "auto",             # auto | ru | uk | be | en
            "engine_auto_update": True,     # проверка yt-dlp в фоне: при первом запуске и раз в ~2 дня
            "engine_last_check": 0,         # unix-время последней успешной проверки
        }

    def get(self, key: str) -> Any:
        default = self.DEFAULTS[key]
        raw = self._db.get_setting(key)
        if raw is None:
            return default
        if isinstance(default, bool):
            return raw == "1"
        if isinstance(default, int):
            try:
                return int(raw)
            except ValueError:
                return default
        return raw

    def set(self, key: str, value: Any) -> None:
        if isinstance(value, bool):
            raw = "1" if value else "0"
        else:
            raw = str(value)
        if self._db.get_setting(key) == raw:
            return
        self._db.set_setting(key, raw)
        self.changed.emit(key)

    # эти ключи не сбрасываются кнопкой «Сбросить настройки»
    KEEP_ON_RESET = ("language", "engine_last_check")

    def reset(self) -> None:
        keep = {k: self._db.get_setting(k) for k in self.KEEP_ON_RESET}
        self._db.clear_settings()
        for key, value in keep.items():
            if value is not None:
                self._db.set_setting(key, value)
        self.changed.emit("*")
