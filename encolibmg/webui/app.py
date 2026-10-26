"""EncoLibMG window: WebView2 (pywebview) showing the local UI server, wired to Api."""

from __future__ import annotations

import ctypes
import logging
from pathlib import Path
from typing import Callable

from encolibmg.paths import app_dir
from encolibmg.webui.api import Api
from encolibmg.webui.jobs import JobManager
from encolibmg.webui.server import UIServer

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
ICON = STATIC / "brand" / "icon.ico"
BG = "#101315"


def _colorref(hex_color: str) -> int:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return (b << 16) | (g << 8) | r


def _style_native(window) -> None:
    """Window icon + title bar in the app's colors (Windows 11 DWM attributes)."""
    try:
        from System import Action
        from System.Drawing import Icon

        form = window.native

        def apply():
            form.Icon = Icon(str(ICON))
            hwnd = form.Handle.ToInt32()
            dwm = ctypes.windll.dwmapi
            for attr, value in ((20, 1), (35, _colorref(BG)), (36, _colorref("#cacccc")), (34, _colorref(BG))):
                v = ctypes.c_int(value)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        form.Invoke(Action(apply))
    except Exception:
        log.debug("native styling skipped", exc_info=True)


def build(debug: bool = False):
    """Creates server, jobs, api and the window (not started yet). Returns (window, api, server)."""
    import webview

    try:  # own taskbar group + icon instead of python.exe's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EncoLibMG.App")
    except Exception:
        pass
    server = UIServer(STATIC)
    server.start()
    holder: dict = {}
    jobs = JobManager(lambda name, data: holder["api"]._emit(name, data))
    api = Api(server, jobs)
    holder["api"] = api
    window = webview.create_window(
        "EncoLibMG", f"{server.base_url}/?t={server.token}", js_api=api, width=1240, height=820,
        min_size=(960, 640), background_color=BG, text_select=True,
    )
    api._window = window
    window.events.shown += lambda: _style_native(window)
    return window, api, server


def run(debug: bool = False, on_start: Callable | None = None) -> None:
    import webview

    window, api, server = build(debug)
    storage = app_dir() / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(on_start, (window, api) if on_start else None, debug=debug, private_mode=False,
                  storage_path=str(storage))
    server.stop()
