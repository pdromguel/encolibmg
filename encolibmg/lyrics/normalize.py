"""Rewrite any LRC into the subset Encore's LyricsEngine.parseLrc understands.

Encore matches a single `[mm:ss.xx]` at the start of each line and ignores
everything else (no [offset:], no word stamps, no repeated stamps).
"""

import re

_STAMP = re.compile(r"\[(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_WORD_STAMP = re.compile(r"<\d+:\d{1,2}(?:[.:]\d{1,3})?>")
_OFFSET = re.compile(r"^\s*\[offset:\s*([+-]?\d+)\s*\]", re.I | re.M)


def _to_ms(m: re.Match) -> int:
    frac = (m.group(3) or "0").ljust(3, "0")
    return (int(m.group(1)) * 60 + int(m.group(2))) * 1000 + int(frac)


def _fmt(ms: int) -> str:
    cs = round(ms / 10)
    minutes, cs = divmod(cs, 6000)
    return f"[{minutes:02d}:{cs // 100:02d}.{cs % 100:02d}]"


def normalize_lrc(text: str, offset_ms: int = 0) -> str:
    """`offset_ms` follows the LRC convention: positive shows lyrics earlier."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    m = _OFFSET.search(text)
    shift = offset_ms + (int(m.group(1)) if m else 0)

    lines: list[tuple[int, int, str]] = []
    for idx, raw in enumerate(text.split("\n")):
        stamps = []
        rest = raw.strip()
        while (sm := _STAMP.match(rest)):
            stamps.append(_to_ms(sm))
            rest = rest[sm.end():]
        if not stamps:
            continue  # metadata tags ([ar:], [ti:]...) and plain text
        words = re.sub(r"\s+", " ", _WORD_STAMP.sub("", rest)).strip()
        if not words:
            continue
        for t in stamps:
            lines.append((max(0, t - shift), idx, words))

    lines.sort()
    return "".join(f"{_fmt(t)} {w}\n" for t, _, w in lines)
