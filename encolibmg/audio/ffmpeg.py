"""Running ffmpeg/ffprobe: one place for the hidden console window and the error message."""

from __future__ import annotations

import subprocess

from encolibmg.core.i18n import t

# without this flag every ffmpeg/ffprobe/Demucs call flashes a console window over the app
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(args: list[str], err_key: str, detail_chars: int = 2000, **params) -> subprocess.CompletedProcess:
    """`ffmpeg -v error -y <args>`; on failure raises RuntimeError(t(err_key, detail=<stderr tail>, **params))."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(t(err_key, detail=proc.stderr[-detail_chars:], **params))
    return proc
