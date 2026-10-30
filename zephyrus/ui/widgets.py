"""Кастомные виджеты: градиентные кнопки, сегмент-переключатель, тумблер, прогресс-бар и т.д."""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import (QAbstractButton, QComboBox, QFrame, QGraphicsDropShadowEffect, QLabel, QListView,
                             QSizePolicy, QWidget)

from ..theme import mix, on_color, qcolor, theme


def make_label(text: str = "", obj: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if obj:
        lab.setObjectName(obj)
    lab.setWordWrap(wrap)
    return lab


def make_combo(items: list[tuple[str, str]] | None = None) -> QComboBox:
    cb = QComboBox()
    cb.setView(QListView())  # нужен для корректной стилизации выпадающего списка
    cb.setCursor(Qt.CursorShape.PointingHandCursor)
    for text, data in items or []:
        cb.addItem(text, data)
    return cb


def set_combo_data(cb: QComboBox, data: str) -> None:
    i = cb.findData(data)
    if i >= 0:
        cb.setCurrentIndex(i)


# ------------------------------------------------------------------ фон
class BackgroundWidget(QWidget):
    """Мягкий фон: тонкий перелив и два «свечения» фирменных цветов."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        pal = theme.palette
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor(pal.bg))
        g.setColorAt(1, QColor(pal.bg2))
        p.fillRect(self.rect(), g)
        r = max(w, h) * 0.6
        for cx, cy, color, alpha in ((w * 0.98, -h * 0.05, pal.accent, 46 if not pal.dark else 34),
                                     (w * 0.05, h * 1.05, pal.accent2, 44 if not pal.dark else 30)):
            rg = QRadialGradient(QPointF(cx, cy), r)
            rg.setColorAt(0, qcolor(color, alpha))
            rg.setColorAt(1, qcolor(color, 0))
            p.fillRect(self.rect(), rg)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, shadow: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._eff: QGraphicsDropShadowEffect | None = None
        if shadow:
            self._eff = QGraphicsDropShadowEffect(self)
            self._eff.setBlurRadius(34)
            self._eff.setOffset(0, 8)
            self.setGraphicsEffect(self._eff)
            theme.changed.connect(self._restyle)
            self._restyle()

    def _restyle(self) -> None:
        pal = theme.palette
        self._eff.setColor(QColor(0, 0, 0, 120) if pal.dark else qcolor(pal.accent, 48))


# ------------------------------------------------------------------ кнопки
class GradientButton(QAbstractButton):
    """Основная кнопка: перелив акцентных цветов, глянец, скругление «таблеткой»."""

    def __init__(self, text: str = "", parent: QWidget | None = None, radius: int = 16) -> None:
        super().__init__(parent)
        self.setText(text)
        self._radius = radius
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self.text()) + 56, 48)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = min(float(self._radius), r.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        enabled = self.isEnabled()
        if enabled:
            c1, c2 = QColor(pal.accent), QColor(pal.accent2)
            if self.isDown():
                c1, c2 = c1.darker(110), c2.darker(110)
            elif self.underMouse():
                c1, c2 = c1.lighter(108), c2.lighter(108)
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillPath(path, g)
            gloss = QLinearGradient(r.topLeft(), r.bottomLeft())
            gloss.setColorAt(0, QColor(255, 255, 255, 80))
            gloss.setColorAt(0.55, QColor(255, 255, 255, 0))
            p.fillPath(path, gloss)
            text_color = QColor(on_color(mix(pal.accent, pal.accent2, 0.5)))
        else:
            p.fillPath(path, QColor(pal.border))
            text_color = QColor(pal.text_faint)
        f = QFont(self.font())
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(text_color)
        p.drawText(r.translated(0, 1 if self.isDown() else 0), Qt.AlignmentFlag.AlignCenter, self.text())

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(e)


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._on_toggled)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 28)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def _on_toggled(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on: bool) -> None:  # noqa: N802
        super().setChecked(on)
        if hasattr(self, "_anim"):
            self._pos = 1.0 if on else 0.0
            self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        off = QColor(pal.border_strong)
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor(mix(pal.border_strong, pal.accent, self._pos)))
        g.setColorAt(1, QColor(mix(pal.border_strong, pal.accent2, self._pos)))
        p.fillPath(path, g if self._pos > 0 else off)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 35))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        if not self.isEnabled():
            p.fillPath(path, QColor(255, 255, 255, 120) if not pal.dark else QColor(0, 0, 0, 100))


class Segmented(QWidget):
    """Сегментный переключатель с плавной «таблеткой»."""
    currentChanged = pyqtSignal(int)

    def __init__(self, items: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = list(items)
        self._index = 0
        self._hl = 0.0
        self._anim = QPropertyAnimation(self, b"highlight", self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _get_hl(self) -> float:
        return self._hl

    def _set_hl(self, v: float) -> None:
        self._hl = v
        self.update()

    highlight = pyqtProperty(float, _get_hl, _set_hl)

    def setItems(self, items: list[str]) -> None:  # noqa: N802
        self._items = list(items)
        self.update()

    def currentIndex(self) -> int:  # noqa: N802
        return self._index

    def setCurrentIndex(self, i: int, animate: bool = True) -> None:  # noqa: N802
        i = max(0, min(i, len(self._items) - 1))
        if animate and i != self._index:
            self._anim.stop()
            self._anim.setStartValue(self._hl)
            self._anim.setEndValue(float(i))
            self._anim.start()
        else:
            self._hl = float(i)
        changed = i != self._index
        self._index = i
        self.update()
        if changed:
            self.currentChanged.emit(i)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(max(1, len(self._items)) * 170, 48)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        n = max(1, len(self._items))
        seg = (self.width() - 8) / n
        self.setCurrentIndex(int((e.position().x() - 4) // seg))

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        pal = theme.palette
        n = max(1, len(self._items))
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        track = QPainterPath()
        track.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(track, QColor(pal.surface_alt))
        p.setPen(QPen(QColor(pal.border), 1.2))
        p.drawPath(track)
        pad = 4.0
        seg = (r.width() - 2 * pad) / n
        hl = QRectF(r.left() + pad + self._hl * seg, r.top() + pad, seg, r.height() - 2 * pad)
        g = QLinearGradient(hl.topLeft(), hl.topRight())
        g.setColorAt(0, QColor(pal.accent))
        g.setColorAt(1, QColor(pal.accent2))
        hp = QPainterPath()
        hp.addRoundedRect(hl, hl.height() / 2, hl.height() / 2)
        p.fillPath(hp, g)
        gloss = QLinearGradient(hl.topLeft(), hl.bottomLeft())
        gloss.setColorAt(0, QColor(255, 255, 255, 80))
        gloss.setColorAt(0.6, QColor(255, 255, 255, 0))
        p.fillPath(hp, gloss)
        f = QFont(self.font())
        f.setPixelSize(14)
        f.setBold(True)
        p.setFont(f)
        active_text = on_color(mix(pal.accent, pal.accent2, 0.5))
        for i, text in enumerate(self._items):
            weight = max(0.0, 1.0 - abs(self._hl - i))
            p.setPen(QColor(mix(pal.text_dim, active_text, weight)))
            p.drawText(QRectF(r.left() + pad + i * seg, r.top() + pad, seg, r.height() - 2 * pad),
                       Qt.AlignmentFlag.AlignCenter, text)


class GradientProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shown = 0.0
        self._target = 0.0
        self._indeterminate = False
        self._phase = 0.0
        self.setFixedHeight(16)
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _get_shown(self) -> float:
        return self._shown

    def _set_shown(self, v: float) -> None:
        self._shown = v
        self.update()

    shown = pyqtProperty(float, _get_shown, _set_shown)

    def setValue(self, v: float) -> None:  # noqa: N802
        self._target = max(0.0, min(100.0, v))
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(self._target)
        self._anim.start()

    def reset(self) -> None:
        self._anim.stop()
        self._shown = self._target = 0.0
        self.setIndeterminate(False)
        self.update()

    def setIndeterminate(self, on: bool) -> None:  # noqa: N802
        if on == self._indeterminate:
            return
        self._indeterminate = on
        if on:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette
        r = QRectF(self.rect())
        track = QPainterPath()
        track.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(track, QColor(pal.surface_alt))
        p.setPen(QPen(QColor(pal.border), 1))
        p.drawPath(track)
        p.setClipPath(track)
        if self._indeterminate:
            cw = r.width() * 0.35
            x = -cw + self._phase * (r.width() + cw)
            fill = QRectF(x, r.top(), cw, r.height())
        else:
            width = r.width() * self._shown / 100.0
            if width <= 0:
                return
            fill = QRectF(r.left(), r.top(), max(width, r.height()), r.height())
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor(pal.accent))
        g.setColorAt(1, QColor(pal.accent2))
        fp = QPainterPath()
        fp.addRoundedRect(fill, r.height() / 2, r.height() / 2)
        p.fillPath(fp, g)
        gloss = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        gloss.setColorAt(0, QColor(255, 255, 255, 110))
        gloss.setColorAt(0.6, QColor(255, 255, 255, 0))
        p.fillPath(fp, gloss)


class NavButton(QAbstractButton):
    """Пункт бокового меню: эмодзи + текст, активный — с градиентной подсветкой."""

    def __init__(self, emoji: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._emoji, self._text = emoji, text
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, 50)

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
        r = QRectF(self.rect()).adjusted(2, 3, -2, -3)
        path = QPainterPath()
        path.addRoundedRect(r, 15, 15)
        if self.isChecked():
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, qcolor(pal.accent, 70))
            g.setColorAt(1, qcolor(pal.accent2, 55))
            p.fillPath(path, g)
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(r.left() + 1, r.top() + 11, 4, r.height() - 22), 2, 2)
            bg = QLinearGradient(0, r.top(), 0, r.bottom())
            bg.setColorAt(0, QColor(pal.accent))
            bg.setColorAt(1, QColor(pal.accent2))
            p.fillPath(bar, bg)
        elif self.underMouse():
            p.fillPath(path, qcolor(pal.accent, 28))
        ef = QFont(self.font())
        ef.setPixelSize(19)
        p.setFont(ef)
        p.setPen(QColor(pal.text))
        p.drawText(QRectF(r.left() + 16, r.top(), 32, r.height()), Qt.AlignmentFlag.AlignCenter, self._emoji)
        tf = QFont(self.font())
        tf.setPixelSize(14)
        tf.setBold(self.isChecked())
        p.setFont(tf)
        p.setPen(QColor(pal.text if self.isChecked() else pal.text_dim))
        p.drawText(QRectF(r.left() + 58, r.top(), r.width() - 62, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)


class GradientLabel(QWidget):
    """Текст с градиентной заливкой (для названия приложения)."""

    def __init__(self, text: str, pixel_size: int = 24, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._font = QFont(self.font())
        self._font.setPixelSize(pixel_size)
        self._font.setBold(True)
        self.setFixedHeight(pixel_size + 10)
        self.setFixedWidth(int(pixel_size * 0.62 * len(text)) + 12)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor(mix(pal.accent, "#000000", 0.0 if pal.dark else 0.12)))
        g.setColorAt(1, QColor(mix(pal.accent2, "#000000", 0.0 if pal.dark else 0.18)))
        p.setFont(self._font)
        p.setPen(QPen(QBrush(g), 1))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)


class RoundedImage(QWidget):
    def __init__(self, w: int = 176, h: int = 99, radius: int = 14, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pm: QPixmap | None = None
        self._radius = radius
        self.setFixedSize(w, h)

    def setPixmap(self, pm: QPixmap | None) -> None:  # noqa: N802
        self._pm = pm
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pal = theme.palette
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)
        p.setClipPath(path)
        if self._pm is None or self._pm.isNull():
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, qcolor(pal.accent, 120))
            g.setColorAt(1, qcolor(pal.accent2, 120))
            p.fillRect(r, g)
            f = QFont(self.font())
            f.setPixelSize(30)
            p.setFont(f)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "🎬")
            return
        scaled = self._pm.scaled(self.size() * self.devicePixelRatioF(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() / self.devicePixelRatioF() - r.width()) / 2
        y = (scaled.height() / self.devicePixelRatioF() - r.height()) / 2
        p.drawPixmap(QPointF(-x, -y), scaled)


def page_header(title: str, subtitle: str) -> QWidget:
    from PyQt6.QtWidgets import QVBoxLayout

    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lay.addWidget(make_label(title, "PageTitle"))
    lay.addWidget(make_label(subtitle, "PageSubtitle", wrap=True))
    return box
