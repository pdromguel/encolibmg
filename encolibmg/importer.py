"""Bring files you already have (CDs, karaoke packs, old downloads) into the library."""

from __future__ import annotations

import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from send2trash import send2trash

from encolibmg import pipeline
from encolibmg.audio import loudness
from encolibmg.audio.convert import (UNSUPPORTED_AUDIO, UNSUPPORTED_VIDEO, convert_audio,
                                      convert_video, duration)
from encolibmg.errors import Cancelled
from encolibmg.library import AUDIO_EXTS, MIDI_EXTS, VIDEO_EXTS, Library, base_name
from encolibmg.lyrics.match import find_synced, read_lrc
from encolibmg.lyrics.normalize import normalize_lrc
from encolibmg.midi_info import midi_names
from encolibmg.tags import write_tags

ALL_AUDIO = AUDIO_EXTS | UNSUPPORTED_AUDIO
ALL_VIDEO = VIDEO_EXTS | UNSUPPORTED_VIDEO
COMPANIONS = {".cdg", ".lrc"} | MIDI_EXTS

KIND_LABEL = {
    "video": "MTV",
    "cdg": "Áudio + CDG",
    "audio_lrc": "Áudio + LRC",
    "audio_midi": "Áudio + guia MIDI",
    "audio": "Só áudio (precisa de letra)",
    "midi": "MIDI",
}

# "01 - ", "01. ", "1) ", "07 " (zero-padded only, so "50 Cent" survives), "SC8113-01 - "
_TRACK_NO = re.compile(r"^\s*(?:\d{1,3}\s*[-._)]\s*|0\d\s+|[A-Z]{1,4}\d{2,6}(?:-\d{1,3})?\s*-\s*)")
_JUNK = re.compile(
    r"\s*[\(\[](?:official\s*)?(?:music\s*)?(?:lyrics?|lyric\s*video|audio|video|clipe\s*oficial|"
    r"karaoke(?:\s*version)?|instrumental\s*karaoke|hq|hd|4k|visualizer|com\s*letra)[\)\]]",
    re.I,
)


def clean_title(s: str) -> str:
    s = _TRACK_NO.sub("", s, count=1)
    s = _JUNK.sub("", s)
    s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip(" -.")


def _tags(path: Path) -> tuple[str, str]:
    try:
        from mutagen import File

        f = File(path, easy=True)
        if f is None or not f.tags:
            return "", ""
        return (f.tags.get("artist") or [""])[0].strip(), (f.tags.get("title") or [""])[0].strip()
    except Exception:
        return "", ""


def infer_name(path: Path, root: Path | None = None) -> tuple[str, str]:
    """Artist/title from tags (or KAR headers), else 'Artist - Title' file name, else parent folder as artist."""
    artist, title = _tags(path)
    if artist and title:
        return clean_title(artist), clean_title(title)
    stem = clean_title(_stem(path.name))
    if path.suffix.lower() in MIDI_EXTS:
        names = midi_names(path)
        if names and names[1]:
            m_artist = names[0] or (stem.split(" - ", 1)[0] if " - " in stem else "")
            if m_artist:
                return clean_title(m_artist), clean_title(names[1])
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return clean_title(artist), clean_title(title)
    parent = path.parent
    artist = parent.name if root is None or parent != root else ""
    return clean_title(artist) or "Desconhecido", title or stem


def _stem(name: str) -> str:
    stem = name.rsplit(".", 1)[0]
    return re.sub(r"\.(multiplexed|guide|melody)$", "", stem, flags=re.I)


@dataclass
class ImportItem:
    main: Path
    companions: list[Path] = field(default_factory=list)
    artist: str = ""
    title: str = ""
    kind: str = "audio"
    status: str = ""
    selected: bool = True

    @property
    def base(self) -> str:
        return base_name(self.artist, self.title)


def _safe_extract(zip_path: Path, dest: Path) -> list[Path]:
    """Extracts only members that stay inside `dest` (no zip-slip)."""
    out = []
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            target = (dest / info.filename).resolve()
            if dest not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            out.append(target)
    return out


