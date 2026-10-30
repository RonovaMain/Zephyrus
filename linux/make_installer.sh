#!/usr/bin/env bash
# Упаковывает готовую сборку PyInstaller (dist/Zephyrus) в:
#   installer/Output/Zephyrus-<версия>-linux-<арх>.run      — универсальный установщик (один файл)
#   installer/Output/Zephyrus-<версия>-linux-<арх>.tar.gz   — портативный архив (распаковал и запустил)
#   installer/Output/SHA256SUMS-linux.txt                   — контрольные суммы
#
# Использование:  bash linux/make_installer.sh [версия]
# Версия по умолчанию берётся из zephyrus/paths.py (APP_VERSION).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/Zephyrus"
OUT="$ROOT/installer/Output"
ARCH="$(uname -m)"
VERSION="${1:-$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$ROOT/zephyrus/paths.py")}"
[ -n "$VERSION" ] || { echo "Не удалось определить версию" >&2; exit 1; }

[ -x "$DIST/Zephyrus" ] || { echo "Не найдена сборка $DIST/Zephyrus — сначала запустите PyInstaller" >&2; exit 1; }

ICON="$ROOT/assets/zephyrus.png"
[ -f "$ICON" ] || ICON="$DIST/_internal/assets/zephyrus.png"
[ -f "$ICON" ] || { echo "Не найдена иконка assets/zephyrus.png (python tools/make_icon.py)" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# --- содержимое установщика ---
mkdir -p "$STAGE/app"
cp -a "$DIST/." "$STAGE/app/"
[ -f "$ROOT/LICENSE" ] && cp "$ROOT/LICENSE" "$STAGE/app/LICENSE"
cp "$ICON" "$STAGE/zephyrus.png"
tar -C "$STAGE" -czf "$STAGE/payload.tgz" app zephyrus.png

sed -e "s/@VERSION@/$VERSION/g" -e "s/@ARCH@/$ARCH/g" "$ROOT/linux/install_header.sh" > "$STAGE/header.sh"
grep -q '^__ARCHIVE_BELOW__$' "$STAGE/header.sh" || { echo "В заголовке нет маркера архива" >&2; exit 1; }

mkdir -p "$OUT"
RUN="$OUT/Zephyrus-$VERSION-linux-$ARCH.run"
cat "$STAGE/header.sh" "$STAGE/payload.tgz" > "$RUN"
chmod +x "$RUN"

# --- портативный архив ---
PORT="Zephyrus-$VERSION-linux-$ARCH"
mkdir -p "$STAGE/portable/$PORT"
cp -a "$DIST/." "$STAGE/portable/$PORT/"
cp "$ICON" "$STAGE/portable/$PORT/zephyrus.png"
[ -f "$ROOT/LICENSE" ] && cp "$ROOT/LICENSE" "$STAGE/portable/$PORT/LICENSE"
tar -C "$STAGE/portable" -czf "$OUT/$PORT.tar.gz" "$PORT"

( cd "$OUT" && sha256sum "$(basename "$RUN")" "$PORT.tar.gz" > SHA256SUMS-linux.txt )

echo "Готово:"
ls -lh "$OUT" | grep -i linux || true
