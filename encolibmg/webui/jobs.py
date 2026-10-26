"""One heavy job at a time (GPU, disk), reported to the UI as `job` events."""

from __future__ import annotations

import itertools
import logging
import threading
import time
from typing import Any, Callable

from encolibmg.errors import Cancelled
from encolibmg.i18n import t

log = logging.getLogger(__name__)
MIN_INTERVAL = 0.05  # s between progress events (≤ 20/s)


class Busy(Exception):
    """Another job is still running."""


class JobManager:
    def __init__(self, emit: Callable[[str, dict], None]):
        self._emit = emit
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self.current: dict | None = None
        self._cancel = threading.Event()

    @property
    def busy(self) -> bool:
        return self.current is not None

    def snapshot(self) -> dict | None:
        return dict(self.current) if self.current else None

    def start(self, label: str, fn: Callable[[Callable, threading.Event], Any], kind: str = "job") -> int:
        """`fn(progress, cancel)` runs in a thread; its return value must be JSON-able."""
        with self._lock:
            if self.current:
                raise Busy(t("err.busy", label=self.current["label"]))
            job_id = next(self._ids)
            self._cancel = cancel = threading.Event()
            self.current = {"id": job_id, "label": label, "kind": kind, "step": label, "frac": None}
        self._emit("job", {"type": "start", **self.current})
        last = {"t": 0.0, "step": None}

        def progress(step: str, frac: float | None = None):
            """`step` is an i18n key ("step.download") or ready text; the UI gets both the text and the key."""
            now = time.monotonic()
            if step == last["step"] and now - last["t"] < MIN_INTERVAL and frac not in (None, 1.0):
                return
            last.update(t=now, step=step)
            key = step if step.startswith("step.") else None
            text = t(step) if key else step
            if self.current:
                self.current.update(step=text, key=key, frac=frac)
            self._emit("job", {"type": "progress", "id": job_id, "step": text, "key": key, "frac": frac})

        def run():
            try:
                result = fn(progress, cancel)
                self._finish(job_id, {"type": "done", "result": result})
            except Cancelled:
                self._finish(job_id, {"type": "cancelled"})
            except Exception as e:
                log.exception("job %s failed", label)
                self._finish(job_id, {"type": "error", "error": str(e) or type(e).__name__,
                                      "kind": type(e).__name__})

        threading.Thread(target=run, daemon=True, name=f"job-{job_id}").start()
        return job_id

    def _finish(self, job_id: int, payload: dict):
        with self._lock:
            label = self.current["label"] if self.current else ""
            kind = self.current["kind"] if self.current else "job"
            self.current = None
        self._emit("job", {"id": job_id, "label": label, "kind": kind, **payload})

    def cancel(self) -> bool:
        if self.current:
            self._cancel.set()
            return True
        return False
