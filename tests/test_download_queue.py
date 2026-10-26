import threading
import time
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from encolibmg import pipeline
from encolibmg.core.errors import AlreadyExists, Cancelled, NoAudioMatch
from encolibmg.download_queue import DownloadQueue
from encolibmg.library import Library
from encolibmg.lyrics.lrclib import LyricsCandidate


def cand(artist, title):
    return LyricsCandidate(1, artist, title, "", 200.0, "[00:01.00] la\n", None)


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


@pytest.fixture
def q(tmp_path):
    return DownloadQueue(tmp_path / "queue.json", tmp_path / "work")


class Fakes:
    """Stand-ins for the network and GPU parts; they record what ran and when."""

    def __init__(self, missing=(), errors=None, slow_finish=0.0):
        self.missing, self.errors, self.slow = set(missing), errors or {}, slow_finish
        self.log, self.max_waiting = [], 0

    def find(self, artist, title, duration=None):
        self.log.append(("find", title))
        return None if title in self.missing else cand(artist, title)

    def prepare(self, lib, c, work, step=None, cancel=None):
        if c.title in self.errors and self.errors[c.title][0] == "prepare":
            raise self.errors[c.title][1]
        step("step.download", 0.5)
        wav = work / "source.wav"
        wav.write_bytes(b"wav")
        self.log.append(("download", c.title))
        return pipeline.Prepared(f"{c.artist} - {c.title}", c.artist, c.title, "[00:01.00] la\n", wav)

    def finish(self, lib, prep, step=None, cancel=None, make_guide=True):
        if prep.title in self.errors and self.errors[prep.title][0] == "finish":
            raise self.errors[prep.title][1]
        step("step.separate", 0.3)
        end = time.time() + self.slow
        while time.time() < end:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            time.sleep(0.01)
        self.log.append(("finish", prep.title))
        return SimpleNamespace(has_guide=make_guide)

    def run(self, q, lib, cancel=None):
        return q.run(lib, lambda *a: None, cancel or threading.Event(),
                     find_lyrics=self.find, prepare=self.prepare, finish=self.finish)


def states(q, lib):
    return {i.title: (i.state, i.reason or i.level) for i in q.for_library(lib.path)}


def test_runs_everything_and_reports(q, lib):
    f = Fakes(missing={"Nowhere"})
    q.add(lib.path, [{"artist": "A", "title": "One", "lyrics": asdict(cand("A", "One"))}], "search")
    q.add(lib.path, [{"artist": "B", "title": "Two"}, {"artist": "C", "title": "Nowhere"}], "list",
          make_guide=False)
    summary = f.run(q, lib)
    assert summary == {"full": 1, "no_guide": 1, "skipped": 0, "failed": 1}
    assert states(q, lib) == {"One": ("done", "full"), "Two": ("done", "no_guide"), "Nowhere": ("failed", "no_lyrics")}
    assert ("find", "One") not in f.log  # lyrics chosen on the search screen are used as they are
    assert not q.has_work(lib.path)
    assert list((q.workroot).glob("*/source.wav")) == []  # downloads are cleaned up


def test_order_and_overlap(q, lib):
    """Songs finish in the order they were added; the next download overlaps the GPU work."""
    f = Fakes(slow_finish=0.15)
    q.add(lib.path, [{"artist": "A", "title": t} for t in ("1", "2", "3")], "list")
    f.run(q, lib)
    assert [x[1] for x in f.log if x[0] == "finish"] == ["1", "2", "3"]
    assert f.log.index(("download", "2")) < f.log.index(("finish", "1"))


def test_downloads_stay_at_most_one_ahead(q, lib):
    f = Fakes(slow_finish=0.1)
    q.add(lib.path, [{"artist": "A", "title": str(n)} for n in range(5)], "list")
    seen = []
    q.on_change = lambda: seen.append(sum(i.state == "downloaded" for i in q.items))
    f.run(q, lib)
    assert max(seen) <= 1


def test_errors_become_reasons_and_retry(q, lib):
    f = Fakes(errors={"Dup": ("prepare", AlreadyExists("x")), "Far": ("prepare", NoAudioMatch("x")),
                      "Boom": ("finish", RuntimeError("ffmpeg broke"))})
    q.add(lib.path, [{"artist": "A", "title": t} for t in ("Dup", "Far", "Boom")], "list")
    summary = f.run(q, lib)
    assert summary == {"full": 0, "no_guide": 0, "skipped": 1, "failed": 2}
    assert states(q, lib) == {"Dup": ("skipped", "exists"), "Far": ("failed", "no_audio"), "Boom": ("failed", "error")}
    boom = next(i for i in q.items if i.title == "Boom")
    assert boom.error == "ffmpeg broke"
    q.retry(boom.id)
    assert boom.state == "waiting" and boom.reason == "" and q.has_work(lib.path)


def test_pause_keeps_the_download_and_survives_a_restart(q, lib, tmp_path):
    f = Fakes(slow_finish=5.0)
    q.add(lib.path, [{"artist": "A", "title": "Long"}], "list")
    cancel = threading.Event()
    done = {}

    def go():
        try:
            f.run(q, lib, cancel)
        except Cancelled:
            done["cancelled"] = True

    th = threading.Thread(target=go)
    th.start()
    for _ in range(300):
        if any(i.state == "processing" for i in q.items):
            break
        time.sleep(0.01)
    cancel.set()
    th.join(10)
    assert done == {"cancelled": True}
    assert states(q, lib) == {"Long": ("downloaded", "")}
    # the app closes and opens again: same state, the WAV is still there
    q2 = DownloadQueue(tmp_path / "queue.json", tmp_path / "work")
    it = q2.for_library(lib.path)[0]
    assert it.state == "downloaded" and (q2.workroot / it.id / "source.wav").exists()
    f2 = Fakes()
    f2.run(q2, lib)
    assert ("download", "Long") not in f2.log and ("finish", "Long") in f2.log  # not downloaded again


def test_restart_puts_interrupted_songs_back(tmp_path, lib):
    q = DownloadQueue(tmp_path / "queue.json", tmp_path / "work")
    a, b, c = q.add(lib.path, [{"artist": "A", "title": t} for t in ("x", "y", "z")], "list")
    a.state, b.state = "downloading", "processing"
    b.prepared = {"base": "A - y", "artist": "A", "title": "y", "lrc_text": "", "wav": str(tmp_path / "gone.wav")}
    c.state = "done"
    q._save()
    q2 = DownloadQueue(tmp_path / "queue.json", tmp_path / "work")
    assert [i.state for i in q2.items] == ["waiting", "waiting", "done"]  # y's download is gone: start over


def test_no_duplicates_and_editing(q, lib):
    q.add(lib.path, [{"artist": "A", "title": "One"}], "list")
    again = q.add(lib.path, [{"artist": "a", "title": "one"}, {"artist": "A", "title": "Two"}], "list")
    assert [i.title for i in again] == ["Two"]
    one = q.for_library(lib.path)[0]
    one.state = "processing"
    with pytest.raises(ValueError):
        q.remove(one.id)
    one.state = "done"
    q.clear_finished(lib.path)
    assert [i.title for i in q.for_library(lib.path)] == ["Two"]
    assert q.for_library(lib.path / "other") == []
