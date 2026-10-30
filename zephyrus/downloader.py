"""Очередь загрузок и запуск yt-dlp через асинхронный QProcess."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from .database import Database
from .engine import EngineManager
from .paths import CACHE_DIR, IS_WINDOWS
from .sessions import SessionManager
from .settings import Settings
from .ytdlp_args import (REC_SEP, BuildOptions, ProgressParser, build_download_args, build_info_args,
                         quality_label, summarize_formats)

log = logging.getLogger(__name__)
_SPLIT_RE = re.compile(rb"[\r\n]+")


@dataclass
class Job:
    url: str
    mode: str                 # video | audio
    quality: str
    playlist: bool = False
    session: str = "auto"     # auto | none | <profile id>
    outdir: str = ""
    history_id: int | None = None
    id: int = 0
    title: str = ""
    label: str = ""           # подпись формата для истории (при ручном выборе)


def _prepare_cookie_file(sessions: SessionManager, url: str, session: str, tag: str) -> str | None:
    if session == "none":
        return None
    pid = None
    if session == "auto":
        prof = sessions.profile_for_url(url)
        pid = prof["id"] if prof else None
    else:
        pid = session
    if not pid:
        return None
    try:
        return str(sessions.export_temp_cookiefile(pid, CACHE_DIR / f"cookies_{tag}.txt"))
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось подготовить cookies: %s", exc)
        return None


def _kill_tree(proc: QProcess) -> None:
    pid = int(proc.processId())
    if IS_WINDOWS and pid:
        try:
            subprocess.Popen(["taskkill", "/PID", str(pid), "/T", "/F"], creationflags=0x08000000,  # noqa: S603,S607
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    proc.kill()


def _env(engine: EngineManager) -> QProcessEnvironment:
    env = QProcessEnvironment.systemEnvironment()
    env.insert("PYTHONUTF8", "1")
    env.insert("PYTHONIOENCODING", "utf-8")
    env.insert("PATH", str(engine.ffmpeg_dir) + os.pathsep + env.value("PATH", ""))
    return env


class DownloadManager(QObject):
    jobStarted = pyqtSignal(object)
    progressChanged = pyqtSignal(object)            # ProgressParser
    logLine = pyqtSignal(str)
    jobFinished = pyqtSignal(object, bool, str, list)   # job, ok, message, [paths]
    queueChanged = pyqtSignal()
    historyChanged = pyqtSignal()

    def __init__(self, db: Database, settings: Settings, engine: EngineManager, sessions: SessionManager) -> None:
        super().__init__()
        self._db, self._s, self._engine, self._sessions = db, settings, engine, sessions
        self._queue: list[Job] = []
        self._proc: QProcess | None = None
        self._job: Job | None = None
        self._parser: ProgressParser | None = None
        self._buf = b""
        self._cancelled = False
        self._cookie_tmp: Path | None = None
        self._record: Path | None = None
        self._next_id = 1

    # ---------- публичное API ----------
    @property
    def current_job(self) -> Job | None:
        return self._job

    @property
    def queue(self) -> list[Job]:
        return list(self._queue)

    def is_busy(self) -> bool:
        return self._proc is not None

    def enqueue(self, job: Job) -> None:
        job.id = self._next_id
        self._next_id += 1
        self._queue.append(job)
        self.queueChanged.emit()
        QTimer.singleShot(0, self._start_next)

    def clear_queue(self) -> None:
        self._queue.clear()
        self.queueChanged.emit()

    def cancel_current(self) -> None:
        if self._proc is not None:
            self._cancelled = True
            _kill_tree(self._proc)

    # ---------- запуск ----------
    def _start_next(self) -> None:
        if self._proc is not None or not self._queue:
            return
        job = self._queue.pop(0)
        self.queueChanged.emit()
        if not self._engine.is_ready():
            self.jobFinished.emit(job, False, "yt-dlp не найден. Положите yt-dlp.exe в папку bin или нажмите «Обновить движок».", [])
            QTimer.singleShot(0, self._start_next)
            return

        s = self._s
        outdir = job.outdir or s.get("download_dir")
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as exc:
            self.jobFinished.emit(job, False, f"Не удалось создать папку загрузки: {exc}", [])
            QTimer.singleShot(0, self._start_next)
            return

        cookie_file = _prepare_cookie_file(self._sessions, job.url, job.session, str(job.id))
        self._cookie_tmp = Path(cookie_file) if cookie_file else None
        self._record = CACHE_DIR / f"rec_{job.id}.txt"
        self._record.unlink(missing_ok=True)

        opts = BuildOptions(
            url=job.url, mode=job.mode, quality=job.quality, outdir=outdir,
            ffmpeg_dir=str(self._engine.ffmpeg_dir), record_file=str(self._record), cookie_file=cookie_file,
            playlist=job.playlist, container=s.get("video_container"), audio_format=s.get("audio_format"),
            filename_template=s.get("filename_template") or "%(title).150B [%(id)s].%(ext)s",
            embed_thumbnail=s.get("embed_thumbnail"), embed_metadata=s.get("embed_metadata"),
            embed_subs=s.get("embed_subs"), subs_langs=s.get("subs_langs"), sponsorblock=s.get("sponsorblock"),
            rate_limit=s.get("rate_limit"), fragments=s.get("fragments"), proxy=s.get("proxy"),
        )
        job.outdir = outdir
        self._job, self._cancelled, self._buf = job, False, b""
        self._parser = ProgressParser(mode=job.mode)

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setProcessEnvironment(_env(self._engine))
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._proc = proc
        self.jobStarted.emit(job)
        self.progressChanged.emit(self._parser)
        proc.start(str(self._engine.ytdlp_path), build_download_args(opts))

    # ---------- вывод ----------
    def _on_output(self) -> None:
        if self._proc is None:
            return
        self._buf += bytes(self._proc.readAllStandardOutput())
        parts = _SPLIT_RE.split(self._buf)
        self._buf = parts.pop()  # неполная последняя строка
        self._consume(parts)

    def _consume(self, raw_lines: list[bytes]) -> None:
        if not self._parser:
            return
        changed = False
        for raw in raw_lines:
            line = raw.decode("utf-8", "replace")
            if self._parser.feed(line):
                self.logLine.emit(line.strip())
            changed = True
        if changed:
            self.progressChanged.emit(self._parser)

    def _on_error(self, err: QProcess.ProcessError) -> None:
        if err == QProcess.ProcessError.FailedToStart and self._proc is not None:
            self._finish(False, "Не удалось запустить yt-dlp (проверьте файл в LOCALAPPDATA\\Zephyrus\\bin)", [])

    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        if self._proc is None:
            return
        if self._buf:
            self._consume([self._buf])
            self._buf = b""
        parser = self._parser
        records = self._read_records()
        if self._cancelled:
            return self._finish(False, "Загрузка отменена", [])
        if code != 0 and not records:
            msg = (parser.last_error if parser else "") or f"yt-dlp завершился с кодом {code}"
            return self._finish(False, msg, [])
        if not records and parser and parser.last_destination:
            records = [(Path(parser.last_destination).stem, parser.last_destination)]
        if not records:
            return self._finish(False, "yt-dlp не сообщил путь к файлу", [])
        self._finish(True, "Готово", records)

    def _read_records(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if self._record and self._record.exists():
            for line in self._record.read_text(encoding="utf-8", errors="replace").splitlines():
                if REC_SEP in line:
                    title, path = line.split(REC_SEP, 1)
                    if path.strip():
                        out.append((title.strip(), path.strip()))
        return out

    def _finish(self, ok: bool, message: str, records: list[tuple[str, str]]) -> None:
        job, proc = self._job, self._proc
        self._proc = None
        self._job = None
        if proc is not None:
            proc.deleteLater()
        for tmp in (self._cookie_tmp, self._record):
            if tmp:
                try:
                    Path(tmp).unlink(missing_ok=True)
                except OSError:
                    pass
        self._cookie_tmp = self._record = None
        if job is None:
            return
        paths: list[str] = []
        if ok:
            fmt = job.label or quality_label(job.mode, job.quality, self._s.get("video_container"),
                                             self._s.get("audio_format"))
            for i, (title, path) in enumerate(records):
                paths.append(path)
                if job.history_id and i == 0:
                    self._db.update_history(job.history_id, title or Path(path).stem, fmt, path)
                else:
                    self._db.add_history(title or Path(path).stem, job.url, job.mode, job.quality, fmt, path)
            self.historyChanged.emit()
        self.jobFinished.emit(job, ok, message, paths)
        QTimer.singleShot(200, self._start_next)


class InfoFetcher(QObject):
    """Получение метаданных ссылки (название, обложка, длительность) через yt-dlp -J."""
    ready = pyqtSignal(dict, int)
    failed = pyqtSignal(str, int)

    def __init__(self, engine: EngineManager, settings: Settings, sessions: SessionManager) -> None:
        super().__init__()
        self._engine, self._s, self._sessions = engine, settings, sessions
        self._proc: QProcess | None = None
        self._token = 0
        self._cookie_tmp: Path | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def cancel(self) -> None:
        self._token += 1
        self._timer.stop()
        if self._proc is not None:
            proc, self._proc = self._proc, None
            proc.finished.disconnect()
            _kill_tree(proc)
            proc.deleteLater()
        self._drop_cookies()

    def fetch(self, url: str, playlist: bool, session: str) -> int:
        self.cancel()
        if not self._engine.is_ready():
            self.failed.emit("Движок не найден", self._token)
            return self._token
        token = self._token
        cookie = _prepare_cookie_file(self._sessions, url, session, f"info_{token}")
        self._cookie_tmp = Path(cookie) if cookie else None
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.setProcessEnvironment(_env(self._engine))
        proc.finished.connect(lambda *_: self._on_finished(proc, token))
        self._proc = proc
        proc.start(str(self._engine.ytdlp_path), build_info_args(url, playlist, cookie, self._s.get("proxy")))
        self._timer.start(60_000)
        return token

    def _drop_cookies(self) -> None:
        if self._cookie_tmp:
            try:
                self._cookie_tmp.unlink(missing_ok=True)
            except OSError:
                pass
            self._cookie_tmp = None

    def _on_timeout(self) -> None:
        token = self._token
        self.cancel()
        self.failed.emit("Превышено время ожидания", token)

    def _on_finished(self, proc: QProcess, token: int) -> None:
        if proc is not self._proc or token != self._token:
            return
        self._timer.stop()
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        self._proc = None
        proc.deleteLater()
        self._drop_cookies()
        start = out.find("{")
        try:
            data = json.loads(out[start:]) if start >= 0 else None
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            msg = next((ln[7:] for ln in err.splitlines() if ln.startswith("ERROR: ")), "") or "Не удалось получить информацию"
            self.failed.emit(msg, token)
            return
        self.ready.emit(self._summarize(data), token)

    @staticmethod
    def _summarize(d: dict) -> dict:
        entries = d.get("entries") or []
        is_playlist = d.get("_type") == "playlist"
        thumb = d.get("thumbnail") or ""
        for t in reversed(d.get("thumbnails") or []):
            url = t.get("url") or ""
            if ".jpg" in url:
                thumb = url
                break
        if is_playlist and not thumb and entries:
            first = entries[0] or {}
            thumb = first.get("thumbnail") or ((first.get("thumbnails") or [{}])[-1].get("url", ""))
        return {
            "title": d.get("title") or d.get("id") or "Без названия",
            "uploader": d.get("uploader") or d.get("channel") or "",
            "duration": d.get("duration"),
            "thumbnail": thumb,
            "is_playlist": is_playlist,
            "count": d.get("playlist_count") or len(entries),
            "formats": summarize_formats(d.get("formats") or []) if not is_playlist else {"videos": [], "audios": []},
        }
