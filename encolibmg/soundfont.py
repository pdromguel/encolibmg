"""The library's SoundFont (used by Encore for MIDI/.kar tracks and the guide melody).

Stored under SoundFonts/ and referenced as additionalContents.soundFont,
a path relative to the library (EncoreLoader.js ~L318).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from threading import Event

from send2trash import send2trash

from encolibmg.files import download, rel, unique_path
from encolibmg.library import Library
from encolibmg.manifest import ensure_additional, read_manifest, write_manifest

FOLDER = "SoundFonts"
EXTS = {".sf2", ".sf3", ".dls"}
GENERALUSER_URL = "https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2"
GENERALUSER_LICENSE = "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/documentation/LICENSE.txt"


def current_soundfont(lib: Library) -> str | None:
    return (read_manifest(lib.path).get("additionalContents") or {}).get("soundFont")


def _set(lib: Library, value: str | None) -> None:
    data = read_manifest(lib.path)
    ensure_additional(data)
    if value:
        data["additionalContents"]["soundFont"] = value
    else:
        data["additionalContents"].pop("soundFont", None)
    write_manifest(lib.path, data)


def install_soundfont(lib: Library, src: Path) -> str:
    src = Path(src)
    if src.suffix.lower() not in EXTS:
        raise ValueError(f"O Encore aceita SoundFont .sf2, .sf3 ou .dls (não {src.suffix}).")
    folder = lib.path / FOLDER
    same = folder / src.name
    if same.exists() and same.stat().st_size == src.stat().st_size:
        dest = same  # already there
    else:
        dest = unique_path(folder, src.name)
        shutil.copy2(src, dest)
    value = rel(lib.path, dest)
    _set(lib, value)
    return value


def remove_soundfont(lib: Library) -> None:
    """Back to Encore's built-in sounds; the file goes to the Recycle Bin if it lives in SoundFonts/."""
    cur = current_soundfont(lib)
    _set(lib, None)
    if cur:
        p = lib.path / cur
        if p.exists() and (lib.path / FOLDER) in p.resolve().parents:
            send2trash(str(p))


def download_generaluser(lib: Library, on_progress=None, cancel: Event | None = None, session=None) -> str:
    """GeneralUser GS (free GM SoundFont, license allows use and redistribution) + its license text."""
    folder = lib.path / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "GeneralUser-GS.sf2"
    if not dest.exists():
        download(GENERALUSER_URL, dest, on_progress, cancel, session=session)
    try:
        download(GENERALUSER_LICENSE, folder / "GeneralUser-GS-LICENSE.txt", session=session)
    except Exception:
        pass  # the SoundFont itself is what matters
    value = rel(lib.path, dest)
    _set(lib, value)
    return value
