"""Темы: светлая / тёмная / системная + смена акцентного оттенка. Генерирует QSS и палитру."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from string import Template

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

from .paths import CACHE_DIR, IS_WINDOWS

# ключ: (название, основной, вторичный) — основной→вторичный даёт фирменный перелив
ACCENTS: dict[str, tuple[str, str, str]] = {
    "sakura": ("Сакура", "#FF8FB8", "#8FD0FF"),
    "sky": ("Небо", "#6EC4FF", "#FFB0D0"),
    "lavender": ("Лаванда", "#B197FC", "#8FD0FF"),
    "mint": ("Мята", "#5FDDB5", "#8FD0FF"),
    "peach": ("Персик", "#FFA68A", "#FFD58A"),
}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """Смешать два цвета: t=0 → a, t=1 → b."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#{:02X}{:02X}{:02X}".format(round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t))


def luminance(h: str) -> float:
    r, g, b = _rgb(h)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def on_color(bg: str) -> str:
    """Читаемый цвет текста поверх заливки."""
    return "#3A2145" if luminance(bg) > 0.62 else "#FFFFFF"


def qcolor(h: str, alpha: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(alpha)
    return c


def rgba(h: str, a: float) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r},{g},{b},{a})"


def hue_partner(h: str) -> str:
    c = QColor(h)
    hue, sat, val, _ = c.getHsv()
    partner = QColor.fromHsv((hue + 150) % 360 if hue >= 0 else 200, max(90, sat // 2 + 40), 255)
    return partner.name().upper()


@dataclass(frozen=True)
class Palette:
    dark: bool
    bg: str
    bg2: str
    surface: str
    surface_alt: str
    border: str
    border_strong: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent2: str
    accent_soft: str
    accent_text: str
    on_accent: str
    danger: str
    danger_soft: str
    success: str


def make_palette(dark: bool, accent: str, accent2: str) -> Palette:
    if dark:
        surface = "#1F1B29"
        return Palette(
            True, "#15121C", "#111823", surface, "#282335", "#352F45", "#4A4260",
            "#F4EFFA", "#A89FBA", "#6F6783", accent, accent2, mix(accent, surface, 0.80), accent,
            on_color(mix(accent, accent2, 0.5)), "#FF6B72", mix("#FF6B72", surface, 0.82), "#4ADE9B")
    return Palette(
        False, mix(accent, "#FFFFFF", 0.93), mix(accent2, "#FFFFFF", 0.90), "#FFFFFF",
        mix(accent, "#FFFFFF", 0.92), mix(accent, "#FFFFFF", 0.78), mix(accent, "#FFFFFF", 0.52),
        "#2B2235", "#7C7088", "#B3A9BD", accent, accent2, mix(accent, "#FFFFFF", 0.84), mix(accent, "#000000", 0.28),
        on_color(mix(accent, accent2, 0.5)), "#E5484D", mix("#E5484D", "#FFFFFF", 0.88), "#2FB67C")


QSS = Template(r"""
QWidget { color: $text; font-family: $font; font-size: 13px; }
QMainWindow, QDialog, QMessageBox, QInputDialog, QColorDialog { background: $bg; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; border-radius: 8px; padding: 6px 8px; }
QLabel { background: transparent; }
QLabel#PageTitle { font-size: 28px; font-weight: 700; }
QLabel#PageSubtitle, QLabel#Dim { color: $text_dim; }
QLabel#CardTitle { font-size: 15px; font-weight: 600; }
QLabel#RowTitle { font-weight: 600; }
QLabel#Stat { font-size: 15px; font-weight: 600; }
QLabel#Error { color: $danger; }
QLabel#Success { color: $success; }
QLabel#Pill { background: $accent_soft; color: $accent_text; border-radius: 10px; padding: 3px 10px; font-weight: 600; }

QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 18px; }
QFrame#Sidebar { background: $sidebar; border: none; border-right: 1px solid $border; }
QFrame#Row { background: $surface_alt; border: 1px solid $border; border-radius: 14px; }

QPushButton { background: $surface_alt; border: 1px solid $border; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: $accent_soft; border-color: $accent; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $text_faint; background: transparent; border-color: $border; }
QPushButton#Danger { color: $danger; }
QPushButton#Danger:hover { background: $danger_soft; border-color: $danger; }
QPushButton#Small { padding: 6px 12px; border-radius: 10px; }
QToolButton { background: transparent; border: none; border-radius: 10px; padding: 7px; }
QToolButton:hover { background: $accent_soft; }
QToolButton:disabled { color: $text_faint; }

QLineEdit, QSpinBox, QDoubleSpinBox { background: $surface_alt; border: 1.5px solid $border; border-radius: 12px; padding: 9px 14px;
    selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:hover, QSpinBox:hover { border-color: $border_strong; }
QLineEdit:focus, QSpinBox:focus { border-color: $accent; }
QLineEdit:read-only { color: $text_dim; }

QComboBox { background: $surface_alt; border: 1.5px solid $border; border-radius: 12px; padding: 8px 14px; min-height: 22px; }
QComboBox:hover { border-color: $border_strong; }
QComboBox:focus, QComboBox:on { border-color: $accent; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 32px; border: none; }
QComboBox::down-arrow { image: url($arrow); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border; padding: 6px; outline: 0;
    selection-background-color: $accent_soft; selection-color: $text; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 2px 8px; border-radius: 8px; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 4px; min-height: 36px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 4px; min-width: 36px; margin: 2px 0; }
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QTableView { background: transparent; border: none; gridline-color: transparent; outline: 0;
    selection-background-color: $accent_soft; selection-color: $text; }
QTableView::item { padding: 6px 10px; border-bottom: 1px solid $border; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: $text_dim; border: none; border-bottom: 2px solid $border;
    padding: 8px 10px; font-weight: 600; }
QTableCornerButton::section { background: transparent; border: none; }

QListWidget { background: $surface_alt; border: 1px solid $border; border-radius: 12px; padding: 6px; outline: 0; }
QListWidget::item { padding: 7px 10px; border-radius: 8px; }
QListWidget::item:selected { background: $accent_soft; color: $text; }

QPlainTextEdit { background: $surface_alt; border: 1px solid $border; border-radius: 12px; padding: 10px;
    font-family: "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace; font-size: 12px; color: $text_dim; }

QMenu { background: $surface; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 8px 22px; border-radius: 8px; }
QMenu::item:selected { background: $accent_soft; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }
QProgressBar { background: $surface_alt; border: 1px solid $border; border-radius: 8px; text-align: center; }
QProgressBar::chunk { background: $accent; border-radius: 7px; }
""")


class ThemeManager(QObject):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._mode = "light"
        self._accent_key = "sakura"
        self._custom = "#FF8FB8"
        self._palette = make_palette(False, ACCENTS["sakura"][1], ACCENTS["sakura"][2])

    # ---------- состояние ----------
    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def accent_key(self) -> str:
        return self._accent_key

    def _resolve_dark(self) -> bool:
        if self._mode == "dark":
            return True
        if self._mode == "light":
            return False
        try:
            return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except AttributeError:
            return False

    def accent_pair(self, key: str | None = None, custom: str | None = None) -> tuple[str, str]:
        key = key or self._accent_key
        if key == "custom":
            c = (custom or self._custom).upper()
            return c, hue_partner(c)
        return ACCENTS[key][1], ACCENTS[key][2]

    def configure(self, mode: str, accent_key: str, custom: str) -> None:
        self._mode, self._accent_key, self._custom = mode, accent_key, custom
        a1, a2 = self.accent_pair()
        self._palette = make_palette(self._resolve_dark(), a1, a2)

    # ---------- применение ----------
    def _arrow_png(self, color: str) -> str:
        path = CACHE_DIR / "ui" / f"arrow_{color.lstrip('#')}.png"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            pm = QPixmap(24, 24)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), 2.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])
            p.end()
            pm.save(str(path), "PNG")
        return path.as_posix()

    def apply(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()
        p = self._palette
        app.setStyle("Fusion")
        qpal = QPalette()
        qpal.setColor(QPalette.ColorRole.Window, QColor(p.bg))
        qpal.setColor(QPalette.ColorRole.WindowText, QColor(p.text))
        qpal.setColor(QPalette.ColorRole.Base, QColor(p.surface_alt))
        qpal.setColor(QPalette.ColorRole.AlternateBase, QColor(p.surface))
        qpal.setColor(QPalette.ColorRole.Text, QColor(p.text))
        qpal.setColor(QPalette.ColorRole.Button, QColor(p.surface_alt))
        qpal.setColor(QPalette.ColorRole.ButtonText, QColor(p.text))
        qpal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.surface))
        qpal.setColor(QPalette.ColorRole.ToolTipText, QColor(p.text))
        qpal.setColor(QPalette.ColorRole.Highlight, QColor(p.accent))
        qpal.setColor(QPalette.ColorRole.HighlightedText, QColor(p.on_accent))
        qpal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p.text_faint))
        app.setPalette(qpal)

        sidebar = rgba(p.surface, 0.72 if not p.dark else 0.60)
        font = '"Segoe UI Variable Text","Segoe UI","Inter","Noto Sans","Ubuntu",sans-serif'
        app.setStyleSheet(QSS.safe_substitute(
            font=font, sidebar=sidebar, arrow=self._arrow_png(p.text_dim), **p.__dict__))
        self.changed.emit()
        for w in app.topLevelWidgets():
            self.style_window(w)
            for child in w.findChildren(QWidget):
                child.update()

    def style_window(self, w: QWidget) -> None:
        """Тёмный/цветной заголовок окна Windows 10/11 (DWM)."""
        if not IS_WINDOWS or not w.isWindow():
            return
        try:
            hwnd = int(w.winId())
            dwm = ctypes.windll.dwmapi
            dark = ctypes.c_int(1 if self._palette.dark else 0)
            if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4) != 0:
                dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), 4)

            def colorref(h: str) -> ctypes.c_int:
                r, g, b = _rgb(h)
                return ctypes.c_int(r | (g << 8) | (b << 16))

            caption, text = colorref(self._palette.bg), colorref(self._palette.text)
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)  # Windows 11: цвет заголовка
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), 4)
        except Exception:  # noqa: BLE001
            pass


theme = ThemeManager()
