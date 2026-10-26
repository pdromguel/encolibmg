"""Tiny in-memory audio player for the sync window (decode with ffmpeg, play with sounddevice)."""

from __future__ import annotations

import subprocess
import threading
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


class Player:
    """`channel`: 'both', 'left' (Multiplex instrumental) or 'right' (Multiplex vocals)."""

    def __init__(self, path: Path | None = None, data: np.ndarray | None = None, stream_factory=None):
        self.data = data if data is not None else decode(path)
        self.sr = SR
        self.pos = 0
        self.playing = False
        self.channel = "both"
        self._lock = threading.Lock()
        self._stream = None
        self._factory = stream_factory

    @property
    def duration(self) -> float:
        return len(self.data) / self.sr

    @property
    def position(self) -> float:
        """What the listener hears now: frames sent minus output latency."""
        latency = getattr(self._stream, "latency", 0.0) or 0.0
        if isinstance(latency, (tuple, list)):
            latency = latency[-1]
        return max(0.0, self.pos / self.sr - (latency if self.playing else 0.0))

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if not self.playing:
                outdata.fill(0)
                return
            chunk = self.data[self.pos:self.pos + frames]
            self.pos += len(chunk)
            if len(chunk) < frames:
                self.playing = False
        if self.channel == "left":
            chunk = np.repeat(chunk[:, :1], 2, axis=1)
        elif self.channel == "right":
            chunk = np.repeat(chunk[:, 1:], 2, axis=1)
        outdata[:len(chunk)] = chunk
        outdata[len(chunk):] = 0

    def _ensure_stream(self):
        if self._stream is None:
            if self._factory is None:
                import sounddevice as sd

                self._factory = sd.OutputStream
            self._stream = self._factory(samplerate=self.sr, channels=2, dtype="float32",
                                         callback=self._callback)
            self._stream.start()

    def play(self):
        self._ensure_stream()
        with self._lock:
            if self.pos >= len(self.data):
                self.pos = 0
            self.playing = True

    def pause(self):
        with self._lock:
            self.playing = False

    def seek(self, seconds: float):
        with self._lock:
            self.pos = int(min(max(0.0, seconds), self.duration) * self.sr)

    def close(self):
        self.pause()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
