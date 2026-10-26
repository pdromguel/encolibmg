import subprocess
import tkinter as tk

import numpy as np
import pytest

from encolibmg.library import Library


@pytest.fixture
def app():
    from encolibmg.gui.app import App

    # creating many Tk() in one process occasionally fails to init Tcl on Windows; retry
    for attempt in range(3):
        try:
            a = App()
            break
        except tk.TclError as e:
            err = e
    else:
        pytest.skip(f"Tk indisponível: {err}")
    yield a
    a.destroy()


def pump(app, until, tries=100):
    for _ in range(tries):
        app.update()
        if until():
            return True
        app.after(20)
    return False


@pytest.fixture
def lib(tmp_path):
    lib = Library.create(tmp_path / "EncoreLibrary", "Teste")
    (lib.path / "A - B.multiplexed.mp3").write_bytes(b"")
    (lib.path / "A - B.lrc").write_text("[00:01.00] um\n[00:03.00] dois\n", encoding="utf-8")
    (lib.path / "C - D.mp3").write_bytes(b"")
    return lib


def test_app_builds_and_lists_library(app, lib):
    app.set_library(lib)
    app.update()
    rows = [app.library_tab.tree.item(i, "values") for i in app.library_tab.tree.get_children()]
    assert ("A", "B", "Multiplex + LRC", ".lrc .multiplexed.mp3") in rows
    assert any(r[2].startswith("⚠") for r in rows)
    assert "1 invisíveis" in app.library_tab.count.get()
    tabs = [app.notebook.tab(t, "text").strip() for t in app.notebook.tabs()]
    assert tabs == ["Adicionar", "Biblioteca", "Verificar", "Importar", "Visual e som"]


def test_library_buttons_follow_selection(app, lib):
    app.set_library(lib)
    tab = app.library_tab
    row = next(i for i in tab.tree.get_children() if tab.tree.item(i, "values")[0] == "A")
    tab.tree.selection_set(row)
    app.update()
    state = {k: str(b.cget("state")) for k, b in tab.btn.items()}
    assert state == {"edit": "normal", "sync": "normal", "guide": "normal", "preview": "disabled",
                     "clip": "normal", "mux": "disabled", "remove": "normal"}


def test_guide_preview_draws(app, lib):
    from encolibmg.audio.player import Player
    from encolibmg.guide.align import Word
    from encolibmg.guide.melody import Note
    from encolibmg.guide.midi import write_guide
    from encolibmg.gui.guide_preview import GuidePreview

    words = [[Word(1.0 + 0.3 * i, w) for i, w in enumerate("um dois três".split())],
             [Word(3.0 + 0.3 * i, w) for i, w in enumerate("quatro cinco seis".split())]]
    write_guide(lib.path / "A - B.guide.mid", [Note(1.0, 2.0, 60), Note(3.0, 4.0, 64)], words, "B", "A")
    track = next(t for t in lib.scan() if t.base == "A - B")
    player = Player(data=np.zeros((44100 * 5, 2), dtype=np.float32), stream_factory=lambda **kw: _Stream())
    w = GuidePreview(app, track, player=player)
    player.pos = int(1.5 * 44100)
    app.update()
    w._tick()
    assert len(w.lines) == 2 and w.lines[1][0] == (3.0, "quatro ")
    assert w.canvas.find_all() and w.lyric.find_all()
    w.close()


def test_worker_reports_result(app):
    from encolibmg.gui.worker import Worker

    w = Worker(app)
    got = {}
    w.run(lambda p, c: (p("passo", 0.5), 42)[1],
          on_progress=lambda s, f: got.setdefault("p", (s, f)), on_done=lambda r: got.setdefault("r", r))
    assert pump(app, lambda: "r" in got)
    assert got == {"p": ("passo", 0.5), "r": 42}
    assert not w.busy


def test_check_tab_runs_and_fixes(app, lib):
    app.set_library(lib)
    app.check_tab.run_check()
    assert pump(app, lambda: not app.jobs.busy and app.check_tab.issues)
    kinds = sorted(i.kind for i in app.check_tab.issues)
    # both test mp3s have no tags; the multiplex one has no MIDI guide
    assert kinds == ["missing_tags", "missing_tags", "no_guide", "orphan"]


def test_import_tab_scan_preview(app, lib, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "Adele - Hello.mp4").write_bytes(b"")
    (src / "A - B.mp4").write_bytes(b"")
    app.set_library(lib)
    app.import_tab.source.set(str(src))
    app.import_tab.scan()
    assert pump(app, lambda: app.import_tab.items)
    rows = {app.import_tab.tree.item(i, "values")[1]: app.import_tab.tree.item(i, "values")
            for i in app.import_tab.tree.get_children()}
    assert rows["Adele"][0] == "☑"
    assert rows["A"][0] == "☐" and rows["A"][5] == "já existe"


def test_sync_window_shift_anchor_and_save(app, lib):
    from encolibmg.audio.player import Player
    from encolibmg.gui.sync_window import SyncWindow

    track = next(t for t in lib.scan() if t.base == "A - B")
    player = Player(data=np.zeros((44100 * 5, 2), dtype=np.float32), stream_factory=lambda **kw: _Stream())
    w = SyncWindow(app, track, player=player)
    w.nudge(500)
    assert [l.ms for l in w.lines] == [1500, 3500]
    # tap line 2 while "playing" at 4.15 s -> anchored at 4.0 s (150 ms reaction);
    # a single anchor moves the whole lyric
    player.playing, player.pos = True, int(4.15 * 44100)
    w.tree.selection_set("1")
    w._space(None)
    assert [l.ms for l in w.lines] == [2000, 4000]
    # a second anchor on line 1 at 1.15 s stretches between them
    player.pos = int(1.15 * 44100)
    w.tree.selection_set("0")
    w._space(None)
    assert [l.ms for l in w.lines] == [1000, 4000]
    w.save()
    assert (lib.path / "A - B.lrc").read_text(encoding="utf-8") == "[00:01.00] um\n[00:04.00] dois\n"
    w.close()


class _Stream:
    latency = 0.0

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


def test_manifest_dialog_saves(app, lib):
    from encolibmg.gui.dialogs import ManifestDialog
    from encolibmg.manifest import read_manifest

    d = ManifestDialog(app, lib.path)
    d.name.set("Karaokê da Família")
    assert d.flag_vars["enableMtvCategory"].get() is True  # Encore's default shows as checked
    d.flag_vars["enableMtvCategory"].set(False)
    d.ok()
    m = read_manifest(lib.path)
    assert m["title"] == "Karaokê da Família" and m["flags"] == {"enableMtvCategory": False}


def test_visual_tab_lists_assets(app, lib, tmp_path):
    from encolibmg import soundfont, visual

    visual.add_category(lib, "Praia")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    visual.add_bumper(lib, tmp_path / "logo.png")
    (tmp_path / "gm.sf2").write_bytes(b"RIFF")
    soundfont.install_soundfont(lib, tmp_path / "gm.sf2")
    app.set_library(lib)
    app.update()
    tab = app.visual_tab
    assert tab.cats.get(0) == "Praia  (0)"
    assert tab.bump.get(0) == "Bumpers/logo.png"
    assert tab.sf_var.get() == "SoundFonts/gm.sf2"
    assert tab.boot_var.get().startswith("nenhum")
    tabs = [app.notebook.tab(t, "text").strip() for t in app.notebook.tabs()]
    assert tabs[-1] == "Visual e som"
