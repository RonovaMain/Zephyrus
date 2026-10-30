#!/usr/bin/env bash
# =============================================================================
#  Zephyrus — универсальный установщик для Linux (самораспаковывающийся архив).
#  Работает на любом дистрибутиве с bash и tar: Ubuntu, Debian, Fedora, Arch, openSUSE и др.
#
#  Использование:
#     ./Zephyrus-<версия>-linux-<арх>.run                 установка для текущего пользователя
#     ./Zephyrus-<версия>-linux-<арх>.run --system        установка для всех (нужен sudo)
#     ./Zephyrus-<версия>-linux-<арх>.run --prefix DIR    своя папка установки
#     ./Zephyrus-<версия>-linux-<арх>.run --uninstall     удаление
#     ./Zephyrus-<версия>-linux-<арх>.run --help
# =============================================================================
set -euo pipefail

APP_NAME="Zephyrus"
APP_VERSION="@VERSION@"
APP_ARCH="@ARCH@"
MARKER=".zephyrus-install"
ARCHIVE_MARK="__ARCHIVE_BELOW__"

if [ -t 1 ]; then
  G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; N=$'\033[0m'
else
  G=""; Y=""; R=""; B=""; N=""
fi
say()  { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '%s!%s %s\n' "$Y" "$N" "$*" >&2; }
err()  { printf '%sОшибка:%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

usage() {
  cat <<EOF
${B}${APP_NAME} ${APP_VERSION}${N} (${APP_ARCH}) — установщик для Linux

Параметры:
  --user           установить для текущего пользователя (по умолчанию, sudo не нужен)
  --system         установить для всех пользователей в /opt (нужен root или sudo)
  --prefix DIR     установить в указанную папку
  --uninstall      удалить программу
  --purge          при удалении стереть и данные пользователя (история, сессии)
  -y, --yes        не задавать вопросов
  --extract DIR    только распаковать файлы в DIR, ничего не устанавливая
  --info           показать версию и выйти
  -h, --help       эта справка

Куда ставится:
  пользователь:  ~/.local/opt/Zephyrus, ярлык в меню, команда ~/.local/bin/zephyrus
  система:       /opt/Zephyrus, ярлык в /usr/local/share/applications, команда /usr/local/bin/zephyrus
Данные программы (база, сессии, движок) всегда лежат в ~/.local/share/Zephyrus.
EOF
}

MODE=""; PREFIX=""; ACTION="install"; PURGE=0; ASSUME_YES=0; EXTRACT_TO=""
ORIG_ARGS=("$@")
while [ $# -gt 0 ]; do
  case "$1" in
    --user) MODE="user" ;;
    --system) MODE="system" ;;
    --prefix) [ $# -ge 2 ] || err "После --prefix нужен путь"; PREFIX="$2"; shift ;;
    --uninstall) ACTION="uninstall" ;;
    --purge) PURGE=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    --extract) [ $# -ge 2 ] || err "После --extract нужен путь"; EXTRACT_TO="$2"; shift ;;
    --info) say "${APP_NAME} ${APP_VERSION} (${APP_ARCH})"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) err "Неизвестный параметр: $1 (см. --help)" ;;
  esac
  shift
done

if [ -z "$MODE" ]; then
  if [ "$(id -u)" -eq 0 ]; then MODE="system"; else MODE="user"; fi
fi

# ---------- пути ----------
set_paths() {
  if [ "$MODE" = "system" ]; then
    PREFIX="${PREFIX:-/opt/${APP_NAME}}"
    BIN_DIR="/usr/local/bin"
    APPS_DIR="/usr/local/share/applications"
    ICON_DIR="/usr/local/share/icons/hicolor/512x512/apps"
  else
    local data="${XDG_DATA_HOME:-$HOME/.local/share}"
    PREFIX="${PREFIX:-$HOME/.local/opt/${APP_NAME}}"
    BIN_DIR="$HOME/.local/bin"
    APPS_DIR="$data/applications"
    ICON_DIR="$data/icons/hicolor/512x512/apps"
  fi
}

