"""Главное окно: боковое меню + 4 вкладки."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QScrollArea,
                             QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from ..branding import logo_icon, logo_pixmap
from ..context import AppContext
from ..downloader import Job
from ..paths import APP_AUTHOR, APP_NAME, APP_VERSION
from ..theme import theme
from .download_page import DownloadPage
from .history_page import HistoryPage
from .settings_page import SettingsPage
from .sessions_page import SessionsPage
from .widgets import BackgroundWidget, GradientLabel, NavButton, make_label


def scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    area.viewport().setAutoFillBackground(False)
    widget.setAutoFillBackground(False)
    return area


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(logo_icon())
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)

        bg = BackgroundWidget()
        self.setCentralWidget(bg)
        root = QHBoxLayout(bg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.download_page = DownloadPage(ctx)
        self.sessions_page = SessionsPage(ctx)
        self.history_page = HistoryPage(ctx)
        self.settings_page = SettingsPage(ctx)
        self.stack.addWidget(scrollable(self.download_page))
        self.stack.addWidget(scrollable(self.sessions_page))
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(scrollable(self.settings_page))
        root.addWidget(self.stack, 1)

        self.history_page.navigateToDownloads.connect(lambda: self._go(0))
        self._setup_tray()
        ctx.downloads.jobFinished.connect(self._on_job_finished)
        theme.changed.connect(lambda: theme.style_window(self))
        ctx.engine.versions(lambda yt, _ff: self.engine_lbl.setText(f"yt-dlp {yt}"))

    # ------------------------------------------------------------ боковое меню
    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(250)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(16, 24, 16, 18)
        lay.setSpacing(4)

        brand = QHBoxLayout()
        brand.setContentsMargins(6, 0, 0, 0)
        brand.setSpacing(12)
        logo = QLabel()
        dpr = self.devicePixelRatioF()
        logo.setPixmap(logo_pixmap(46, dpr))
        logo.setFixedSize(46, 46)
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(GradientLabel(APP_NAME, 24))
        title.addWidget(make_label("media downloader", "Dim"))
        brand.addWidget(logo)
        brand.addLayout(title)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(26)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.nav: list[NavButton] = []
        for i, (emoji, text) in enumerate((("📥", "Загрузка"), ("🔑", "Сессии"), ("📜", "История"), ("⚙️", "Настройки"))):
            b = NavButton(emoji, text)
            self.group.addButton(b, i)
            b.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            lay.addWidget(b)
            self.nav.append(b)
        self.nav[0].setChecked(True)
        lay.addStretch(1)

        self.engine_lbl = make_label("yt-dlp …", "Dim")
        lay.addWidget(self.engine_lbl)
        lay.addWidget(make_label(f"v{APP_VERSION}  ·  {APP_AUTHOR}", "Dim"))
        return bar

    def _go(self, idx: int) -> None:
        self.nav[idx].setChecked(True)
        self.stack.setCurrentIndex(idx)

    # ------------------------------------------------------------ трей и уведомления
    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(logo_icon(), self)
            self.tray.setToolTip(APP_NAME)
            self.tray.show()

    def _on_job_finished(self, job: Job, ok: bool, message: str, paths: list) -> None:
        if not self.ctx.settings.get("notifications") or self.tray is None or message == "Загрузка отменена":
            return
        if ok:
            name = paths[0].replace("\\", "/").rsplit("/", 1)[-1] if paths else job.url
            self.tray.showMessage("Загрузка завершена", name, QSystemTrayIcon.MessageIcon.Information, 5000)
        else:
            self.tray.showMessage("Ошибка загрузки", message, QSystemTrayIcon.MessageIcon.Warning, 7000)

    # ------------------------------------------------------------ окно
    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        theme.style_window(self)

    def closeEvent(self, e) -> None:  # noqa: N802
        if self.ctx.downloads.is_busy():
            answer = QMessageBox.question(self, APP_NAME, "Идёт загрузка. Закрыть программу и прервать её?")
            if answer != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.ctx.downloads.cancel_current()
        if self.tray:
            self.tray.hide()
        super().closeEvent(e)
