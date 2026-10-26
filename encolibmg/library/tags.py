from pathlib import Path

from mutagen.id3 import ID3, TIT2, TPE1, ID3NoHeaderError


def write_tags(mp3: Path, artist: str, title: str) -> None:
    """ID3v2.3 — the version Encore's jsmediatags reads most reliably."""
    try:
        tags = ID3(mp3)
    except ID3NoHeaderError:
        tags = ID3()
    tags.setall("TPE1", [TPE1(encoding=3, text=artist)])
    tags.setall("TIT2", [TIT2(encoding=3, text=title)])
    tags.save(mp3, v2_version=3)
