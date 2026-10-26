"""In-memory LRC editing: global shift, anchor-based retiming, vocal onset."""

from __future__ import annotations

import bisect
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


def shift(lines: list[Line], ms: int) -> list[Line]:
    return [Line(max(0, l.ms + ms), l.text) for l in lines]


def retime(lines: list[Line], anchors: dict[int, int], offset_ms: int = 0) -> list[tuple[int, Line]]:
    """Retime lines so line `i` lands on `anchors[i]` ms, then add `offset_ms`.

    One anchor shifts everything; more anchors give a piecewise-linear map
    (shift + stretch), extrapolated from the nearest segment at the ends.
    Returns (original index, new line) sorted by time.
    """
    # one point per distinct original time; a later anchor on the same time wins
    pts = dict(sorted((lines[i].ms, ms) for i, ms in anchors.items()))
    olds = sorted(pts)

    def remap(t: int) -> int:
        if not olds:
            return t
        if len(olds) == 1:
            return t + pts[olds[0]] - olds[0]
        k = bisect.bisect_right(olds, t)
        k = min(max(k, 1), len(olds) - 1)
        o0, o1 = olds[k - 1], olds[k]
        n0, n1 = pts[o0], pts[o1]
        return round(n0 + (t - o0) * (n1 - n0) / (o1 - o0))

    out = [(i, Line(max(0, remap(l.ms) + offset_ms), l.text)) for i, l in enumerate(lines)]
    return sorted(out, key=lambda p: p[1].ms)


def apply_anchors(lines: list[Line], anchors: dict[int, int]) -> list[Line]:
    return [l for _, l in retime(lines, anchors)]


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
