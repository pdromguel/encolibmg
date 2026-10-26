"""Turning lists into queue entries ({"artist", "title", "duration"?}): pasted text, a YouTube playlist, a CSV
exported from Spotify (Exportify) or any CSV with artist/title columns."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from encolibmg.core.i18n import t
from encolibmg.library.importer import clean_title

_DASH = re.compile(r"\s+[-–—]\s+")
# what streaming services append to titles and lyrics sites leave out
_SUFFIX = re.compile(r"\s+[-–—]\s+(?:(?:\d{4}\s+)?remaster(?:ed)?(?:\s+\d{4})?(?:\s+version)?|radio\s+edit|single\s+version|"
                     r"album\s+version|mono(?:\s+version)?|stereo(?:\s+version)?|original\s+mix)\b.*$", re.I)
_FEAT = re.compile(r"\s*[\(\[]\s*(?:feat\.?|ft\.?|featuring|with)\s+[^\)\]]*[\)\]]|\s+(?:feat\.?|ft\.?)\s+.*$", re.I)
# "(Official 4K Video)", "[Lyric Video]", "(Remastered 2009)"… but not "(Who Loves Me)"
_VIDEO_TAG = re.compile(r"\s*[\(\[][^\)\]]*\b(?:official|video|audio|lyrics?|4k|hd|hq|remaster(?:ed)?|visuali[sz]er|mv)\b"
                        r"[^\)\]]*[\)\]]", re.I)
_CHANNEL = re.compile(r"\s*(?:-\s*topic|vevo|official)\s*$", re.I)


def tidy_title(title: str) -> str:
    return clean_title(_VIDEO_TAG.sub("", _FEAT.sub("", _SUFFIX.sub("", title)))).strip()


def split_name(text: str, default_artist: str = "") -> dict:
    """'Artist - Title' → both; a bare title keeps `default_artist` (e.g. the channel name)."""
    text = clean_title(text.strip())
    parts = _DASH.split(text, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return {"artist": parts[0].strip(), "title": tidy_title(parts[1])}
    return {"artist": default_artist.strip(), "title": tidy_title(text)}


def parse_list(text: str) -> list[dict]:
    """One song per line, 'Artist - Title'. Blank lines and lines starting with # are ignored."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            e = split_name(line)
            if e["title"]:
                out.append(e)
    return out


_TITLE_COLS = ("track name", "title", "name", "song", "música", "musica", "título", "titulo")
_ARTIST_COLS = ("artist name(s)", "artist name", "artist", "artists", "artista", "artistas")
_DURATION_COLS = ("duration (ms)", "duration_ms", "track duration (ms)")


def parse_csv_text(text: str) -> list[dict]:
    """Exportify (Spotify) and similar CSVs: title + artist columns, duration (ms) when present."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = {c.strip().casefold(): c for c in (rows.fieldnames or [])}
    tcol = next((cols[c] for c in _TITLE_COLS if c in cols), None)
    acol = next((cols[c] for c in _ARTIST_COLS if c in cols), None)
    dcol = next((cols[c] for c in _DURATION_COLS if c in cols), None)
    if tcol is None:
        raise ValueError(t("err.csv_columns"))
    out = []
    for row in rows:
        title = tidy_title(row.get(tcol) or "")
        if not title:
            continue
        artist = (row.get(acol) or "") if acol else ""
        artist = re.split(r"\s*[,;]\s*", artist.strip())[0] if artist else ""  # first artist only
        e = {"artist": artist, "title": title}
        try:
            if dcol and row.get(dcol):
                e["duration"] = int(float(row[dcol])) / 1000
        except ValueError:
            pass
        out.append(e)
    return out


def parse_csv(path: Path) -> list[dict]:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return parse_csv_text(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return parse_csv_text(raw.decode("utf-8", "replace"))


def playlist_entries(url: str, extract=None) -> list[dict]:
    """Song names from a YouTube (Music) playlist, without downloading anything."""
    if extract is None:
        from yt_dlp import YoutubeDL

        def extract(u):
            with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}) as y:
                return y.extract_info(u, download=False)
    info = extract(url) or {}
    if not info.get("entries"):
        raise ValueError(t("err.playlist_empty"))
    out = []
    for e in info["entries"]:
        if not e or not e.get("title") or e.get("title") in ("[Deleted video]", "[Private video]"):
            continue
        channel = _CHANNEL.sub("", e.get("channel") or e.get("uploader") or "")
        out.append(split_name(e["title"], default_artist=channel))
    return [e for e in out if e["title"]]
