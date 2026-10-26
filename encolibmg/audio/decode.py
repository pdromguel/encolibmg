"""Decode any file ffmpeg can read into a float32 array."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from encolibmg.audio.ffmpeg import NO_WINDOW

SR = 44100


def decode(path: Path, sr: int = SR) -> np.ndarray:
    """Any file ffmpeg reads → float32 array (frames, 2)."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f32le",
                           "-ac", "2", "-ar", str(sr), "-"], capture_output=True, creationflags=NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-800:])
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2)


def decode_mono(path: Path, channel: int = -1, sr: int = 8000) -> np.ndarray:
    """One channel (0 = left, 1 = right, -1 = both mixed) as float32 mono, resampled by ffmpeg.

    For waveforms and onsets: at 8 kHz mono a 4-minute song is ~7 MB instead of ~85 MB at 44.1 kHz stereo.
    """
    pick = ["-af", f"pan=mono|c0=c{channel}"] if channel >= 0 else ["-ac", "1"]
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", *pick, "-f", "f32le",
                           "-ar", str(sr), "-"], capture_output=True, creationflags=NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-800:])
    return np.frombuffer(proc.stdout, dtype=np.float32)
