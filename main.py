"""Zephyrus — точка входа."""
from __future__ import annotations

import ctypes
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

# QtWebEngine нужно импортировать ДО создания QApplication
from PyQt6 import QtWebEngineWidgets  # noqa: F401
from PyQt6.QtCore import QCoreApplication, Qt, QLockFile
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from zephyrus import paths
from zephyrus.branding import logo_icon, logo_pixmap
from zephyrus.context import AppContext
from zephyrus.crypto import Vault, VaultError
from zephyrus.database import Database
from zephyrus.downloader import DownloadManager, InfoFetcher
from zephyrus.engine import EngineManager
from zephyrus.sessions import SessionManager
from zephyrus.settings import Settings
from zephyrus.theme import theme
from zephyrus.ui.main_window import MainWindow


def setup_logging() -> None:
    handler = RotatingFileHandler(paths.LOG_DIR / "zephyrus.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def hook(exc_type, exc, tb) -> None:
        logging.critical("Необработанная ошибка", exc_info=(exc_type, exc, tb))
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = hook


def acquire_single_instance():
    """Не даём запустить вторую копию. Имя мьютекса совпадает с AppMutex в Inno Setup."""
    if paths.IS_WINDOWS:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        handle = k32.CreateMutexW(None, False, "ZephyrusSingleInstance")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    lock = QLockFile(str(paths.DATA_DIR / "app.lock"))
    return lock if lock.tryLock(100) else None


def main() -> int:
    paths.ensure_dirs()
    setup_logging()
    if paths.IS_WINDOWS:
        try:  # отдельная иконка в панели задач
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RonovaDev.Zephyrus")
        except OSError:
            pass

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(paths.APP_NAME)      # => AppLocalDataLocation = %LOCALAPPDATA%\Zephyrus
    app.setApplicationVersion(paths.APP_VERSION)
    app.setWindowIcon(logo_icon())

    instance = acquire_single_instance()
    if instance is None:
        QMessageBox.information(None, paths.APP_NAME, "Zephyrus уже запущен.")
        return 0

    splash = QSplashScreen(logo_pixmap(180, app.devicePixelRatio()))
    splash.show()
    app.processEvents()

    # старые временные cookies (если прошлый запуск завершился аварийно)
    for stale in paths.CACHE_DIR.glob("cookies_*.txt"):
        stale.unlink(missing_ok=True)
    for stale in paths.CACHE_DIR.glob("rec_*.txt"):
        stale.unlink(missing_ok=True)

    try:
        vault = Vault(paths.KEY_PATH)
    except VaultError as exc:
        splash.close()
        QMessageBox.critical(None, paths.APP_NAME, str(exc))
        return 1

    db = Database(paths.DB_PATH)
    settings = Settings(db)
    theme.configure(settings.get("theme_mode"), settings.get("accent"), settings.get("accent_custom"))
    theme.apply(app)

    engine = EngineManager()
    engine.ensure_installed()   # первый запуск: копируем yt-dlp/ffmpeg в LOCALAPPDATA\Zephyrus\bin

    sessions = SessionManager(db, vault)
    downloads = DownloadManager(db, settings, engine, sessions)
    info = InfoFetcher(engine, settings, sessions)
    ctx = AppContext(db, settings, engine, sessions, downloads, info)

    window = MainWindow(ctx)
    window.show()
    splash.finish(window)

    if not engine.is_ready():
        QMessageBox.warning(window, paths.APP_NAME,
                            "Не найден yt-dlp. Положите yt-dlp.exe и ffmpeg.exe в папку bin проекта "
                            "(python tools/fetch_binaries.py) либо нажмите «Обновить движок» в настройках.")

    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