need_root_for_system() {
  if [ "$MODE" = "system" ] && [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || err "Для --system нужны права root (sudo не найден)"
    say "Для установки в систему нужны права администратора — запрашиваю sudo…"
    exec sudo -- bash "$0" "${ORIG_ARGS[@]}"
  fi
}

# ---------- проверка системных библиотек (Qt / WebEngine) ----------
check_deps() {
  local ldc="" missing=()
  ldc="$(command -v ldconfig 2>/dev/null || true)"
  [ -n "$ldc" ] || ldc="/sbin/ldconfig"
  [ -x "$ldc" ] || return 0
  local cache; cache="$("$ldc" -p 2>/dev/null || true)"
  [ -n "$cache" ] || return 0
  grep -q 'libxcb-cursor\.so\.0' <<<"$cache"   || missing+=("libxcb-cursor")
  grep -q 'libnss3\.so'          <<<"$cache"   || missing+=("libnss3")
  grep -q 'libxkbcommon-x11\.so' <<<"$cache"   || missing+=("libxkbcommon-x11")
  grep -q 'libasound\.so\.2'     <<<"$cache"   || missing+=("libasound")
  if [ "${#missing[@]}" -gt 0 ]; then
    warn "Не найдены системные библиотеки: ${missing[*]}. Без них окно может не запуститься."
    local id="" like=""
    if [ -r /etc/os-release ]; then
      id="$(. /etc/os-release; echo "${ID:-}")"; like="$(. /etc/os-release; echo "${ID_LIKE:-}")"
    fi
    case " $id $like " in
      *ubuntu*|*debian*) say "  Установите:  sudo apt install libxcb-cursor0 libnss3 libxkbcommon-x11-0 libasound2" ;;
      *fedora*|*rhel*)   say "  Установите:  sudo dnf install xcb-util-cursor nss libxkbcommon-x11 alsa-lib" ;;
      *arch*)            say "  Установите:  sudo pacman -S xcb-util-cursor nss libxkbcommon-x11 alsa-lib" ;;
      *suse*)            say "  Установите:  sudo zypper install libxcb-cursor0 mozilla-nss libxkbcommon-x11-0 libasound2" ;;
      *)                 say "  Установите пакеты, содержащие: libxcb-cursor, libnss3, libxkbcommon-x11, libasound." ;;
    esac
  fi
}

# ---------- работа с архивом ----------
archive_line() {
  local n
  n="$(grep -an "^${ARCHIVE_MARK}\$" "$0" | head -n 1 | cut -d: -f1)" || true
  [ -n "$n" ] || err "Установщик повреждён: не найден архив (запускайте скачанный .run-файл, а не копию без данных)"
  echo "$n"
}

extract_payload() {
  local dest="$1" n
  n="$(archive_line)"
  tail -n +"$((n + 1))" "$0" | tar -xzf - -C "$dest" || err "Не удалось распаковать архив (файл повреждён?)"
}

refresh_caches() {
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
  local hicolor; hicolor="$(dirname "$(dirname "$(dirname "$ICON_DIR")")")"
  command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -f "$hicolor/index.theme" ] && \
    gtk-update-icon-cache -q -t -f "$hicolor" >/dev/null 2>&1 || true
}

