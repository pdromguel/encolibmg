"""Shared plumbing for the bridge: the {ok, data} envelope, the library in use, jobs, dialogs, media URLs."""

from __future__ import annotations

import functools
import json
import logging
from pathlib import Path

from encolibmg import i18n
from encolibmg.i18n import t as tr
from encolibmg.library import Library, LibraryError, Track
from encolibmg.paths import load_config, save_config

log = logging.getLogger("encolibmg.webui.api")

# errors the user caused or can fix: shown, not logged with a traceback
EXPECTED = ("NoLibrary", "Busy", "AlreadyExists", "NoAudioMatch", "LibraryError", "ValueError", "KeyError",
            "LookupError", "FileExistsError")


def step_text(s: str) -> str:
    """Progress steps from the engine are i18n keys; composite labels translate them here."""
    return tr(s) if s.startswith("step.") else s


class NoLibrary(Exception):
    pass


def api(fn):
    """Uniform envelope + logging for every bridge call."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": fn(self, *args, **kwargs)}
        except Exception as e:  # the UI shows the message; details go to the log
            kind = type(e).__name__
            if kind not in EXPECTED:
                log.exception("api %s failed", fn.__name__)
            msg = str(e).strip("'\"") or kind
            return {"ok": False, "error": msg, "kind": kind}
    return wrapper


class ApiCore:
    """State and helpers every area uses. Private names start with "_" so pywebview does not expose them."""

    def __init__(self, server, jobs):
        self._server = server
        self._jobs = jobs
        self._window = None
        self._lib: Library | None = None
        self._init_areas()
        i18n.set_language(load_config().get("language", "auto"))
        last = load_config().get("library")
        if last:
            try:
                self._set_library(Library.open(Path(last)))
            except LibraryError:
                log.warning("last library missing: %s", last)

    def _init_areas(self):
        """Each area mixin adds its own state here (cooperative: call super())."""

    def _extra_roots(self) -> list[Path]:
        """Folders besides the library that /media may serve (cooperative)."""
        return []

    def _emit(self, name: str, data: dict):
        if self._window is not None:
            self._window.evaluate_js(f"window.encolib && encolib.emit({json.dumps(name)}, {json.dumps(data)})")

    def _need(self) -> Library:
        if self._lib is None:
            raise NoLibrary(tr("err.no_library"))
        return self._lib

    def _set_library(self, lib: Library):
        self._lib = lib
        cfg = load_config()
        cfg["library"] = str(lib.path)
        save_config(cfg)
        self._refresh_roots()

    def _refresh_roots(self):
        self._server.set_roots(([self._lib.path] if self._lib else []) + self._extra_roots())

    def _track(self, base: str) -> Track:
        key = base.lower()
        for t in self._need().scan():
            if t.base.lower() == key:
                return t
        raise KeyError(tr("err.track_missing", base=base))

    def _job(self, label: str, fn, kind: str = "job") -> dict:
        def wrapped(progress, cancel):
            try:
                return fn(progress, cancel)
            finally:
                self._emit("library", {})
        return {"job": self._jobs.start(label, wrapped, kind)}

    def _dialog(self, kind: int, multiple=False, types=()) -> list[str]:
        if self._window is None:
            return []
        res = self._window.create_file_dialog(kind, allow_multiple=multiple, file_types=types)
        return list(res or [])

    def _open_files(self, types, multiple=False) -> list[str]:
        import webview

        return self._dialog(webview.FileDialog.OPEN, multiple, types)

    def _pick_folder(self) -> str | None:
        import webview

        paths = self._dialog(webview.FileDialog.FOLDER)
        return paths[0] if paths else None

    def _url(self, p: Path | None) -> str | None:
        return self._server.media_url(p) if p else None

    @staticmethod
    def _multiplex(t: Track) -> Path | None:
        return next((f for f in t.files if ".multiplexed." in f.name.lower()), None)
