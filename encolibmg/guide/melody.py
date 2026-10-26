"""Vocal stem → clean monophonic melody notes.

Encore's built-in guide averages raw frame pitches; here we track f0 with
CREPE and segment it with hysteresis so vibrato, short dropouts and octave
glitches do not become notes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_NOTE = 0.09        # s
MERGE_GAP = 0.08       # s, same pitch
GAP_SPLIT = 0.05       # s of silence that ends a note
CHANGE_ST = 0.8        # semitones away from the note's median…
CHANGE_LEN = 0.06      # …for this long starts a new note
OCTAVE_SHORT = 0.25    # s, only short notes get octave-corrected
FMIN, FMAX = 65.0, 1100.0
VOICED_PERIODICITY = 0.5
VOICED_RANGE_DB = 40.0


@dataclass(frozen=True)
class Note:
    start: float
    end: float
    pitch: int

    @property
    def length(self) -> float:
        return self.end - self.start


def _median_filter(x: np.ndarray, k: int = 5) -> np.ndarray:
    if len(x) < k:
        return x.copy()
    pad = k // 2
    padded = np.pad(x, pad, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, k)
    return np.median(windows, axis=1)


def f0_to_notes(times: np.ndarray, f0_hz: np.ndarray, voiced: np.ndarray) -> list[Note]:
    times, f0_hz, voiced = np.asarray(times), np.asarray(f0_hz, dtype=float), np.asarray(voiced, dtype=bool)
    if len(times) < 2:
        return []
    hop = float(times[1] - times[0])
    voiced = voiced & (f0_hz > 0)
    midi = np.zeros_like(f0_hz)
    midi[voiced] = 69 + 12 * np.log2(f0_hz[voiced] / 440.0)
    smooth = midi.copy()
    smooth[voiced] = _median_filter(midi[voiced])  # filter only along voiced frames

    gap_frames = max(1, round(GAP_SPLIT / hop))
    change_frames = max(1, round(CHANGE_LEN / hop))

    raw: list[tuple[float, float, float]] = []  # (start, end, median midi)
    cur: list[int] = []      # frame indexes of the open note
    pending: list[int] = []  # frames that disagree with the open note
    silent = 0

    def close(frames):
        if frames:
            raw.append((times[frames[0]], times[frames[-1]] + hop, float(np.median(smooth[frames]))))

    for i in range(len(times)):
        if not voiced[i]:
            silent += 1
            if silent >= gap_frames and cur:
                close(cur + pending)
                cur, pending = [], []
            continue
        silent = 0
        if not cur:
            cur = [i]
            continue
        ref = np.median(smooth[cur])
        if abs(smooth[i] - ref) > CHANGE_ST:
            pending.append(i)
            if len(pending) >= change_frames:
                close(cur)
                cur, pending = pending, []
        else:
            cur += pending + [i]  # a short excursion belongs to the note
            pending = []
    close(cur + pending)

    notes = [Note(round(s, 4), round(e, 4), int(round(m))) for s, e, m in raw if e - s >= MIN_NOTE]
    return merge_same(notes)


def merge_same(notes: list[Note]) -> list[Note]:
    out: list[Note] = []
    for n in notes:
        if out and out[-1].pitch == n.pitch and n.start - out[-1].end < MERGE_GAP:
            out[-1] = Note(out[-1].start, n.end, n.pitch)
        else:
            out.append(n)
    return out


def fix_octaves(notes: list[Note]) -> list[Note]:
    out = list(notes)
    for i, n in enumerate(out):
        if n.length >= OCTAVE_SHORT:
            continue
        neigh = [out[j].pitch for j in (i - 1, i + 1) if 0 <= j < len(out)]
        if not neigh:
            continue
        ref = sum(neigh) / len(neigh)
        best = min((n.pitch - 12, n.pitch, n.pitch + 12), key=lambda p: abs(p - ref))
        if best != n.pitch and abs(n.pitch - ref) - abs(best - ref) >= 6:
            out[i] = Note(n.start, n.end, best)
    return out


def clip_to_windows(notes: list[Note], windows: list[tuple[float, float]]) -> list[Note]:
    out = []
    for n in notes:
        for a, b in windows:
            s, e = max(n.start, a), min(n.end, b)
            if e - s >= MIN_NOTE:
                out.append(Note(round(s, 4), round(e, 4), n.pitch))
    return merge_same(sorted(out, key=lambda n: n.start))


def extract_f0(vocals: np.ndarray, sr: int, device: str | None = None):
    """CREPE f0 every 10 ms. Returns (times, f0_hz, periodicity, loudness_db)."""
    import torch
    import torchaudio.functional as AF
    import torchcrepe

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    x = torch.as_tensor(np.asarray(vocals, dtype=np.float32))
    if x.ndim == 2:
        x = x.mean(dim=1)
    audio = AF.resample(x, sr, 16000).unsqueeze(0)
    f0, per = torchcrepe.predict(audio, 16000, hop_length=160, fmin=FMIN, fmax=FMAX, model="full",
                                 batch_size=1024, device=device, return_periodicity=True)
    per = torchcrepe.filter.median(per, 3)
    f0 = f0[0].cpu().numpy()
    per = per[0].cpu().numpy()
    a = audio[0].numpy()
    n = len(f0)
    frames = np.pad(a, (0, max(0, n * 160 - len(a))))[: n * 160].reshape(n, 160)
    loud = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    return np.arange(n) * 0.01, f0, per, loud


def detect_notes(vocals: np.ndarray, sr: int, windows: list[tuple[float, float]] | None = None,
                 f0_fn=None) -> list[Note]:
    times, f0, per, loud = (f0_fn or extract_f0)(vocals, sr)
    voiced = (per >= VOICED_PERIODICITY) & (loud >= loud.max() - VOICED_RANGE_DB)
    notes = fix_octaves(f0_to_notes(times, f0, voiced))
    return clip_to_windows(notes, windows) if windows else notes
