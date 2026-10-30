"""Общий контекст: все сервисы приложения в одном месте (передаётся страницам интерфейса)."""
from __future__ import annotations

from dataclasses import dataclass

from .database import Database
from .downloader import DownloadManager, InfoFetcher
from .engine import EngineManager
from .sessions import SessionManager
from .settings import Settings


@dataclass
class AppContext:
    db: Database
    settings: Settings
    engine: EngineManager
    sessions: SessionManager
    downloads: DownloadManager
    info: InfoFetcher
