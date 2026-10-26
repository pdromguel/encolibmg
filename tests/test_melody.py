import numpy as np
import pytest

from encolibmg.guide.melody import Note, clip_to_windows, f0_to_notes, fix_octaves

HOP = 0.01


def hz(midi):
    return 440.0 * 2 ** ((np.asarray(midi, dtype=float) - 69) / 12)


def contour(segments):
    """segments: list of (seconds, midi or None). Returns times, f0, voiced."""
    midis = []
    for dur, m in segments:
        midis += [m] * round(dur / HOP)
    voiced = np.array([m is not None for m in midis])
    f0 = np.array([hz(m) if m is not None else 0.0 for m in midis])
    times = np.arange(len(midis)) * HOP
    return times, f0, voiced


def summary(notes):
    return [(round(n.start, 2), round(n.end, 2), n.pitch) for n in notes]


def test_staircase_with_vibrato_is_three_notes():
    times, f0, voiced = contour([(0.5, None), (0.6, 60), (0.6, 62), (0.6, 64), (0.5, None)])
    vib = 0.3 * np.sin(2 * np.pi * 5.5 * times)  # ±0.3 semitone vibrato
    f0 = np.where(voiced, f0 * 2 ** (vib / 12), 0)
    assert [n.pitch for n in f0_to_notes(times, f0, voiced)] == [60, 62, 64]
    notes = f0_to_notes(times, f0, voiced)
    assert notes[0].start == pytest.approx(0.5, abs=0.02)
    assert notes[2].end == pytest.approx(2.3, abs=0.02)


def test_short_dropout_does_not_split_note():
    times, f0, voiced = contour([(0.5, 67), (0.04, None), (0.5, 67)])
    assert summary(f0_to_notes(times, f0, voiced)) == [(0.0, 1.04, 67)]


def test_real_gap_splits_note():
    times, f0, voiced = contour([(0.5, 67), (0.1, None), (0.5, 67)])
    assert [n.pitch for n in f0_to_notes(times, f0, voiced)] == [67, 67]


def test_short_glitch_inside_note_is_ignored():
    # 30 ms jump (< 60 ms) does not create a new note
    times, f0, voiced = contour([(0.4, 60), (0.03, 65), (0.4, 60)])
    assert [n.pitch for n in f0_to_notes(times, f0, voiced)] == [60]


def test_tiny_notes_dropped():
    times, f0, voiced = contour([(0.06, 70), (0.3, None), (0.4, 72)])
    assert [n.pitch for n in f0_to_notes(times, f0, voiced)] == [72]


def test_same_pitch_after_change_back_merges_when_gap_small():
    notes = [Note(0.0, 0.5, 60), Note(0.55, 1.0, 60), Note(1.3, 1.6, 60)]
    from encolibmg.guide.melody import merge_same

    assert summary(merge_same(notes)) == [(0.0, 1.0, 60), (1.3, 1.6, 60)]


def test_fix_octave_errors():
    notes = [Note(0, 0.5, 60), Note(0.5, 0.7, 74), Note(0.7, 1.2, 61)]
    assert [n.pitch for n in fix_octaves(notes)] == [60, 62, 61]
    # long notes are trusted even if far away
    notes = [Note(0, 0.5, 60), Note(0.5, 1.5, 74), Note(1.5, 2.0, 61)]
    assert [n.pitch for n in fix_octaves(notes)] == [60, 74, 61]


def test_clip_to_windows():
    notes = [Note(0.0, 1.0, 60), Note(2.0, 3.0, 62), Note(4.9, 5.5, 64), Note(9.0, 9.5, 65)]
    # the 4.9 s note keeps only 50 ms inside the window -> too short, dropped
    assert summary(clip_to_windows(notes, [(1.5, 4.95)])) == [(2.0, 3.0, 62)]
    # trimmed but long enough -> kept with the window edge as its end
    assert summary(clip_to_windows(notes, [(0.5, 5.2)])) == [(0.5, 1.0, 60), (2.0, 3.0, 62), (4.9, 5.2, 64)]


@pytest.mark.slow
def test_extract_f0_real_crepe():
    from encolibmg.guide.melody import detect_notes, extract_f0

    sr = 22050
    t = np.arange(int(sr * 2)) / sr
    x = np.concatenate([np.zeros(sr // 2), 0.3 * np.sin(2 * np.pi * 220 * t), np.zeros(sr // 2)])
    times, f0, per, loud = extract_f0(x, sr)
    mid = (times > 1.0) & (times < 2.0)
    assert np.median(f0[mid]) == pytest.approx(220, rel=0.02)
    notes = detect_notes(x, sr)
    assert [n.pitch for n in notes] == [57]  # A3
    assert notes[0].start == pytest.approx(0.5, abs=0.05)
