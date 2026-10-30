"""SQLite: настройки, история загрузок, метаданные cookie-профилей."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    created_at TEXT NOT NULL,
    mode       TEXT NOT NULL,          -- video | audio
    quality    TEXT NOT NULL,          -- 1080 / best / 192 ...
    format     TEXT NOT NULL,          -- человекочитаемо: «MP4 · 1080p»
    path       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);
CREATE TABLE IF NOT EXISTS profiles (
    id           TEXT PRIMARY KEY,
    site         TEXT NOT NULL,        -- ключ сайта или custom:<host>
    name         TEXT NOT NULL,
    hosts        TEXT NOT NULL,        -- домены через запятую, для автоподстановки
    created_at   TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 0,
    cookie_count INTEGER NOT NULL DEFAULT 0
);
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---------- settings ----------
    def get_setting(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def clear_settings(self) -> None:
        self._conn.execute("DELETE FROM settings")
        self._conn.commit()

    # ---------- history ----------
    def add_history(self, title: str, url: str, mode: str, quality: str, fmt: str, path: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO history(title,url,created_at,mode,quality,format,path) VALUES(?,?,?,?,?,?,?)",
            (title, url, now_iso(), mode, quality, fmt, path),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def update_history(self, hid: int, title: str, fmt: str, path: str) -> None:
        self._conn.execute(
            "UPDATE history SET title=?, format=?, path=?, created_at=? WHERE id=?",
            (title, fmt, path, now_iso(), hid),
        )
        self._conn.commit()

    def list_history(self, query: str = "") -> list[sqlite3.Row]:
        if query:
            like = f"%{query}%"
            return self._conn.execute(
                "SELECT * FROM history WHERE title LIKE ? OR url LIKE ? OR path LIKE ? ORDER BY id DESC",
                (like, like, like),
            ).fetchall()
        return self._conn.execute("SELECT * FROM history ORDER BY id DESC").fetchall()

    def get_history(self, hid: int) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM history WHERE id=?", (hid,)).fetchone()

    def delete_history(self, hid: int) -> None:
        self._conn.execute("DELETE FROM history WHERE id=?", (hid,))
        self._conn.commit()

    def clear_history(self) -> None:
        self._conn.execute("DELETE FROM history")
        self._conn.commit()

    # ---------- profiles ----------
    def list_profiles(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM profiles ORDER BY site, created_at").fetchall()

    def get_profile(self, pid: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()

    def insert_profile(self, pid: str, site: str, name: str, hosts: Iterable[str], cookie_count: int) -> None:
        has_active = self._conn.execute("SELECT 1 FROM profiles WHERE site=? AND active=1", (site,)).fetchone()
        self._conn.execute(
            "INSERT INTO profiles(id,site,name,hosts,created_at,active,cookie_count) VALUES(?,?,?,?,?,?,?)",
            (pid, site, name, ",".join(sorted(set(hosts))), now_iso(), 0 if has_active else 1, cookie_count),
        )
        self._conn.commit()

    def rename_profile(self, pid: str, name: str) -> None:
        self._conn.execute("UPDATE profiles SET name=? WHERE id=?", (name, pid))
        self._conn.commit()

    def set_active_profile(self, pid: str) -> None:
        row = self.get_profile(pid)
        if not row:
            return
        self._conn.execute("UPDATE profiles SET active=0 WHERE site=?", (row["site"],))
        self._conn.execute("UPDATE profiles SET active=1 WHERE id=?", (pid,))
        self._conn.commit()

    def delete_profile(self, pid: str) -> None:
        row = self.get_profile(pid)
        self._conn.execute("DELETE FROM profiles WHERE id=?", (pid,))
        if row and row["active"]:
            nxt = self._conn.execute("SELECT id FROM profiles WHERE site=? ORDER BY created_at LIMIT 1", (row["site"],)).fetchone()
            if nxt:
                self._conn.execute("UPDATE profiles SET active=1 WHERE id=?", (nxt["id"],))
        self._conn.commit()

    def raw(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()
