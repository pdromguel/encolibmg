"""Reading karaoke MIDI files (.kar/.mid) without trusting their text encoding."""

from __future__ import annotations

import re
from pathlib import Path

import mido

MIN_LYRIC_EVENTS = 5


_KANA = re.compile(r"[぀-ヿ]")
_KANJI = re.compile(r"[一-鿿]")


def _looks_japanese(s: str) -> bool:
    # Western bytes like "çã" (E7 E3) are also valid Shift-JIS ("鈬"); real Japanese has kana,
    # or is kanji without Latin letters mixed in
    return bool(_KANA.search(s)) or (bool(_KANJI.search(s)) and not re.search(r"[A-Za-z]", s))


def decode_text(raw: bytes) -> str:
    """KAR text is usually ASCII/Windows-1252, Japanese files use Shift-JIS; newer ones UTF-8."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        s = raw.decode("cp932")
        if _looks_japanese(s):
            return s
    except UnicodeDecodeError:
        pass
    return raw.decode("cp1252", errors="replace")


def _texts(path: Path) -> list[tuple[str, str]]:
    """[(type, decoded text)] for every text/lyrics meta event, in file order."""
    mid = mido.MidiFile(str(path), charset="latin-1")  # latin-1 round-trips the raw bytes
    out = []
    for track in mid.tracks:
        for msg in track:
            if msg.type in ("text", "lyrics"):
                out.append((msg.type, decode_text(msg.text.encode("latin-1")).strip("\x00")))
    return out


def midi_names(path: Path) -> tuple[str | None, str | None] | None:
    """(artist, title) from KAR '@T' headers (title, then artist) or Encore '{#TITLE=…}' metadata."""
    try:
        texts = [t for _, t in _texts(path)]
    except Exception:
        return None
    meta = {}
    for t in texts:
        for part in t.split("}"):
            if part.startswith("{#") and "=" in part:
                k, v = part[2:].split("=", 1)
                meta[k.upper()] = v.strip()
    if meta.get("TITLE"):
        return meta.get("ARTIST"), meta["TITLE"]
    heads = [t[2:].strip() for t in texts if t.upper().startswith("@T") and t[2:].strip()]
    if not heads:
        return None
    return (heads[1] if len(heads) > 1 else None), heads[0]


def midi_has_lyrics(path: Path) -> bool:
    try:
        texts = _texts(path)
    except Exception:
        return False
    words = [t for _, t in texts if t.strip() and not t.startswith(("@", "%", "{#"))]
    return len(words) >= MIN_LYRIC_EVENTS
