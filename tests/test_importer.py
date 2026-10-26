import subprocess
import zipfile

import pytest

from encolibmg.library import importer
from encolibmg.library.importer import clean_title, import_item, infer_name, mark_existing, scan_source
from encolibmg.library import Library
from encolibmg.lyrics.lrclib import LyricsCandidate
from encolibmg.library.tags import write_tags


def sine(path, seconds=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={seconds}",
                    str(path)], check=True)
    return path


@pytest.mark.parametrize("raw,clean", [
    ("01 - Bohemian Rhapsody", "Bohemian Rhapsody"),
    ("07. Hello", "Hello"),
    ("03 Hello", "Hello"),
    ("50 Cent", "50 Cent"),
    ("99 Luftballons", "99 Luftballons"),
    ("SC8113-01 - Hello", "Hello"),
    ("Hello (Official Audio)", "Hello"),
    ("Hello [Karaoke Version]", "Hello"),
    ("Hello (Lyrics)", "Hello"),
    ("Hello (Live)", "Hello (Live)"),
    ("Águas_de_Março", "Águas de Março"),
])
def test_clean_title(raw, clean):
    assert clean_title(raw) == clean


def test_infer_from_tags(tmp_path):
    f = sine(tmp_path / "track01.mp3")
    write_tags(f, "Queen", "Bohemian Rhapsody")
    assert infer_name(f, tmp_path) == ("Queen", "Bohemian Rhapsody")


def test_infer_from_filename_and_folder(tmp_path):
    a = tmp_path / "02 - Adele - Hello (Official Video).mp4"
    a.write_bytes(b"")
    assert infer_name(a, tmp_path) == ("Adele", "Hello")
    b = tmp_path / "Queen" / "05 - Love of My Life.flac"
    b.parent.mkdir()
    b.write_bytes(b"")
    assert infer_name(b, tmp_path) == ("Queen", "Love of My Life")
    c = tmp_path / "Solo.ogg"
    c.write_bytes(b"")
    assert infer_name(c, tmp_path) == ("Desconhecido", "Solo")


def test_scan_pairs_cdg_case_insensitive_and_zip(tmp_path):
    src = tmp_path / "src"
    sine(src / "ABBA - Waterloo.MP3")
    (src / "abba - waterloo.cdg").write_bytes(b"cdg")
    sine(src / "Adele - Hello.flac")
    (src / "Adele - Hello.lrc").write_text("[00:01.00]Hello", encoding="utf-8")
    sine(src / "Lone - Audio.mp3")
    (src / "Only - Lyrics.lrc").write_text("x")
    zpath = src / "pack.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Toto - Africa.mp3", (src / "Lone - Audio.mp3").read_bytes())
        z.writestr("Toto - Africa.cdg", b"cdg")
        z.writestr("../evil.mp3", b"x")
    items = scan_source(src, tmp_path / "tmp")
    got = sorted((i.artist, i.title, i.kind, len(i.companions)) for i in items)
    assert got == [("ABBA", "Waterloo", "cdg", 1), ("Adele", "Hello", "audio_lrc", 1),
                   ("Lone", "Audio", "audio", 0), ("Toto", "Africa", "cdg", 1)]
    assert not (tmp_path / "evil.mp3").exists()
    assert sorted(p.name for p in src.iterdir()) == sorted([  # preview never changes the source
        "ABBA - Waterloo.MP3", "abba - waterloo.cdg", "Adele - Hello.flac", "Adele - Hello.lrc",
        "Lone - Audio.mp3", "Only - Lyrics.lrc", "pack.zip"])


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


def lib_files(lib):
    return sorted(p.name for p in lib.path.iterdir() if p.name != "manifest.json")


