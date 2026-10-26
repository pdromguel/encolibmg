import numpy as np
import pytest

from encolibmg.lyrics.sync import Line, format_lrc, parse_lrc, vocal_onset


def test_parse_format_roundtrip():
    text = "[00:01.00] a\n[00:05.00] b\n"
    assert parse_lrc(text) == [Line(1000, "a"), Line(5000, "b")]
    assert format_lrc(parse_lrc(text)) == text


def test_parse_normalizes_input():
    assert parse_lrc("[ar:x]\n[00:02.00][00:01.00]oi") == [Line(1000, "oi"), Line(2000, "oi")]
    assert parse_lrc("") == []


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
