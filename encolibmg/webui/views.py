"""Engine objects → plain dicts for the UI (JSON over the pywebview bridge)."""

from __future__ import annotations

import re

from encolibmg.library import AUDIO_EXTS, Library, Track, kind_label


def badges(t: Track) -> list[str]:
    out = []
    if t.kind == "orphan":
        out.append("ORPHAN")
    if t.multiplexed:
        out.append("MP")
    elif t.exts & AUDIO_EXTS:
        out.append("AUDIO")
    if ".lrc" in t.exts:
        out.append("LRC")
    if ".cdg" in t.exts:
        out.append("CDG")
    if t.has_guide:
        out.append("GUIDE")
    if t.kind == "mtv":
        out.append("MTV")
    elif t.has_video:
        out.append("CLIP")
    if t.kind == "midi":
        out.append("MIDI")
    return out


def track_dict(t: Track) -> dict:
    files = []
    mtime = 0.0
    for f in t.files:
        try:
            st = f.stat()
            files.append({"name": f.name, "size": st.st_size})
            mtime = max(mtime, st.st_mtime)
        except OSError:
            files.append({"name": f.name, "size": 0})
    return {
        "base": t.base, "artist": t.artist, "title": t.title, "kind": t.kind, "label": kind_label(t),
        "badges": badges(t), "files": files, "has_guide": t.has_guide, "has_video": t.has_video,
        "multiplexed": t.multiplexed, "has_lrc": ".lrc" in t.exts, "mtime": mtime,
    }


def stats(tracks: list[Track]) -> dict:
    return {
        "tracks": len(tracks),
        "multiplex": sum(1 for t in tracks if t.multiplexed),
        "guides": sum(1 for t in tracks if t.has_guide),
        "mtv": sum(1 for t in tracks if t.kind == "mtv"),
        "orphans": sum(1 for t in tracks if t.kind == "orphan"),
        "no_guide": sum(1 for t in tracks if t.kind == "multiplex_lrc" and not t.has_guide),
    }


def lyrics_dict(c) -> dict:
    return {"id": c.id, "artist": c.artist, "title": c.title, "album": c.album, "duration": c.duration,
            "synced": bool(c.synced)}


def video_dict(v, target: float | None = None) -> dict:
    match = bool(target and v.duration and abs(v.duration - target) <= 2.0)
    return {"id": v.id, "title": v.title, "channel": v.channel, "duration": v.duration, "url": v.url,
            "thumb": f"https://i.ytimg.com/vi/{v.id}/mqdefault.jpg", "match": match}


def issue_dict(i, idx: int, lib: Library) -> dict:
    from encolibmg.checker import kind_label as issue_label

    try:
        rel = i.path.relative_to(lib.path).as_posix()
    except ValueError:
        rel = i.path.name
    return {"id": idx, "kind": i.kind, "label": issue_label(i.kind), "file": rel,
            "message": i.message, "fixable": i.fixable, "base": i.track.base if i.track else None}


def import_dict(it, idx: int) -> dict:
    from encolibmg.importer import kind_label as import_label, status_text

    return {"id": idx, "artist": it.artist, "title": it.title, "kind": it.kind,
            "kind_label": import_label(it.kind), "source": it.main.name,
            "companions": [c.name for c in it.companions], "status": it.status,
            "status_text": status_text(it.status), "selected": it.selected, "base": it.base}


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
