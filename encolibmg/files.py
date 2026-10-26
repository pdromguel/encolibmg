"""Small file helpers shared by the asset modules (SoundFont, visual)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from threading import Event

import requests

from encolibmg.errors import Cancelled


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    return re.sub(r"\s+", " ", name).strip(" .") or "sem nome"


def unique_path(folder: Path, name: str) -> Path:
    """folder/name, or 'name (2).ext', 'name (3).ext'… if taken."""
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    stem, suffix, n = p.stem, p.suffix, 2
    while p.exists():
        p = folder / f"{stem} ({n}){suffix}"
        n += 1
    return p


def rel(lib_path: Path, p: Path) -> str:
    """Path stored in manifest.json: relative to the library, forward slashes."""
    return Path(p).relative_to(lib_path).as_posix()


def download(url: str, dest: Path, on_progress=None, cancel: Event | None = None, session=None) -> Path:
    session = session or requests
    tmp = dest.with_name(dest.name + ".part")
    with session.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                if cancel is not None and cancel.is_set():
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise Cancelled()
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done / total)
    shutil.move(str(tmp), str(dest))
    return dest
