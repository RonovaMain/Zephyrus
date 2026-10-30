# -*- mode: python ; coding: utf-8 -*-
# Сборка:  pyinstaller --noconfirm --clean Zephyrus.spec
# Результат: dist\Zephyrus\Zephyrus.exe (режим onedir)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # «из коробки» yt-dlp / ffmpeg / ffprobe: попадут в папку установки (dist\Zephyrus\_internal\bin)
    datas=[('bin', 'bin'), ('assets', 'assets')],
    hiddenimports=[],
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
