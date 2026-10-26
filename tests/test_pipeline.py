from threading import Event

import pytest

from encolibmg import pipeline
from encolibmg.core.errors import AlreadyExists, Cancelled, NoAudioMatch
from encolibmg.library import Library
from encolibmg.lyrics.lrclib import LyricsCandidate
from encolibmg.youtube import VideoCandidate

LYR = LyricsCandidate(1, "Adele", "Hello", "25", 295.0, "[00:01.0]Hello\n[ar:x]\n", None)
VID = VideoCandidate("abc", "Adele - Hello", "Adele", 296.0, "https://www.youtube.com/watch?v=abc")


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


@pytest.fixture
def fakes(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline.youtube, "search", lambda q, n=10: calls.append(("search", q)) or [VID])

    def dl_audio(url, dest, cancel=None, cb=None):
        calls.append(("download", url))
        (dest / "source.wav").write_bytes(b"wav")
        return dest / "source.wav"

    def sep(wav, work, cancel=None, cb=None):
        work.mkdir()
        (work / "i.wav").write_bytes(b"i")
        (work / "v.wav").write_bytes(b"v")
        return work / "i.wav", work / "v.wav"

    def mux(i, v, dest):
        dest.write_bytes(b"mp3")
        return dest

    def dl_video(url, dest, cancel=None, cb=None, video_only=False):
        calls.append(("video", video_only))
        (dest / "video.mp4").write_bytes(b"mp4")
        return dest / "video.mp4"

    monkeypatch.setattr(pipeline.youtube, "download_audio", dl_audio)
    monkeypatch.setattr(pipeline.youtube, "download_video", dl_video)
    monkeypatch.setattr(pipeline, "separate", sep)
    monkeypatch.setattr(pipeline, "make_multiplex", mux)
    monkeypatch.setattr(pipeline, "write_tags", lambda *a: calls.append(("tags", a[1:])))
    monkeypatch.setattr(pipeline, "build_guide",
                        lambda lib, track, p=None, c=None: (calls.append(("guide", track.base)) or (track, {})))
    return calls


def leftovers(lib):
    return [p.name for p in lib.path.iterdir() if p.name != "manifest.json"]


def test_add_song_writes_pair(lib, fakes):
    steps = []
    track = pipeline.add_song(lib, LYR, on_progress=lambda s, f: steps.append(s))
    assert track.kind == "multiplex_lrc"
    assert sorted(leftovers(lib)) == ["Adele - Hello.lrc", "Adele - Hello.multiplexed.mp3"]
    assert (lib.path / "Adele - Hello.lrc").read_text(encoding="utf-8") == "[00:01.00] Hello\n"
    assert ("tags", ("Adele", "Hello")) in fakes
    assert steps[0] == "step.search_audio" and steps[-1] == "step.save"  # keys; JobManager translates


def test_add_song_existing_raises_before_download(lib, fakes):
    (lib.path / "adele - hello.mp4").write_bytes(b"")
    with pytest.raises(AlreadyExists):
        pipeline.add_song(lib, LYR)
    assert fakes == []


def test_add_song_no_match(lib, fakes, monkeypatch):
    far = VideoCandidate("x", "Hello", "c", 400.0, "u")
    monkeypatch.setattr(pipeline.youtube, "search", lambda q, n=10: [far])
    with pytest.raises(NoAudioMatch):
        pipeline.add_song(lib, LYR)
    assert leftovers(lib) == []


def test_cancel_cleans_temp(lib, fakes, monkeypatch):
    cancel = Event()

    def sep(wav, work, c=None, cb=None):
        cancel.set()
        raise Cancelled()

    monkeypatch.setattr(pipeline, "separate", sep)
    with pytest.raises(Cancelled):
        pipeline.add_song(lib, LYR, cancel=cancel)
    assert leftovers(lib) == []


def test_add_mtv_writes_mp4(lib, fakes):
    track = pipeline.add_mtv(lib, "Adele", "Hello", VID)
    assert track.kind == "mtv"
    assert leftovers(lib) == ["Adele - Hello.mp4"]


def sine(path, seconds=1):
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=d={seconds}", str(path)], check=True)
    return path


def test_track_from_local(lib, fakes, tmp_path):
    src = sine(tmp_path / "minha.flac")
    track = pipeline.track_from_local(lib, src, "Adele", "Hello", "[00:01.0]Hello")
    assert track.kind == "multiplex_lrc"
    assert sorted(leftovers(lib)) == ["Adele - Hello.lrc", "Adele - Hello.multiplexed.mp3"]
    assert src.exists()  # source is never touched
    assert not any(c[0] == "download" for c in fakes)


def test_convert_to_multiplex(lib, fakes, monkeypatch):
    trashed = []
    monkeypatch.setattr(pipeline, "send2trash", trashed.append)
    sine(lib.path / "Adele - Hello.mp3")
    (lib.path / "Adele - Hello.lrc").write_text("[00:01.00] Hello\n", encoding="utf-8")
    track = lib.scan()[0]
    new = pipeline.convert_to_multiplex(lib, track)
    assert new.kind == "multiplex_lrc"
    assert trashed == [str(lib.path / "Adele - Hello.mp3")]


def test_convert_rejects_multiplex(lib, fakes):
    (lib.path / "A - B.multiplexed.mp3").write_bytes(b"")
    (lib.path / "A - B.lrc").write_bytes(b"")
    with pytest.raises(ValueError):
        pipeline.convert_to_multiplex(lib, lib.scan()[0])


def test_add_clip_video_only(lib, fakes):
    (lib.path / "Adele - Hello.multiplexed.mp3").write_bytes(b"")
    (lib.path / "Adele - Hello.lrc").write_bytes(b"")
    track = pipeline.add_clip(lib, lib.scan()[0], VID)
    assert ("video", True) in fakes
    assert track.has_video and track.kind == "multiplex_lrc"


def test_add_clip_refuses_when_video_exists(lib, fakes):
    for n in ("A - B.multiplexed.mp3", "A - B.lrc", "A - B.mp4"):
        (lib.path / n).write_bytes(b"")
    with pytest.raises(AlreadyExists):
        pipeline.add_clip(lib, lib.scan()[0], VID)


def test_add_song_generates_guide_by_default(lib, fakes):
    pipeline.add_song(lib, LYR)
    assert ("guide", "Adele - Hello") in fakes


def test_add_song_without_guide(lib, fakes):
    pipeline.add_song(lib, LYR, make_guide=False)
    assert not any(c[0] == "guide" for c in fakes)


def test_prepare_then_finish(lib, fakes, tmp_path):
    work = tmp_path / "queue-work"
    work.mkdir()
    prep = pipeline.prepare_song(lib, LYR, work)
    assert prep.base == "Adele - Hello" and prep.wav.parent == work and prep.lrc_text == "[00:01.00] Hello\n"
    assert leftovers(lib) == []  # nothing in the library until the GPU part
    track = pipeline.finish_song(lib, prep)
    assert track.kind == "multiplex_lrc"
    assert sorted(leftovers(lib)) == ["Adele - Hello.lrc", "Adele - Hello.multiplexed.mp3"]


def test_finish_refuses_a_song_added_meanwhile(lib, fakes, tmp_path):
    prep = pipeline.prepare_song(lib, LYR, tmp_path)
    (lib.path / "Adele - Hello.mp4").write_bytes(b"")  # added by hand while waiting in the queue
    with pytest.raises(AlreadyExists):
        pipeline.finish_song(lib, prep)
