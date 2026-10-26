"""Dev tool: run the real app on the test library, visit screens, save screenshots, report JS errors.

    python scripts/screenshots/app.py OUT_DIR route [route ...]
    step = a route ("home", "sync/Artist - Song": navigate + numbered screenshot) | "go:<route>" (navigate only)
           | "shot:<name>" | "frames:<name>:<count>:<ms>" | "js:<code>" | "wait:<seconds>"

The README screenshots use a demo library: python scripts/screenshots/demo_library.py <folder>

Uses a temporary %APPDATA% so the real config is never touched. ENCOLIB_LANG=en / pt-BR picks the language.
"""

import atexit
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if "ENCOLIB_TEST_LIB" not in os.environ:
    sys.exit("Set ENCOLIB_TEST_LIB to the path of a test EncoreLibrary.")
TEST_LIB = Path(os.environ["ENCOLIB_TEST_LIB"])

appdata = Path(tempfile.mkdtemp(prefix="encolib-appdata-"))
atexit.register(shutil.rmtree, appdata, ignore_errors=True)  # the WebView2 profile is ~25 MB per run
os.environ["APPDATA"] = str(appdata)
(appdata / "EncoLibMG").mkdir()
(appdata / "EncoLibMG" / "config.json").write_text(json.dumps({"library": str(TEST_LIB), "language": os.environ.get("ENCOLIB_LANG", "auto")}), encoding="utf-8")
sys.path.insert(0, str(ROOT))

from encolibmg.webui.app import run  # noqa: E402


def grab(win, path: Path):
    """PrintWindow renders only the app window, even when another window covers it."""
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = int(win.native.Handle.ToInt64())
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT: includes the WebView2 surface

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(path)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    steps = sys.argv[2:] or ["home"]

    def driver(window, api):
        time.sleep(4.0)
        window.on_top = True
        window.move(30, 30)
        window.resize(1280, 820)
        n = 0
        for step in steps:
            if step.startswith("go:"):  # navigate without a screenshot (add a wait: if the screen loads data)
                window.evaluate_js(f"location.hash = '#/{step[3:]}'")
                time.sleep(0.45)
                continue
            if step.startswith("shot:"):  # screenshot of what is on screen now, named
                grab(window, out / f"{step[5:]}.png")
                continue
            if step.startswith("frames:"):  # frames:NAME:COUNT:MS -> NAME-00.png … for animations
                name, count, ms = step[7:].split(":")
                for k in range(int(count)):
                    t0 = time.time()
                    grab(window, out / f"{name}-{k:02d}.png")
                    time.sleep(max(0, int(ms) / 1000 - (time.time() - t0)))
                continue
            if step.startswith("wait:"):
                time.sleep(float(step[5:]))
                continue
            if step.startswith("print:"):
                print(step[6:40], "=>", window.evaluate_js(step[6:]))
                continue
            if step.startswith("js:"):
                window.evaluate_js(step[3:])
                time.sleep(1.2)
                continue
            window.evaluate_js(f"location.hash = '#/{step}'")
            time.sleep(2.6)
            n += 1
            grab(window, out / f"{n:02d}-{step.split('/')[0]}.png")
        errors = window.evaluate_js("JSON.stringify(window.__errors)")
        print("JS errors:", errors)
        window.destroy()

    run(on_start=driver)


if __name__ == "__main__":
    main()
