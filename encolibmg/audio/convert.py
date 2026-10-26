"""Format conversion to what Encore plays, plus small ffprobe helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from encolibmg.audio import ffmpeg
from encolibmg.audio.ffmpeg import NO_WINDOW

# formats Encore ignores that we know how to convert
UNSUPPORTED_AUDIO = {".flac", ".wma", ".aac", ".opus", ".aiff", ".aif", ".ape", ".mka", ".wv"}
UNSUPPORTED_VIDEO = {".mov", ".wmv", ".m4v", ".mpg", ".mpeg", ".flv", ".ts", ".vob", ".3gp"}


def _ffmpeg(args: list[str], name: str) -> None:
    ffmpeg.run(args, "err.ffmpeg_convert", detail_chars=1500, name=name)


def convert_audio(src: Path, dest_mp3: Path) -> Path:
    _ffmpeg(["-i", str(src), "-map", "0:a:0", "-map_metadata", "0", "-c:a", "libmp3lame", "-b:a", "320k",
             "-id3v2_version", "3", str(dest_mp3)], Path(src).name)
    return Path(dest_mp3)


def convert_video(src: Path, dest_mp4: Path) -> Path:
    _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
             str(dest_mp4)], Path(src).name)
    return Path(dest_mp4)


def duration(path: Path) -> float | None:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                           str(path)], capture_output=True, text=True, creationflags=NO_WINDOW)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None
