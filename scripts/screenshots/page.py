"""Open a page in a real WebView2 window, scroll through it and save screenshots (dev tool).

    python scripts/screenshots/page.py <url-or-file> <out-prefix> [width height] [scrolls...]
"""

import sys
import threading
import time
from pathlib import Path

import webview


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
    target, prefix = sys.argv[1], Path(sys.argv[2])
    w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1280, 820)
    scrolls = [int(v) for v in sys.argv[5:]] or [0]
    url = target if "://" in target else Path(target).resolve().as_uri()
    win = webview.create_window("snap", url, width=w, height=h, x=40, y=40, on_top=True)

    def run():
        time.sleep(3.5)
        for i, s in enumerate(scrolls):
            win.evaluate_js(f"window.scrollTo(0, {s})")
            time.sleep(1.6)
            grab(win, prefix.with_name(f"{prefix.name}-{i}.png"))
        errs = win.evaluate_js("JSON.stringify(window.__errors || [])")
        print("errors:", errs)
        win.destroy()

    def hook():
        win.evaluate_js("window.__errors=[];addEventListener('error',e=>window.__errors.push(e.message))")

    win.events.loaded += hook
    threading.Thread(target=run, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
