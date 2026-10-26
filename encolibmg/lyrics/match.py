"""Find synced lyrics without a person choosing: for a local file (duration known) or a name in a list."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from encolibmg.lyrics import lrclib
from encolibmg.lyrics.lrclib import LyricsCandidate

DURATION_TOLERANCE = 3.0
TITLE_MIN = 0.8    # how alike the title must be (0–1) to accept lyrics nobody looked at
ARTIST_MIN = 0.6   # artists vary more ("Tom Jobim" / "Antônio Carlos Jobim & Elis")


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


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)            # "(Remastered 2011)", "[Live]"
    return re.sub(r"[^\w]+", " ", s).strip()


def similarity(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b.split(" feat ")[0] or b in a.split(" feat ")[0]:  # "Queen" vs "Queen & David Bowie"
        return max(SequenceMatcher(None, a, b).ratio(), 0.9)
    return SequenceMatcher(None, a, b).ratio()


def find_by_name(artist: str, title: str, duration: float | None = None, search=None,
                 tol: float = DURATION_TOLERANCE) -> LyricsCandidate | None:
    """Synced lyrics for a song given only by name (a pasted list, a playlist, a CSV).

    Only accepts a result whose title (and artist, when known) really matches, and whose length matches when
    `duration` is known; otherwise None, so the queue says "no lyrics" instead of downloading the wrong song.
    Live/remix/karaoke versions lose unless the name asks for them.
    """
    from encolibmg.youtube import UNWANTED, _has_word

    search = search or lrclib.search
    query = f"{artist} - {title}" if artist else title
    unwanted = [w for w in UNWANTED if not _has_word(query, w)]
    cands = [c for c in search(query) if c.synced]
    best, best_score = None, 0.0
    for c in cands:
        ts = similarity(title, c.title)
        ars = similarity(artist, c.artist) if artist else 1.0
        if ts < TITLE_MIN or ars < ARTIST_MIN:
            continue
        if duration is not None and abs(c.duration - duration) > tol:
            continue
        score = ts + ars - (0.5 if any(_has_word(c.title, w) for w in unwanted) else 0)
        if duration is not None:
            score -= abs(c.duration - duration) / 100
        else:  # no length to compare: the version most entries agree on (the album one, not an extended mix)
            score += 0.01 * sum(abs(o.duration - c.duration) <= tol for o in cands if o is not c)
        if score > best_score:
            best, best_score = c, score
    return best
