import logging
import sys

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


def main():
    setup_logging()
    from encolibmg.core import i18n
    from encolibmg.core.paths import load_config

    i18n.set_language(load_config().get("language", "auto"))
    try:
        from encolibmg.webui.app import run

        run(debug="--debug" in sys.argv)
    except Exception as e:
        logging.exception("web UI failed to start")
        return _fatal(str(e))


if __name__ == "__main__":
    sys.exit(main())
