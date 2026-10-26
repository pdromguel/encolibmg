"""Translation guarantees: both catalogs complete, no stray Portuguese in the code, steps sent as keys."""

import ast
import json
import re
from pathlib import Path

import pytest

from encolibmg.core import i18n

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "encolibmg"
PARAM = re.compile(r"\{(\w+)\}")


def load(lang):
    return json.loads((PKG / "core" / "locales" / f"{lang}.json").read_text(encoding="utf-8"))


def test_catalogs_have_the_same_keys_and_params():
    pt, en = load("pt-BR"), load("en")
    assert pt.keys() == en.keys()
    for k in pt:
        a, b = pt[k], en[k]
        assert type(a) is type(b), k
        if isinstance(a, dict):
            assert a.keys() == b.keys() == {"one", "other"}, k
            a, b = " ".join(a.values()), " ".join(b.values())
        assert set(PARAM.findall(a)) == set(PARAM.findall(b)), k
        assert b.strip(), f"empty English text: {k}"


def test_t_params_plural_and_fallback():
    i18n.set_language("en")
    assert i18n.t("err.already_exists", base="A - B") == "“A - B” is already in the library."
    assert i18n.t("does.not.exist") == "does.not.exist"
    assert i18n.t("err.already_exists") == "“{base}” is already in the library."  # missing param stays visible
    i18n.set_language("pt-BR")
    assert i18n.t("err.already_exists", base="A - B") == "“A - B” já está na biblioteca."


def test_plural_entries(monkeypatch):
    monkeypatch.setitem(i18n.catalog("en"), "x.tracks", {"one": "{count} track", "other": "{count} tracks"})
    i18n.set_language("en")
    assert i18n.t("x.tracks", count=1) == "1 track"
    assert i18n.t("x.tracks", count=0) == "0 tracks"


def test_resolve_and_detect(monkeypatch):
    assert i18n.resolve("en") == "en" and i18n.resolve("pt-BR") == "pt-BR"
    assert i18n.resolve("auto") in i18n.SUPPORTED
    assert i18n.resolve("klingon") in i18n.SUPPORTED


ACCENTED = re.compile(r"[ãçéêõáíóúâôàÁÉÍÓÚÃÕÇ]")
# strings that are data, not messages (regex ranges, words matched in titles, normalization tables)
ALLOWED = {"acústico", "æ", "ø", "ß"}


def _python_files():
    return [p for p in PKG.rglob("*.py")]


def _docstrings(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def test_no_hardcoded_portuguese_messages_in_python():
    found = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                v = node.value
                if ACCENTED.search(v) and v not in ALLOWED and not v.startswith("["):
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno}: {v[:50]!r}")
    assert not found, "\n".join(found)


def test_progress_steps_are_keys():
    bad = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                arg = node.args[0]
                if name in ("progress", "on_progress", "p") and isinstance(arg, ast.Constant) \
                        and isinstance(arg.value, str) and arg.value and not arg.value.startswith("step."):
                    bad.append(f"{path.relative_to(ROOT)}:{node.lineno}: {arg.value!r}")
    assert not bad, "\n".join(bad)


def test_every_t_key_used_in_python_exists():
    keys = load("en").keys()
    missing = []
    for path in _python_files():
        for m in re.finditer(r"""\b(?:t|tr)\(\s*["']([a-z_]+\.[\w.]+)["']""", path.read_text(encoding="utf-8")):
            if m.group(1) not in keys:
                missing.append(f"{path.relative_to(ROOT)}: {m.group(1)}")
    # f-string keys (kind.{x}, issue.kind.{x}…) are covered by the catalog tests per family
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("kind", ["multiplex_lrc", "audio_lrc", "mtv", "midi", "orphan"])
def test_track_kinds_translated(kind):
    for lang in i18n.SUPPORTED:
        assert f"kind.{kind}" in load(lang)


def test_api_language_switch(tmp_path):
    from encolibmg.webui.api import Api

    class S:
        def set_roots(self, r):
            pass

    a = Api(S(), None)
    res = a.set_language("en")["data"]
    assert res["lang"] == "en" and res["setting"] == "en" and res["catalog"]["job.check"] == "Library check"
    assert a.tracks()["error"] == "Open or create a library first."
    assert a.set_language("pt-BR")["data"]["catalog"]["job.check"] == "Verificação da biblioteca"
    assert a.set_language("xx")["ok"] is False
    assert a.set_language("auto")["data"]["setting"] == "auto"


JS = PKG / "webui" / "static" / "js"
# keys built at runtime in the JS: prefix -> the suffixes it is completed with
JS_DYNAMIC = {
    "ui.lib.f.": ["all", "mp", "guide", "noguide", "mtv", "midi", "issues"],
    "ui.lib.sort.": ["artist", "title", "recent"],
    "ui.import.opt.": ["find_lyrics", "make_multiplex", "normalize", "move"],
    "ui.vis.tab.": ["bgv", "bumpers", "boot", "narr", "sf"],
    "ui.check.what.": [f"{n}{d}" for n in range(1, 9) for d in ("", "d")],
}


def test_every_ui_key_used_in_js_exists():
    keys = load("en").keys()
    used = set()
    for path in JS.rglob("*.js"):
        used |= set(re.findall(r"""["'`]((?:ui|name|step|job|err)\.[a-z0-9_.]+[a-z0-9_])["'`]""", path.read_text(encoding="utf-8")))
    for prefix, rest in JS_DYNAMIC.items():
        used |= {prefix + r for r in rest}
    missing = sorted(k for k in used if k not in keys and not any(k == p.rstrip(".") for p in JS_DYNAMIC))
    assert not missing, missing
    unused = sorted(k for k in keys if k.startswith("ui.") and k not in used)
    assert not unused, f"catalog keys nobody uses: {unused}"


def test_no_portuguese_left_in_the_web_ui():
    found = []
    for path in [*JS.rglob("*.js"), PKG / "webui" / "static" / "index.html"]:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//")[0]
            if ACCENTED.search(code) and "EXAMPLES" not in code and "Português" not in code and "Águas" not in code \
                    and "Você" not in code:
                found.append(f"{path.name}:{n}: {line.strip()[:70]}")
    assert not found, "\n".join(found)


def test_auto_follows_windows_language(monkeypatch):
    from encolibmg.webui.api import Api

    class S:
        def set_roots(self, r):
            pass

    monkeypatch.setattr(i18n, "detect_language", lambda: "en")  # e.g. an English Windows (like the CI runners)
    a = Api(S(), None)
    assert i18n.language() == "en"
    assert a.tracks()["error"] == "Open or create a library first."
    monkeypatch.setattr(i18n, "detect_language", lambda: "pt-BR")
    assert a.set_language("auto")["data"]["lang"] == "pt-BR"
