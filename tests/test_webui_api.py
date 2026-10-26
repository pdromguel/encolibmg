import subprocess

import pytest

from encolibmg.webui.api import Api


class FakeServer:
    def __init__(self):
        self.roots = []

    def set_roots(self, roots):
        self.roots = list(roots)

    def media_url(self, p):
        return f"http://x/media/{p.name}"


class SyncJobs:
    """Runs jobs immediately and keeps the last result."""
    def __init__(self):
        self.results = []

    def start(self, label, fn, kind="job"):
        self.results.append(fn(lambda *a: None, type("E", (), {"is_set": lambda s: False})()))
        return len(self.results)

    def snapshot(self):
        return None

    def cancel(self):
        return False


def multiplex(path, seconds=4):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=440:r=44100:d={seconds}", "-filter_complex",
                    "[0:a]volume=1[l];[1:a]adelay=1000|1000[r];[l][r]join=inputs=2:channel_layout=stereo[a]",
                    "-map", "[a]", str(path)], check=True)


@pytest.fixture
def api(tmp_path):
    a = Api(FakeServer(), SyncJobs())
    res = a.library_create(str(tmp_path), "Teste")
    assert res["ok"], res
    return a


def lib_path(api):
    return api._lib.path


def test_no_library_is_a_clean_error(tmp_path):
    a = Api(FakeServer(), SyncJobs())
    assert a.state() == {"ok": True, "data": {"version": a.state()["data"]["version"], "job": None,
                                              "library": None, "stats": a.state()["data"]["stats"]}}
    res = a.tracks()
    assert res == {"ok": False, "error": "Abra ou crie uma biblioteca primeiro.", "kind": "NoLibrary"}


def test_create_open_and_stats(api, tmp_path):
    st = api.state()["data"]
    assert st["library"]["title"] == "Teste" and st["library"]["path"].endswith("EncoreLibrary")
    assert api._server.roots == [lib_path(api)]
    multiplex(lib_path(api) / "A - B.multiplexed.mp3")
    (lib_path(api) / "A - B.lrc").write_text("[00:01.00] oi\n[00:02.00] tchau\n", encoding="utf-8")
    (lib_path(api) / "C - D.mp4").write_bytes(b"")
    tracks = api.tracks()["data"]
    assert [(t["base"], t["badges"]) for t in tracks] == [("A - B", ["MP", "LRC"]), ("C - D", ["MTV"])]
    assert api.state()["data"]["stats"] == {"tracks": 2, "multiplex": 1, "guides": 0, "mtv": 1, "orphans": 0,
                                            "no_guide": 1}


def test_rename_and_remove(api, monkeypatch):
    (lib_path(api) / "a - b.mp4").write_bytes(b"")
    t = api.track_rename("a - b", "Queen", "Love")["data"]
    assert t["base"] == "Queen - Love"
    monkeypatch.setattr("encolibmg.library.model.send2trash", lambda p: __import__("os").remove(p))
    assert api.track_remove(["Queen - Love"])["data"] == 1
    assert api.tracks()["data"] == []
    assert api.track_rename("nada", "x", "y")["kind"] == "KeyError"


def test_sync_load_save_undo(api):
    multiplex(lib_path(api) / "A - B.multiplexed.mp3")
    (lib_path(api) / "A - B.lrc").write_text("[00:01.00] oi\n[00:02.00] tchau\n", encoding="utf-8")
    d = api.sync_load("A - B")["data"]
    assert d["lines"] == [{"ms": 1000, "text": "oi"}, {"ms": 2000, "text": "tchau"}]
    assert d["multiplexed"] and d["audio"].endswith(".mp3") and 3.9 < d["duration"] < 4.2
    assert len(d["peaks"]) == 100 and max(d["peaks"]) == 1.0 and d["rate"] == pytest.approx(25, abs=.5)
    assert d["onset"] == pytest.approx(1.0, abs=0.1)  # vocals (right) start after 1 s
    saved = api.sync_save("A - B", [{"ms": 1200, "text": "oi"}, {"ms": 2300, "text": "tchau"}])["data"]
    assert saved["lines"][0] == {"ms": 1200, "text": "oi"}
    undone = api.sync_undo("A - B")["data"]
    assert undone["lines"][0] == {"ms": 1000, "text": "oi"}


