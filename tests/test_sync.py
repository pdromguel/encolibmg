import numpy as np
import pytest

from encolibmg.lyrics.sync import Line, apply_anchors, format_lrc, parse_lrc, shift, vocal_onset

LINES = [Line(1000, "a"), Line(5000, "b"), Line(9000, "c"), Line(13000, "d")]


def test_parse_format_roundtrip():
    text = "[00:01.00] a\n[00:05.00] b\n"
    assert parse_lrc(text) == [Line(1000, "a"), Line(5000, "b")]
    assert format_lrc(parse_lrc(text)) == text


def test_parse_normalizes_input():
    assert parse_lrc("[ar:x]\n[00:02.00][00:01.00]oi") == [Line(1000, "oi"), Line(2000, "oi")]
    assert parse_lrc("") == []


def test_shift_never_negative():
    assert shift(LINES, -1500)[:2] == [Line(0, "a"), Line(3500, "b")]
    assert shift(LINES, 250)[0] == Line(1250, "a")


def test_no_anchor_is_identity():
    assert apply_anchors(LINES, {}) == LINES


def test_one_anchor_is_shift():
    assert apply_anchors(LINES, {1: 5600}) == shift(LINES, 600)


def test_two_anchors_linear_with_extrapolation():
    # line 1 (5000) -> 5500, line 2 (9000) -> 10300: slope 1.2, so 1000 -> 700 and 13000 -> 15100
    out = apply_anchors(LINES, {1: 5500, 2: 10300})
    assert [l.ms for l in out] == [700, 5500, 10300, 15100]


def test_three_anchors_piecewise():
    out = apply_anchors(LINES, {0: 1000, 1: 6000, 3: 14000})
    # between 5000->6000 and 13000->14000 the slope is 1: 9000 -> 10000
    assert [l.ms for l in out] == [1000, 6000, 10000, 14000]


def test_anchors_on_same_time_do_not_divide_by_zero():
    lines = [Line(1000, "a"), Line(1000, "a2"), Line(4000, "b")]
    out = apply_anchors(lines, {0: 1500, 1: 1500})
    assert [l.ms for l in out] == [1500, 1500, 4500]


def test_anchors_on_empty_or_single_line():
    assert apply_anchors([], {}) == []
    assert apply_anchors([Line(1000, "x")], {0: 3000}) == [Line(3000, "x")]


def test_vocal_onset_detects_start():
    sr = 22050
    silence = np.zeros(3 * sr)
    t = np.arange(2 * sr) / sr
    voice = 0.3 * np.sin(2 * np.pi * 300 * t)
    noise = 0.0005 * np.random.default_rng(0).standard_normal(5 * sr)
    x = np.concatenate([silence, voice]) + noise
    assert vocal_onset(x, sr) == pytest.approx(3.0, abs=0.06)


def test_vocal_onset_ignores_short_blips():
    sr = 22050
    x = np.zeros(6 * sr)
    x[sr: sr + int(0.1 * sr)] = 0.3  # 100 ms click at 1 s
    x[4 * sr:] = 0.3 * np.sin(2 * np.pi * 300 * np.arange(2 * sr) / sr)
    assert vocal_onset(x, sr) == pytest.approx(4.0, abs=0.06)


def test_vocal_onset_silence_is_none():
    assert vocal_onset(np.zeros(22050 * 2), 22050) is None


def test_vocal_onset_accepts_stereo():
    sr = 22050
    x = np.zeros((4 * sr, 2))
    x[2 * sr:, 1] = 0.3 * np.sin(2 * np.pi * 300 * np.arange(2 * sr) / sr)
    assert vocal_onset(x[:, 1], sr) == pytest.approx(2.0, abs=0.06)


def test_retime_keeps_original_index_and_offset():
    from encolibmg.lyrics.sync import retime

    lines = [Line(1000, "refrão"), Line(5000, "verso"), Line(9000, "refrão")]
    out = retime(lines, {2: 9500}, offset_ms=-200)
    assert out == [(0, Line(1300, "refrão")), (1, Line(5300, "verso")), (2, Line(9300, "refrão"))]
