"""Скачивает yt-dlp и FFmpeg в папку bin\\ проекта (их потом PyInstaller упакует в сборку).

Запуск:
    python tools/fetch_binaries.py                      # последние версии
    python tools/fetch_binaries.py --ytdlp 2025.10.22   # закрепить версию yt-dlp
    python tools/fetch_binaries.py --ffmpeg 7.1.1       # закрепить версию FFmpeg (Windows)
    python tools/fetch_binaries.py --force              # перекачать, даже если файлы уже есть

То же через переменные окружения YTDLP_VERSION и FFMPEG_VERSION (удобно для GitHub Actions).
Если версия не указана — берётся latest.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
IS_WIN = sys.platform.startswith("win")
SUFFIX = ".exe" if IS_WIN else ""
ARM = platform.machine().lower() in ("aarch64", "arm64")
YTDLP_ASSET = "yt-dlp.exe" if IS_WIN else ("yt-dlp_linux_aarch64" if ARM else "yt-dlp_linux")

# Windows: сборки gyan.dev (essentials). Версионные архивы зеркалятся в GitHub-репозитории GyanD/codexffmpeg.
FFMPEG_WIN_LATEST = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_WIN_PINNED = "https://github.com/GyanD/codexffmpeg/releases/download/{v}/ffmpeg-{v}-essentials_build.zip"
FFMPEG_LINUX = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"


def download(url: str, label: str) -> bytes:
    print(f"↓ {label}: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Zephyrus-build"})
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        while chunk := resp.read(1 << 20):
            buf.write(chunk)
            if total:
                print(f"\r  {buf.tell() * 100 // total}%", end="", flush=True)
        print()
    return buf.getvalue()


def fetch_ytdlp(version: str | None) -> str:
    base = ("https://github.com/yt-dlp/yt-dlp/releases/download/" + version + "/") if version \
        else "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
    data = download(base + YTDLP_ASSET, f"yt-dlp {version or 'latest'}")
    sums = download(base + "SHA2-256SUMS", "контрольные суммы").decode("utf-8", "replace")
    expected = next((ln.split()[0] for ln in sums.splitlines()
                     if len(ln.split()) == 2 and ln.split()[1].lstrip("*") == YTDLP_ASSET), "")
    actual = hashlib.sha256(data).hexdigest()
    if not expected or actual != expected.lower():
        sys.exit(f"SHA-256 yt-dlp не совпал (ожидалось {expected or '—'}, получено {actual})")
    target = BIN / f"yt-dlp{SUFFIX}"
    target.write_bytes(data)
    target.chmod(0o755)
    return actual


def fetch_ffmpeg(version: str | None) -> None:
    need = [f"ffmpeg{SUFFIX}", f"ffprobe{SUFFIX}"]
    url = (FFMPEG_WIN_PINNED.format(v=version) if version else FFMPEG_WIN_LATEST) if IS_WIN else FFMPEG_LINUX
    data = download(url, f"FFmpeg {version or 'latest'}")
    found: set[str] = set()
    if IS_WIN:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                name = Path(member).name
                if name in need and "/bin/" in member:
                    with z.open(member) as src, open(BIN / name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.add(name)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as t:
            for member in t.getmembers():
                name = Path(member.name).name
                if name in need and "/bin/" in member.name:
                    with t.extractfile(member) as src, open(BIN / name, "wb") as dst:  # type: ignore[union-attr]
                        shutil.copyfileobj(src, dst)
                    (BIN / name).chmod(0o755)
                    found.add(name)
    missing = set(need) - found
    if missing:
        sys.exit(f"В архиве не найдено: {', '.join(sorted(missing))}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ytdlp", default=os.environ.get("YTDLP_VERSION") or None, help="версия yt-dlp, например 2025.10.22")
    ap.add_argument("--ffmpeg", default=os.environ.get("FFMPEG_VERSION") or None, help="версия FFmpeg, например 7.1.1 (Windows)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    BIN.mkdir(exist_ok=True)
    info: dict[str, str] = {}
    if args.force or not (BIN / f"yt-dlp{SUFFIX}").exists():
        info["yt-dlp"] = f"{args.ytdlp or 'latest'} (sha256 {fetch_ytdlp(args.ytdlp)[:12]}…)"
    else:
        print("yt-dlp уже есть, пропуск (--force чтобы перекачать)")
    if args.force or any(not (BIN / n).exists() for n in (f"ffmpeg{SUFFIX}", f"ffprobe{SUFFIX}")):
        fetch_ffmpeg(args.ffmpeg)
        info["ffmpeg"] = args.ffmpeg or "latest"
    else:
        print("ffmpeg/ffprobe уже есть, пропуск")

    if info:
        (BIN / "versions.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Готово:", ", ".join(sorted(p.name for p in BIN.iterdir() if p.is_file() and p.name != ".gitkeep")))


if __name__ == "__main__":
    main()
