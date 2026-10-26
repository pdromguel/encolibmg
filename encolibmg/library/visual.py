"""Library look & feel stored in manifest.additionalContents (paths relative to the library):

- bgvCategories: [{BGV_CATEGORY, BGV_LIST}] background videos   (EncoreHome.js ~L530)
- bumperImages: [...] images shown on the idle screen            (UIManager.js ~L2762)
- bootVideo: video played when the library loads                (EncoreLoader.js ~L342)
- scoreNarrations: [{min, max, file}] audio played with the score (PlaybackManager.js ~L994)

Subfolders are fine here: Encore only scans the library root for songs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Event

from send2trash import send2trash

from encolibmg import youtube
from encolibmg.audio.convert import convert_audio, convert_video
from encolibmg.audio.ffmpeg import NO_WINDOW
from encolibmg.core.files import rel, safe_name, unique_path
from encolibmg.library.model import Library, inside
from encolibmg.library.manifest import ensure_additional, read_manifest, write_manifest
from encolibmg.core.i18n import t

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SFX_EXTS = {".mp3", ".wav", ".ogg", ".m4a"}
BGV_MAX_SECONDS = 300.0
BGV_SKIP_INTRO = 30.0


def _load(lib: Library) -> dict:
    data = read_manifest(lib.path)
    ensure_additional(data)
    return data


def _extra(data: dict) -> dict:
    return data["additionalContents"]


def _trash(lib: Library, relpath: str) -> None:
    """Recycle-bin a library asset; paths escaping the library (e.g. a tampered manifest) are ignored."""
    try:
        p = inside(lib.path, relpath)
    except ValueError:
        return
    if p.is_file():
        send2trash(str(p))


# --- background videos ------------------------------------------------------
def bgv_categories(lib: Library) -> list[dict]:
    return [dict(c) for c in _extra(_load(lib))["bgvCategories"]]


def _find(cats: list[dict], name: str) -> dict:
    for c in cats:
        if c.get("BGV_CATEGORY", "").casefold() == name.casefold():
            return c
    raise KeyError(t("err.category_missing", name=name))


def add_category(lib: Library, name: str) -> str:
    name = safe_name(name)
    data = _load(lib)
    cats = _extra(data)["bgvCategories"]
    if any(c.get("BGV_CATEGORY", "").casefold() == name.casefold() for c in cats):
        raise ValueError(t("err.category_exists", name=name))
    cats.append({"BGV_CATEGORY": name, "BGV_LIST": []})
    write_manifest(lib.path, data)
    return name


def rename_category(lib: Library, old: str, new: str) -> str:
    """Only the name shown in Encore changes; files stay where they are."""
    new = safe_name(new)
    data = _load(lib)
    cats = _extra(data)["bgvCategories"]
    cat = _find(cats, old)
    if new.casefold() != old.casefold() and any(c["BGV_CATEGORY"].casefold() == new.casefold() for c in cats):
        raise ValueError(t("err.category_exists", name=new))
    cat["BGV_CATEGORY"] = new
    write_manifest(lib.path, data)
    return new


def remove_category(lib: Library, name: str) -> None:
    data = _load(lib)
    cats = _extra(data)["bgvCategories"]
    cat = _find(cats, name)
    for v in cat.get("BGV_LIST", []):
        _trash(lib, v)
    cats.remove(cat)
    write_manifest(lib.path, data)


def _probe(path: Path) -> dict:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,height",
                           "-of", "json", str(path)], capture_output=True, text=True, creationflags=NO_WINDOW)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return {}


def _bgv_ready(path: Path) -> bool:
    """Already what Encore plays best: mp4, H.264, ≤1080p, no audio track."""
    streams = _probe(path).get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    return (path.suffix.lower() == ".mp4" and len(video) == 1 and video[0].get("codec_name") == "h264"
            and (video[0].get("height") or 0) <= 1080 and not any(s.get("codec_type") == "audio" for s in streams))


def _to_bgv(src: Path, dest: Path) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-an",
         "-vf", "scale=-2:'min(1080,ih)'", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(t("err.ffmpeg_convert", name=src.name, detail=proc.stderr[-800:]))


def add_bgv_file(lib: Library, category: str, src: Path, move: bool = False) -> str:
    """Copies (or converts) a video into BGV/<category>/ and lists it. Returns its manifest path."""
    src = Path(src)
    data = _load(lib)
    cat = _find(_extra(data)["bgvCategories"], category)
    dest = unique_path(lib.path / "BGV" / safe_name(cat["BGV_CATEGORY"]), safe_name(src.stem) + ".mp4")
    if _bgv_ready(src):
        (shutil.move if move else shutil.copy2)(str(src), str(dest))
    else:
        _to_bgv(src, dest)
    value = rel(lib.path, dest)
    cat.setdefault("BGV_LIST", []).append(value)
    write_manifest(lib.path, data)
    return value


def bgv_section(duration: float | None) -> tuple[float, float] | None:
    """Scenic YouTube videos run for hours; Encore loops BGVs, so a few minutes is plenty."""
    if not duration or duration <= BGV_MAX_SECONDS:
        return None
    start = BGV_SKIP_INTRO if duration > BGV_MAX_SECONDS + BGV_SKIP_INTRO else 0.0
    return start, start + BGV_MAX_SECONDS


def add_bgv_video(lib: Library, category: str, video: youtube.VideoCandidate, on_progress=None,
                  cancel: Event | None = None) -> str:
    progress = on_progress or (lambda step, frac=None: None)
    with tempfile.TemporaryDirectory(prefix=".encore-tmp-", dir=lib.path) as tmp:
        progress("step.download_video", 0.0)
        src = youtube.download_video(video.url, Path(tmp), cancel, lambda f: progress("step.download_video", f),
                                     video_only=True, section=bgv_section(video.duration))
        named = src.with_name(safe_name(video.title)[:80] + src.suffix)
        src.rename(named)
        progress("step.prepare_video", None)
        return add_bgv_file(lib, category, named, move=True)


def remove_bgv(lib: Library, category: str, relpath: str) -> None:
    data = _load(lib)
    cat = _find(_extra(data)["bgvCategories"], category)
    listed = relpath in cat.get("BGV_LIST", [])
    cat["BGV_LIST"] = [v for v in cat.get("BGV_LIST", []) if v != relpath]
    write_manifest(lib.path, data)
    if listed:  # only files the manifest owns
        _trash(lib, relpath)


# --- idle-screen images -----------------------------------------------------
def bumpers(lib: Library) -> list[str]:
    return list(_extra(_load(lib))["bumperImages"])


def add_bumper(lib: Library, src: Path) -> str:
    src = Path(src)
    if src.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(t("err.image_ext", exts=", ".join(sorted(IMAGE_EXTS))))
    dest = unique_path(lib.path / "Bumpers", safe_name(src.name))
    shutil.copy2(src, dest)
    data = _load(lib)
    value = rel(lib.path, dest)
    _extra(data)["bumperImages"].append(value)
    write_manifest(lib.path, data)
    return value


def remove_bumper(lib: Library, relpath: str) -> None:
    data = _load(lib)
    listed = relpath in _extra(data)["bumperImages"]
    _extra(data)["bumperImages"] = [b for b in _extra(data)["bumperImages"] if b != relpath]
    write_manifest(lib.path, data)
    if listed:
        _trash(lib, relpath)


# --- boot video ---------------------------------------------------------------
def boot_video(lib: Library) -> str | None:
    return _extra(_load(lib)).get("bootVideo")


def set_boot_video(lib: Library, src: Path) -> str:
    old = boot_video(lib)
    folder = lib.path / "Boot"
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / ".boot.new.mp4"
    convert_video(Path(src), tmp)
    if old:
        _trash(lib, old)
    dest = unique_path(folder, "boot.mp4")
    tmp.rename(dest)
    data = _load(lib)
    value = rel(lib.path, dest)
    _extra(data)["bootVideo"] = value
    write_manifest(lib.path, data)
    return value


def clear_boot_video(lib: Library) -> None:
    old = boot_video(lib)
    data = _load(lib)
    _extra(data).pop("bootVideo", None)
    write_manifest(lib.path, data)
    if old:
        _trash(lib, old)


# --- score narrations ---------------------------------------------------------
def narrations(lib: Library) -> list[dict]:
    items = _extra(_load(lib)).get("scoreNarrations") or []
    return sorted((dict(n) for n in items), key=lambda n: n["min"])


def set_narration(lib: Library, lo: int, hi: int, src: Path) -> str:
    lo, hi = int(lo), int(hi)
    if not 0 <= lo <= hi <= 100:
        raise ValueError(t("err.narration_range"))
    current = narrations(lib)
    for n in current:
        same = n["min"] == lo and n["max"] == hi
        if not same and lo <= n["max"] and n["min"] <= hi:
            raise ValueError(t("err.narration_overlap", min=n["min"], max=n["max"]))
    src = Path(src)
    folder = lib.path / "Narrations"
    folder.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower() if src.suffix.lower() in SFX_EXTS else ".mp3"
    tmp = folder / f".{lo}-{hi}.new{ext}"
    if ext == src.suffix.lower():
        shutil.copy2(src, tmp)
    else:
        convert_audio(src, tmp)
    for n in current:
        if n["min"] == lo and n["max"] == hi:
            _trash(lib, n["file"])
    dest = unique_path(folder, f"{lo}-{hi}{ext}")
    tmp.rename(dest)
    data = _load(lib)
    items = [n for n in (_extra(data).get("scoreNarrations") or []) if not (n["min"] == lo and n["max"] == hi)]
    items.append({"min": lo, "max": hi, "file": rel(lib.path, dest)})
    _extra(data)["scoreNarrations"] = sorted(items, key=lambda n: n["min"])
    write_manifest(lib.path, data)
    return rel(lib.path, dest)


def remove_narration(lib: Library, lo: int, hi: int) -> None:
    data = _load(lib)
    items = _extra(data).get("scoreNarrations") or []
    gone = [n for n in items if n["min"] == lo and n["max"] == hi]
    _extra(data)["scoreNarrations"] = [n for n in items if n not in gone]
    if not _extra(data)["scoreNarrations"]:
        _extra(data).pop("scoreNarrations")
    write_manifest(lib.path, data)
    for n in gone:
        _trash(lib, n["file"])
