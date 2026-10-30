"""Вкладка «🔑 Сессии»: плитки сайтов, вход через встроенный Chromium, управление профилями."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractButton, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..context import AppContext
from ..favicons import get_favicons
from ..sessions import SITE_BY_KEY, SITES, SessionManager, Site, site_icon_domain, site_label
from ..theme import qcolor, theme
from ..utils import host_of
from .login_dialog import LoginDialog
from .widgets import Card, make_label, page_header

TILE_W, TILE_H = 158, 132


def paint_site_icon(p: QPainter, rect: QRectF, domain: str, letter: str, color: str) -> None:
    """Значок сайта на белой плашке: favicon либо цветная буква."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(rect, rect.width() * 0.3, rect.width() * 0.3)
    p.fillPath(path, QColor("#FFFFFF"))
    p.setPen(QPen(QColor(0, 0, 0, 22), 1))
    p.drawPath(path)
    pm = get_favicons().get(domain)
    if pm is not None:
        inner = rect.adjusted(rect.width() * 0.2, rect.width() * 0.2, -rect.width() * 0.2, -rect.width() * 0.2)
        p.drawPixmap(inner.toRect(), pm)
    else:
        f = QFont()
        f.setPixelSize(int(rect.height() * 0.5))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)
    p.restore()


class SiteTile(QAbstractButton):
    def __init__(self, name: str, domain: str, letter: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name, self._domain, self._letter, self._color = name, domain, letter, color
        self._status = ""
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(TILE_W, TILE_H)
        get_favicons().loaded.connect(lambda d: self.update() if d == self._domain else None)

    def set_status(self, text: str, active: bool) -> None:
        self._status, self._active = text, active
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(TILE_W, TILE_H)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette
        hover = self.underMouse()
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(r, 20, 20)
        p.fillPath(path, QColor(pal.accent_soft if hover else pal.surface))
        p.setPen(QPen(QColor(pal.accent if hover else pal.border), 1.6 if hover else 1.2))
        p.drawPath(path)
        paint_site_icon(p, QRectF(r.center().x() - 24, r.top() + 16, 48, 48), self._domain, self._letter, self._color)
        f = QFont(self.font())
        f.setPixelSize(14)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(pal.text))
        p.drawText(QRectF(r.left(), r.top() + 70, r.width(), 22), Qt.AlignmentFlag.AlignCenter, self._name)
        f.setPixelSize(11)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(pal.success if self._active else pal.text_dim))
        p.drawText(QRectF(r.left() + 6, r.top() + 94, r.width() - 12, 20), Qt.AlignmentFlag.AlignCenter,
                   ("● " if self._active else "") + self._status)


class IconBadge(QWidget):
    def __init__(self, domain: str, letter: str, color: str, size: int = 40) -> None:
        super().__init__()
        self._d, self._l, self._c = domain, letter, color
        self.setFixedSize(size, size)
        get_favicons().loaded.connect(lambda d: self.update() if d == self._d else None)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        paint_site_icon(p, QRectF(self.rect()).adjusted(1, 1, -1, -1), self._d, self._l, self._c)


