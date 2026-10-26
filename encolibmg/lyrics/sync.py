"""In-memory LRC: parse and format, and where the singing starts (the Sync screen does the retiming in JS)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from encolibmg.lyrics.normalize import normalize_lrc

ONSET_FRAME = 0.05     # s
ONSET_RANGE_DB = 30.0  # below the loudest frame
ONSET_MIN_LEN = 0.30   # s of continuous voice


@dataclass(frozen=True)
class Line:
    ms: int
    text: str


def parse_lrc(text: str) -> list[Line]:
    out = []
    for row in normalize_lrc(text).splitlines():
        stamp, _, words = row.partition("] ")
        mm, ss = stamp[1:].split(":")
        out.append(Line(round((int(mm) * 60 + float(ss)) * 1000), words))
    return out


def format_lrc(lines: list[Line]) -> str:
    raw = "".join(f"[{l.ms // 60000:02d}:{l.ms % 60000 / 1000:05.2f}]{l.text}\n" for l in lines)
    return normalize_lrc(raw)



def vocal_onset(samples: np.ndarray, sr: int) -> float | None:
    """Seconds where sustained singing starts in a vocal stem, or None."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    hop = max(1, int(sr * ONSET_FRAME))
    n = len(x) // hop
    if n == 0:
        return None
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    if rms.max() < 1e-4:
        return None
    db = 20 * np.log10(np.maximum(rms, 1e-12))
    loud = db > db.max() - ONSET_RANGE_DB
    need = max(1, round(ONSET_MIN_LEN / ONSET_FRAME))
    run = 0
    for i, on in enumerate(loud):
        run = run + 1 if on else 0
        if run >= need:
            return (i - need + 1) * hop / sr
    return None
