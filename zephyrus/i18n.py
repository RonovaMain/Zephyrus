"""Локализация интерфейса (без зависимостей от Qt — можно импортировать откуда угодно).

* Каталоги строк лежат в zephyrus/locales/<код>.py (словарь STRINGS).
* Английский — базовый: если в языке нет ключа, берётся английская строка.
* Язык выбирается в настройках: «auto» = язык системы, а если такого языка в программе нет — английский.
"""
from __future__ import annotations

from .locales import CATALOGS

DEFAULT = "en"

# порядок = порядок в выпадающем списке (названия на родных языках)
LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "uk": "Українська",
    "be": "Беларуская",
    "en": "English",
}

_current = DEFAULT
_strings: dict[str, str] = CATALOGS[DEFAULT]


def set_language(code: str) -> str:
    """Включить язык (неизвестный код => английский). Возвращает фактически выбранный код."""
    global _current, _strings
    _current = code if code in CATALOGS else DEFAULT
    _strings = CATALOGS[_current]
    return _current


def current_language() -> str:
    return _current


def tr(key: str, **kwargs: object) -> str:
    """Перевести ключ; {плейсхолдеры} подставляются из kwargs."""
    text = _strings.get(key)
    if text is None:
        text = CATALOGS[DEFAULT].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def match_language(system_tags: list[str] | tuple[str, ...]) -> str:
    """Подобрать язык по списку языков системы (например ['ru-RU', 'en-US']).

    Смотрим основной язык системы (первый в списке). Нет такого перевода — английский.
    """
    if not system_tags:
        return DEFAULT
    base = str(system_tags[0]).replace("_", "-").split("-")[0].strip().lower()
    return base if base in CATALOGS else DEFAULT


def resolve_language(setting: str, system_tags: list[str] | tuple[str, ...]) -> str:
    """setting — значение из настроек: «auto» или код языка."""
    if setting and setting != "auto" and setting in CATALOGS:
        return setting
    return match_language(system_tags)
