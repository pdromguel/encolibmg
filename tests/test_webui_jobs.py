import threading
import time

import pytest

from encolibmg.errors import Cancelled
from encolibmg.webui.jobs import Busy, JobManager


class Sink:
    def __init__(self):
        self.events = []
        self.done = threading.Event()

    def __call__(self, name, data):
        self.events.append((name, data))
        if data.get("type") in ("done", "error", "cancelled"):
            self.done.set()


def test_progress_and_result():
    sink = Sink()
    jm = JobManager(sink)

    def work(progress, cancel):
        for i in range(100):
            progress("passo", i / 100)  # throttled
        progress("passo", 1.0)
        return {"ok": 1}

    jid = jm.start("Teste", work)
    assert sink.done.wait(5)
    types = [d["type"] for _, d in sink.events]
    assert types[0] == "start" and types[-1] == "done"
    assert sink.events[-1][1]["result"] == {"ok": 1} and sink.events[-1][1]["id"] == jid
    assert 2 <= types.count("progress") < 100
    assert not jm.busy


def test_only_one_job_at_a_time():
    sink, gate = Sink(), threading.Event()
    jm = JobManager(sink)
    jm.start("Longo", lambda p, c: gate.wait(5))
    with pytest.raises(Busy):
        jm.start("Outro", lambda p, c: None)
    assert jm.snapshot()["label"] == "Longo"
    gate.set()
    assert sink.done.wait(5)


def test_cancel_and_error():
    sink = Sink()
    jm = JobManager(sink)

    def work(progress, cancel):
        while not cancel.is_set():
            time.sleep(0.01)
        raise Cancelled()

    jm.start("Cancelável", work)
    assert jm.cancel()
    assert sink.done.wait(5) and sink.events[-1][1]["type"] == "cancelled"

    sink2 = Sink()
    jm2 = JobManager(sink2)
    jm2.start("Quebra", lambda p, c: 1 / 0)
    assert sink2.done.wait(5)
    last = sink2.events[-1][1]
    assert last["type"] == "error" and last["kind"] == "ZeroDivisionError"
