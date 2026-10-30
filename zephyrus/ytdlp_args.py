"""Сборка аргументов yt-dlp и разбор его вывода (без зависимостей от Qt — легко тестировать)."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

REC_SEP = "::ZSEP::"

PROGRESS_TEMPLATE = (
    "download:ZPROG|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s"
    "|%(progress.speed)s|%(progress.eta)s|%(progress.fragment_index)s|%(progress.fragment_count)s"
    "|%(progress.status)s|%(info.vcodec)s|%(info.acodec)s"
)
POSTPROCESS_TEMPLATE = "postprocess:ZPOST|%(progress.postprocessor)s|%(progress.status)s"

PROG_RE = re.compile(
    r"^ZPROG\|(?P<done>[^|]*)\|(?P<total>[^|]*)\|(?P<est>[^|]*)\|(?P<speed>[^|]*)\|(?P<eta>[^|]*)"
    r"\|(?P<fi>[^|]*)\|(?P<fc>[^|]*)\|(?P<status>[^|]*)\|(?P<vcodec>[^|]*)\|(?P<acodec>[^|]*)"
)
POST_RE = re.compile(r"^ZPOST\|(?P<name>[^|]*)\|(?P<status>[^|]*)")
ITEM_RE = re.compile(r"Downloading (?:item|video) (\d+) of (\d+)")
DEST_RE = re.compile(r"^\[download\] Destination: (.+)$")
MERGE_RE = re.compile(r'^\[Merger\] Merging formats into "(.+)"$')
EXTRACT_RE = re.compile(r"^\[ExtractAudio\] Destination: (.+)$")
ALREADY_RE = re.compile(r"^\[download\] (.+) has already been downloaded")
ERROR_RE = re.compile(r"^ERROR: (.+)$")

PP_NAMES_RU = {
    "Merger": "Объединение видео и аудио",
    "ExtractAudio": "Конвертация в аудио",
    "VideoConvertor": "Конвертация видео",
    "EmbedThumbnail": "Встраивание обложки",
    "Metadata": "Запись метаданных",
    "FFmpegMetadata": "Запись метаданных",
    "EmbedSubtitle": "Встраивание субтитров",
    "ModifyChapters": "Вырезание сегментов SponsorBlock",
    "SponsorBlock": "Запрос SponsorBlock",
    "MoveFiles": "Перемещение файла",
}


def to_float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


@dataclass
class ProgressParser:
    """Накапливает состояние по строкам вывода и считает общий прогресс 0..100."""
    mode: str = "video"
    percent: float | None = 0.0
    speed: float | None = None
    eta: float | None = None
    size: float | None = None
    status: str = "Подготовка…"
    item: int = 1
    item_count: int = 1
    streams_done: int = 0
    expected_streams: int | None = None
    last_error: str = ""
    last_destination: str = ""
    indeterminate: bool = False
    log_lines: list[str] = field(default_factory=list)

    def feed(self, line: str) -> bool:
        """Вернуть True, если строку надо показать в журнале."""
        line = line.strip()
        if not line:
            return False

        m = PROG_RE.match(line)
        if m:
            self._on_progress(m)
            return False

        m = POST_RE.match(line)
        if m:
            if m["status"] == "started":
                self.indeterminate = True
                self.status = PP_NAMES_RU.get(m["name"], f"Обработка: {m['name']}")
                self.speed = self.eta = None
            return False

        m = ITEM_RE.search(line)
        if m:
            self.item, self.item_count = int(m[1]), max(1, int(m[2]))
            self.streams_done, self.expected_streams = 0, None
            self.indeterminate = False
            self.percent = self._overall(0.0)

        for rx in (DEST_RE, MERGE_RE, EXTRACT_RE):
            m = rx.match(line)
            if m:
                self.last_destination = m[1]
        m = ALREADY_RE.match(line)
        if m:
            self.last_destination = m[1]
            self.status = "Файл уже скачан"
        m = ERROR_RE.match(line)
        if m:
            self.last_error = m[1]
        return True

    def _on_progress(self, m: re.Match) -> None:
        self.indeterminate = False
        done = to_float(m["done"]) or 0.0
        total = to_float(m["total"]) or to_float(m["est"])
        fi, fc = to_float(m["fi"]), to_float(m["fc"])
        if total:
            frac: float | None = min(1.0, done / total)
        elif fc:
            frac = min(1.0, (fi or 0) / fc)
        else:
            frac = None
        self.size = total or done or None
        self.speed = to_float(m["speed"])
        self.eta = to_float(m["eta"])

        vc, ac = m["vcodec"], m["acodec"]
        has_v, has_a = vc not in ("none", "NA", ""), ac not in ("none", "NA", "")
        if self.expected_streams is None:
            self.expected_streams = 1 if (self.mode == "audio" or (has_v and has_a)) else 2
        if self.mode == "audio" or (has_a and not has_v):
            self.status = "Загрузка аудио"
        elif has_v and not has_a:
            self.status = "Загрузка видео"
        else:
            self.status = "Загрузка"
        finished = m["status"] == "finished"
        if finished:
            frac = 1.0
        self.percent = self._overall(frac) if frac is not None else None
        if frac is None:
            self.indeterminate = True
        if finished:
            self.streams_done += 1

    def _overall(self, stream_frac: float) -> float:
        expected = self.expected_streams or (1 if self.mode == "audio" else 2)
        item_frac = (min(self.streams_done, expected - 1) + stream_frac) / expected
        # последние ~2% оставляем на постобработку
        return max(0.0, min(98.0, ((self.item - 1) + item_frac) / self.item_count * 100.0))


# ------------------------------------------------------------------ аргументы
VIDEO_QUALITIES = [("Лучшее доступное", "best"), ("4K · 2160p", "2160"), ("2K · 1440p", "1440"),
                   ("Full HD · 1080p", "1080"), ("HD · 720p", "720"), ("480p", "480"), ("360p", "360")]
AUDIO_QUALITIES = [("Лучшее (VBR)", "0"), ("320 кбит/с", "320"), ("256 кбит/с", "256"),
                   ("192 кбит/с", "192"), ("128 кбит/с", "128")]


def quality_label(mode: str, quality: str, container: str, audio_fmt: str) -> str:
    if quality.startswith("fmt:"):
        return (audio_fmt.upper() if mode == "audio" else container.upper()) + " · ручной выбор"
    if mode == "audio":
        q = "лучшее" if quality == "0" else f"{quality} кбит/с"
        return f"{audio_fmt.upper()} · {q}"
    q = "лучшее" if quality == "best" else f"{quality}p"
    return f"{container.upper()} · {q}"


@dataclass
class BuildOptions:
    url: str
    mode: str
    quality: str
    outdir: str
    ffmpeg_dir: str
    record_file: str
    cookie_file: str | None = None
    playlist: bool = False
    container: str = "mp4"
    audio_format: str = "mp3"
    filename_template: str = "%(title).150B [%(id)s].%(ext)s"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_subs: bool = False
    subs_langs: str = "ru,en"
    sponsorblock: bool = False
    rate_limit: str = ""
    fragments: int = 4
    proxy: str = ""


def build_download_args(o: BuildOptions) -> list[str]:
    a: list[str] = [
        "--ignore-config", "--newline", "--color", "no_color", "--encoding", "utf-8",
        "--ffmpeg-location", o.ffmpeg_dir,
        "--progress-template", PROGRESS_TEMPLATE,
        "--progress-template", POSTPROCESS_TEMPLATE,
        "--print-to-file", f"after_move:%(title)s{REC_SEP}%(filepath)s", o.record_file,
        "--retries", "10", "--fragment-retries", "10", "--socket-timeout", "30", "--no-mtime",
        "-P", o.outdir,
    ]
    if sys.platform.startswith("win"):
        a.append("--windows-filenames")

    if o.playlist:
        template = "%(playlist_title|Playlist)s/%(playlist_index)03d - %(title).150B.%(ext)s"
        a += ["--yes-playlist", "-o", template]
    else:
        a += ["--no-playlist", "-o", o.filename_template]

    manual = o.quality[4:] if o.quality.startswith("fmt:") else ""
    if o.mode == "audio":
        a += ["-f", f"{manual}/ba/b" if manual else "ba/b", "-x", "--audio-format", o.audio_format]
        if o.audio_format in ("mp3", "m4a", "opus") and not manual:
            a += ["--audio-quality", "0" if o.quality == "0" else f"{o.quality}K"]
        if o.embed_thumbnail and o.audio_format != "wav":
            a.append("--embed-thumbnail")
    else:
        merge = o.container if o.container == "mkv" else f"{o.container}/mkv"
        if manual:
            # пользователь сам выбрал видео и звук: yt-dlp скачает их отдельно, FFmpeg склеит
            a += ["-f", f"{manual}/bv*+ba/b", "--merge-output-format", merge]
        else:
            cap = "res" if o.quality == "best" else f"res:{o.quality}"
            codecs = {"mp4": "vcodec:h264,acodec:m4a", "webm": "vcodec:vp9,acodec:opus"}.get(o.container, "")
            a += ["-f", "bv*+ba/b", "-S", cap + ("," + codecs if codecs else ""), "--merge-output-format", merge]
        if o.embed_thumbnail and o.container != "webm":
            a.append("--embed-thumbnail")
        if o.embed_subs:
            a += ["--embed-subs", "--sub-langs", o.subs_langs or "ru,en"]
        a.append("--embed-chapters")

    if o.embed_metadata:
        a.append("--embed-metadata")
    if o.sponsorblock:
        a += ["--sponsorblock-remove", "sponsor,selfpromo,interaction"]
    if o.rate_limit.strip():
        a += ["-r", o.rate_limit.strip()]
    if o.fragments and o.fragments > 1:
        a += ["-N", str(o.fragments)]
    if o.proxy.strip():
        a += ["--proxy", o.proxy.strip()]
    if o.cookie_file:
        a += ["--cookies", o.cookie_file]
    return a + ["--", o.url]


def build_info_args(url: str, playlist: bool, cookie_file: str | None, proxy: str) -> list[str]:
    a = ["--ignore-config", "-J", "--no-warnings", "--encoding", "utf-8", "--socket-timeout", "20",
         "--flat-playlist" if playlist else "--no-playlist"]
    if proxy.strip():
        a += ["--proxy", proxy.strip()]
    if cookie_file:
        a += ["--cookies", cookie_file]
    return a + ["--", url]


# ------------------------------------------------------------------ список форматов
def codec_name(code: str | None) -> str:
    c = (code or "").lower()
    for prefix, name in (("avc", "H.264"), ("h264", "H.264"), ("vp09", "VP9"), ("vp9", "VP9"), ("av01", "AV1"),
                         ("hev", "HEVC"), ("hvc", "HEVC"), ("h265", "HEVC"), ("vp8", "VP8"), ("mp4a", "AAC"),
                         ("opus", "Opus"), ("vorbis", "Vorbis"), ("ac-3", "AC3"), ("ec-3", "E-AC3"),
                         ("flac", "FLAC"), ("mp3", "MP3")):
        if c.startswith(prefix):
            return name
    return c.split(".")[0].upper() if c and c != "none" else ""


def _has(codec: str | None) -> bool:
    return bool(codec) and codec not in ("none", "NA")


def _size_text(f: dict) -> str:
    n = f.get("filesize") or f.get("filesize_approx")
    if not n:
        return ""
    mb = n / 1024 / 1024
    return f"~{mb / 1024:.1f} ГБ" if mb >= 1024 else f"~{mb:.0f} МБ"


def summarize_formats(formats: list[dict]) -> dict:
    """Из formats yt-dlp делаем два списка для выбора: видео (отдельно) и звук (отдельно).

    Если сайт отдаёт только готовые «видео+звук» форматы — они попадают в videos с muxed=True,
    а список аудио остаётся пустым (звук уже внутри).
    """
    video_only: dict[tuple, dict] = {}
    muxed: dict[tuple, dict] = {}
    audio: dict[tuple, dict] = {}
    for f in formats or []:
        fid = str(f.get("format_id", ""))
        if not fid or f.get("protocol") == "mhtml" or f.get("format_note") == "storyboard":
            continue
        vc, ac = f.get("vcodec"), f.get("acodec")
        height = int(f.get("height") or 0)
        tbr = float(f.get("tbr") or f.get("vbr") or 0)
        if _has(vc) and height:
            fps = int(round(f.get("fps") or 0))
            fps_txt = str(fps) if fps > 30 else ""
            label = f"{height}p{fps_txt} · {codec_name(vc)} · {f.get('ext', '')}"
            size = _size_text(f)
            if size:
                label += f" · {size}"
            entry = {"id": fid, "label": label, "height": height, "fps": fps, "tbr": tbr, "muxed": _has(ac)}
            target = muxed if _has(ac) else video_only
            key = (height, fps_txt, codec_name(vc), f.get("ext"))
            if key not in target or tbr > target[key]["tbr"]:
                target[key] = entry
        elif _has(ac) and not _has(vc):
            abr = float(f.get("abr") or f.get("tbr") or 0)
            lang = f.get("language") or ""
            label = f"{abr:.0f} кбит/с · {codec_name(ac)} · {f.get('ext', '')}" if abr else f"{codec_name(ac)} · {f.get('ext', '')}"
            if lang:
                label += f" · {lang}"
            size = _size_text(f)
            if size:
                label += f" · {size}"
            key = (round(abr / 8), codec_name(ac), lang)
            if key not in audio or abr > audio[key]["abr"]:
                audio[key] = {"id": fid, "label": label, "abr": abr}

    def sort_video(items: dict) -> list[dict]:
        return sorted(items.values(), key=lambda e: (e["height"], e["fps"], e["tbr"]), reverse=True)

    videos = sort_video(video_only) or sort_video(muxed)
    audios = sorted(audio.values(), key=lambda e: e["abr"], reverse=True)[:14]
    return {"videos": videos, "audios": audios if video_only or audios else []}
