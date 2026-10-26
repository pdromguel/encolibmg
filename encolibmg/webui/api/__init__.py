"""Methods the UI calls through `window.pywebview.api.*`, one module per screen area.

Every public method returns {"ok": True, "data": ...} or {"ok": False, "error": ..., "kind": ...}.
Heavy work goes through JobManager and answers {"job": id}; the result arrives as a `job` event.
"""

from encolibmg.webui.api.add import AddApi
from encolibmg.webui.api.check import CheckApi
from encolibmg.webui.api.core import NoLibrary, api
from encolibmg.webui.api.imports import ImportApi
from encolibmg.webui.api.library import LibraryApi
from encolibmg.webui.api.sync import SyncApi
from encolibmg.webui.api.visual import VisualApi


class Api(LibraryApi, AddApi, SyncApi, CheckApi, ImportApi, VisualApi):
    """The object pywebview exposes to JavaScript."""


__all__ = ["Api", "NoLibrary", "api"]
