"""The download queue: many songs added one after another, with the next download overlapping the GPU work.

Each song goes  waiting → finding → downloading → downloaded → processing → done
                                   (or failed / skipped, with the reason)
Two workers share it while it runs: one finds lyrics and downloads audio (network), staying at most one song
ahead; the other separates vocals, builds the Multiplex and the guide (GPU). The list is saved to queue.json after
every change, so it survives closing the app; a paused or interrupted song resumes where it can (a finished
download is kept).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable

from encolibmg import pipeline
from encolibmg.core.errors import AlreadyExists, Cancelled, NoAudioMatch
from encolibmg.core.i18n import t
from encolibmg.library import Library, base_name
from encolibmg.lyrics.lrclib import LyricsCandidate
from encolibmg.lyrics.match import find_by_name

log = logging.getLogger(__name__)

ACTIVE = ("finding", "downloading", "processing")
PENDING = ("waiting", "finding", "downloading", "downloaded", "processing")
FINISHED = ("done", "skipped")
PREFETCH = 1  # downloaded songs allowed to wait for the GPU (each is a ~40 MB WAV)


@dataclass
class Item:
    artist: str
    title: str
    library: str                      # the queue belongs to one library folder
    source: str = "search"            # search | list | playlist | csv
    duration: float | None = None     # known for Spotify CSV rows: helps choose the lyrics
    lyrics: dict | None = None        # a chosen LyricsCandidate (from the search screen)
    make_guide: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: str = "waiting"
    step: str = ""                    # i18n key of the current step
    frac: float | None = None
    reason: str = ""                  # failed/skipped: no_lyrics | no_audio | exists | error
    error: str = ""                   # message shown for reason == error
    level: str = ""                   # done: full (Multiplex + guide) | no_guide
    prepared: dict | None = None      # downloaded: pipeline.Prepared as a dict
    added: float = field(default_factory=time.time)

    @property
    def base(self) -> str:
        return base_name(self.artist, self.title) if self.artist else self.title

    def public(self) -> dict:
        d = {k: getattr(self, k) for k in ("id", "artist", "title", "source", "state", "step", "frac", "reason",
                                             "error", "level", "make_guide")}
        d["base"] = self.base
        return d


class DownloadQueue:
    def __init__(self, path: Path, workroot: Path, on_change: Callable[[], None] | None = None):
        self.path, self.workroot = Path(path), Path(workroot)
        self.on_change = on_change or (lambda: None)
        self.lock = threading.RLock()
        self.wake = threading.Condition(self.lock)
        self.items: list[Item] = self._load()

    # --- storage ---------------------------------------------------------------------------------------
    def _load(self) -> list[Item]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        names = {f.name for f in fields(Item)}
        items = [Item(**{k: v for k, v in d.items() if k in names}) for d in raw.get("items", [])]
        for it in items:  # the app closed mid-work: put each song back where it can resume
            if it.state == "processing":
                it.state = "downloaded"
            if it.state == "downloaded" and not (it.prepared and Path(it.prepared["wav"]).exists()):
                it.state, it.prepared = "waiting", None
            if it.state in ("finding", "downloading"):
                it.state = "waiting"
            it.step, it.frac = "", None
        return items

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": [asdict(i) for i in self.items]}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def _changed(self):
        self._save()
        self.wake.notify_all()
        try:
            self.on_change()
        except Exception:
            log.exception("queue on_change failed")

    # --- editing ------------------------------------------------------------------------------------------
    def for_library(self, library: Path | str) -> list[Item]:
        lib = str(Path(library))
        with self.lock:
            return [i for i in self.items if i.library == lib]

    def add(self, library: Path | str, entries: list[dict], source: str, make_guide: bool = True) -> list[Item]:
        """entries: {"artist", "title", "duration"?, "lyrics"?}. Songs already waiting in this library's queue are
        not added twice."""
        lib = str(Path(library))
        with self.lock:
            pending = {i.base.casefold() for i in self.items if i.library == lib and i.state in PENDING}
            added = []
            for e in entries:
                it = Item(artist=e.get("artist", "").strip(), title=e["title"].strip(), library=lib, source=source,
                          duration=e.get("duration"), lyrics=e.get("lyrics"), make_guide=make_guide)
                if it.title and it.base.casefold() not in pending:
                    pending.add(it.base.casefold())
                    self.items.append(it)
                    added.append(it)
            if added:
                self._changed()
            return added

    def get(self, item_id: str) -> Item:
        with self.lock:
            return next(i for i in self.items if i.id == item_id)

    def retry(self, item_id: str):
        with self.lock:
            it = self.get(item_id)
            if it.state in ("failed", "skipped"):
                it.state, it.reason, it.error, it.step, it.frac = "waiting", "", "", "", None
                self._changed()

    def remove(self, item_id: str):
        with self.lock:
            it = self.get(item_id)
            if it.state in ACTIVE:
                raise ValueError(t("err.queue_busy_item"))
            self.items.remove(it)
            shutil.rmtree(self.workroot / it.id, ignore_errors=True)
            self._changed()

    def clear_finished(self, library: Path | str):
        lib = str(Path(library))
        with self.lock:
            self.items = [i for i in self.items if not (i.library == lib and i.state in FINISHED)]
            self._changed()

    def has_work(self, library: Path | str) -> bool:
        return any(i.state in PENDING for i in self.for_library(library))

    def _set(self, it: Item, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(it, k, v)
            self._changed()

    # --- running ------------------------------------------------------------------------------------------
    def run(self, lib: Library, progress: Callable, cancel: threading.Event,
            find_lyrics=None, prepare=None, finish=None) -> dict:
        """Works through this library's queue until it is empty or `cancel` is set. Returns a summary
        {"full", "no_guide", "skipped", "failed"} of what finished during this run."""
        find_lyrics = find_lyrics or find_by_name
        prepare = prepare or pipeline.prepare_song
        finish = finish or pipeline.finish_song
        lib_key = str(Path(lib.path))
        summary = {"full": 0, "no_guide": 0, "skipped": 0, "failed": 0}
        downloader_done = threading.Event()

        def mine(state: str) -> list[Item]:
            return [i for i in self.items if i.library == lib_key and i.state == state]

        def fail(it: Item, e: Exception):
            if isinstance(e, AlreadyExists):
                self._set(it, state="skipped", reason="exists", step="", frac=None)
                summary["skipped"] += 1
            else:
                reason = "no_audio" if isinstance(e, NoAudioMatch) else "error"
                self._set(it, state="failed", reason=reason, error=str(e) or type(e).__name__, step="", frac=None)
                summary["failed"] += 1

        def download_loop():
            try:
                while not cancel.is_set():
                    with self.lock:
                        # stay at most PREFETCH songs ahead of the GPU
                        while len(mine("downloaded")) >= PREFETCH and mine("waiting") and not cancel.is_set():
                            self.wake.wait(0.5)
                        nxt = mine("waiting")
                        if cancel.is_set() or not nxt:
                            return
                        it = nxt[0]
                        self._set(it, state="finding", step="step.find_lyrics", frac=None)
                    try:
                        cand = LyricsCandidate(**it.lyrics) if it.lyrics else find_lyrics(it.artist, it.title,
                                                                                        it.duration)
                        if cand is None:
                            self._set(it, state="failed", reason="no_lyrics", step="", frac=None)
                            summary["failed"] += 1
                            continue
                        work = self.workroot / it.id
                        work.mkdir(parents=True, exist_ok=True)
                        self._set(it, state="downloading", artist=cand.artist, title=cand.title,
                                  lyrics=asdict(cand))

                        def step(key, frac=None, it=it):
                            with self.lock:
                                it.step, it.frac = key, frac
                            self.on_change()

                        prep = prepare(lib, cand, work, step, cancel)
                        self._set(it, state="downloaded", prepared={**asdict(prep), "wav": str(prep.wav)},
                                  step="", frac=None)
                    except Cancelled:
                        self._set(it, state="waiting", step="", frac=None)
                        return
                    except Exception as e:
                        log.warning("queue: %s failed while downloading: %s", it.base, e)
                        shutil.rmtree(self.workroot / it.id, ignore_errors=True)
                        fail(it, e)
            finally:
                downloader_done.set()
                with self.lock:
                    self.wake.notify_all()

        downloader = threading.Thread(target=download_loop, name="queue-download", daemon=True)
        downloader.start()
        try:
            while not cancel.is_set():
                with self.lock:
                    while not mine("downloaded") and not downloader_done.is_set() and not cancel.is_set():
                        self.wake.wait(0.5)
                    ready = mine("downloaded")
                    if cancel.is_set() or not ready:
                        break
                    it = ready[0]
                    self._set(it, state="processing", step="step.separate", frac=0.0)
                    prep = pipeline.Prepared(**{**it.prepared, "wav": Path(it.prepared["wav"])})

                def step(key, frac=None, it=it):
                    with self.lock:
                        it.step, it.frac = key, frac
                    progress(f"{it.base} · {t(key)}", frac, key)  # text for the footer, key for the Add steps
                    self.on_change()

                try:
                    track = finish(lib, prep, step, cancel, it.make_guide)
                    level = "full" if track.has_guide else "no_guide"
                    self._set(it, state="done", level=level, prepared=None, step="", frac=None)
                    summary[level] += 1
                    shutil.rmtree(self.workroot / it.id, ignore_errors=True)
                except Cancelled:
                    self._set(it, state="downloaded", step="", frac=None)  # keeps the download for next time
                    break
                except Exception as e:
                    log.warning("queue: %s failed while processing: %s", it.base, e)
                    shutil.rmtree(self.workroot / it.id, ignore_errors=True)
                    with self.lock:
                        it.prepared = None
                    fail(it, e)
        finally:
            downloader.join(timeout=30)  # a cancelled download stops within a second or two
        if cancel.is_set():
            raise Cancelled()
        return summary
