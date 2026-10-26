"""Runs the real EncoLibMG window and plays a script of steps against it (used by tests/test_ui.py).

    python tests/ui/driver.py steps.json result.json

Steps (JSON list), run in order:
    {"go": "library"}                       navigate (hash route) and wait for the screen to settle
    {"js": "code"}                          run JavaScript
    {"until": "expr", "timeout": 10}        wait until the JS expression is truthy (fails the run otherwise)
    {"read": "expr", "as": "name"}          store JSON.stringify(expr) under "name" in the result
    {"wait": 0.5}                           sleep
The result file gets {"values": {...}, "errors": [JS errors], "failed": "message or null"}.
The caller must point APPDATA at a temporary folder: the app's config and WebView2 profile live there.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from encolibmg.webui.app import run  # noqa: E402


def main():
    steps = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    result = {"values": {}, "errors": [], "failed": None}

    def js(window, code):
        return window.evaluate_js(code)

    def until(window, expr, timeout):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if js(window, f"!!({expr})"):
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        return False

    def driver(window, api):
        try:
            if not until(window, "window.__encolib && document.querySelector('.hdr .nav a')", 30):
                raise RuntimeError("the app did not start")
            for n, step in enumerate(steps):
                if "go" in step:
                    js(window, f"location.hash = {json.dumps('#/' + step['go'])}")
                    name = step["go"].split("/")[0]
                    if not until(window, f"document.querySelector('.view[data-screen=\"{name}\"]')", 10):
                        raise RuntimeError(f"step {n}: screen {name} did not open")
                    time.sleep(0.6)  # pixel wipe
                elif "js" in step:
                    js(window, step["js"])
                elif "until" in step:
                    if not until(window, step["until"], step.get("timeout", 10)):
                        raise RuntimeError(f"step {n}: timed out waiting for {step['until']}")
                elif "read" in step:
                    result["values"][step["as"]] = json.loads(js(window, f"JSON.stringify({step['read']})") or "null")
                elif "wait" in step:
                    time.sleep(step["wait"])
        except Exception as e:
            result["failed"] = str(e)
        finally:
            try:
                result["errors"] = json.loads(js(window, "JSON.stringify(window.__errors || [])") or "[]")
            except Exception:
                pass
            out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            window.destroy()

    run(on_start=driver)


if __name__ == "__main__":
    main()
