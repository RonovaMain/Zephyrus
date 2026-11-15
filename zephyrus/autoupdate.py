"""Автообновление yt-dlp в фоне.

* Первый запуск (проверок ещё не было) — проверяем сразу; если yt-dlp нет вовсе — скачиваем.
* Дальше — примерно раз в 2 дня, пока программа открыта (таймер сверяется каждые 30 минут).
  Если программа была закрыта дольше 2 дней, проверка пройдёт при следующем запуске.
* Скачивается только более новая версия: сначала узнаём тег последнего релиза на GitHub и сравниваем
  с локальной версией. Сама загрузка идёт через EngineManager.update_ytdlp (SHA-256 + атомарная замена).
* Пока идёт загрузка видео, файл не трогаем — повторим позже. Ошибки сети молча логируются.
"""
from __future__ import annotations

import logging
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .downloader import DownloadManager
from .engine import EngineManager, probe_version, version_key
from .settings import Settings

log = logging.getLogger(__name__)

CHECK_INTERVAL_S = 2 * 24 * 3600      # «примерно каждые 2 дня»
TICK_MS = 30 * 60 * 1000              # как часто сверяем время последней проверки
RETRY_MS = 10 * 60 * 1000             # повтор после неудачи (нет сети, файл занят)
FIRST_DELAY_MS = 3000                 # дать окну спокойно открыться


class AutoUpdater(QObject):
    engineMissing = pyqtSignal()      # yt-dlp нет и скачать его не удалось (один раз за запуск)

    def __init__(self, engine: EngineManager, settings: Settings, downloads: DownloadManager) -> None:
        super().__init__()
        self._engine, self._s, self._downloads = engine, settings, downloads
        self._busy = False
        self._warned = False
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        settings.changed.connect(self._on_setting)
        engine.updateFinished.connect(self._on_update_finished)
        downloads.jobFinished.connect(lambda *_: QTimer.singleShot(5000, self._tick))

    def start(self) -> None:
        self._timer.start()
        QTimer.singleShot(FIRST_DELAY_MS, self._tick)

    # ---------- когда пора проверять ----------
    def _due(self) -> bool:
        if not self._engine.is_ready():
            return True               # без yt-dlp программа бесполезна — качаем независимо от переключателя
        if not self._s.get("engine_auto_update"):
            return False
        last, now = int(self._s.get("engine_last_check")), int(time.time())
        return last <= 0 or last > now or now - last >= CHECK_INTERVAL_S

    def _on_setting(self, key: str) -> None:
        if key == "engine_auto_update" and self._s.get("engine_auto_update"):
            QTimer.singleShot(0, self._tick)

    # ---------- проверка ----------
    def _tick(self) -> None:
        if self._busy or self._engine.is_updating or not self._due():
            return
        if self._downloads.is_busy():
            return                    # заменить yt-dlp во время загрузки нельзя; после неё _tick вызовется снова
        self._busy = True
        self._engine.check_latest(self._on_latest)

    def _retry_later(self) -> None:
        self._busy = False
        QTimer.singleShot(RETRY_MS, self._tick)

    def _on_latest(self, tag: str) -> None:
        if not version_key(tag):
            log.info("Автообновление: не удалось узнать последнюю версию yt-dlp")
            self._warn_if_missing()
            return self._retry_later()
        if not self._engine.is_ready():
            return self._download()
        probe_version(str(self._engine.ytdlp_path), ["--version"], lambda local: self._compare(tag, local), self)

    def _compare(self, tag: str, local: str) -> None:
        if local and version_key(local) >= version_key(tag):
            log.info("Автообновление: yt-dlp %s актуален", local)
            self._mark_checked()
            self._busy = False
            return
        log.info("Автообновление: %s -> %s", local or "?", tag)
        self._download()

    def _download(self) -> None:
        if self._downloads.is_busy() or self._engine.is_updating:
            self._busy = False        # ручное обновление или загрузка уже идут — проверим на следующем такте
            return
        self._engine.update_ytdlp()   # результат придёт в _on_update_finished

    # ---------- итог (в том числе ручного обновления кнопкой) ----------
    def _on_update_finished(self, ok: bool, message: str) -> None:
        if ok:
            log.info("Автообновление: %s", message)
            self._mark_checked()
            self._busy = False
            return
        log.warning("Автообновление не удалось: %s", message)
        self._warn_if_missing()
        self._retry_later()

    def _mark_checked(self) -> None:
        self._s.set("engine_last_check", int(time.time()))

    def _warn_if_missing(self) -> None:
        if not self._engine.is_ready() and not self._warned:
            self._warned = True
            self.engineMissing.emit()
