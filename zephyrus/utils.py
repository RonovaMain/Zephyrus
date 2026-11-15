"""Мелкие вспомогательные функции."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from urllib.parse import urlparse

from .i18n import tr

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match((text or "").strip()))


def host_of(url: str) -> str:
    try:
        return (urlparse(url.strip()).hostname or "").lower()
    except ValueError:
        return ""


def human_size(num: float | None) -> str:
    if num is None or num < 0:
        return "—"
    units = ("unit.b", "unit.kb", "unit.mb", "unit.gb", "unit.tb")
    value = float(num)
    for i, key in enumerate(units):
        if value < 1024 or i == len(units) - 1:
            return f"{value:.0f} {tr(key)}" if i == 0 else f"{value:.1f} {tr(key)}"
        value /= 1024
    return "—"


def human_speed(bytes_per_sec: float | None) -> str:
    return "—" if not bytes_per_sec else human_size(bytes_per_sec) + tr("unit.per_s")


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def format_duration(seconds: float | None) -> str:
    return format_eta(seconds) if seconds else ""


def base_domain(host: str) -> str:
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def reveal_in_folder(path: str) -> None:
    """Показать файл в проводнике (или открыть папку на других ОС)."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    path = os.path.normpath(path)
    if sys.platform.startswith("win") and os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", path])  # noqa: S603,S607
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def open_folder(folder: str) -> None:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
