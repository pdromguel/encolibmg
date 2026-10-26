import subprocess

import numpy as np
import pytest

from encolibmg.audio.player import SR, Player, decode


class FakeStream:
    latency = 0.05

    def __init__(self, callback, **kw):
        self.callback = callback
        self.started = self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        self.closed = True

    def pull(self, frames):
        out = np.zeros((frames, 2), dtype=np.float32)
        self.callback(out, frames, None, None)
        return out


def make_player():
    data = np.zeros((SR * 2, 2), dtype=np.float32)
    data[:, 0], data[:, 1] = 0.25, 0.75  # L instrumental, R vocals
    streams = []
    p = Player(data=data, stream_factory=lambda **kw: streams.append(FakeStream(**kw)) or streams[-1])
    return p, streams


def test_position_advances_and_pause_outputs_silence():
    p, streams = make_player()
    p.play()
    out = streams[0].pull(SR // 2)
    assert out[0].tolist() == [0.25, 0.75]
    assert p.position == pytest.approx(0.5 - 0.05)  # minus output latency
    p.pause()
    assert not streams[0].pull(100).any()
    assert p.position == pytest.approx(0.5)


def test_channel_selection():
    p, streams = make_player()
    p.channel = "left"
    p.play()
    assert streams[0].pull(4)[0].tolist() == [0.25, 0.25]
    p.channel = "right"
    assert streams[0].pull(4)[0].tolist() == [0.75, 0.75]


def test_seek_and_end_of_track():
    p, streams = make_player()
    p.seek(1.9)
    p.play()
    out = streams[0].pull(SR // 2)
    assert not p.playing
    assert not out[-1].any()  # padded with silence after the end
    p.play()  # replay restarts from the beginning
    assert p.pos == 0
    p.close()
    assert streams[0].closed


def test_decode_real_file(tmp_path):
    f = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1", str(f)], check=True)
    data = decode(f)
    assert data.shape[1] == 2
    assert len(data) / SR == pytest.approx(1.0, abs=0.1)
