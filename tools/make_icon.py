"""Рисует логотип кодом и сохраняет assets/zephyrus.ico (16–256 px) и assets/zephyrus.png.

Запуск:  python tools/make_icon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PyQt6.QtGui import QGuiApplication  # noqa: E402

from zephyrus.branding import logo_image  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(size: int) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    logo_image(size).save(buf, "PNG")
    return bytes(QByteArray(buf.data()))


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(exist_ok=True)
    images = [(s, png_bytes(s)) for s in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    (out / "zephyrus.ico").write_bytes(header + entries + blobs)
    (out / "zephyrus.png").write_bytes(png_bytes(512))
    print("Иконка создана:", out / "zephyrus.ico")


if __name__ == "__main__":
    main()
