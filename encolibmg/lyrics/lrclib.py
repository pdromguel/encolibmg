"""LRCLIB (https://lrclib.net) — free synced-lyrics database."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from encolibmg import __version__

API = "https://lrclib.net/api/search"
HEADERS = {
    "User-Agent": f"EncoLibMG/{__version__} (https://github.com/Encore-Karaoke-Labs/Encore-Karaoke)"
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


def _get(session, params: dict) -> list[dict]:
    resp = session.get(API, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


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
