import logging
import os
import sys
from pathlib import Path

from encolibmg.core.paths import setup_logging


def _fatal(detail: str):
    """No web UI (WebView2 missing or broken): explain it in a native message box, then quit."""
    from encolibmg.core.i18n import t

    text = t("err.webview_missing", detail=detail)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "EncoLibMG", 0x10)
    except Exception:
        print(text, file=sys.stderr)
    return 1


def use_bundled_tools(python: Path | None = None) -> bool:
    """The installer puts ffmpeg next to its own Python ({app}\\python, {app}\\ffmpeg\\bin): use it first."""
    bin_dir = Path(python or sys.executable).resolve().parent.parent / "ffmpeg" / "bin"
    if not (bin_dir / "ffmpeg.exe").is_file():
        return False
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    return True


def main():
    setup_logging()
    if use_bundled_tools():
        logging.info("using the installer's ffmpeg")
    from encolibmg.core import gpu, i18n
    from encolibmg.core.paths import load_config

    logging.info("AI device: %s", gpu.choose_device())  # before anything imports torch
    i18n.set_language(load_config().get("language", "auto"))
    try:
        from encolibmg.webui.app import run

        run(debug="--debug" in sys.argv)
    except Exception as e:
        logging.exception("web UI failed to start")
        return _fatal(str(e))


if __name__ == "__main__":
    sys.exit(main())
