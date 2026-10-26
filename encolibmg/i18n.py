"""Translations shared by the Python engine and the web UI (encolibmg/locales/<lang>.json).

Catalogs are flat: {"key": "text with {params}"}; a plural entry is {"one": "...", "other": "..."}
picked by the `count` param. Unknown keys fall back to English, then to the key itself, so a missing
translation is visible but never crashes.
"""

from __future__ import annotations

import json
import locale
import sys
from functools import lru_cache
from pathlib import Path

LOCALES = Path(__file__).parent / "locales"
SUPPORTED = ("pt-BR", "en")
DEFAULT = "en"
_lang = DEFAULT


class _Params(dict):
    def __missing__(self, key):  # leave unknown {placeholders} visible instead of raising
        return "{" + key + "}"


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict:
    return json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))


def detect_language() -> str:
    """Windows display language → pt-BR for any Portuguese, otherwise English."""
    code = ""
    if sys.platform == "win32":
        try:
            import ctypes

            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if langid & 0x3FF == 0x16:  # LANG_PORTUGUESE
                return "pt-BR"
            return "en"
        except Exception:
            pass
    try:
        code = (locale.getlocale()[0] or "").lower()
    except Exception:
        pass
    return "pt-BR" if code.startswith(("pt", "portuguese")) else "en"


def resolve(setting: str | None) -> str:
    """`setting` is "auto", a supported language, or None (= auto)."""
    if setting in SUPPORTED:
        return setting
    return detect_language()


def set_language(setting: str | None) -> str:
    global _lang
    _lang = resolve(setting)
    return _lang


def language() -> str:
    return _lang


def t(key: str, **params) -> str:
    entry = catalog(_lang).get(key)
    if entry is None:
        entry = catalog(DEFAULT).get(key, key)
    if isinstance(entry, dict):
        entry = entry["one"] if params.get("count") == 1 else entry["other"]
    return entry.format_map(_Params(params)) if params else entry
