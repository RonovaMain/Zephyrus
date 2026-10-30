"""Фирменный знак Zephyrus, нарисованный кодом (QPainter) — не нужны внешние картинки.

Небесно-голубой → нежно-розовый перелив, по центру символ загрузки,
в правом верхнем углу четырёхконечная «примогемная» звезда.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPixmap, QRadialGradient)

SKY = "#86D4FF"
MID = "#BFC9FF"
ROSE = "#FFB3D3"


def sparkle_path(cx: float, cy: float, r: float, pinch: float = 0.17) -> QPainterPath:
    """Четырёхконечная звезда с вогнутыми гранями."""
    k = r * pinch
    p = QPainterPath()
    p.moveTo(cx, cy - r)
    p.quadTo(cx + k, cy - k, cx + r, cy)
    p.quadTo(cx + k, cy + k, cx, cy + r)
    p.quadTo(cx - k, cy + k, cx - r, cy)
    p.quadTo(cx - k, cy - k, cx, cy - r)
    p.closeSubpath()
    return p


def draw_star(p: QPainter, cx: float, cy: float, r: float) -> None:
    """Звезда-примогем: свечение, градиентная заливка, грани и блик."""
    glow = QRadialGradient(QPointF(cx, cy), r * 1.9)
    glow.setColorAt(0.0, QColor(255, 255, 255, 150))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(QPointF(cx, cy), r * 1.9, r * 1.9)

    star = sparkle_path(cx, cy, r)
    fill = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
    fill.setColorAt(0.0, QColor("#FFFFFF"))
    fill.setColorAt(0.55, QColor("#FFE6F2"))
    fill.setColorAt(1.0, QColor("#CFEAFF"))
    p.fillPath(star, fill)

    p.save()
    p.setClipPath(star)
    # грани гема: светлые и тёмные четверти
    for (a, b, alpha, color) in (
        ((cx, cy - r), (cx + r, cy), 70, QColor(255, 255, 255)),
        ((cx, cy + r), (cx - r, cy), 55, QColor(150, 170, 230)),
    ):
        tri = QPainterPath()
        tri.moveTo(cx, cy)
        tri.lineTo(*a)
        tri.lineTo(*b)
        tri.closeSubpath()
        c = QColor(color)
        c.setAlpha(alpha)
        p.fillPath(tri, c)
    pen = QPen(QColor(255, 255, 255, 170), max(0.6, r * 0.05))
    p.setPen(pen)
    for tx, ty in ((cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)):
        p.drawLine(QPointF(cx, cy), QPointF(tx, ty))
    p.restore()

    p.setPen(QPen(QColor(255, 255, 255, 230), max(0.7, r * 0.06)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(star)


def draw_download_glyph(p: QPainter, s: float, color: QColor, dy: float = 0.0) -> None:
    pen = QPen(color, s * 0.085)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(0.46 * s, 0.27 * s + dy), QPointF(0.46 * s, 0.60 * s + dy))
    p.drawPolyline([QPointF(0.31 * s, 0.46 * s + dy), QPointF(0.46 * s, 0.61 * s + dy), QPointF(0.61 * s, 0.46 * s + dy)])
    p.drawPolyline([QPointF(0.25 * s, 0.70 * s + dy), QPointF(0.25 * s, 0.76 * s + dy),
                    QPointF(0.67 * s, 0.76 * s + dy), QPointF(0.67 * s, 0.70 * s + dy)])


def draw_logo(p: QPainter, size: float, background: bool = True) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    if background:
        bg = QLinearGradient(0, 0, s, s)
        bg.setColorAt(0.0, QColor(SKY))
        bg.setColorAt(0.5, QColor(MID))
        bg.setColorAt(1.0, QColor(ROSE))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), s * 0.27, s * 0.27)
        p.fillPath(path, bg)
        gloss = QLinearGradient(0, 0, 0, s * 0.6)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 95))
        gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, gloss)
    draw_download_glyph(p, s, QColor(110, 90, 170, 70), dy=s * 0.014)
    draw_download_glyph(p, s, QColor("#FFFFFF"))
    draw_star(p, s * 0.745, s * 0.265, s * 0.165)
    # маленькая искорка
    small = sparkle_path(s * 0.865, s * 0.485, s * 0.05)
    p.fillPath(small, QColor(255, 255, 255, 235))
    p.restore()


def logo_pixmap(size: int, dpr: float = 1.0, background: bool = True) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    draw_logo(p, size, background)
    p.end()
    return pm


def logo_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(sz))
    return icon


def logo_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    draw_logo(p, size)
    p.end()
    return img
