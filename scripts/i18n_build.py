"""Writes encolibmg/locales/pt-BR.json and en.json from the string tables in scripts/catalog_*.py.

Each table is a list of (key, pt-BR, en). A value may be a dict {"one": ..., "other": ...} for plurals.
Run after editing a table:  python scripts/i18n_build.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_engine import ENGINE  # noqa: E402
from catalog_ui import UI  # noqa: E402

OUT = ROOT / "encolibmg" / "locales"


def main():
    rows = ENGINE + UI
    keys = [k for k, *_ in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        sys.exit(f"duplicate keys: {sorted(dupes)}")
    OUT.mkdir(exist_ok=True)
    for i, lang in enumerate(("pt-BR", "en"), start=1):
        data = {row[0]: row[i] for row in rows}
        (OUT / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8", newline="\n")  # LF on every OS (CI compares)
    print(f"{len(rows)} strings -> {OUT}")


if __name__ == "__main__":
    main()
