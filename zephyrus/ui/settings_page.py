"""Вкладка «⚙️ Настройки»."""
from __future__ import annotations

from PyQt6.QtCore import QLocale, QRectF, QSize, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractButton, QColorDialog, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox,
                             QPushButton, QSpinBox, QVBoxLayout, QWidget)

from ..context import AppContext
from ..i18n import LANGUAGES, current_language, resolve_language, tr
from ..paths import APP_AUTHOR, APP_GITHUB_URL, APP_NAME, APP_VERSION, BIN_DIR, DATA_DIR
from ..theme import ACCENTS, theme
from ..utils import open_folder
from .widgets import (Card, GradientButton, GradientProgressBar, Segmented, ToggleSwitch, make_combo, make_label,
                      page_header, set_combo_data)

MODES = ["light", "dark", "system"]


class AccentSwatch(QAbstractButton):
    def __init__(self, key: str, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setToolTip(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 40)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(40, 40)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c1, c2 = theme.accent_pair(self.key)
        r = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(c1))
        g.setColorAt(1, QColor(c2))
        path = QPainterPath()
        path.addEllipse(r)
        p.fillPath(path, g)
        if self.isChecked():
            p.setPen(QPen(QColor(theme.palette.text), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
        if self.key == "custom":
            p.setPen(QColor("#FFFFFF"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "＋" if not self.isChecked() else "✎")


def setting_row(title: str, desc: str, control: QWidget) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 4, 0, 4)
    lay.setSpacing(16)
    text = QVBoxLayout()
    text.setSpacing(1)
    text.addWidget(make_label(title, "RowTitle"))
    if desc:
        text.addWidget(make_label(desc, "Dim", wrap=True))
    lay.addLayout(text, 1)
    lay.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return w


def section(title: str) -> tuple[Card, QVBoxLayout]:
    card = Card()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(24, 20, 24, 20)
    lay.setSpacing(10)
    lay.addWidget(make_label(title, "CardTitle"))
    return card, lay


class SettingsPage(QWidget):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.s = ctx.settings
        self._build()
        self._load()
        self._wire()
        self._refresh_versions()

    # ------------------------------------------------------------ построение
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)
        root.addWidget(page_header(tr("set.title"), tr("set.subtitle")))

        # --- папка ---
        card, lay = section(tr("set.sec_folder"))
        row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.dir_btn = QPushButton(tr("set.choose"))
        self.open_dir_btn = QPushButton("📂  " + tr("set.open"))
        for b in (self.dir_btn, self.open_dir_btn):
            b.setMinimumHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(self.dir_btn)
        row.addWidget(self.open_dir_btn)
        lay.addLayout(row)
        root.addWidget(card)

        # --- оформление ---
        card, lay = section(tr("set.sec_look"))
        self.mode_seg = Segmented(["☀️  " + tr("set.mode_light"), "🌙  " + tr("set.mode_dark"), "🖥  " + tr("set.mode_system")])
        self.mode_seg.setFixedWidth(430)
        lay.addWidget(setting_row(tr("set.theme"), tr("set.theme_desc"), self.mode_seg))
        sw_box = QWidget()
        sw_lay = QHBoxLayout(sw_box)
        sw_lay.setContentsMargins(0, 0, 0, 0)
        sw_lay.setSpacing(4)
        self.swatches: list[AccentSwatch] = []
        for key in ACCENTS:
            sw = AccentSwatch(key, tr(f"acc.{key}"))
            self.swatches.append(sw)
            sw_lay.addWidget(sw)
        self.custom_sw = AccentSwatch("custom", tr("set.custom_color"))
        self.swatches.append(self.custom_sw)
        sw_lay.addWidget(self.custom_sw)
        lay.addWidget(setting_row(tr("set.accent"), tr("set.accent_desc"), sw_box))
        root.addWidget(card)

        # --- язык ---
        card, lay = section(tr("set.sec_lang"))
        self.lang_combo = make_combo([(tr("set.lang_auto"), "auto")] + [(name, code) for code, name in LANGUAGES.items()])
        self.lang_combo.setMinimumWidth(240)
        lay.addWidget(setting_row(tr("set.language"), tr("set.language_desc"), self.lang_combo))
        root.addWidget(card)

        # --- загрузка ---
        card, lay = section(tr("set.sec_download"))
        self.container = make_combo([("MP4", "mp4"), ("MKV", "mkv"), ("WEBM", "webm")])
        self.audio_fmt = make_combo([("MP3", "mp3"), ("M4A", "m4a"), ("OPUS", "opus"), ("FLAC", "flac"), ("WAV", "wav")])
        for c in (self.container, self.audio_fmt):
            c.setMinimumWidth(140)
        lay.addWidget(setting_row(tr("set.container"), tr("set.container_desc"), self.container))
        lay.addWidget(setting_row(tr("set.audio_fmt"), tr("set.audio_fmt_desc"), self.audio_fmt))
        self.t_thumb = ToggleSwitch()
        self.t_meta = ToggleSwitch()
        self.t_subs = ToggleSwitch()
        self.t_sponsor = ToggleSwitch()
        lay.addWidget(setting_row(tr("set.thumb"), tr("set.thumb_desc"), self.t_thumb))
        lay.addWidget(setting_row(tr("set.meta"), tr("set.meta_desc"), self.t_meta))
        lay.addWidget(setting_row(tr("set.subs"), tr("set.subs_desc"), self.t_subs))
        self.subs_langs = QLineEdit()
        self.subs_langs.setPlaceholderText("ru,en")
        self.subs_langs.setMinimumWidth(180)
        lay.addWidget(setting_row(tr("set.subs_langs"), tr("set.subs_langs_desc"), self.subs_langs))
        lay.addWidget(setting_row(tr("set.sponsor"), tr("set.sponsor_desc"), self.t_sponsor))
        self.template = QLineEdit()
        self.template.setMinimumWidth(300)
        lay.addWidget(setting_row(tr("set.template"), tr("set.template_desc"), self.template))
        root.addWidget(card)

        # --- сеть ---
        card, lay = section(tr("set.sec_net"))
        self.rate = QLineEdit()
        self.rate.setPlaceholderText(tr("set.rate_ph"))
        self.rate.setMinimumWidth(220)
        self.frag = QSpinBox()
        self.frag.setRange(1, 16)
        self.frag.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.frag.setFixedWidth(90)
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText(tr("set.proxy_ph"))
        self.proxy.setMinimumWidth(260)
        lay.addWidget(setting_row(tr("set.rate"), tr("set.rate_desc"), self.rate))
        lay.addWidget(setting_row(tr("set.frag"), tr("set.frag_desc"), self.frag))
        lay.addWidget(setting_row(tr("set.proxy"), tr("set.proxy_desc"), self.proxy))
        self.t_notify = ToggleSwitch()
        lay.addWidget(setting_row(tr("set.notify"), tr("set.notify_desc"), self.t_notify))
        root.addWidget(card)

        # --- движок ---
        card, lay = section(tr("set.sec_engine"))
        self.ver_yt = make_label("…", "RowTitle")
        self.ver_ff = make_label("…", "RowTitle")
        lay.addWidget(setting_row("yt-dlp", tr("set.ytdlp_desc", path=BIN_DIR), self.ver_yt))
        lay.addWidget(setting_row("FFmpeg", tr("set.ffmpeg_desc"), self.ver_ff))
        self.t_autoupd = ToggleSwitch()
        lay.addWidget(setting_row(tr("set.auto_update"), tr("set.auto_update_desc"), self.t_autoupd))
        self.update_btn = GradientButton("🔄   " + tr("set.update_btn"))
        self.update_btn.setMinimumHeight(46)
        lay.addWidget(self.update_btn)
        self.upd_bar = GradientProgressBar()
        self.upd_bar.hide()
        lay.addWidget(self.upd_bar)
        self.upd_status = make_label("", "Dim", wrap=True)
        self.upd_status.hide()
        lay.addWidget(self.upd_status)
        self.data_btn = QPushButton("📁  " + tr("set.open_data"))
        self.data_btn.setObjectName("Small")
        self.data_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.data_btn, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(card)

        # --- о программе ---
        card, lay = section(tr("set.sec_about"))
        lay.addWidget(make_label(f"{APP_NAME} {APP_VERSION}", "RowTitle"))
        lay.addWidget(make_label(tr("set.about_text"), "Dim"))
        author = QHBoxLayout()
        author.setSpacing(10)
        author.addWidget(make_label(tr("set.author"), "Dim"))
        author.addWidget(make_label(APP_AUTHOR, "Pill"))
        self.github_btn = QPushButton("GitHub  ↗")
        self.github_btn.setObjectName("Small")
        self.github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if APP_GITHUB_URL:
            self.github_btn.setToolTip(APP_GITHUB_URL)
        else:
            self.github_btn.setEnabled(False)
            self.github_btn.setToolTip(tr("set.github_tip"))
        author.addWidget(self.github_btn)
        author.addStretch(1)
        lay.addLayout(author)
        self.reset_btn = QPushButton(tr("set.reset"))
        self.reset_btn.setObjectName("Danger")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.reset_btn, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(card)
        root.addStretch(1)

    # ------------------------------------------------------------ загрузка значений
    def _load(self) -> None:
        s = self.s
        widgets = [self.mode_seg, self.container, self.audio_fmt, self.t_thumb, self.t_meta, self.t_subs,
                   self.t_sponsor, self.t_notify, self.t_autoupd, self.lang_combo, self.subs_langs, self.template, self.rate, self.frag, self.proxy]
        for w in widgets:
            w.blockSignals(True)
        self.dir_edit.setText(s.get("download_dir"))
        mode = s.get("theme_mode")
        self.mode_seg.setCurrentIndex(MODES.index(mode) if mode in MODES else 0, animate=False)
        self._select_swatch(s.get("accent"))
        set_combo_data(self.container, s.get("video_container"))
        set_combo_data(self.audio_fmt, s.get("audio_format"))
        self.t_thumb.setChecked(s.get("embed_thumbnail"))
        self.t_meta.setChecked(s.get("embed_metadata"))
        self.t_subs.setChecked(s.get("embed_subs"))
        self.t_sponsor.setChecked(s.get("sponsorblock"))
        self.t_notify.setChecked(s.get("notifications"))
        self.t_autoupd.setChecked(s.get("engine_auto_update"))
        set_combo_data(self.lang_combo, s.get("language"))
        self.subs_langs.setText(s.get("subs_langs"))
        self.template.setText(s.get("filename_template"))
        self.rate.setText(s.get("rate_limit"))
        self.frag.setValue(s.get("fragments"))
        self.proxy.setText(s.get("proxy"))
        for w in widgets:
            w.blockSignals(False)

    def _wire(self) -> None:
        s = self.s
        self.dir_btn.clicked.connect(self._choose_dir)
        self.open_dir_btn.clicked.connect(lambda: open_folder(s.get("download_dir")))
        self.mode_seg.currentChanged.connect(lambda i: self._set_theme(mode=MODES[i]))
        for sw in self.swatches:
            sw.clicked.connect(lambda _=False, w=sw: self._pick_accent(w))
        self.container.currentIndexChanged.connect(lambda: s.set("video_container", self.container.currentData()))
        self.audio_fmt.currentIndexChanged.connect(lambda: s.set("audio_format", self.audio_fmt.currentData()))
        for key, tog in (("embed_thumbnail", self.t_thumb), ("embed_metadata", self.t_meta), ("embed_subs", self.t_subs),
                         ("sponsorblock", self.t_sponsor), ("notifications", self.t_notify),
                         ("engine_auto_update", self.t_autoupd)):
            tog.toggled.connect(lambda on, k=key: s.set(k, on))
        for key, edit in (("subs_langs", self.subs_langs), ("filename_template", self.template),
                          ("rate_limit", self.rate), ("proxy", self.proxy)):
            edit.editingFinished.connect(lambda k=key, e=edit: s.set(k, e.text().strip()))
        self.frag.valueChanged.connect(lambda v: s.set("fragments", v))
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        self.update_btn.clicked.connect(self._update_engine)
        self.data_btn.clicked.connect(lambda: open_folder(str(DATA_DIR)))
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(APP_GITHUB_URL)))
        self.reset_btn.clicked.connect(self._reset)
        eng = self.ctx.engine
        eng.updateStatus.connect(self._on_upd_status)
        eng.updateProgress.connect(lambda v: self.upd_bar.setValue(v))
        eng.updateFinished.connect(self._on_upd_finished)

    # ------------------------------------------------------------ тема
    def _select_swatch(self, key: str) -> None:
        for sw in self.swatches:
            sw.setChecked(sw.key == key)
            sw.update()

    def _set_theme(self, mode: str | None = None, accent: str | None = None, custom: str | None = None) -> None:
        s = self.s
        if mode:
            s.set("theme_mode", mode)
        if accent:
            s.set("accent", accent)
        if custom:
            s.set("accent_custom", custom)
        theme.configure(s.get("theme_mode"), s.get("accent"), s.get("accent_custom"))
        theme.apply()

    def _pick_accent(self, sw: AccentSwatch) -> None:
        if sw.key == "custom":
            color = QColorDialog.getColor(QColor(self.s.get("accent_custom")), self, tr("set.custom_title"))
            if not color.isValid():
                self._select_swatch(self.s.get("accent"))
                return
            self._set_theme(accent="custom", custom=color.name().upper())
        else:
            self._set_theme(accent=sw.key)
        self._select_swatch(self.s.get("accent"))

    # ------------------------------------------------------------ язык
    def _on_language(self) -> None:
        code = self.lang_combo.currentData() or "auto"
        self.s.set("language", code)
        if resolve_language(code, QLocale.system().uiLanguages()) == current_language():
            return
        if QMessageBox.question(self, tr("set.restart_title"), tr("set.restart_text")) == QMessageBox.StandardButton.Yes:
            self.ctx.restart_requested = True   # main.py перезапустит программу после закрытия окна
            self.window().close()

    # ------------------------------------------------------------ папка
    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("set.pick_dir"), self.s.get("download_dir"))
        if path:
            self.s.set("download_dir", path)
            self.dir_edit.setText(path)

    # ------------------------------------------------------------ движок
    def _refresh_versions(self) -> None:
        self.ver_yt.setText("…")
        self.ver_ff.setText("…")
        self.ctx.engine.versions(lambda yt, ff: (self.ver_yt.setText(yt), self.ver_ff.setText(ff)))

    def _update_engine(self) -> None:
        if self.ctx.downloads.is_busy():
            QMessageBox.information(self, APP_NAME, tr("set.wait_dl"))
            return
        self.update_btn.setEnabled(False)
        self.upd_bar.reset()
        self.upd_bar.show()
        self.upd_status.show()
        self.upd_status.setObjectName("Dim")
        self.ctx.engine.update_ytdlp()

    def _on_upd_status(self, text: str) -> None:
        self.upd_status.setText(text)

    def _on_upd_finished(self, ok: bool, message: str) -> None:
        self.update_btn.setEnabled(True)
        self.upd_status.setText(("✓ " if ok else "✕ ") + message)
        self.upd_status.setObjectName("Success" if ok else "Error")
        self.upd_status.style().unpolish(self.upd_status)
        self.upd_status.style().polish(self.upd_status)
        if ok:
            self._refresh_versions()
        else:
            self.upd_bar.hide()

    def _reset(self) -> None:
        if QMessageBox.question(self, tr("set.reset_title"), tr("set.reset_text")) != QMessageBox.StandardButton.Yes:
            return
        self.s.reset()
        self._load()
        self._set_theme()