# ---------- установка ----------
do_install() {
  need_root_for_system
  set_paths
  [ -n "$EXTRACT_TO" ] && { mkdir -p "$EXTRACT_TO"; extract_payload "$EXTRACT_TO"; ok "Файлы распакованы в $EXTRACT_TO"; exit 0; }

  say "${B}Установка ${APP_NAME} ${APP_VERSION}${N}"
  say "  режим:  $MODE"
  say "  папка:  $PREFIX"
  command -v tar >/dev/null 2>&1 || err "Нужна утилита tar"

  WORK="$(mktemp -d)"
  trap 'rm -rf "$WORK"' EXIT
  local tmp="$WORK"
  extract_payload "$tmp"
  [ -x "$tmp/app/${APP_NAME}" ] || err "В архиве нет исполняемого файла ${APP_NAME}"

  if [ -e "$PREFIX" ]; then
    if [ -f "$PREFIX/$MARKER" ] || [ -z "$(ls -A "$PREFIX" 2>/dev/null)" ]; then
      rm -rf "$PREFIX"                      # обновление поверх старой версии
    else
      err "Папка $PREFIX уже существует и не похожа на установку ${APP_NAME}. Укажите другую через --prefix."
    fi
  fi
  mkdir -p "$PREFIX" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
  cp -a "$tmp/app/." "$PREFIX/"
  cp "$tmp/zephyrus.png" "$ICON_DIR/zephyrus.png"
  chmod 755 "$PREFIX/${APP_NAME}"

  ln -sf "$PREFIX/${APP_NAME}" "$BIN_DIR/zephyrus"

  local desktop="$APPS_DIR/zephyrus.desktop"
  cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
GenericName=Медиа-загрузчик
Comment=Загрузчик видео и аудио на базе yt-dlp и FFmpeg
Exec="$PREFIX/${APP_NAME}"
Icon=$ICON_DIR/zephyrus.png
Terminal=false
Categories=Network;AudioVideo;
Keywords=youtube;yt-dlp;download;video;audio;загрузчик;
StartupWMClass=${APP_NAME}
EOF
  chmod 644 "$desktop"

  # копия этого скрипта (без архива) — локальный деинсталлятор
  head -n "$(( $(archive_line) - 1 ))" "$0" > "$PREFIX/uninstall.sh"
  chmod 755 "$PREFIX/uninstall.sh"
  cat > "$PREFIX/$MARKER" <<EOF
MODE=$MODE
PREFIX=$PREFIX
LINK=$BIN_DIR/zephyrus
DESKTOP=$desktop
ICON=$ICON_DIR/zephyrus.png
VERSION=$APP_VERSION
EOF

  refresh_caches
  ok "${APP_NAME} установлен"
  say "  Запуск: найдите «${APP_NAME}» в меню приложений или выполните:  zephyrus"
  case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "Папка $BIN_DIR не входит в PATH — команда zephyrus будет доступна после её добавления." ;; esac
  say "  Удаление:  $PREFIX/uninstall.sh --uninstall"
  check_deps
}

# ---------- удаление ----------
do_uninstall() {
  # ищем установку: сначала указанную, затем пользовательскую, затем системную
  local candidates=()
  if [ -n "$PREFIX" ]; then candidates+=("$PREFIX")
  else
    [ "$MODE" = "system" ] && candidates+=("/opt/${APP_NAME}")
    candidates+=("$HOME/.local/opt/${APP_NAME}" "/opt/${APP_NAME}")
  fi
  local found=""
  for c in "${candidates[@]}"; do [ -f "$c/$MARKER" ] && { found="$c"; break; }; done
  [ -n "$found" ] || err "Установка ${APP_NAME} не найдена"

  # shellcheck disable=SC1090
  . "$found/$MARKER"
  if [ "$MODE" = "system" ] && [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || err "Для удаления системной установки нужен root"
    exec sudo -- bash "$0" "${ORIG_ARGS[@]}"
  fi

  say "${B}Удаление ${APP_NAME}${N} из $found"
  [ -L "${LINK:-}" ] && [ "$(readlink "$LINK")" = "$found/${APP_NAME}" ] && rm -f "$LINK"
  [ -n "${DESKTOP:-}" ] && rm -f "$DESKTOP"
  [ -n "${ICON:-}" ] && rm -f "$ICON"
  rm -rf "$found"
  APPS_DIR="$(dirname "${DESKTOP:-/tmp/x}")"; ICON_DIR="$(dirname "${ICON:-/tmp/x}")"
  refresh_caches
  ok "Программа удалена"

  local data="${XDG_DATA_HOME:-$HOME/.local/share}/${APP_NAME}"
  if [ -d "$data" ]; then
    if [ "$PURGE" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
      read -r -p "Удалить и данные пользователя ($data: история, сессии, движок)? [y/N] " ans || ans=""
      case "$ans" in y|Y|д|Д) PURGE=1 ;; esac
    fi
    if [ "$PURGE" -eq 1 ]; then rm -rf "$data"; ok "Данные удалены"; else say "  Данные оставлены: $data"; fi
  fi
}

case "$ACTION" in
  install)   do_install ;;
  uninstall) do_uninstall ;;
esac
exit 0
__ARCHIVE_BELOW__
