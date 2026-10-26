"""manifest.json of an EncoreLibrary. Unknown keys (BGVs, SoundFont…) are always preserved."""

import json
from pathlib import Path

# (flag key in manifest["flags"], label shown in the app, Encore's default when the key is absent)
# EncoreHome.js reads enableMtvCategory/enableDefaultCategories with `?? true`.
FLAGS = [
    ("enableMtvCategory", "Mostrar categoria MTV", True),
    ("enableDefaultCategories", "Mostrar categorias padrão", True),
    ("flipArtistTitle", "Inverter artista/título na exibição", False),
    ("skipToFirstNoteOn", "MIDI: pular silêncio inicial", False),
]


def read_manifest(lib_path: Path) -> dict:
    return json.loads((Path(lib_path) / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(lib_path: Path, data: dict) -> None:
    path = Path(lib_path) / "manifest.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def flag_value(data: dict, key: str) -> bool:
    default = next(d for k, _, d in FLAGS if k == key)
    return bool((data.get("flags") or {}).get(key, default))


def set_flag(data: dict, key: str, value: bool) -> None:
    """Stores only values that differ from Encore's default, so `false` survives for default-on flags."""
    default = next(d for k, _, d in FLAGS if k == key)
    flags = dict(data.get("flags") or {})
    if value == default:
        flags.pop(key, None)
    else:
        flags[key] = value
    if flags:
        data["flags"] = flags
    else:
        data.pop("flags", None)


def ensure_additional(data: dict) -> bool:
    """Encore only adds the automatic MTV category when additionalContents.bgvCategories exists
    (EncoreHome.js ~L500). Returns True when something was added."""
    extra = data.setdefault("additionalContents", {})
    changed = False
    for key in ("bgvCategories", "bumperImages"):
        if not isinstance(extra.get(key), list):
            extra[key] = []
            changed = True
    return changed
