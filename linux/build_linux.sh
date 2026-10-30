#!/usr/bin/env bash
# Полная локальная сборка под Linux: зависимости -> движок -> иконка -> PyInstaller -> установщик .run
#
# Перед первой сборкой установите системные пакеты (пример для Ubuntu/Debian):
#   sudo apt install python3-venv python3-pip libegl1 libgl1 libnss3 libxcomposite1 libxdamage1 \
#        libxrandr2 libxtst6 libxkbfile1 libasound2 libxkbcommon-x11-0 libxcb-cursor0 \
#        libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
#        libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libdbus-1-3 libfontconfig1 libcups2
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "=== 1/5 Виртуальное окружение ==="
[ -x .venv/bin/python ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== 2/5 yt-dlp и FFmpeg в bin/ ==="
python tools/fetch_binaries.py

echo "=== 3/5 Иконка ==="
QT_QPA_PLATFORM=offscreen python tools/make_icon.py

echo "=== 4/5 PyInstaller (onedir) ==="
pyinstaller --noconfirm --clean Zephyrus.spec

echo "=== 5/5 Установщик .run и портативный архив ==="
bash linux/make_installer.sh

echo
echo "Готово. Файлы в installer/Output/"
