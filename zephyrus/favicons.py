"""Значки сайтов: берём favicon через сервис Google, кэшируем на диск. Пока грузится — рисуем букву."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .paths import CACHE_DIR


class FaviconCache(QObject):
    loaded = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._nam = QNetworkAccessManager(self)
        self._mem: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._failed: set[str] = set()

    def get(self, domain: str) -> QPixmap | None:
        if not domain:
            return None
        if domain in self._mem:
            return self._mem[domain]
        path = CACHE_DIR / "icons" / f"{domain}.png"
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._mem[domain] = pm
                return pm
        if domain not in self._pending and domain not in self._failed:
            self._fetch(domain)
        return None

    def _fetch(self, domain: str) -> None:
        self._pending.add(domain)
        req = QNetworkRequest(QUrl(f"https://www.google.com/s2/favicons?domain={domain}&sz=64"))
        req.setTransferTimeout(10_000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, d=domain: self._done(r, d))

    def _done(self, reply: QNetworkReply, domain: str) -> None:
        self._pending.discard(domain)
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._failed.add(domain)
            return
        pm = QPixmap()
        if pm.loadFromData(bytes(reply.readAll())):
            try:
                pm.save(str(CACHE_DIR / "icons" / f"{domain}.png"), "PNG")
            except OSError:
                pass
            self._mem[domain] = pm
            self.loaded.emit(domain)
        else:
            self._failed.add(domain)


favicons: FaviconCache | None = None


def get_favicons() -> FaviconCache:
    global favicons
    if favicons is None:
        favicons = FaviconCache()
    return favicons
