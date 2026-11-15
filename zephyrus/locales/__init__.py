"""Каталоги переводов. Чтобы добавить язык: скопируйте en.py в <код>.py, переведите строки,
добавьте модуль сюда и запись в LANGUAGES (zephyrus/i18n.py). Нет ключа в языке — берётся английский."""
from . import be, en, ru, uk

CATALOGS: dict[str, dict[str, str]] = {
    "en": en.STRINGS,
    "ru": ru.STRINGS,
    "uk": uk.STRINGS,
    "be": be.STRINGS,
}
