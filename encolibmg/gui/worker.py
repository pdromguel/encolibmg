"""Runs one long job in a thread and hands its events back to the Tk loop."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from typing import Callable

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, root: tk.Misc):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self._handlers: dict = {}
        self._poll()

    def run(self, fn: Callable, *, on_progress=None, on_done=None, on_error=None) -> None:
        """`fn(on_progress, cancel)` runs in a thread; callbacks run in the Tk thread."""
        if self.busy:
            raise RuntimeError("Já existe uma tarefa em andamento.")
        self.busy = True
        self.cancel = threading.Event()
        self._handlers = {"progress": on_progress, "done": on_done, "error": on_error}
        cancel = self.cancel

        def target():
            try:
                result = fn(lambda step, frac=None: self.events.put(("progress", (step, frac))), cancel)
                self.events.put(("done", result))
            except BaseException as e:  # reported to the UI, never lost in the thread
                log.exception("job failed")
                self.events.put(("error", e))

        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind in ("done", "error"):
                    self.busy = False
                handler = self._handlers.get(kind)
                if handler:
                    handler(*payload) if kind == "progress" else handler(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)
