"""The download queue for the page: add songs (search results, a pasted list, a YouTube playlist, a CSV), pause,
resume, retry, remove. It runs as one job, so it never competes with another job for the GPU."""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from encolibmg import queue_sources
from encolibmg.core.i18n import t as tr
from encolibmg.core.paths import app_dir
from encolibmg.download_queue import DownloadQueue
from encolibmg.webui.api.core import ApiCore, api
from encolibmg.webui.jobs import Busy

EMIT_EVERY = 0.2  # s between progress updates to the page (state changes are sent at once)


class QueueApi(ApiCore):
    def _init_areas(self):
        super()._init_areas()
        self._queue_paused = False
        self._queue_sig: tuple = ()
        self._queue_sent = 0.0
        self._queue_done = 0
        self._queue = DownloadQueue(app_dir() / "queue.json", app_dir() / "queue-work", on_change=self._queue_changed)
        # songs left from the last session wait for "Resume": the GPU isn't taken the moment the app opens
        self._queue_paused = any(i.state in ("waiting", "downloaded") for i in self._queue.items)
        if self._jobs is not None:
            self._jobs.on_idle = self._queue_kick

    # --- internals --------------------------------------------------------------------------------------------
    def _queue_items(self):
        return self._queue.for_library(self._lib.path) if self._lib else []

    def _queue_running(self) -> bool:
        cur = getattr(self._jobs, "current", None)
        return bool(cur and cur.get("kind") == "queue")

    def _queue_payload(self) -> dict:
        return {"items": [i.public() for i in self._queue_items()], "running": self._queue_running(),
                "paused": self._queue_paused}

    def _queue_changed(self):
        items = self._queue_items()
        sig = tuple((i.id, i.state) for i in items)
        now = time.monotonic()
        if sig == self._queue_sig and now - self._queue_sent < EMIT_EVERY:
            return
        self._queue_sig, self._queue_sent = sig, now
        self._emit("queue", self._queue_payload())
        done = sum(i.state == "done" for i in items)
        if done != self._queue_done:
            self._queue_done = done
            self._emit("library", {})  # a finished song is in the library now

    def _queue_kick(self):
        """Starts the queue job when there is work, it isn't paused and no other job is running."""
        lib = self._lib
        if self._jobs is None or lib is None or self._queue_paused or not self._queue.has_work(lib.path):
            return
        queue = self._queue

        def work(progress, cancel):
            try:
                return queue.run(lib, progress, cancel)
            finally:
                self._emit("library", {})
        try:
            self._jobs.start(tr("job.queue"), work, "queue")
        except Busy:
            pass  # another job is running: on_idle calls us again when it ends
        self._emit("queue", self._queue_payload())

    def _queue_add(self, entries: list[dict], source: str, make_guide: bool) -> dict:
        added = self._queue.add(self._need().path, entries, source, bool(make_guide))
        if added:
            self._queue_paused = False  # adding songs means "download these now"
        self._queue_kick()
        return {"added": len(added), "found": len(entries), **self._queue_payload()}

    # --- the page ------------------------------------------------------------------------------------------
    @api
    def queue_state(self):
        return self._queue_payload()

    @api
    def queue_add_results(self, ids: list[int], make_guide: bool = True):
        """Songs picked on the Add screen: their lyrics are already chosen."""
        cands = [self._lyrics[int(i)] for i in ids]
        return self._queue_add([{"artist": c.artist, "title": c.title, "lyrics": asdict(c)} for c in cands],
                               "search", make_guide)

    @api
    def queue_add_text(self, text: str, make_guide: bool = True):
        return self._queue_add(queue_sources.parse_list(text), "list", make_guide)

    @api
    def queue_add_playlist(self, url: str, make_guide: bool = True):
        parts = urlsplit(url.strip())
        host = parts.hostname or ""
        if parts.scheme != "https" or not (host == "youtu.be" or host.endswith("youtube.com")):
            raise ValueError(tr("err.only_youtube"))
        return self._queue_add(queue_sources.playlist_entries(url.strip()), "playlist", make_guide)

    @api
    def queue_add_csv(self, make_guide: bool = True):
        files = self._open_files((f"{tr('dialog.csv')} (*.csv)", f"{tr('dialog.all')} (*.*)"))
        if not files:
            return None
        return self._queue_add(queue_sources.parse_csv(Path(files[0])), "csv", make_guide)

    @api
    def job_cancel(self):
        """The footer's Cancel. On the queue it means "pause": otherwise it would start again right away."""
        if self._queue_running():
            self._queue_paused = True
        return self._jobs.cancel()

    @api
    def queue_pause(self):
        self._queue_paused = True
        if self._queue_running():
            self._jobs.cancel()  # the current song keeps its download; it resumes from there
        return self._queue_payload()

    @api
    def queue_resume(self):
        self._queue_paused = False
        self._queue_kick()
        return self._queue_payload()

    @api
    def queue_retry(self, item_id: str):
        self._queue.retry(item_id)
        self._queue_kick()
        return self._queue_payload()

    @api
    def queue_remove(self, item_id: str):
        self._queue.remove(item_id)
        return self._queue_payload()

    @api
    def queue_clear(self):
        self._queue.clear_finished(self._need().path)
        return self._queue_payload()
