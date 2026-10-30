"""Вкладка «📥 Загрузка»."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QListWidget, QPlainTextEdit, QPushButton,
                             QVBoxLayout, QWidget, QLineEdit)

from ..context import AppContext
from ..downloader import Job
from ..sessions import site_label
from ..utils import format_duration, format_eta, human_size, human_speed, looks_like_url, open_folder, reveal_in_folder
from ..ytdlp_args import AUDIO_QUALITIES, VIDEO_QUALITIES
from .widgets import (Card, GradientButton, GradientProgressBar, RoundedImage, Segmented, ToggleSwitch,
                      make_combo, make_label, page_header, set_combo_data)


class DownloadPage(QWidget):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self._token = -1
        self._last_path = ""
        self._thumb_reply: QNetworkReply | None = None
        self._nam = QNetworkAccessManager(self)
        self._debounce = QTimer(self, singleShot=True, interval=750)
        self._debounce.timeout.connect(self._analyze)
        self._formats: dict = {"videos": [], "audios": []}
        self._manual_on = False
        self._show_audio_pick = False
        self._build()
        self._wire()
        self._refresh_labels()
        self._refresh_sessions()
        self._fill_quality()

    # ------------------------------------------------------------ построение
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)
        root.addWidget(page_header("Загрузка", "Вставьте ссылку на видео, плейлист или трек — Zephyrus сделает остальное."))

        # --- ввод ---
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 22, 24, 22)
        cl.setSpacing(16)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://…  ссылка на видео или плейлист")
        self.url.setClearButtonEnabled(True)
        self.url.setMinimumHeight(48)
        self.paste_btn = QPushButton("📋  Вставить")
        self.paste_btn.setMinimumHeight(48)
        self.paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.url, 1)
        row.addWidget(self.paste_btn)
        cl.addLayout(row)

        self.preview = QWidget()
        pl = QHBoxLayout(self.preview)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(16)
        self.thumb = RoundedImage()
        pl.addWidget(self.thumb)
        pv = QVBoxLayout()
        pv.setSpacing(4)
        self.pv_title = make_label("", "CardTitle", wrap=True)
        self.pv_meta = make_label("", "Dim")
        pv.addStretch(1)
        pv.addWidget(self.pv_title)
        pv.addWidget(self.pv_meta)
        pv.addStretch(1)
        pl.addLayout(pv, 1)
        self.preview.hide()
        cl.addWidget(self.preview)

        self.segment = Segmented(["🎬  Видео MP4", "🎵  Аудио MP3"])
        cl.addWidget(self.segment)

        self.qmode = Segmented(["⚡  Лучшее доступное", "🎚  Выбрать вручную"])
        self.qmode.setEnabled(False)
        cl.addWidget(self.qmode)
        self.qmode_hint = make_label("Ручной выбор качества видео и звука появится после анализа ссылки.", "Dim", wrap=True)
        cl.addWidget(self.qmode_hint)

        # ручной выбор: видео и звук отдельно, склейка в FFmpeg
        self.manual_box = QWidget()
        ml = QGridLayout(self.manual_box)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setHorizontalSpacing(14)
        ml.setVerticalSpacing(6)
        self.v_lbl = make_label("Качество видео", "Dim")
        self.a_lbl = make_label("Качество звука", "Dim")
        self.vfmt = make_combo()
        self.afmt = make_combo()
        self.manual_note = make_label("", "Dim", wrap=True)
        ml.addWidget(self.v_lbl, 0, 0)
        ml.addWidget(self.a_lbl, 0, 1)
        ml.addWidget(self.vfmt, 1, 0)
        ml.addWidget(self.afmt, 1, 1)
        ml.addWidget(self.manual_note, 2, 0, 1, 2)
        ml.setColumnStretch(0, 3)
        ml.setColumnStretch(1, 2)
        self.manual_box.hide()
        cl.addWidget(self.manual_box)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        self.q_lbl = make_label("Качество (максимум)", "Dim")
        grid.addWidget(self.q_lbl, 0, 0)
        grid.addWidget(make_label("Сессия (cookies)", "Dim"), 0, 1)
        grid.addWidget(make_label("Плейлист целиком", "Dim"), 0, 2)
        self.quality = make_combo()
        self.session = make_combo()
        self.playlist = ToggleSwitch(self.ctx.settings.get("playlist"))
        grid.addWidget(self.quality, 1, 0)
        grid.addWidget(self.session, 1, 1)
        grid.addWidget(self.playlist, 1, 2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        cl.addLayout(grid)

        self.error = make_label("", "Error", wrap=True)
        self.error.hide()
        cl.addWidget(self.error)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.start_btn = GradientButton("⬇   Скачать")
        self.cancel_btn = QPushButton("✕  Отмена")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setMinimumHeight(48)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.hide()
        actions.addWidget(self.start_btn, 1)
        actions.addWidget(self.cancel_btn)
        cl.addLayout(actions)
        root.addWidget(card)

        # --- прогресс ---
        prog = Card()
        pg = QVBoxLayout(prog)
        pg.setContentsMargins(24, 20, 24, 20)
        pg.setSpacing(12)
        top = QHBoxLayout()
        self.status = make_label("Готов к загрузке", "CardTitle")
        self.item_lbl = make_label("", "Dim")
        top.addWidget(self.status, 1)
        top.addWidget(self.item_lbl)
        pg.addLayout(top)
        self.bar = GradientProgressBar()
        pg.addWidget(self.bar)

        stats = QHBoxLayout()
        self.stat_labels: dict[str, object] = {}
        for key, caption in (("pct", "Прогресс"), ("speed", "Скорость"), ("eta", "Осталось"), ("size", "Размер")):
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(make_label(caption, "Dim"))
            value = make_label("—", "Stat")
            col.addWidget(value)
            self.stat_labels[key] = value
            stats.addLayout(col, 1)
        pg.addLayout(stats)

        foot = QHBoxLayout()
        self.log_btn = QPushButton("Журнал  ▾")
        self.log_btn.setObjectName("Small")
        self.log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn = QPushButton("📂  Показать файл")
        self.open_btn.setObjectName("Small")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.hide()
        foot.addWidget(self.log_btn)
        foot.addStretch(1)
        foot.addWidget(self.open_btn)
        pg.addLayout(foot)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(800)
        self.log.setFixedHeight(170)
        self.log.hide()
        pg.addWidget(self.log)
        root.addWidget(prog)

        # --- очередь ---
        self.queue_card = Card()
        ql = QVBoxLayout(self.queue_card)
        ql.setContentsMargins(24, 18, 24, 18)
        ql.setSpacing(10)
        qh = QHBoxLayout()
        self.queue_title = make_label("В очереди", "CardTitle")
        self.clear_queue_btn = QPushButton("Очистить очередь")
        self.clear_queue_btn.setObjectName("Small")
        qh.addWidget(self.queue_title, 1)
        qh.addWidget(self.clear_queue_btn)
        ql.addLayout(qh)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(130)
        ql.addWidget(self.queue_list)
        self.queue_card.hide()
        root.addWidget(self.queue_card)
        root.addStretch(1)

    def _wire(self) -> None:
        s, d = self.ctx.settings, self.ctx.downloads
        self.url.textChanged.connect(self._on_url_changed)
        self.url.returnPressed.connect(self._start)
        self.paste_btn.clicked.connect(self._paste)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(d.cancel_current)
        self.segment.currentChanged.connect(self._on_mode_changed)
        self.qmode.currentChanged.connect(lambda *_: self._update_manual())
        self.quality.currentIndexChanged.connect(self._save_quality)
        self.playlist.toggled.connect(lambda on: s.set("playlist", on))
        self.log_btn.clicked.connect(self._toggle_log)
        self.open_btn.clicked.connect(self._open_result)
        self.clear_queue_btn.clicked.connect(d.clear_queue)
        d.jobStarted.connect(self._on_job_started)
        d.progressChanged.connect(self._on_progress)
        d.logLine.connect(self.log.appendPlainText)
        d.jobFinished.connect(self._on_job_finished)
        d.queueChanged.connect(self._refresh_queue)
        self.ctx.info.ready.connect(self._on_info)
        self.ctx.info.failed.connect(self._on_info_failed)
        self.ctx.sessions.changed.connect(self._refresh_sessions)
        s.changed.connect(lambda *_: self._refresh_labels())
        self.segment.setCurrentIndex(0 if s.get("format_mode") == "video" else 1, animate=False)

    # ------------------------------------------------------------ настройки формата
    def _refresh_labels(self) -> None:
        s = self.ctx.settings
        self.segment.setItems([f"🎬  Видео {s.get('video_container').upper()}", f"🎵  Аудио {s.get('audio_format').upper()}"])

    def _fill_quality(self) -> None:
        s = self.ctx.settings
        audio = self.segment.currentIndex() == 1
        items = AUDIO_QUALITIES if audio else VIDEO_QUALITIES
        self.quality.blockSignals(True)
        self.quality.clear()
        for text, data in items:
            self.quality.addItem(text, data)
        set_combo_data(self.quality, s.get("audio_quality" if audio else "video_quality"))
        self.quality.blockSignals(False)

    def _on_mode_changed(self, idx: int) -> None:
        self.ctx.settings.set("format_mode", "audio" if idx == 1 else "video")
        self._fill_quality()
        self._update_manual()

    def _save_quality(self) -> None:
        data = self.quality.currentData()
        if data is not None:
            self.ctx.settings.set("audio_quality" if self.segment.currentIndex() == 1 else "video_quality", data)

    def _refresh_sessions(self) -> None:
        current = self.session.currentData() or "auto"
        self.session.blockSignals(True)
        self.session.clear()
        self.session.addItem("Авто — по сайту ссылки", "auto")
        self.session.addItem("Без cookies", "none")
        for p in self.ctx.sessions.profiles():
            self.session.addItem(f"{site_label(p['site'])} · {p['name']}", p["id"])
        set_combo_data(self.session, current)
        self.session.blockSignals(False)

    # ------------------------------------------------------------ ссылка и анализ
    def _paste(self) -> None:
        text = (QApplication.clipboard().text() or "").strip()
        if text:
            self.url.setText(text.splitlines()[0].strip())
            self.url.setFocus()

    def _on_url_changed(self, text: str) -> None:
        self.error.hide()
        self._debounce.stop()
        if looks_like_url(text):
            self._debounce.start()
        else:
            self.ctx.info.cancel()
            self.preview.hide()
            self._set_formats(None)

    def _analyze(self) -> None:
        url = self.url.text().strip()
        if not looks_like_url(url):
            return
        self.preview.show()
        self.thumb.setPixmap(None)
        self.pv_title.setText("Получаем информацию…")
        self.pv_meta.setText("")
        self._set_formats(None)
        self._token = self.ctx.info.fetch(url, self.playlist.isChecked(), self.session.currentData() or "auto")

    def _on_info(self, info: dict, token: int) -> None:
        if token != self._token:
            return
        self.pv_title.setText(info["title"])
        parts = [info["uploader"]] if info["uploader"] else []
        if info["is_playlist"]:
            parts.append(f"плейлист · {info['count']} видео")
        elif info["duration"]:
            parts.append(format_duration(info["duration"]))
        self.pv_meta.setText("  •  ".join(parts))
        self._set_formats(info.get("formats"))
        if info["thumbnail"]:
            if self._thumb_reply is not None:
                self._thumb_reply.abort()
            req = QNetworkRequest(QUrl(info["thumbnail"]))
            req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            req.setTransferTimeout(15_000)
            reply = self._nam.get(req)
            self._thumb_reply = reply
            reply.finished.connect(lambda r=reply, t=token: self._on_thumb(r, t))

    def _on_thumb(self, reply: QNetworkReply, token: int) -> None:
        reply.deleteLater()
        if reply is self._thumb_reply:
            self._thumb_reply = None
        if token != self._token or reply.error() != QNetworkReply.NetworkError.NoError:
            return
        pm = QPixmap()
        if pm.loadFromData(bytes(reply.readAll())):
            self.thumb.setPixmap(pm)

    def _on_info_failed(self, message: str, token: int) -> None:
        if token != self._token:
            return
        self.pv_title.setText("Не удалось получить информацию о ссылке")
        self.pv_meta.setText(message)

    # ------------------------------------------------------------ ручной выбор форматов
    def _set_formats(self, fmts: dict | None) -> None:
        self._formats = fmts or {"videos": [], "audios": []}
        self.vfmt.clear()
        for v in self._formats["videos"]:
            self.vfmt.addItem(v["label"], f"{v['id']}|{1 if v['muxed'] else 0}")
        self.afmt.clear()
        if self._formats["audios"]:
            self.afmt.addItem("Лучший звук (авто)", "")
            for a in self._formats["audios"]:
                self.afmt.addItem(a["label"], a["id"])
        self._update_manual()

    def _manual_active(self) -> bool:
        return self._manual_on

    def _update_manual(self) -> None:
        audio_mode = self.segment.currentIndex() == 1
        vids, auds = self._formats["videos"], self._formats["audios"]
        muxed_only = bool(vids) and vids[0]["muxed"]
        available = bool(auds) if audio_mode else bool(vids)
        self.qmode.setEnabled(available)
        self.qmode_hint.setVisible(not available)
        if not available and self.qmode.currentIndex() == 1:
            self.qmode.setCurrentIndex(0)
        manual = available and self.qmode.currentIndex() == 1
        self._manual_on = manual
        self.manual_box.setVisible(manual)
        self.q_lbl.setVisible(not manual)
        self.quality.setVisible(not manual)
        if not manual:
            return
        show_v = not audio_mode
        show_a = audio_mode or (not muxed_only and bool(auds))
        self._show_audio_pick = show_a
        for w in (self.v_lbl, self.vfmt):
            w.setVisible(show_v)
        for w in (self.a_lbl, self.afmt):
            w.setVisible(show_a)
        container = self.ctx.settings.get("video_container").upper()
        if audio_mode:
            self.manual_note.setText(f"Выбранная дорожка будет скачана и конвертирована в {self.ctx.settings.get('audio_format').upper()} через FFmpeg.")
        elif muxed_only:
            self.manual_note.setText("Для этого сайта доступны только готовые форматы — звук уже внутри видео.")
        else:
            self.manual_note.setText(f"Видео и звук скачиваются отдельно и склеиваются FFmpeg в один файл {container}. "
                                     "Если лучшее качество плохое — выберите строкой ниже.")

    def _manual_selection(self, audio_mode: bool) -> tuple[str, str]:
        """(спецификация формата для yt-dlp, подпись для истории)."""
        aud_id = self.afmt.currentData() or ""
        aud_text = (self.afmt.currentText().split(" · ")[0] if aud_id else "звук авто")
        if audio_mode:
            return (aud_id or "ba"), aud_text
        vid_id, muxed = (self.vfmt.currentData() or "|0").split("|")
        v_text = self.vfmt.currentText().split(" · ")[0]
        container = self.ctx.settings.get("video_container").upper()
        if muxed == "1":
            return vid_id, f"{container} · {v_text}"
        if self._show_audio_pick and aud_id:
            return f"{vid_id}+{aud_id}", f"{container} · {v_text} + {aud_text}"
        return f"{vid_id}+ba/{vid_id}", f"{container} · {v_text} + звук авто"

    # ------------------------------------------------------------ запуск
    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()

    def _start(self) -> None:
        url = self.url.text().strip()
        if not looks_like_url(url):
            self._show_error("Вставьте корректную ссылку, начинающуюся с http:// или https://")
            return
        audio_mode = self.segment.currentIndex() == 1
        quality, label = self.quality.currentData() or "best", ""
        if self._manual_active():
            spec, label = self._manual_selection(audio_mode)
            quality = "fmt:" + spec
        job = Job(url=url, mode="audio" if audio_mode else "video", quality=quality, label=label,
                  playlist=self.playlist.isChecked(), session=self.session.currentData() or "auto")
        if self.ctx.downloads.is_busy():
            self.status.setText("Добавлено в очередь")
        self.ctx.downloads.enqueue(job)
        self.ctx.info.cancel()
        self.url.clear()
        self.preview.hide()
        self._set_formats(None)

    def _toggle_log(self) -> None:
        show = not self.log.isVisible()
        self.log.setVisible(show)
        self.log_btn.setText("Журнал  ▴" if show else "Журнал  ▾")

    def _open_result(self) -> None:
        if self._last_path:
            reveal_in_folder(self._last_path)
        else:
            open_folder(self.ctx.settings.get("download_dir"))

    # ------------------------------------------------------------ события загрузки
    def _on_job_started(self, job: Job) -> None:
        self.log.clear()
        self.bar.reset()
        self.bar.setIndeterminate(True)
        self.status.setText("Запуск…")
        self.item_lbl.setText("")
        self.open_btn.hide()
        self.cancel_btn.show()
        for lab in self.stat_labels.values():
            lab.setText("—")

    def _on_progress(self, parser) -> None:
        self.status.setText(parser.status)
        self.item_lbl.setText(f"Элемент {parser.item} из {parser.item_count}" if parser.item_count > 1 else "")
        if parser.percent is None or parser.indeterminate:
            self.bar.setIndeterminate(True)
        else:
            self.bar.setIndeterminate(False)
            self.bar.setValue(parser.percent)
        self.stat_labels["pct"].setText("—" if parser.percent is None else f"{parser.percent:.1f}%")
        self.stat_labels["speed"].setText(human_speed(parser.speed))
        self.stat_labels["eta"].setText(format_eta(parser.eta))
        self.stat_labels["size"].setText(human_size(parser.size))

    def _on_job_finished(self, job: Job, ok: bool, message: str, paths: list) -> None:
        self.bar.setIndeterminate(False)
        self.cancel_btn.hide()
        if ok:
            self.bar.setValue(100)
            self.status.setText("Готово ✓")
            self.stat_labels["pct"].setText("100%")
            self._last_path = paths[0] if paths else ""
            self.open_btn.show()
        else:
            self.bar.reset()
            self.status.setText(f"Ошибка: {message}" if message != "Загрузка отменена" else message)

    def _refresh_queue(self) -> None:
        queue = self.ctx.downloads.queue
        self.queue_card.setVisible(bool(queue))
        self.queue_title.setText(f"В очереди: {len(queue)}")
        self.queue_list.clear()
        for job in queue:
            self.queue_list.addItem(("🎵  " if job.mode == "audio" else "🎬  ") + job.url)
