import subprocess

import numpy as np
import pytest
import soundfile as sf

from encolibmg.audio import loudness
from encolibmg.audio.loudness import Loudness, gain_for, needs_fix
from encolibmg.audio.multiplex import make_multiplex


def tone(path, freq=440, amp=0.03, seconds=4, sr=44100):
    t = np.arange(int(sr * seconds)) / sr
    x = amp * np.sin(2 * np.pi * freq * t)
    sf.write(path, np.stack([x, x], 1), sr)
    return path


def to_mp3(src, dest):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-b:a", "320k", str(dest)], check=True)
    return dest


def test_gain_for_reaches_target():
    assert gain_for(Loudness(-30, -20)) == pytest.approx(14)


def test_gain_limited_by_true_peak():
    # +14 dB would push the peak to +2 dBTP; capped so peak lands at -1
    assert gain_for(Loudness(-30, -12)) == pytest.approx(11)


def test_silence_gets_no_gain():
    assert gain_for(Loudness(float("-inf"), float("-inf"))) == 0
    assert not needs_fix(Loudness(float("-inf"), float("-inf")))


def test_needs_fix_tolerance():
    assert not needs_fix(Loudness(-17.0, -3))
    assert needs_fix(Loudness(-18.0, -3))


def test_measure_and_normalize_mp3(tmp_path):
    mp3 = to_mp3(tone(tmp_path / "q.wav"), tmp_path / "q.mp3")
    before = loudness.measure(mp3)
    assert before.i < -25
    assert loudness.normalize_file(mp3)
    after = loudness.measure(mp3)
    assert after.i == pytest.approx(-16, abs=1)
    assert loudness.is_marked(mp3)


def test_marked_file_is_not_touched_again(tmp_path):
    mp3 = to_mp3(tone(tmp_path / "q.wav"), tmp_path / "q.mp3")
    loudness.normalize_file(mp3)
    mtime = mp3.stat().st_mtime_ns
    assert not loudness.normalize_file(mp3)
    assert mp3.stat().st_mtime_ns == mtime


def test_normalize_video_keeps_video_and_marks(tmp_path):
    wav = tone(tmp_path / "q.wav")
    mp4 = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=4",
                    "-i", str(wav), "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)
    assert loudness.normalize_file(mp4)
    assert loudness.is_marked(mp4)
    assert loudness.measure(mp4).i == pytest.approx(-16, abs=1)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                            "stream=codec_name", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True)
    assert probe.stdout.strip() == "h264"


def test_video_without_audio_is_skipped(tmp_path):
    mp4 = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
                    "-c:v", "libx264", str(mp4)], check=True)
    assert not loudness.normalize_file(mp4)


def test_multiplex_is_normalized_and_marked(tmp_path):
    inst = tone(tmp_path / "i.wav", 440, amp=0.02)
    voc = tone(tmp_path / "v.wav", 880, amp=0.02)
    out = make_multiplex(inst, voc, tmp_path / "X.multiplexed.mp3")
    assert loudness.measure(out).i == pytest.approx(-16, abs=1)
    assert loudness.is_marked(out)
    assert not (tmp_path / "X.multiplexed.mix.wav").exists()
