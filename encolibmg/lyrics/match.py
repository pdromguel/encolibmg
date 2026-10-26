"""Find synced lyrics for a local audio file (title + duration known)."""

from __future__ import annotations

from pathlib import Path

from encolibmg.lyrics import lrclib
from encolibmg.lyrics.lrclib import LyricsCandidate

DURATION_TOLERANCE = 3.0


def find_synced(artist: str, title: str, duration: float | None, search=None,
                tol: float = DURATION_TOLERANCE) -> LyricsCandidate | None:
    """Best synced candidate whose duration is within `tol` s of the file (closest wins)."""
    search = search or lrclib.search
    cands = [c for c in search(f"{artist} - {title}") if c.synced]
    if duration is None:
        return cands[0] if cands else None
    near = [c for c in cands if abs(c.duration - duration) <= tol]
    return min(near, key=lambda c: abs(c.duration - duration), default=None)


def read_lrc(path: Path) -> str:
    """LRC files in the wild are UTF-8 (with or without BOM) or Windows-1252."""
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")
