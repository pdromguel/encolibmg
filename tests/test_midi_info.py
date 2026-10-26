import json

import mido

from encolibmg.library import checker
from encolibmg.library.importer import infer_name
from encolibmg.library import Library
from encolibmg.library.manifest import FLAGS, ensure_additional, flag_value, set_flag
from encolibmg.library.midi_info import decode_text, midi_has_lyrics, midi_names


def kar(path, texts: list[bytes], kind="text"):
    """Writes raw text bytes (any encoding) like real .kar files do."""
    mid = mido.MidiFile(charset="latin-1")
    track = mido.MidiTrack()
    for raw in texts:
        track.append(mido.MetaMessage(kind, text=raw.decode("latin-1")))
    mid.tracks.append(track)
    mid.save(str(path))
    return path


LYRICS = [b"\\La", b"la ", b"one ", b"two ", b"three ", b"four"]  # filler lyric events (placeholder words)


def test_decode_text_encodings():
    assert decode_text("Ação".encode("utf-8")) == "Ação"
    assert decode_text("君の名は".encode("cp932")) == "君の名は"
    assert decode_text("Coração".encode("cp1252")) == "Coração"  # also valid Shift-JIS bytes
    assert decode_text("桜".encode("cp932")) == "桜"
    assert decode_text("Ação Ç".encode("cp1252")) == "Ação Ç"


def test_kar_headers_title_then_artist(tmp_path):
    p = kar(tmp_path / "x.kar", [b"@KMIDI KARAOKE FILE", b"@THello", b"@TAdele", b"@T(c) 2015"] + LYRICS)
    assert midi_names(p) == ("Adele", "Hello")
    assert midi_has_lyrics(p)


def test_kar_shift_jis_title(tmp_path):
    p = kar(tmp_path / "j.kar", ["@T君の名は".encode("cp932"), "@TRADWIMPS".encode("cp932")] + LYRICS)
    assert midi_names(p) == ("RADWIMPS", "君の名は")


def test_encore_style_metadata(tmp_path):
    p = kar(tmp_path / "g.mid", ["{#TITLE=Águas}".encode(), "{#ARTIST=Elis}".encode()] + LYRICS, kind="lyrics")
    assert midi_names(p) == ("Elis", "Águas")


def test_midi_without_lyrics(tmp_path):
    p = kar(tmp_path / "n.mid", [b"@TInstrumental"])
    assert not midi_has_lyrics(p)
    assert midi_names(p) == (None, "Instrumental")


def test_importer_uses_kar_names(tmp_path):
    p = kar(tmp_path / "track07.kar", [b"@THello", b"@TAdele"] + LYRICS)
    assert infer_name(p, tmp_path) == ("Adele", "Hello")
    q = kar(tmp_path / "Adele - qualquer.kar", [b"@THello"] + LYRICS)  # title only: artist from file name
    assert infer_name(q, tmp_path) == ("Adele", "Hello")


def test_checker_midi_without_lyrics_and_incomplete_manifest(tmp_path):
    lib = Library.create(tmp_path / "L", "t")
    (lib.path / "manifest.json").write_text(json.dumps({"title": "old"}), encoding="utf-8")
    kar(lib.path / "A - B.mid", [b"@TB"])
    issues = {i.kind: i for i in checker.check(lib)}
    assert set(issues) == {"midi_no_lyrics", "manifest_incomplete"}
    assert not issues["midi_no_lyrics"].fixable
    checker.fix(lib, issues["manifest_incomplete"])
    data = json.loads((lib.path / "manifest.json").read_text(encoding="utf-8"))
    assert data == {"title": "old", "additionalContents": {"bgvCategories": [], "bumperImages": []}}


def test_new_library_has_additional_contents(tmp_path):
    lib = Library.create(tmp_path / "L", "t")
    data = json.loads((lib.path / "manifest.json").read_text(encoding="utf-8"))
    assert not ensure_additional(data)


def test_default_on_flags_store_false():
    data = {}
    assert flag_value(data, "enableMtvCategory") is True       # Encore's default
    set_flag(data, "enableMtvCategory", False)
    assert data == {"flags": {"enableMtvCategory": False}}
    set_flag(data, "enableMtvCategory", True)
    assert data == {}
    set_flag(data, "flipArtistTitle", True)
    assert data == {"flags": {"flipArtistTitle": True}}
    assert [k for k, _, d in FLAGS if d] == ["enableMtvCategory", "enableDefaultCategories"]
