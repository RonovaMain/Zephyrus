"""Вкладка «📜 История»: таблица из SQLite, проверка наличия файлов, «Скачать повторно»."""
from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..context import AppContext
from ..downloader import Job
from ..theme import theme
from ..utils import open_folder, reveal_in_folder
from .widgets import Card, make_label, page_header

COLUMNS = ["Название", "URL", "Дата", "Формат", "Путь к файлу", ""]


class HistoryPage(QWidget):
    navigateToDownloads = pyqtSignal()

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self._build()
        ctx.downloads.historyChanged.connect(self.reload)
        theme.changed.connect(self.reload)
        self._timer = QTimer(self, interval=4000)
        self._timer.timeout.connect(self._refresh_presence)
        self.reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)
        root.addWidget(page_header("История", "Всё, что вы скачали. Если файл удалён с диска — запись бледнеет, и его можно скачать заново."))

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Поиск по названию, ссылке или пути")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda *_: self.reload())
        self.stats = make_label("", "Dim")
        self.clear_btn = QPushButton("🗑  Очистить историю")
        self.clear_btn.setObjectName("Danger")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.stats)
        bar.addWidget(self.clear_btn)
        root.addLayout(bar)

        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 14)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(4, 220)
        self.table.setColumnWidth(5, 300)
        self.table.cellDoubleClicked.connect(self._open_row)
        cl.addWidget(self.table)
        self.empty = make_label("История пуста — скачайте что-нибудь, и оно появится здесь.", "Dim")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.empty)
        root.addWidget(card, 1)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self._timer.start()
        self.reload()

    def hideEvent(self, e) -> None:  # noqa: N802
        super().hideEvent(e)
        self._timer.stop()

    # ---------- данные ----------
    def reload(self) -> None:
        rows = self.ctx.db.list_history(self.search.text().strip())
        pal = theme.palette
        self.table.setRowCount(len(rows))
        missing = 0
        for r, row in enumerate(rows):
            exists = os.path.exists(row["path"])
            missing += 0 if exists else 1
            try:
                when = datetime.fromisoformat(row["created_at"]).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                when = row["created_at"]
            values = [row["title"], row["url"], when, row["format"], row["path"]]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                color = QColor(pal.text if exists else pal.text_faint)
                if not exists:
                    color.setAlpha(150)
                item.setForeground(color)
                if c == 0:
                    f = item.font()
                    f.setBold(exists)
                    item.setFont(f)
                self.table.setItem(r, c, item)
            self.table.setCellWidget(r, 5, self._actions(row, exists))
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.stats.setText(f"Записей: {len(rows)}" + (f" · файл удалён: {missing}" if missing else ""))
        self.clear_btn.setEnabled(bool(self.ctx.db.list_history()))

    def _actions(self, row, exists: bool) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(8)
        show = QPushButton("📂 Показать")
        show.setObjectName("Small")
        show.setEnabled(exists)
        show.clicked.connect(lambda _=False, p=row["path"]: reveal_in_folder(p))
        redo = QPushButton("↻ Скачать повторно")
        redo.setObjectName("Small")
        redo.setEnabled(not exists)
        redo.clicked.connect(lambda _=False, rid=row["id"]: self._redownload(rid))
        for b in (show, redo):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)
        return box

    def _refresh_presence(self) -> None:
        """Лёгкая проверка: изменилось ли наличие файлов на диске."""
        rows = self.ctx.db.list_history(self.search.text().strip())
        state = [os.path.exists(r["path"]) for r in rows]
        if state != getattr(self, "_last_state", None):
            self._last_state = state
            self.reload()

    # ---------- действия ----------
    def _open_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 4)
        if item and os.path.exists(item.text()):
            reveal_in_folder(item.text())

    def _redownload(self, hid: int) -> None:
        rec = self.ctx.db.get_history(hid)
        if not rec:
            return
        folder = os.path.dirname(rec["path"])
        job = Job(url=rec["url"], mode=rec["mode"], quality=rec["quality"], history_id=hid,
                  outdir=folder if folder else "", label=rec["format"] if rec["quality"].startswith("fmt:") else "")
        self.ctx.downloads.enqueue(job)
        self.navigateToDownloads.emit()

    def _clear(self) -> None:
        if QMessageBox.question(self, "Очистить историю", "Удалить все записи истории?\nСами файлы на диске останутся.") \
                == QMessageBox.StandardButton.Yes:
            self.ctx.db.clear_history()
            self.reload()