class SessionsPage(QWidget):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.sm: SessionManager = ctx.sessions
        self._tiles: list[tuple[SiteTile, str]] = []
        self._cols = 0
        self._build()
        self.sm.changed.connect(self.refresh)
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)
        root.addWidget(page_header(
            "Сессии",
            "Войдите в аккаунт на сайте — Zephyrus сохранит cookies в зашифрованный профиль и подставит их в yt-dlp "
            "автоматически (для закрытых, возрастных и платных видео)."))

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for site in SITES:
            tile = SiteTile(site.name, site.icon_domain, site.letter, site.color)
            tile.clicked.connect(lambda _=False, s=site: self._login(s.key, s.name, s.login_url))
            self._tiles.append((tile, site.key))
        custom = SiteTile("Другой сайт", "", "＋", theme.palette.accent)
        custom.set_status("любой адрес", False)
        custom.clicked.connect(self._login_custom)
        self._tiles.append((custom, "__custom__"))
        root.addWidget(self.grid_host)

        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(make_label("Мои профили", "CardTitle"), 1)
        imp = QPushButton("📄  Импорт cookies.txt")
        imp.setObjectName("Small")
        imp.setCursor(Qt.CursorShape.PointingHandCursor)
        imp.clicked.connect(self._import)
        head.addWidget(imp)
        cl.addLayout(head)
        self.profiles_box = QVBoxLayout()
        self.profiles_box.setSpacing(8)
        cl.addLayout(self.profiles_box)
        self.empty = make_label("Профилей пока нет. Нажмите на плитку сайта, чтобы войти в аккаунт.", "Dim", wrap=True)
        cl.addWidget(self.empty)
        self.note = make_label(
            "Профили шифруются ключом, привязанным к вашей учётной записи Windows. Если Google/YouTube не пускает "
            "во встроенном браузере — экспортируйте cookies.txt расширением и используйте «Импорт».", "Dim", wrap=True)
        cl.addWidget(self.note)
        root.addWidget(card)
        root.addStretch(1)
        self._relayout()

    # ---------- плитки ----------
    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self) -> None:
        avail = max(self.width() - 72, TILE_W)
        cols = max(1, (avail + 14) // (TILE_W + 14))
        if cols == self._cols:
            return
        self._cols = cols
        for i, (tile, _key) in enumerate(self._tiles):
            self.grid.addWidget(tile, i // cols, i % cols)

    def refresh(self) -> None:
        profiles = self.sm.profiles()
        for tile, key in self._tiles:
            if key == "__custom__":
                continue
            mine = [p for p in profiles if p["site"] == key]
            active = any(p["active"] for p in mine)
            tile.set_status(f"профилей: {len(mine)}" if mine else "нет профилей", active)
        # список профилей
        while self.profiles_box.count():
            item = self.profiles_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for p in profiles:
            self.profiles_box.addWidget(self._profile_row(p))
        self.empty.setVisible(not profiles)

    def _profile_row(self, p: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("Row")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)
        site = SITE_BY_KEY.get(p["site"])
        lay.addWidget(IconBadge(site_icon_domain(p["site"]), site.letter if site else "?", site.color if site else "#999999"))
        info = QVBoxLayout()
        info.setSpacing(0)
        info.addWidget(make_label(p["name"], "RowTitle"))
        try:
            when = datetime.fromisoformat(p["created_at"]).strftime("%d.%m.%Y")
        except ValueError:
            when = ""
        info.addWidget(make_label(f"{site_label(p['site'])} · cookies: {p['cookie_count']} · {when}", "Dim"))
        lay.addLayout(info, 1)
        if p["active"]:
            lay.addWidget(make_label("Активен", "Pill"))
        else:
            b = QPushButton("Сделать активным")
            b.setObjectName("Small")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, pid=p["id"]: self.sm.set_active(pid))
            lay.addWidget(b)
        ren = QPushButton("✏")
        ren.setObjectName("Small")
        ren.setToolTip("Переименовать")
        ren.clicked.connect(lambda _=False, pid=p["id"], n=p["name"]: self._rename(pid, n))
        dele = QPushButton("🗑")
        dele.setObjectName("Danger")
        dele.setProperty("small", True)
        dele.setToolTip("Удалить профиль полностью")
        dele.clicked.connect(lambda _=False, pid=p["id"], n=p["name"]: self._delete(pid, n))
        for b in (ren, dele):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)
        return row

    # ---------- действия ----------
    def _next_name(self, site_key: str) -> str:
        return f"Профиль {len(self.sm.profiles(site_key)) + 1}"

    def _login(self, site_key: str, name: str, url: str, hosts: list[str] | None = None) -> None:
        dlg = LoginDialog(name, url, self.window())
        if dlg.exec() != LoginDialog.DialogCode.Accepted:
            dlg.deleteLater()
            return
        cookies = dlg.cookies()
        dlg.deleteLater()
        pname, ok = QInputDialog.getText(self, "Название профиля", "Как назвать этот профиль?", text=self._next_name(site_key))
        if not ok or not pname.strip():
            return
        self.sm.add_profile(site_key, pname.strip(), cookies, hosts)

    def _login_custom(self) -> None:
        url, ok = QInputDialog.getText(self, "Другой сайт", "Адрес страницы входа (https://…):")
        url = url.strip()
        if not ok or not url:
            return
        if "://" not in url:
            url = "https://" + url
        key, hosts = SessionManager.custom_site_key(url)
        if not hosts or not hosts[0]:
            QMessageBox.warning(self, "Zephyrus", "Не удалось определить домен сайта.")
            return
        self._login(key, host_of(url), url, hosts)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите cookies.txt", "", "Cookies (*.txt);;Все файлы (*)")
        if not path:
            return
        names = [s.name for s in SITES] + ["Другой сайт…"]
        choice, ok = QInputDialog.getItem(self, "Сайт", "Для какого сайта эти cookies?", names, 0, False)
        if not ok:
            return
        if choice == "Другой сайт…":
            host, ok = QInputDialog.getText(self, "Домен", "Домен сайта (например example.com):")
            if not ok or not host.strip():
                return
            site_key = f"custom:{host.strip().lower()}"
        else:
            site_key = next(s.key for s in SITES if s.name == choice)
        pname, ok = QInputDialog.getText(self, "Название профиля", "Название:", text=self._next_name(site_key))
        if not ok or not pname.strip():
            return
        try:
            self.sm.import_netscape_file(site_key, pname.strip(), path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Импорт cookies", str(exc))

    def _rename(self, pid: str, old: str) -> None:
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое название:", text=old)
        if ok and name.strip():
            self.sm.rename(pid, name.strip())

    def _delete(self, pid: str, name: str) -> None:
        if QMessageBox.question(self, "Удалить профиль", f"Удалить профиль «{name}» вместе с сохранёнными cookies?") \
                == QMessageBox.StandardButton.Yes:
            self.sm.delete(pid)
