import subprocess

import numpy as np
import pytest
import soundfile as sf

from encolibmg.audio.multiplex import make_multiplex
from encolibmg.tags import write_tags


def tone(path, freq, seconds=2, stereo=True, sr=44100):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.3 * np.sin(2 * np.pi * freq * t)
    sf.write(path, np.stack([x, x], 1) if stereo else x, sr)
    return path


def dominant_freq(x, sr):
    spec = np.abs(np.fft.rfft(x))
    return np.fft.rfftfreq(len(x), 1 / sr)[spec.argmax()]


def decode(mp3, wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), str(wav)], check=True)
    return sf.read(wav)


def test_multiplex_left_instrumental_right_vocals(tmp_path):
    inst = tone(tmp_path / "no_vocals.wav", 440)
    voc = tone(tmp_path / "vocals.wav", 880)
    out = make_multiplex(inst, voc, tmp_path / "X.multiplexed.mp3")
    data, sr = decode(out, tmp_path / "check.wav")
    assert data.shape[1] == 2
    assert dominant_freq(data[:, 0], sr) == pytest.approx(440, abs=5)
    assert dominant_freq(data[:, 1], sr) == pytest.approx(880, abs=5)


def test_write_tags_roundtrip(tmp_path):
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3

    src = tone(tmp_path / "a.wav", 440, seconds=1)
    mp3 = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), str(mp3)], check=True)
    write_tags(mp3, "Tom Jobim", "Águas de Março")
    tags = EasyID3(mp3)
    assert tags["artist"] == ["Tom Jobim"]
    assert tags["title"] == ["Águas de Março"]
    assert ID3(mp3).version[:2] == (2, 3)


def test_overall_progress_merges_bars():
    from encolibmg.audio.separate import _Overall

    o = _Overall(bars=4)
    assert o.feed(50) == pytest.approx(0.125)
    assert o.feed(100) == pytest.approx(0.25)
    assert o.feed(0) == pytest.approx(0.25)  # second bar starts
    assert o.feed(50) == pytest.approx(0.375)
    for _ in range(3):
        o.feed(0), o.feed(100)
    assert o.feed(100) == 0.99  # never shows 100% before files are written


@pytest.mark.slow
def test_separate_real_demucs(tmp_path):
    from encolibmg.audio.separate import separate

    src = tone(tmp_path / "source.wav", 440, seconds=5)
    seen = []
    inst, voc = separate(src, tmp_path / "work", on_progress=seen.append)
    assert inst.name == "no_vocals.wav" and inst.exists()
    assert voc.name == "vocals.wav" and voc.exists()


def test_decode_real_file(tmp_path):
    from encolibmg.audio.decode import SR, decode

    f = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1", str(f)], check=True)
    data = decode(f)
    assert data.shape[1] == 2
    assert len(data) / SR == pytest.approx(1.0, abs=0.1)
