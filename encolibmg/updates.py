"""Keeping up to date: a notice when a new EncoLibMG release is out (never installs it by itself), and updating
yt-dlp, which YouTube changes break every few weeks."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time

import requests

from encolibmg import __version__
from encolibmg.core.i18n import t
from encolibmg.core.paths import load_config, save_config

log = logging.getLogger(__name__)

REPO = "pdromguel/encolibmg"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
CHECK_EVERY = 24 * 3600  # s: at most one automatic check a day
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def parse_version(v: str) -> tuple[int, ...]:
    """'v1.2.10' → (1, 2, 10); anything after the numbers ('-beta') is ignored."""
    nums = re.findall(r"\d+", v.split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)


def latest_release(session=None) -> dict | None:
    """{"version", "url", "name"} of the newest published release, or None when offline / no release yet."""
    session = session or requests
    try:
        r = session.get(RELEASES_API, timeout=10, headers={"Accept": "application/vnd.github+json",
                                                          "User-Agent": f"EncoLibMG/{__version__}"})
        if r.status_code != 200:
            return None
        data = r.json()
        return {"version": data["tag_name"].lstrip("v"), "url": data.get("html_url") or RELEASES_PAGE,
                "name": data.get("name") or data["tag_name"]}
    except (requests.RequestException, KeyError, ValueError):
        return None


def check(force: bool = False, session=None, now=time.time) -> dict:
    """{"current", "latest", "newer", "url"}. Without `force`, asks GitHub at most once a day (the answer is
    remembered in the config)."""
    cfg = load_config()
    cached = cfg.get("update_check") or {}
    if not force and "at" in cached and now() - cached["at"] < CHECK_EVERY:
        rel = cached.get("release")
    else:
        rel = latest_release(session)
        cfg["update_check"] = {"at": now(), "release": rel}
        save_config(cfg)
    newer = bool(rel) and parse_version(rel["version"]) > parse_version(__version__)
    return {"current": __version__, "latest": rel["version"] if rel else None, "newer": newer,
            "url": rel["url"] if rel else RELEASES_PAGE}


def ytdlp_version() -> str:
    """The installed yt-dlp version, read in a fresh process (this one keeps the version it imported)."""
    out = subprocess.run([sys.executable, "-c", "import importlib.metadata as m; print(m.version('yt-dlp'))"],
                         capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
    return out.stdout.strip() or "?"


def update_ytdlp(on_progress=lambda key, frac=None: None) -> dict:
    """pip install -U yt-dlp in the app's own Python. {"before", "after", "changed"}; the app must be reopened
    to use a new version."""
    on_progress("step.update_ytdlp", None)
    before = ytdlp_version()
    proc = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
                           "yt-dlp"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW, timeout=600)
    if proc.returncode != 0:
        log.warning("yt-dlp update failed: %s", proc.stderr[-2000:])
        raise RuntimeError(t("err.update_failed", detail=(proc.stderr.strip().splitlines() or ["?"])[-1][:300]))
    after = ytdlp_version()
    return {"before": before, "after": after, "changed": before != after}
