"""End-to-end: opens the real window (WebView2) on a generated library and runs the main flows.

    pytest -m ui

One app run plays the whole script (pywebview can start only once per process); the tests then check what
it reported. No network, no GPU: tracks are sine tones and the lyrics are placeholder lines.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.ui,
    pytest.mark.skipif(sys.platform != "win32", reason="the window needs Windows + WebView2"),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing"),
]

DRIVER = Path(__file__).parent / "ui" / "driver.py"
MP = "Demo Band - First Light"
PLAIN = "Demo Band - Paper Boats"
ORPHAN = "Test Artist - No Words"
LRC = "[00:01.00] placeholder line one\n[00:02.50] placeholder line two\n[00:04.00] placeholder line three\n"


def tone(path: Path, stereo_vocals=False):
    args = ["-f", "lavfi", "-i", "sine=f=220:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6"]
    mix = ["-filter_complex", "[0:a][1:a]amerge=inputs=2"] if stereo_vocals else ["-map", "0:a"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, *mix, "-b:a", "96k", str(path)], check=True)


def make_library(root: Path) -> Path:
    from encolibmg.library import Library

    lib = Library.create(root / "EncoreLibrary", "UI Test").path
    tone(lib / f"{MP}.multiplexed.mp3", stereo_vocals=True)
    (lib / f"{MP}.lrc").write_text(LRC, encoding="utf-8")
    tone(lib / f"{PLAIN}.mp3")
    (lib / f"{PLAIN}.lrc").write_text(LRC, encoding="utf-8")
    tone(lib / f"{ORPHAN}.mp3")
    return lib


Q = "document.querySelector"
QA = "[...document.querySelectorAll"


def texts(sel):
    return f"{QA}({json.dumps(sel)})].map(e => e.textContent.trim())"


def click_text(sel, text):
    return f"{QA}({json.dumps(sel)})].find(e => e.textContent.trim().includes({json.dumps(text)})).click()"


def key(k, ctrl=False):
    return f"dispatchEvent(new KeyboardEvent('keydown', {{ key: {json.dumps(k)}, ctrlKey: {str(ctrl).lower()} }}))"


SCRIPT = [
    # home, in English (the config asks for it)
    {"until": f"{Q}('.stat .num') && {Q}('.stat .num').textContent.trim() === '3'"},
    {"read": texts(".hdr .nav a"), "as": "nav"},
    {"read": texts(".stat .num"), "as": "stats"},
    {"read": f"{Q}('.hero-tag').textContent.trim()", "as": "tagline"},
    # library: list, filters, badges
    {"go": "library"},
    {"until": "document.querySelectorAll('.trow').length === 3"},
    {"read": texts(".trow .t"), "as": "titles"},
    {"read": f"{QA}('.trow')].map(r => [r.querySelector('.t').textContent.trim(), "
             "Array.from(r.querySelectorAll('.badge'), b => b.textContent.trim())])", "as": "badges"},
    {"js": click_text(".ltools .seg button", "Hidden")},
    {"until": "document.querySelectorAll('.trow').length === 1"},
    {"read": texts(".trow .t"), "as": "hidden"},
    {"js": click_text(".ltools .seg button", "All")},
    {"until": "document.querySelectorAll('.trow').length === 3"},
    # rename through the drawer and the dialog
    {"js": click_text(".trow", "Paper Boats")},
    {"until": f"{Q}('.drawer.open')"},
    {"js": click_text(".drawer .dgrid button", "Edit")},
    {"until": f"{Q}('.scrim input')"},
    {"js": "(() => { const i = document.querySelectorAll('.scrim input'); i[1].value = 'Paper Planes';"
           " i[1].dispatchEvent(new Event('input')); document.querySelector('.scrim button[type=submit]').click(); })()"},
    {"until": f"{QA}('.trow .t')].some(e => e.textContent.includes('Paper Planes'))"},
    {"js": key("Escape")},
    # check finds the track without lyrics
    {"go": "check"},
    {"js": f"{Q}('.page-head .btn.lg').click()"},
    {"until": f"{Q}('.igroup')", "timeout": 30},
    {"read": texts(".igroup h4 span:first-child"), "as": "issue_groups"},
    {"read": texts(".irow .f"), "as": "issue_files"},
    # sync: lines + waveform, shift +0.1 s, save with Ctrl S
    {"go": "sync/" + MP},
    {"until": f"{Q}('.sline')", "timeout": 20},
    {"read": "document.querySelectorAll('.sline').length", "as": "sync_lines"},
    {"read": "window.__encolib.store.state.view.sync.data.peaks.length", "as": "peaks"},
    {"js": key("]")},
    {"until": f"{Q}('.offset').textContent.includes('0.10')"},
    {"js": key("s", ctrl=True)},
    {"until": f"{Q}('#toasts').textContent.includes('Lyrics saved')"},
    # look & sound tabs
    {"go": "visual"},
    {"until": f"{Q}('.tabs button')"},
    {"read": texts(".tabs button"), "as": "visual_tabs"},
    # switch the language live
    {"js": "window.__encolib.setLanguage('pt-BR')"},
    {"until": f"{Q}('.hdr .nav').textContent.includes('Início')"},
    {"read": texts(".hdr .nav a"), "as": "nav_pt"},
    {"read": texts(".tabs button"), "as": "visual_tabs_pt"},
    {"read": "document.documentElement.lang", "as": "lang_pt"},
]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("ui")
    lib = make_library(root)
    appdata = root / "appdata"
    (appdata / "EncoLibMG").mkdir(parents=True)
    (appdata / "EncoLibMG" / "config.json").write_text(json.dumps({"library": str(lib), "language": "en"}),
                                                       encoding="utf-8")
    steps, result = root / "steps.json", root / "result.json"
    steps.write_text(json.dumps(SCRIPT), encoding="utf-8")
    env = {**os.environ, "APPDATA": str(appdata)}
    proc = subprocess.run([sys.executable, str(DRIVER), str(steps), str(result)], env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=240)
    if not result.exists():
        pytest.fail(f"the app did not report back:\n{proc.stdout[-2000:]}\n{proc.stderr[-3000:]}")
    data = json.loads(result.read_text(encoding="utf-8"))
    data["lib"] = lib
    return data


def test_script_ran_without_js_errors(run):
    assert run["failed"] is None, run["failed"]
    assert run["errors"] == []


def test_home_in_english(run):
    v = run["values"]
    assert [n[1:] for n in v["nav"]] == ["Home", "Add", "Library", "Check", "Import", "Look & sound"]
    assert v["stats"][0] == "3" and v["tagline"] == "Your karaoke library, in tune."


def test_library_lists_tracks_with_badges(run):
    v = run["values"]
    assert sorted(v["titles"]) == ["First Light", "No Words", "Paper Boats"]
    badges = dict((t, b) for t, b in v["badges"])
    assert badges["First Light"] == ["MP", "LRC"]
    assert badges["Paper Boats"] == ["AUDIO", "LRC"]
    assert badges["No Words"][0] == "⚠ HIDDEN"
    assert v["hidden"] == ["No Words"]


def test_rename_renamed_files_on_disk(run):
    names = sorted(p.name for p in run["lib"].iterdir())
    assert "Demo Band - Paper Planes.mp3" in names and "Demo Band - Paper Planes.lrc" in names
    assert not any("Paper Boats" in n for n in names)


def test_check_reports_audio_without_lyrics(run):
    v = run["values"]
    assert "Audio without lyrics" in v["issue_groups"]
    assert any("No Words" in f for f in v["issue_files"])


def test_sync_saved_shifted_lyrics(run):
    v = run["values"]
    assert v["sync_lines"] == 3 and v["peaks"] > 50
    lrc = (run["lib"] / f"{MP}.lrc").read_text(encoding="utf-8")
    assert lrc.splitlines()[0].startswith("[00:01.10]"), lrc


def test_language_switch_is_live(run):
    v = run["values"]
    assert v["visual_tabs"][0] == "Background videos"
    assert [n[1:] for n in v["nav_pt"]][:3] == ["Início", "Adicionar", "Biblioteca"]
    assert v["visual_tabs_pt"][0] == "Vídeos de fundo" and v["lang_pt"] == "pt-BR"
