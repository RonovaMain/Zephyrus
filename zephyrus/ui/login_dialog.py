"""Окно авторизации на QWebEngineView. Перехватывает cookies и отдаёт их для сохранения в профиль."""
from __future__ import annotations

import re

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtNetwork import QNetworkCookie
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QToolButton, QVBoxLayout

from ..theme import theme
from .widgets import GradientButton, make_label


def _cookie_to_dict(c: QNetworkCookie) -> dict:
    return {
        "domain": c.domain(),
        "path": c.path() or "/",
        "secure": c.isSecure(),
        "httponly": c.isHttpOnly(),
        "expires": 0 if c.isSessionCookie() else int(c.expirationDate().toSecsSinceEpoch()),
        "name": bytes(c.name()).decode("utf-8", "replace"),
        "value": bytes(c.value()).decode("utf-8", "replace"),
    }


class LoginDialog(QDialog):
    def __init__(self, site_name: str, url: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Вход — {site_name}")
        self.resize(1040, 740)
        self._cookies: dict[tuple[str, str, str], dict] = {}

        # off-the-record профиль: на диск ничего не пишется, cookies забираем сами
        self._profile = QWebEngineProfile(self)
        ua = re.sub(r"\s*QtWebEngine/\S+", "", self._profile.httpUserAgent())
        self._profile.setHttpUserAgent(ua)
        store = self._profile.cookieStore()
        store.cookieAdded.connect(self._on_added)
        store.cookieRemoved.connect(self._on_removed)
        store.loadAllCookies()

        self._page = QWebEnginePage(self._profile, self)
        try:
            self._page.newWindowRequested.connect(lambda req: self.view.setUrl(req.requestedUrl()))
        except AttributeError:
            pass
        self.view = QWebEngineView(self)
        self.view.setPage(self._page)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.back = QToolButton(text="◀")
        self.fwd = QToolButton(text="▶")
        self.reload = QToolButton(text="⟳")
        for b in (self.back, self.fwd, self.reload):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            bar.addWidget(b)
        self.addr = QLineEdit()
        self.addr.setReadOnly(True)
        bar.addWidget(self.addr, 1)
        lay.addLayout(bar)
        lay.addWidget(self.view, 1)

        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.hint = make_label("Войдите в аккаунт, затем нажмите «Сохранить сессию».", "Dim", wrap=True)
        self.count = make_label("Cookies: 0", "Pill")
        cancel = QPushButton("Отмена")
        cancel.setMinimumHeight(46)
        self.save_btn = GradientButton("✅  Сохранить сессию")
        self.save_btn.setMinimumWidth(240)
        foot.addWidget(self.hint, 1)
        foot.addWidget(self.count)
        foot.addWidget(cancel)
        foot.addWidget(self.save_btn)
        lay.addLayout(foot)

        self.back.clicked.connect(self.view.back)
        self.fwd.clicked.connect(self.view.forward)
        self.reload.clicked.connect(self.view.reload)
        self.view.urlChanged.connect(lambda u: self.addr.setText(u.toString()))
        cancel.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)
        self.view.setUrl(QUrl(url))

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        theme.style_window(self)

    # ---------- cookies ----------
    def _on_added(self, cookie: QNetworkCookie) -> None:
        d = _cookie_to_dict(cookie)
        self._cookies[(d["domain"], d["path"], d["name"])] = d
        self.count.setText(f"Cookies: {len(self._cookies)}")

    def _on_removed(self, cookie: QNetworkCookie) -> None:
        d = _cookie_to_dict(cookie)
        self._cookies.pop((d["domain"], d["path"], d["name"]), None)
        self.count.setText(f"Cookies: {len(self._cookies)}")

    def cookies(self) -> list[dict]:
        return list(self._cookies.values())

    def _save(self) -> None:
        if not self._cookies:
            QMessageBox.information(self, "Zephyrus", "Пока не получено ни одной cookie. Сначала войдите в аккаунт на сайте.")
            return
        self.accept()

    def done(self, result: int) -> None:
        # порядок удаления важен: сначала страница, потом профиль
        self.view.stop()
        self._page.deleteLater()
        self._profile.deleteLater()
        super().done(result)
