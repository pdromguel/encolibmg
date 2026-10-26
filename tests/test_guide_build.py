import subprocess

import numpy as np
import pytest

from encolibmg import checker, pipeline
from encolibmg.guide import build
from encolibmg.guide.midi import read_guide
from encolibmg.library import Library, kind_label

LRC = "[00:01.00] one two three\n[00:03.00] four five six\n"


def multiplex(path, seconds=6):
    # left: silence, right: 440 Hz "voice"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=440:r=44100:d={seconds}", "-filter_complex",
                    "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]", "-map", "[a]", str(path)], check=True)
    return path


def fake_f0(vocals, sr):
    n = int(len(vocals) / sr / 0.01)
    times = np.arange(n) * 0.01
    f0 = np.where((times > 1.0) & (times < 4.5), 440.0, 0.0)
    return times, f0, (f0 > 0).astype(float), np.where(f0 > 0, -10.0, -80.0)


def fake_aligner(segment, words):
    return [(0.3 + 0.5 * i, 0.9) for i in range(len(words))]


@pytest.fixture
def lib(tmp_path):
    lib = Library.create(tmp_path / "EncoreLibrary", "t")
    multiplex(lib.path / "A - B.multiplexed.mp3")
    (lib.path / "A - B.lrc").write_text(LRC, encoding="utf-8")
    return lib


def test_build_guide_writes_companion(lib):
    track = lib.scan()[0]
    new, stats = build.build_guide(lib, track, aligner=fake_aligner, f0_fn=fake_f0)
    assert new.has_guide and kind_label(new) == "Multiplex + LRC + guia"
    g = read_guide(lib.path / "A - B.guide.mid")
    assert [n.pitch for n in g.notes] == [69]
    assert [t for _, t in g.lyrics] == ["one ", "two ", "three ", "/four ", "five ", "six "]
    assert stats == {"aligned": 2, "fallback": 0, "notes": 1}
    assert not list(lib.path.glob(".*.tmp"))


def test_rebuild_backs_up_old_guide(lib, tmp_path):
    track = lib.scan()[0]
    build.build_guide(lib, track, aligner=fake_aligner, f0_fn=fake_f0)
    build.build_guide(lib, lib.scan()[0], aligner=fake_aligner, f0_fn=fake_f0)
    assert list((tmp_path / "appdata").rglob("A - B.guide.mid"))


def test_build_guide_requires_multiplex_and_lrc(tmp_path):
    lib = Library.create(tmp_path / "L", "t")
    (lib.path / "C - D.mp3").write_bytes(b"")
    (lib.path / "C - D.lrc").write_text(LRC)
    with pytest.raises(ValueError):
        build.build_guide(lib, lib.scan()[0], aligner=fake_aligner, f0_fn=fake_f0)


def test_checker_reports_and_fixes_missing_guide(lib, monkeypatch):
    issues = [i for i in checker.check(lib) if i.kind == "no_guide"]
    assert len(issues) == 1 and issues[0].fixable
    monkeypatch.setattr(build, "default_aligner", lambda: fake_aligner)
    real = build.detect_notes
    monkeypatch.setattr(build, "detect_notes", lambda v, sr, w, f0_fn=None: real(v, sr, w, f0_fn=fake_f0))
    assert "guia gerado" in checker.fix(lib, issues[0])
    assert not [i for i in checker.check(lib) if i.kind == "no_guide"]


def test_pipeline_guide_failure_keeps_track(lib, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("sem GPU")

    monkeypatch.setattr(pipeline, "build_guide", boom)
    track = lib.scan()[0]
    assert pipeline._with_guide(lib, track, True, lambda *a: None, None) is track
