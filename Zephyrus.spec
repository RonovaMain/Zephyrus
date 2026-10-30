# -*- mode: python ; coding: utf-8 -*-
# Сборка:  pyinstaller --noconfirm --clean Zephyrus.spec
# Результат: dist\Zephyrus\Zephyrus.exe (режим onedir)

from PyInstaller.utils.hooks import collect_all

# Автоматически собираем абсолютно все зависимости, бинарники и скрытые импорты для WebEngine
datas_we, binaries_we, hiddenimports_we = collect_all('PyQt6_WebEngine')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_we,
    # Объединяем системные файлы WebEngine с вашими личными папками bin и assets
    datas=[('bin', 'bin'), ('assets', 'assets')] + datas_we,
    hiddenimports=hiddenimports_we + ['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Zephyrus',
    debug=False,
    strip=False,
    upx=False,
    console=False,                 # без чёрного окна консоли
    icon='assets/zephyrus.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Zephyrus',
)