def scan_source(folder: Path, tmp_dir: Path) -> list[ImportItem]:
    """Builds the preview. Reads only; zips are extracted into `tmp_dir`."""
    folder, tmp_dir = Path(folder), Path(tmp_dir)
    files = [f for f in folder.rglob("*") if f.is_file()]
    for n, z in enumerate([f for f in files if f.suffix.lower() == ".zip"]):
        try:
            files += _safe_extract(z, tmp_dir / f"{n:03d}_{z.stem}")
        except zipfile.BadZipFile:
            continue

    groups: dict[tuple[Path, str], list[Path]] = defaultdict(list)
    for f in files:
        ext = f.suffix.lower()
        if ext in ALL_AUDIO | ALL_VIDEO | COMPANIONS:
            groups[(f.parent, _stem(f.name).casefold())].append(f)

    items = []
    for (_, _), group in sorted(groups.items(), key=lambda kv: str(kv[0])):
        by_ext = {f.suffix.lower(): f for f in group}
        video = next((f for f in group if f.suffix.lower() in ALL_VIDEO), None)
        audio = next((f for f in group if f.suffix.lower() in ALL_AUDIO), None)
        midi = next((f for f in group if f.suffix.lower() in MIDI_EXTS), None)
        if video:
            main, comps, kind = video, [], "video"
        elif audio:
            main = audio
            comps = [by_ext[e] for e in (".cdg", ".lrc", ".kar", ".mid") if e in by_ext]
            kind = ("cdg" if ".cdg" in by_ext else "audio_lrc" if ".lrc" in by_ext
                    else "audio_midi" if midi else "audio")
        elif midi:
            main, comps, kind = midi, [], "midi"
        else:
            continue  # lone .lrc/.cdg
        root = folder if tmp_dir not in main.parents else main.parent
        artist, title = infer_name(main, root)
        items.append(ImportItem(main, comps, artist, title, kind))
    return items


def mark_existing(lib: Library, items: list[ImportItem]) -> None:
    existing = {t.base.lower() for t in lib.scan()}
    seen = set()
    for it in items:
        key = it.base.lower()
        if key in existing:
            it.status, it.selected = "já existe", False
        elif key in seen:
            it.status, it.selected = "repetida na origem", False
        seen.add(key)


def _place(src: Path, dest_dir: Path, base: str) -> Path:
    """Copies `src` as base+ext, converting formats Encore can't play."""
    ext = src.suffix.lower()
    if ext in UNSUPPORTED_AUDIO:
        return convert_audio(src, dest_dir / f"{base}.mp3")
    if ext in UNSUPPORTED_VIDEO:
        return convert_video(src, dest_dir / f"{base}.mp4")
    if ext == ".lrc":
        dest = dest_dir / f"{base}.lrc"
        dest.write_text(normalize_lrc(read_lrc(src)), encoding="utf-8", newline="\n")
        return dest
    dest = dest_dir / f"{base}{ext}"
    shutil.copy2(src, dest)
    return dest


def import_item(lib: Library, item: ImportItem, *, move: bool = False, find_lyrics: bool = True,
                make_multiplex: bool = False, normalize: bool = True, cancel: Event | None = None,
                on_progress=None, search=None) -> str:
    """Imports one item; returns its final status text. Never overwrites."""
    progress = on_progress or (lambda step, frac=None: None)
    base = item.base
    if lib.exists(base):
        return "já existe"
    if cancel is not None and cancel.is_set():
        raise Cancelled()

    lrc_text = None
    if item.kind == "audio_lrc":
        lrc_text = read_lrc(next(c for c in item.companions if c.suffix.lower() == ".lrc"))
    elif item.kind == "audio":
        if not find_lyrics:
            return "sem letra (não importada)"
        progress("buscando letra", None)
        cand = find_synced(item.artist, item.title, duration(item.main), search=search)
        if cand is None:
            return "sem letra (não importada)"
        lrc_text = cand.synced

    if make_multiplex and lrc_text:
        pipeline.track_from_local(lib, item.main, item.artist, item.title, lrc_text, progress, cancel)
        result = "importada (Multiplex + LRC)"
    else:
        with pipeline._workdir(lib) as tmp:
            progress("copiando", None)
            files = [_place(item.main, tmp, base)]
            files += [_place(c, tmp, base) for c in item.companions]
            if lrc_text and not any(f.suffix == ".lrc" for f in files):
                lrc = tmp / f"{base}.lrc"
                lrc.write_text(normalize_lrc(lrc_text), encoding="utf-8", newline="\n")
                files.append(lrc)
            media = files[0]
            if media.suffix.lower() == ".mp3":
                write_tags(media, item.artist, item.title)
            if normalize and media.suffix.lower() in AUDIO_EXTS | VIDEO_EXTS:
                progress("ajustando volume", None)
                loudness.normalize_file(media)
            pipeline._finish(lib, files, base)
        result = f"importada ({KIND_LABEL['audio_lrc'] if lrc_text else KIND_LABEL[item.kind]})"

    if move:
        for src in [item.main, *item.companions]:
            if src.exists():
                send2trash(str(src))
    return result
