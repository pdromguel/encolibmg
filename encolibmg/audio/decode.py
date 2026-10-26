"""Decode any file ffmpeg can read into a float32 array."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

SR = 44100
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def decode(path: Path, sr: int = SR) -> np.ndarray:
    """Any file ffmpeg reads → float32 array (frames, 2)."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f32le",
                           "-ac", "2", "-ar", str(sr), "-"], capture_output=True, creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-800:])
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2)
