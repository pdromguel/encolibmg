import numpy as np
import pytest

from encolibmg.guide.align import (ALIGN_SR, Word, align_line, align_lyrics, fallback_words,
                                    line_windows)
from encolibmg.lyrics.sync import Line

LINES = [Line(1000, "one two three"), Line(4000, "four five"), Line(8000, "(ah ah) ♪")]


def test_line_windows_last_line_capped():
    assert line_windows(LINES, 30.0) == [(1.0, 4.0), (4.0, 8.0), (8.0, 16.0)]
    assert line_windows(LINES, 10.0)[-1] == (8.0, 10.0)


def test_fallback_uses_note_onsets():
    assert fallback_words(3, 1.0, 4.0, [0.5, 1.0, 1.6, 2.2, 2.9, 5.0]) == [1.0, 1.6, 2.9]


def test_fallback_without_onsets_is_even_and_starts_on_line():
    t = fallback_words(4, 2.0, 6.0, [])
    assert t[0] == 2.0 and t == sorted(t) and t[-1] < 6.0
    assert fallback_words(0, 0, 1, []) == []


def fake_aligner(result):
    calls = []

    def aligner(segment, words):
        calls.append(words)
        return result(segment, words) if callable(result) else result
    aligner.calls = calls
    return aligner


def test_align_line_accepts_good_alignment():
    al = fake_aligner([(0.55, 0.9), (0.9, 0.8), (1.5, 0.7)])
    t = align_line(np.zeros(ALIGN_SR * 3, np.float32), 0.7, 1.0, 4.0, ["one", "two", "three"], al)
    # first word heard 0.25 s after the .lrc time: the aligner wins
    assert t == [pytest.approx(1.25), pytest.approx(1.6), pytest.approx(2.2)]


def test_align_line_far_first_word_keeps_lrc_time():
    al = fake_aligner([(0.0, 0.9), (1.5, 0.8)])  # 0.7 s before the .lrc time
    t = align_line(np.zeros(ALIGN_SR * 3, np.float32), 0.0, 0.7 + 0.0, 4.0, ["a", "b"], al)
    assert t[0] == 0.7


def test_align_line_rejects_low_score_out_of_order_or_late():
    seg = np.zeros(ALIGN_SR * 3, np.float32)
    assert align_line(seg, 0.7, 1.0, 4.0, ["a", "b"], fake_aligner([(0.3, 0.05), (0.9, 0.05)])) is None
    assert align_line(seg, 0.7, 1.0, 4.0, ["a", "b"], fake_aligner([(0.9, 0.9), (0.3, 0.9)])) is None
    assert align_line(seg, 0.7, 1.0, 4.0, ["a", "b"], fake_aligner([(3.6, 0.9), (4.0, 0.9)])) is None
    assert align_line(seg, 0.7, 1.0, 4.0, ["a", "b"], fake_aligner(None)) is None


def test_align_line_words_without_letters_follow_previous():
    al = fake_aligner([(0.3, 0.9), (1.0, 0.9)])
    t = align_line(np.zeros(ALIGN_SR * 3, np.float32), 0.7, 1.0, 4.0, ["hey", "", "you"], al)
    assert al.calls == [["hey", "you"]]
    assert t == [1.0, pytest.approx(1.05), pytest.approx(1.7)]


def test_align_lyrics_mixes_aligned_and_fallback():
    def result(segment, words):
        return None if words == ["four", "five"] else [(0.3 + 0.4 * i, 0.9) for i in range(len(words))]

    vocals = np.zeros(ALIGN_SR * 20, np.float32)
    words, stats = align_lyrics(vocals, ALIGN_SR, LINES, onsets=[4.0, 5.5, 6.0], aligner=fake_aligner(result))
    assert [[w.text for w in line] for line in words] == [["one", "two", "three"], ["four", "five"], ["(ah", "ah)", "♪"]]
    assert words[0][0] == Word(1.0, "one")
    assert [w.start for w in words[1]] == [4.0, 5.5]          # fallback on note onsets
    assert stats == {"aligned": 2, "fallback": 1}
    assert all(a.start < b.start for line in words for a, b in zip(line, line[1:]))
