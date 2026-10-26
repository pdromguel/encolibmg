"""Start time of every word, line by line.

Each .lrc line is cut from the vocal stem and force-aligned with MMS_FA
(torchaudio, multilingual). A line whose alignment looks wrong falls back to
spreading its words over the melody's note onsets. The first word keeps the
line's .lrc time unless the aligner heard it within FIRST_WORD_SNAP of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from encolibmg.guide.romanize import words_for_alignment
from encolibmg.lyrics.sync import Line

ALIGN_SR = 16000
PAD = 0.3            # s of audio around each line
LAST_LINE_MAX = 8.0  # s, window of the last line
MIN_SCORE = 0.2      # mean aligner confidence to accept a line
MIN_STEP = 0.05      # s between consecutive words
FIRST_WORD_SNAP = 0.5  # s: aligned first word may move this far from the .lrc time

# aligner(segment_16k, roman_words) -> [(start_seconds_in_segment, score)] or None
Aligner = Callable[[np.ndarray, list[str]], "list[tuple[float, float]] | None"]


@dataclass(frozen=True)
class Word:
    start: float
    text: str


def line_windows(lines: list[Line], audio_end: float) -> list[tuple[float, float]]:
    out = []
    for i, l in enumerate(lines):
        start = l.ms / 1000
        end = lines[i + 1].ms / 1000 if i + 1 < len(lines) else min(start + LAST_LINE_MAX, audio_end)
        out.append((start, max(end, start + 0.5)))
    return out


def _increasing(times: list[float], start: float) -> list[float]:
    out = [start]
    for t in times[1:]:
        out.append(max(t, out[-1] + MIN_STEP))
    return out


def fallback_words(n: int, start: float, end: float, onsets: list[float]) -> list[float]:
    """First word at `start`; the rest on note onsets inside the line, else evenly spaced."""
    if n <= 0:
        return []
    cands = sorted(o for o in onsets if start + MIN_STEP <= o < end)
    if len(cands) >= n - 1 and n > 1:
        idx = np.linspace(0, len(cands) - 1, n - 1).round().astype(int)
        return _increasing([start] + [cands[i] for i in idx], start)
    span = (end - start) * 0.85
    return _increasing([start + span * k / n for k in range(n)], start)


def align_line(segment: np.ndarray, seg_start: float, line_start: float, line_end: float,
               romans: list[str], aligner: Aligner) -> list[float] | None:
    """Absolute start per word, or None when the alignment can't be trusted."""
    idx = [i for i, r in enumerate(romans) if r]
    if not idx:
        return None
    try:
        res = aligner(segment, [romans[i] for i in idx])
    except Exception:
        return None
    if not res or len(res) != len(idx):
        return None
    starts = [seg_start + s for s, _ in res]
    score = float(np.mean([sc for _, sc in res]))
    if score < MIN_SCORE or any(b < a for a, b in zip(starts, starts[1:])):
        return None
    if starts[0] > line_end or starts[-1] > line_end + PAD:
        return None
    # words without letters (♪, numbers) sit right after the previous word
    times, k = [], 0
    for i in range(len(romans)):
        if k < len(idx) and idx[k] == i:
            times.append(starts[k])
            k += 1
        else:
            times.append(times[-1] + MIN_STEP if times else line_start)
    # the aligner hears the real onset; trust it near the .lrc time, else keep the .lrc time
    first = times[0] if abs(times[0] - line_start) <= FIRST_WORD_SNAP else line_start
    return _increasing([first] + times[1:], first)


def align_lyrics(vocals: np.ndarray, sr: int, lines: list[Line], onsets: list[float],
                 aligner: Aligner | None = None, on_progress=None) -> tuple[list[list[Word]], dict]:
    """Returns words per line and stats {'aligned': n, 'fallback': n}."""
    x = np.asarray(vocals, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    audio = _resample(x, sr)
    aligner = aligner or MMSAligner()
    windows = line_windows(lines, len(audio) / ALIGN_SR)
    out, stats = [], {"aligned": 0, "fallback": 0}
    for n, (line, (start, end)) in enumerate(zip(lines, windows)):
        if on_progress:
            on_progress(n / max(1, len(lines)))
        pairs = words_for_alignment(line.text)
        if not pairs:
            out.append([])
            continue
        a, b = max(0.0, start - PAD), end + PAD
        seg = audio[int(a * ALIGN_SR): int(b * ALIGN_SR)]
        times = align_line(seg, a, start, end, [r for _, r in pairs], aligner)
        if times is None:
            times = fallback_words(len(pairs), start, end, onsets)
            stats["fallback"] += 1
        else:
            stats["aligned"] += 1
        out.append([Word(round(t, 3), d) for t, (d, _) in zip(times, pairs)])
    return out, stats


def _resample(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == ALIGN_SR:
        return x
    import torch
    import torchaudio.functional as AF

    return AF.resample(torch.from_numpy(np.array(x, dtype=np.float32)), sr, ALIGN_SR).numpy()


class MMSAligner:
    """torchaudio MMS_FA forced aligner (model ~1.2 GB, downloaded on first use)."""

    def __init__(self, device: str | None = None):
        import torch
        from torchaudio.pipelines import MMS_FA

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = MMS_FA.get_model().to(self.device).eval()
        self.tokenizer = MMS_FA.get_tokenizer()
        self.aligner = MMS_FA.get_aligner()

    def __call__(self, segment: np.ndarray, words: list[str]):
        if len(segment) < ALIGN_SR * 0.2:
            return None
        torch = self.torch
        with torch.inference_mode():
            wave = torch.from_numpy(segment).unsqueeze(0).to(self.device)
            emission, _ = self.model(wave)
            spans = self.aligner(emission[0], self.tokenizer(words))
        ratio = len(segment) / emission.shape[1] / ALIGN_SR
        out = []
        for word_spans in spans:
            if not word_spans:
                return None
            score = sum(s.score * (s.end - s.start) for s in word_spans) / sum(s.end - s.start for s in word_spans)
            out.append((word_spans[0].start * ratio, float(score)))
        return out
