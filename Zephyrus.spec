# -*- mode: python ; coding: utf-8 -*-
# Сборка:  pyinstaller --noconfirm --clean Zephyrus.spec
# Результат: dist\Zephyrus\Zephyrus.exe (режим onedir)

# ИСПРАВЛЕНО: заменено collect_binary_files на collect_dynamic_libs
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ['main.py'],
    pathex=[],
    # ИСПРАВЛЕНО: собираем динамические библиотеки .dll движка
    binaries=collect_dynamic_libs('PyQt6_WebEngine'),
    # Объединяем ваши папки bin и assets с системными ресурсами PyQt6 и WebEngine
    datas=[('bin', 'bin'), ('assets', 'assets')] + collect_data_files('PyQt6_WebEngine') + collect_data_files('PyQt6'),
    # Явно указываем скрытые импорты, чтобы PyInstaller точно ничего не упустил
    hiddenimports=['PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore'],
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
