"""LRCLIB (https://lrclib.net) — free synced-lyrics database."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from encolibmg import __version__
from encolibmg.core.i18n import t

API = "https://lrclib.net/api/search"
HEADERS = {
    "User-Agent": f"EncoLibMG/{__version__} (https://github.com/pdromguel/encolibmg)"
}


@dataclass
class LyricsCandidate:
    id: int
    artist: str
    title: str
    album: str
    duration: float
    synced: str | None
    plain: str | None


RETRY_WAITS = (1.5, 4.0)  # s before the 2nd and 3rd try when LRCLIB is briefly down
# LRCLIB answers 503 "The server is busy" when a search finds nothing (measured: misses → 503 in ~1.4 s,
# hits → 200 in ~0.4 s). So a 503 that repeats means "no results", not an outage.
BUSY_MEANS_EMPTY = 503


class LyricsUnavailable(RuntimeError):
    """LRCLIB didn't answer (server error, no connection) even after retrying."""


def _status(e: Exception) -> int | None:
    return getattr(getattr(e, "response", None), "status_code", None)


def _transient(e: Exception) -> bool:
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return True
    status = _status(e)
    return isinstance(e, requests.HTTPError) and status is not None and status >= 500


def _get(session, params: dict) -> list[dict]:
    """One search call. A 503 is tried twice and then means "nothing found"; other server errors and dropped
    connections are tried three times and then raise LyricsUnavailable."""
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            resp = session.get(API, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if not _transient(e):
                raise
            if _status(e) == BUSY_MEANS_EMPTY and attempt >= 1:
                return []
            if attempt == len(RETRY_WAITS):
                raise LyricsUnavailable(t("err.lyrics_unavailable", detail=_status(e) or type(e).__name__)) from e
            time.sleep(RETRY_WAITS[attempt])
    return []


def search(query: str, session=None) -> list[LyricsCandidate]:
    """Search by free text; 'Artist - Title' is sent as separate fields."""
    session = session or requests
    if " - " in query:
        artist, title = query.split(" - ", 1)
        params = {"track_name": title.strip(), "artist_name": artist.strip()}
    else:
        params = {"q": query.strip()}
    items = _get(session, params)
    if not items and "q" not in params:
        # field search is strict; fall back to fuzzy free text
        items = _get(session, {"q": f"{params['artist_name']} {params['track_name']}"})

    out = []
    for item in items:
        if item.get("instrumental"):
            continue
        out.append(
            LyricsCandidate(
                id=item["id"],
                artist=item.get("artistName") or "",
                title=item.get("trackName") or "",
                album=item.get("albumName") or "",
                duration=float(item.get("duration") or 0),
                synced=item.get("syncedLyrics") or None,
                plain=item.get("plainLyrics") or None,
            )
        )
    # synced first, then exact artist/title matches (LRCLIB has many
    # "Adele, Adele" / "Hello [Hello, 2015]" variants); stable sort keeps
    # LRCLIB's relevance order inside each group
    want_artist = params.get("artist_name", "").casefold()
    want_title = params.get("track_name", "").casefold()
    out.sort(key=lambda c: (
        c.synced is None,
        bool(want_artist) and c.artist.casefold() != want_artist,
        bool(want_title) and c.title.casefold() != want_title,
    ))
    return out
