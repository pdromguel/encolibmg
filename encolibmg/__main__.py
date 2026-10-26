import logging
import sys

from encolibmg.paths import setup_logging


def _tk():
    from encolibmg.gui.app import App

    App().mainloop()


def main():
    setup_logging()
    if "--tk" in sys.argv:
        return _tk()
    try:
        from encolibmg.webui.app import run
    except Exception:  # pywebview/WebView2 missing: the old window still works
        logging.exception("web UI unavailable, falling back to Tk")
        return _tk()
    run(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