def test_settings_roundtrip(api):
    s = api.settings_get()["data"]
    assert s["title"] == "Teste" and {f["key"]: f["value"] for f in s["flags"]}["enableMtvCategory"] is True
    s["title"] = "Família"
    s["flags"] = [{"key": "enableMtvCategory", "value": False}]
    assert api.settings_save(s)["data"]["library"]["title"] == "Família"
    assert {f["key"]: f["value"] for f in api.settings_get()["data"]["flags"]}["enableMtvCategory"] is False
    assert api.settings_save({"title": " "})["kind"] == "ValueError"


def test_check_and_fix_through_jobs(api):
    (lib_path(api) / ".encore-tmp-x").mkdir()
    assert api.check(False)["data"] == {"job": 1}
    issues = api._jobs.results[-1]
    assert [i["kind"] for i in issues] == ["temp_leftover"] and issues[0]["fixable"]
    api.fix([0])
    assert api._jobs.results[-1] == {0: {"ok": True, "message": "apagada"}}


def test_import_scan_edit(api, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "01 - Hello.mp4").write_bytes(b"")
    items = api.import_scan(str(src))["data"]
    # a file right in the chosen folder has no artist folder: the user fixes it in the preview
    assert items[0]["artist"] == "Desconhecido" and items[0]["title"] == "Hello" and items[0]["selected"]
    assert api._import_tmp in api._server.roots
    items = api.import_edit(0, artist="Adele")["data"]
    assert items[0]["base"] == "Adele - Hello"
    items = api.import_edit(0, selected=False)["data"]
    assert items[0]["selected"] is False


def test_visual_state_and_categories(api):
    st = api.bgv_category("add", "Praia")["data"]
    assert st["categories"] == [{"name": "Praia", "videos": []}] and st["boot"] is None
    assert api.bgv_category("add", "praia")["kind"] == "ValueError"
    st = api.bgv_category("rename", "Praia", "Mar")["data"]
    assert st["categories"][0]["name"] == "Mar"


def test_open_url_only_youtube(api, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    assert api.open_url("https://www.youtube.com/watch?v=abc")["ok"]
    assert api.open_url("file:///C:/Windows/system32/calc.exe")["kind"] == "ValueError"
    assert api.open_url("https://evil.example/youtube.com")["kind"] == "ValueError"
    assert opened == ["https://www.youtube.com/watch?v=abc"]


def test_open_folder_only_opens_folders_inside_library(api, monkeypatch):
    opened = []
    monkeypatch.setattr("os.startfile", opened.append)
    (lib_path(api) / "BGV").mkdir()
    (lib_path(api) / "virus.exe").write_bytes(b"MZ")
    assert api.open_folder()["ok"] and api.open_folder("BGV")["ok"]
    assert api.open_folder("virus.exe")["kind"] == "ValueError"
    assert api.open_folder("../..")["kind"] == "ValueError"
    assert api.open_folder("C:/Windows")["kind"] == "ValueError"
    assert [p.name for p in map(__import__("pathlib").Path, opened)] == ["EncoreLibrary", "BGV"]


def test_every_method_the_ui_calls_exists():
    """The JS calls the bridge by name; after splitting the API into areas none may go missing."""
    import re
    from pathlib import Path

    js = Path(__file__).resolve().parent.parent / "encolibmg" / "webui" / "static" / "js"
    called = set()
    for f in js.rglob("*.js"):
        called |= set(re.findall(r"""\b(?:call|tryCall|runJob)\(\s*["'](\w+)["']""", f.read_text(encoding="utf-8")))
    assert len(called) > 30
    missing = sorted(n for n in called if not callable(getattr(Api, n, None)) or n.startswith("_"))
    assert not missing, missing


def test_waveform_cache_keeps_only_recent_tracks(api, tmp_path, monkeypatch):
    from encolibmg.webui.api import sync

    monkeypatch.setattr(sync, "waveform", lambda path, channel: {"peaks": [0.5], "path": str(path)})
    files = []
    for n in range(sync.PEAK_CACHE + 3):
        f = tmp_path / f"{n}.mp3"
        f.write_bytes(b"x")
        files.append(f)
        api._peaks_for(f, 1)
    assert len(api._peaks) == sync.PEAK_CACHE
    assert f"{files[0]}:1" not in api._peaks and f"{files[-1]}:1" in api._peaks
