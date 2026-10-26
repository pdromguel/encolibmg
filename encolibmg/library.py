"""EncoreLibrary folder: manifest, file naming and scanning.

Encore only looks at files in the library root and pairs them by base name
(see FsSvc.js in the Encore repo), so everything here is flat.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from send2trash import send2trash

from encolibmg.errors import AlreadyExists
from encolibmg.tags import write_tags

AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".wav"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi"}
MIDI_EXTS = {".mid", ".kar"}
LYRIC_EXTS = {".lrc", ".cdg"}
IGNORED = {"manifest.json", "songdb.json"}
MAX_BASE_LEN = 150


class LibraryError(Exception):
    pass


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _clean(part: str) -> str:
    part = _nfc(part).replace('"', "'")
    part = part.replace("/", "-").replace("\\", "-")
    part = re.sub(r'[<>:|?*\x00-\x1f]', "", part)
    part = re.sub(r"\s+", " ", part).strip()
    return part.rstrip(". ")


def base_name(artist: str, title: str) -> str:
    """File base name in the 'Artist - Title' form Encore expects."""
    name = f"{_clean(artist) or 'Desconhecido'} - {_clean(title) or 'Sem título'}"
    if len(name) > MAX_BASE_LEN:
        name = name[:MAX_BASE_LEN]
    return name.rstrip(". ")


def inside(root: Path, rel: str) -> Path:
    """Resolves `rel` under `root`; raises ValueError if it points anywhere else
    (`..`, absolute paths, other drives). Use for every path that comes from the UI or a manifest."""
    root = Path(root).resolve()
    target = (root / rel).resolve() if rel else root
    if target != root and root not in target.parents:
        raise ValueError("Caminho fora da biblioteca.")
    return target


def _split_base(base: str) -> tuple[str, str]:
    if " - " in base:
        artist, title = base.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", base


def _strip_ext(name: str) -> str:
    """'X.multiplexed.mp3' -> 'X', 'X.guide.kar' -> 'X', 'X.lrc' -> 'X'."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    for suffix in (".multiplexed", ".guide", ".melody", ".chorus"):
        if stem.lower().endswith(suffix):
            return stem[: -len(suffix)]
    return stem


@dataclass
class Track:
    base: str
    artist: str
    title: str
    files: list[Path] = field(default_factory=list)
    kind: str = "orphan"

    @property
    def exts(self) -> set[str]:
        return {f.suffix.lower() for f in self.files}

    @property
    def multiplexed(self) -> bool:
        return any(".multiplexed." in f.name.lower() for f in self.files)

    @property
    def has_video(self) -> bool:
        return bool(self.exts & VIDEO_EXTS)

    @property
    def has_guide(self) -> bool:
        return any(re.search(r"\.(guide|melody)\.(mid|kar)$", f.name, re.I) for f in self.files)

    def file_with(self, exts: set[str]) -> Path | None:
        return next((f for f in self.files if f.suffix.lower() in exts), None)


KIND_LABEL = {
    "multiplex_lrc": "Multiplex + LRC",
    "audio_lrc": "Áudio + LRC",
    "mtv": "MTV",
    "midi": "MIDI",
    "orphan": "⚠ invisível no Encore",
}


def kind_label(track: Track) -> str:
    label = KIND_LABEL.get(track.kind, track.kind)
    if track.kind in ("multiplex_lrc", "audio_lrc"):
        if track.has_guide:
            label += " + guia"
        if track.has_video:
            label += " + clipe"
    return label


def _classify(track: Track) -> str:
    exts = track.exts
    has_audio = bool(exts & AUDIO_EXTS)
    has_lyrics = bool(exts & LYRIC_EXTS) or bool(exts & MIDI_EXTS)
    if has_audio and has_lyrics:
        return "multiplex_lrc" if track.multiplexed else "audio_lrc"
    if exts & VIDEO_EXTS:
        return "mtv"
    if exts & MIDI_EXTS:
        return "midi"
    return "orphan"


class Library:
    def __init__(self, path: Path):
        self.path = Path(path)

    @property
    def title(self) -> str:
        try:
            data = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
            return data.get("title") or self.path.name
        except (OSError, ValueError):
            return self.path.name

    @classmethod
    def create(cls, path: Path, title: str) -> "Library":
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        manifest = path / "manifest.json"
        if not manifest.exists():
            # additionalContents must exist for Encore to add its automatic MTV category
            data = {"title": title, "description": "Criada pelo EncoLibMG",
                    "additionalContents": {"bgvCategories": [], "bumperImages": []}}
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return cls(path)

    @classmethod
    def open(cls, path: Path) -> "Library":
        path = Path(path)
        if not (path / "manifest.json").is_file():
            raise LibraryError(f"{path} não tem manifest.json — não é uma biblioteca do Encore.")
        return cls(path)

    def scan(self) -> list[Track]:
        groups: dict[str, Track] = {}
        for f in sorted(self.path.iterdir()):
            if not f.is_file() or f.name.lower() in IGNORED or f.name.startswith("._"):
                continue
            ext = f.suffix.lower()
            if ext not in AUDIO_EXTS | VIDEO_EXTS | MIDI_EXTS | LYRIC_EXTS:
                continue
            base = _nfc(_strip_ext(f.name))
            key = base.lower()
            if key not in groups:
                artist, title = _split_base(base)
                groups[key] = Track(base, artist, title)
            groups[key].files.append(f)
        tracks = list(groups.values())
        for t in tracks:
            t.kind = _classify(t)
        return sorted(tracks, key=lambda t: (t.artist.lower(), t.title.lower()))

    def exists(self, base: str) -> bool:
        key = _nfc(base).lower()
        return any(t.base.lower() == key for t in self.scan())

    def rename_track(self, track: Track, artist: str, title: str) -> Track:
        """Renames every sibling file and rewrites mp3 tags. Case-only renames are allowed."""
        new_base = base_name(artist, title)
        if new_base.lower() != track.base.lower() and self.exists(new_base):
            raise AlreadyExists(f"'{new_base}' já está na biblioteca.")
        for f in track.files:
            target = f.with_name(new_base + f.name[len(track.base):])
            if target.name != f.name:
                f.rename(target)
            if target.suffix.lower() == ".mp3":
                write_tags(target, artist.strip(), title.strip())
        return next(t for t in self.scan() if t.base == new_base)

    def remove(self, track: Track) -> None:
        for f in track.files:
            if f.exists():
                send2trash(str(f))
