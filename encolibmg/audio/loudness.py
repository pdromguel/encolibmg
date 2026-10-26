"""EBU R128 loudness: measure with ffmpeg, apply one fixed gain (no compression).

Files are marked after processing so they are never re-encoded twice:
mp3 → ID3 TXXX frame; other containers → `comment` metadata.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mutagen.id3 import ID3, TXXX, ID3NoHeaderError
from encolibmg.i18n import t

TARGET = -16.0
MAX_TP = -1.0
TOLERANCE = 1.5
MARK_KEY = "EncoreLM-Loudness"
MARK = f"{MARK_KEY}={TARGET:g}"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# container -> audio codec args when re-encoding
_AUDIO_CODEC = {
    ".mp3": ["-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3"],
    ".m4a": ["-c:a", "aac", "-b:a", "256k"],
    ".ogg": ["-c:a", "libvorbis", "-q:a", "6"],
    ".wav": ["-c:a", "pcm_s16le"],
    ".mp4": ["-c:a", "aac", "-b:a", "256k"],
    ".mkv": ["-c:a", "aac", "-b:a", "256k"],
    ".webm": ["-c:a", "libopus", "-b:a", "192k"],
    ".avi": ["-c:a", "libmp3lame", "-b:a", "320k"],
}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi"}


@dataclass
class Loudness:
    i: float   # integrated LUFS
    tp: float  # true peak dBTP


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=_NO_WINDOW)


def measure(path: Path) -> Loudness:
    proc = _run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-map", "0:a:0",
                 "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"^\s*I:\s*(-?[\d.]+|-inf) LUFS", proc.stderr, re.M)
    tp = re.findall(r"^\s*Peak:\s*(-?[\d.]+|-inf) dBFS", proc.stderr, re.M)
    if proc.returncode != 0 or not i or not tp:
        raise RuntimeError(t("err.measure_loudness", name=Path(path).name, detail=proc.stderr[-800:]))
    return Loudness(float(i[-1]), float(tp[-1]))


def gain_for(l: Loudness, target: float = TARGET, max_tp: float = MAX_TP) -> float:
    if l.i == float("-inf"):
        return 0.0
    g = target - l.i
    return min(g, max_tp - l.tp)


def needs_fix(l: Loudness, target: float = TARGET, tol: float = TOLERANCE) -> bool:
    return l.i != float("-inf") and abs(target - l.i) > tol


def is_marked(path: Path) -> bool:
    path = Path(path)
    if path.suffix.lower() == ".mp3":
        try:
            return bool(ID3(path).getall(f"TXXX:{MARK_KEY}"))
        except ID3NoHeaderError:
            return False
    proc = _run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "json", str(path)])
    try:
        return MARK_KEY in json.loads(proc.stdout)["format"]["tags"]["comment"]
    except (ValueError, KeyError):
        return False


def mark_mp3(path: Path) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.setall(f"TXXX:{MARK_KEY}", [TXXX(encoding=3, desc=MARK_KEY, text=f"{TARGET:g}")])
    tags.save(path, v2_version=3)


def has_audio(path: Path) -> bool:
    proc = _run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                 "-of", "csv=p=0", str(path)])
    return bool(proc.stdout.strip())


def normalize_file(path: Path) -> bool:
    """Re-encode the audio with the gain that reaches TARGET. Returns True if the file changed."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in _AUDIO_CODEC or is_marked(path) or not has_audio(path):
        return False
    l = measure(path)
    if not needs_fix(l):
        if ext == ".mp3":
            mark_mp3(path)
        return False
    g = gain_for(l)
    tmp = path.with_name(f".{path.stem}.loudnorm{ext}")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-map", "0", "-map_metadata", "0"]
    if ext in VIDEO_EXTS:
        cmd += ["-c:v", "copy", "-c:s", "copy"]
    cmd += ["-af", f"volume={g:.2f}dB", *_AUDIO_CODEC[ext]]
    if ext != ".mp3":
        cmd += ["-metadata", f"comment={MARK}"]
    proc = _run(cmd + [str(tmp)])
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(t("err.ffmpeg_normalize", name=path.name, detail=proc.stderr[-800:]))
    os.replace(tmp, path)
    if ext == ".mp3":
        mark_mp3(path)
    return True
