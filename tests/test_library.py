import json

import pytest

from encolibmg.library import Library, LibraryError, base_name


def test_base_name_strips_invalid():
    assert base_name("AC/DC", "T.N.T.") == "AC-DC - T.N.T"


def test_base_name_collapses_spaces_and_quotes():
    assert base_name('  Queen ', 'Bohemian  "Rhapsody"?') == "Queen - Bohemian 'Rhapsody'"


def test_base_name_keeps_unicode():
    assert base_name("宇多田ヒカル", "First Love") == "宇多田ヒカル - First Love"
    assert base_name("Tom Jobim", "Águas de Março") == "Tom Jobim - Águas de Março"


def test_base_name_max_len():
    name = base_name("A" * 100, "B" * 100)
    assert len(name) <= 150
    assert not name.endswith((" ", "."))


def test_create_writes_manifest(tmp_path):
    lib = Library.create(tmp_path / "EncoreLibrary", "Minha Biblioteca")
    data = json.loads((lib.path / "manifest.json").read_text(encoding="utf-8"))
    assert data["title"] == "Minha Biblioteca"


def test_create_keeps_existing_manifest(tmp_path):
    folder = tmp_path / "EncoreLibrary"
    folder.mkdir()
    (folder / "manifest.json").write_text('{"title": "Antiga"}', encoding="utf-8")
    Library.create(folder, "Nova")
    assert json.loads((folder / "manifest.json").read_text())["title"] == "Antiga"


def test_open_requires_manifest(tmp_path):
    with pytest.raises(LibraryError):
        Library.open(tmp_path)


def _touch(folder, *names):
    for n in names:
        (folder / n).write_bytes(b"")


def test_scan_kinds(tmp_path):
    lib = Library.create(tmp_path / "lib", "x")
    _touch(
        lib.path,
        "Queen - Bohemian Rhapsody.multiplexed.mp3",
        "Queen - Bohemian Rhapsody.lrc",
        "ABBA - Waterloo.mp3",
        "ABBA - Waterloo.lrc",
        "Adele - Hello.mp4",
        "Old - Song.kar",
        "Lost - Audio.mp3",
    )
    kinds = {t.base: t.kind for t in lib.scan()}
    assert kinds == {
        "Queen - Bohemian Rhapsody": "multiplex_lrc",
        "ABBA - Waterloo": "audio_lrc",
        "Adele - Hello": "mtv",
        "Old - Song": "midi",
        "Lost - Audio": "orphan",
    }
    queen = next(t for t in lib.scan() if t.artist == "Queen")
    assert queen.title == "Bohemian Rhapsody"
    assert len(queen.files) == 2


def test_scan_ignores_manifest_and_songdb(tmp_path):
    lib = Library.create(tmp_path / "lib", "x")
    _touch(lib.path, "songdb.json")
    assert lib.scan() == []


def test_exists_case_insensitive(tmp_path):
    lib = Library.create(tmp_path / "lib", "x")
    _touch(lib.path, "Queen - Bohemian Rhapsody.multiplexed.mp3")
    assert lib.exists("queen - bohemian rhapsody")
    assert not lib.exists("Queen - Other")


def test_remove_deletes_all_files(tmp_path, monkeypatch):
    removed = []
    monkeypatch.setattr("encolibmg.library.model.send2trash", lambda p: removed.append(p))
    lib = Library.create(tmp_path / "lib", "x")
    _touch(lib.path, "A - B.multiplexed.mp3", "A - B.lrc", "C - D.mp4")
    track = next(t for t in lib.scan() if t.base == "A - B")
    lib.remove(track)
    assert sorted(removed) == sorted(str(f) for f in track.files)


def _mp3(path):
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=d=1", str(path)], check=True)


def test_rename_track_renames_siblings_and_tags(tmp_path):
    from mutagen.easyid3 import EasyID3

    lib = Library.create(tmp_path / "lib", "x")
    _mp3(lib.path / "queen - bohemian rhapsody.multiplexed.mp3")
    _touch(lib.path, "queen - bohemian rhapsody.lrc", "queen - bohemian rhapsody.mp4")
    track = lib.scan()[0]
    new = lib.rename_track(track, "Queen", "Bohemian Rhapsody")
    assert sorted(f.name for f in new.files) == [
        "Queen - Bohemian Rhapsody.lrc", "Queen - Bohemian Rhapsody.mp4",
        "Queen - Bohemian Rhapsody.multiplexed.mp3"]
    assert sorted(p.name for p in lib.path.iterdir()) == sorted([f.name for f in new.files] + ["manifest.json"])
    tags = EasyID3(lib.path / "Queen - Bohemian Rhapsody.multiplexed.mp3")
    assert tags["artist"] == ["Queen"] and tags["title"] == ["Bohemian Rhapsody"]


def test_rename_track_collision(tmp_path):
    from encolibmg.core.errors import AlreadyExists

    lib = Library.create(tmp_path / "lib", "x")
    _touch(lib.path, "A - B.mp4", "C - D.mp4")
    a = next(t for t in lib.scan() if t.base == "A - B")
    with pytest.raises(AlreadyExists):
        lib.rename_track(a, "c", "d")
    assert (lib.path / "A - B.mp4").exists()


def test_kind_label_with_clip(tmp_path):
    from encolibmg.library import kind_label

    lib = Library.create(tmp_path / "lib", "x")
    _touch(lib.path, "A - B.multiplexed.mp3", "A - B.lrc", "A - B.mp4", "C - D.mp4")
    labels = {t.base: kind_label(t) for t in lib.scan()}
    assert labels == {"A - B": "Multiplex + LRC + clipe", "C - D": "MTV"}


def test_manifest_preserves_unknown_keys(tmp_path):
    from encolibmg.library.manifest import read_manifest, write_manifest

    lib = Library.create(tmp_path / "lib", "x")
    data = read_manifest(lib.path)
    data["additionalContents"] = {"soundFont": "gm.sf2"}
    write_manifest(lib.path, data)
    data = read_manifest(lib.path)
    data["title"] = "Nova"
    data.setdefault("flags", {})["enableMtvCategory"] = True
    write_manifest(lib.path, data)
    final = read_manifest(lib.path)
    assert final["additionalContents"] == {"soundFont": "gm.sf2"}
    assert final["flags"] == {"enableMtvCategory": True}
    assert lib.title == "Nova"


def test_app_dir_migrates_old_name(tmp_path, monkeypatch):
    from encolibmg.core.paths import app_dir

    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    old = tmp_path / "ad" / "EncoreLibraryManager"
    (old / "backups").mkdir(parents=True)
    (old / "config.json").write_text('{"library": "D:/EncoreLibrary"}', encoding="utf-8")
    d = app_dir()
    assert d.name == "EncoLibMG"
    assert (d / "config.json").read_text(encoding="utf-8") == '{"library": "D:/EncoreLibrary"}'
    assert (d / "backups").is_dir() and not old.exists()


def test_inside_rejects_escapes(tmp_path):
    from encolibmg.library import inside

    lib = Library.create(tmp_path / "lib", "x")
    (lib.path / "BGV").mkdir()
    assert inside(lib.path, "BGV") == (lib.path / "BGV").resolve()
    assert inside(lib.path, "") == lib.path.resolve()
    for bad in ("../x", "BGV/../../x", str(tmp_path / "other"), "C:/Windows", r"..\..\x"):
        with pytest.raises(ValueError):
            inside(lib.path, bad)
