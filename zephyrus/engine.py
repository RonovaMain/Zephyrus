"""Движок: yt-dlp + FFmpeg.

Схема «гибридного кэша»:
  1. В папке установки лежат базовые версии (bin\\ рядом с exe или в _internal\\bin).
  2. При запуске недостающие файлы копируются в LOCALAPPDATA\\Zephyrus\\bin.
  3. Программа ВСЕГДА запускает yt-dlp из LOCALAPPDATA\\Zephyrus\\bin.
  4. «Обновить движок» асинхронно скачивает свежий yt-dlp с GitHub (с проверкой SHA-256)
     и атомарно заменяет файл в LOCALAPPDATA.
"""
from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QProcess, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .paths import (APP_VERSION, BIN_DIR, ENGINE_FILES, FFMPEG_NAME, IS_WINDOWS, YTDLP_NAME,
                    bundled_bin_dirs)

log = logging.getLogger(__name__)

RELEASE_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"


def _release_asset_name() -> str:
    if IS_WINDOWS:
        return "yt-dlp_x86.exe" if platform.machine().lower() in ("x86", "i386", "i686") else "yt-dlp.exe"
    if sys.platform == "darwin":
        return "yt-dlp_macos"
    return "yt-dlp_linux_aarch64" if platform.machine().lower() in ("aarch64", "arm64") else "yt-dlp_linux"


def probe_version(program: str, args: list[str], callback: Callable[[str], None], parent: QObject) -> None:
    """Асинхронно спросить версию программы (без блокировки интерфейса)."""
    proc = QProcess(parent)
    state = {"done": False}

    def finish(text: str) -> None:
        if state["done"]:
            return
        state["done"] = True
        callback(text)
        proc.deleteLater()

    def on_finished(*_: object) -> None:
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace").strip().splitlines()
        first = out[0] if out else ""
        m = re.search(r"version\s+(\S+)", first)
        finish(m.group(1) if m else first)

    proc.finished.connect(on_finished)
    proc.errorOccurred.connect(lambda err: finish("") if err == QProcess.ProcessError.FailedToStart else None)
    proc.start(program, args)


class EngineManager(QObject):
    updateStatus = pyqtSignal(str)
    updateProgress = pyqtSignal(int)          # 0..100
    updateFinished = pyqtSignal(bool, str)    # ok, message

    def __init__(self) -> None:
        super().__init__()
        self._nam = QNetworkAccessManager(self)
        self._updating = False
        self._reply: QNetworkReply | None = None
        self._tmp_file = None

    # ---------- пути ----------
    @property
    def ytdlp_path(self) -> Path:
        return BIN_DIR / YTDLP_NAME

    @property
    def ffmpeg_dir(self) -> Path:
        return BIN_DIR

    @property
    def is_updating(self) -> bool:
        return self._updating

    def is_ready(self) -> bool:
        return self.ytdlp_path.exists()

    # ---------- первый запуск ----------
    def ensure_installed(self) -> list[str]:
        """Скопировать недостающие файлы из папки установки в LOCALAPPDATA\\Zephyrus\\bin."""
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for name in ENGINE_FILES:
            target = BIN_DIR / name
            if target.exists():
                continue
            for src_dir in bundled_bin_dirs():
                src = src_dir / name
                if src.exists():
                    try:
                        shutil.copy2(src, target)
                        if not IS_WINDOWS:
                            target.chmod(0o755)
                        copied.append(name)
                    except OSError as exc:
                        log.error("Не удалось скопировать %s: %s", name, exc)
                    break
        return copied

    def versions(self, callback: Callable[[str, str], None]) -> None:
        """callback(ytdlp_version, ffmpeg_version) — вызывается когда обе версии известны."""
        result: dict[str, str] = {}

        def got(key: str, value: str) -> None:
            result[key] = value or "не найден"
            if len(result) == 2:
                callback(result["yt"], result["ff"])

        probe_version(str(self.ytdlp_path), ["--version"], lambda v: got("yt", v), self)
        probe_version(str(BIN_DIR / FFMPEG_NAME), ["-version"], lambda v: got("ff", v), self)

    # ---------- обновление yt-dlp ----------
    def _get(self, url: str) -> QNetworkReply:
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setRawHeader(b"User-Agent", f"Zephyrus/{APP_VERSION}".encode())
        req.setTransferTimeout(30_000)
        return self._nam.get(req)

    def update_ytdlp(self) -> None:
        if self._updating:
            return
        self._updating = True
        self.updateProgress.emit(0)
        self.updateStatus.emit("Получение контрольных сумм…")
        reply = self._get(RELEASE_BASE + "SHA2-256SUMS")
        reply.finished.connect(lambda: self._on_sums(reply))

    def _fail(self, message: str) -> None:
        self._updating = False
        self._cleanup_tmp()
        self.updateFinished.emit(False, message)

    def _on_sums(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return self._fail(f"Не удалось получить контрольные суммы: {reply.errorString()}")
        asset = _release_asset_name()
        expected = ""
        for line in bytes(reply.readAll()).decode("utf-8", "replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == asset:
                expected = parts[0].lower()
        if not expected:
            return self._fail(f"В релизе нет контрольной суммы для {asset}")
        self._expected_hash = expected
        self._tmp_path = BIN_DIR / (YTDLP_NAME + ".download")
        try:
            self._tmp_file = open(self._tmp_path, "wb")
        except OSError as exc:
            return self._fail(f"Нет доступа к папке движка: {exc}")
        self.updateStatus.emit("Скачивание yt-dlp…")
        self._reply = self._get(RELEASE_BASE + asset)
        self._reply.readyRead.connect(self._on_chunk)
        self._reply.downloadProgress.connect(self._on_dl_progress)
        self._reply.finished.connect(self._on_binary)

    def _on_chunk(self) -> None:
        if self._reply is not None and self._tmp_file is not None:
            self._tmp_file.write(bytes(self._reply.readAll()))

    def _on_dl_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.updateProgress.emit(int(received * 100 / total))

    def _cleanup_tmp(self) -> None:
        if self._tmp_file is not None:
            try:
                self._tmp_file.close()
            except OSError:
                pass
            self._tmp_file = None
        tmp = getattr(self, "_tmp_path", None)
        if tmp is not None:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass

    def _on_binary(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return self._fail(f"Ошибка загрузки: {reply.errorString()}")
        self._on_chunk_remaining(reply)
        self._tmp_file.close()
        self._tmp_file = None
        self.updateStatus.emit("Проверка целостности…")

        digest = hashlib.sha256()
        with open(self._tmp_path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != self._expected_hash or self._tmp_path.stat().st_size < 2_000_000:
            return self._fail("Контрольная сумма не совпала — файл не установлен")

        target = self.ytdlp_path
        try:
            if not IS_WINDOWS:
                self._tmp_path.chmod(0o755)
            os.replace(self._tmp_path, target)
        except OSError as exc:
            return self._fail(f"Не удалось заменить файл (закройте активные загрузки): {exc}")
        self._updating = False
        self.updateProgress.emit(100)
        self.updateFinished.emit(True, "Движок обновлён до последней версии")

    def _on_chunk_remaining(self, reply: QNetworkReply) -> None:
        rest = bytes(reply.readAll())
        if rest and self._tmp_file is not None:
            self._tmp_file.write(rest)
