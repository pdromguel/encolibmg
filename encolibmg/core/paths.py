import glob
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path


APP_NAME = "EncoLibMG"
OLD_APP_DIR = "EncoreLibraryManager"  # name before the rename; config and backups move over once


def app_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    d = base / APP_NAME
    old = base / OLD_APP_DIR
    if not d.exists() and old.is_dir():
        try:
            old.rename(d)
        except OSError:
            shutil.copytree(old, d)
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config() -> dict:
    try:
        return json.loads((app_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    (app_dir() / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def backup_file(path: Path) -> Path:
    """Copies `path` to backups/<timestamp>/ before it is changed; returns the copy."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    dest = app_dir() / "backups" / stamp / Path(path).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def latest_backup(name: str) -> Path | None:
    root = app_dir() / "backups"
    found = sorted(root.glob(f"*/{glob.escape(name)}")) if root.exists() else []
    return found[-1] if found else None


def setup_logging() -> Path:
    log = app_dir() / "log.txt"
    logging.basicConfig(
        filename=log,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )
    return log
