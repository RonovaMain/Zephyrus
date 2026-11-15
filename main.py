"""Zephyrus — точка входа."""
from __future__ import annotations

import ctypes
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

# QtWebEngine нужно импортировать ДО создания QApplication
from PyQt6 import QtWebEngineWidgets  # noqa: F401
from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QLockFile, QProcess, Qt, QTranslator
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from zephyrus import i18n, paths
from zephyrus.autoupdate import AutoUpdater
from zephyrus.branding import logo_icon, logo_pixmap
from zephyrus.context import AppContext
from zephyrus.crypto import Vault, VaultError
from zephyrus.database import Database
from zephyrus.downloader import DownloadManager, InfoFetcher
from zephyrus.engine import EngineManager
from zephyrus.i18n import tr
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
        if sys.stderr is not None:  # в оконной сборке (console=False) stderr отсутствует
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


def system_languages() -> list[str]:
    return list(QLocale.system().uiLanguages())


_qt_translators: list[QTranslator] = []


def install_qt_translations(app: QApplication, code: str) -> None:
    """Стандартные окна Qt (Yes/No, выбор цвета и файла) — на выбранном языке. Нет перевода — останется английский."""
    for t in _qt_translators:
        app.removeTranslator(t)
    _qt_translators.clear()
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase",):
        t = QTranslator(app)
        if t.load(QLocale(code), name, "_", path):
            app.installTranslator(t)
            _qt_translators.append(t)


def release_single_instance(instance) -> None:
    """Освободить блокировку «одна копия» — нужно перед перезапуском (смена языка)."""
    if instance is None:
        return
    if paths.IS_WINDOWS:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle(instance)
    else:
        instance.unlock()


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

    # язык до чтения настроек — по системе; точный выбор пользователя применится чуть ниже
    install_qt_translations(app, i18n.set_language(i18n.match_language(system_languages())))

    instance = acquire_single_instance()
    if instance is None:
        QMessageBox.information(None, paths.APP_NAME, tr("app.running"))
        return 0

    splash = QSplashScreen(logo_pixmap(180, app.devicePixelRatio()))
    splash.show()
    app.processEvents()

    # старые временные cookies (если прошлый запуск завершился аварийно)
    for stale in paths.CACHE_DIR.glob("cookies_*.txt"):
        stale.unlink(missing_ok=True)
    for stale in paths.CACHE_DIR.glob("rec_*.txt"):
        stale.unlink(missing_ok=True)

    db = Database(paths.DB_PATH)
    settings = Settings(db)
    lang = i18n.set_language(i18n.resolve_language(settings.get("language"), system_languages()))
    install_qt_translations(app, lang)

    try:
        vault = Vault(paths.KEY_PATH)
    except VaultError as exc:
        splash.close()
        QMessageBox.critical(None, paths.APP_NAME, str(exc))
        db.close()
        return 1

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

    # автообновление yt-dlp: при первом запуске и затем примерно раз в 2 дня (пока программа открыта)
    updater = AutoUpdater(engine, settings, downloads)
    updater.engineMissing.connect(lambda: QMessageBox.warning(window, paths.APP_NAME, tr("app.no_engine")))
    updater.start()

    code = app.exec()
    db.close()
    if ctx.restart_requested:   # пользователь сменил язык и согласился на перезапуск
        release_single_instance(instance)
        args = sys.argv[1:] if paths.IS_FROZEN else sys.argv
        QProcess.startDetached(sys.executable, args)
    return code


if __name__ == "__main__":
    sys.exit(main())