def test_import_copy_converts_and_does_not_overwrite(lib, tmp_path):
    src = tmp_path / "src"
    sine(src / "ABBA - Waterloo.mp3")
    (src / "ABBA - Waterloo.cdg").write_bytes(b"cdg")
    sine(src / "Adele - Hello.flac")
    (src / "Adele - Hello.lrc").write_text("[offset:500]\n[00:01.00]Hello", encoding="utf-8")
    items = scan_source(src, tmp_path / "tmp")
    results = [import_item(lib, i) for i in items]
    assert results == ["imported:cdg", "imported:audio_lrc"]
    assert lib_files(lib) == ["ABBA - Waterloo.cdg", "ABBA - Waterloo.mp3",
                              "Adele - Hello.lrc", "Adele - Hello.mp3"]
    assert (lib.path / "Adele - Hello.lrc").read_text(encoding="utf-8") == "[00:00.50] Hello\n"
    assert (src / "Adele - Hello.flac").exists()  # copy mode keeps the source
    # second import of the same folder: nothing new
    again = scan_source(src, tmp_path / "tmp2")
    mark_existing(lib, again)
    assert [i.status for i in again] == ["exists", "exists"]
    assert [import_item(lib, i) for i in again] == ["exists", "exists"]


def test_import_audio_without_lyrics_is_skipped(lib, tmp_path):
    sine(tmp_path / "src" / "Lone - Audio.mp3")
    item = scan_source(tmp_path / "src", tmp_path / "tmp")[0]
    assert import_item(lib, item, search=lambda q: []) == "no_lyrics"
    assert lib_files(lib) == []


def test_import_audio_finds_lyrics(lib, tmp_path):
    sine(tmp_path / "src" / "Lone - Audio.mp3", seconds=3)
    item = scan_source(tmp_path / "src", tmp_path / "tmp")[0]
    cand = LyricsCandidate(1, "Lone", "Audio", "", 3.2, "[00:01.0]la", None)
    assert import_item(lib, item, search=lambda q: [cand]) == "imported:audio_lrc"
    assert lib_files(lib) == ["Lone - Audio.lrc", "Lone - Audio.mp3"]


def test_import_move_trashes_source(lib, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(importer, "send2trash", trashed.append)
    sine(tmp_path / "src" / "Adele - Hello.mp3")
    (tmp_path / "src" / "Adele - Hello.lrc").write_text("[00:01.00]x", encoding="utf-8")
    item = scan_source(tmp_path / "src", tmp_path / "tmp")[0]
    import_item(lib, item, move=True)
    assert sorted(trashed) == sorted([str(item.main), str(item.companions[0])])


def test_import_multiplex_uses_local_pipeline(lib, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(importer.pipeline, "track_from_local",
                        lambda lib, audio, a, t, lrc, p, c: calls.append((audio.name, a, t)))
    sine(tmp_path / "src" / "Adele - Hello.flac")
    (tmp_path / "src" / "Adele - Hello.lrc").write_text("[00:01.00]x", encoding="utf-8")
    item = scan_source(tmp_path / "src", tmp_path / "tmp")[0]
    assert import_item(lib, item, make_multiplex=True) == "imported:multiplex"
    assert calls == [("Adele - Hello.flac", "Adele", "Hello")]


def test_duplicates_inside_source_are_flagged(lib, tmp_path):
    sine(tmp_path / "src" / "a" / "Adele - Hello.mp4")
    sine(tmp_path / "src" / "b" / "Adele - Hello.mp4")
    items = scan_source(tmp_path / "src", tmp_path / "tmp")
    mark_existing(lib, items)
    assert [i.status for i in items] == ["", "duplicate"]


def test_status_text_in_both_languages():
    from encolibmg.core import i18n
    from encolibmg.library.importer import status_text

    assert status_text("imported:cdg") == "importada (Áudio + CDG)"
    assert status_text("exists") == "já existe"
    assert status_text("error:disco cheio") == "✖ disco cheio"
    assert status_text("") == ""
    i18n.set_language("en")
    assert status_text("imported:audio_lrc") == "imported (Audio + LRC)"
    assert status_text("no_lyrics") == "no lyrics (not imported)"
