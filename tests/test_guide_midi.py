import mido
import pytest

from encolibmg.guide.align import Word
from encolibmg.guide.melody import Note
from encolibmg.guide.midi import read_guide, write_guide

NOTES = [Note(1.0, 1.5, 60), Note(1.5, 2.25, 62), Note(4.0, 5.0, 64)]
LINES = [[Word(1.0, "Is"), Word(1.5, "this"), Word(2.0, "real?")],
         [],
         [Word(4.0, "Ação"), Word(4.5, "é"), Word(4.8, "vida")]]


def test_roundtrip(tmp_path):
    p = write_guide(tmp_path / "X.guide.mid", NOTES, LINES, "Título", "Artista")
    g = read_guide(p)
    assert g.notes == NOTES
    assert g.lyrics == [(1.0, "Is "), (1.5, "this "), (2.0, "real? "),
                        (4.0, "/Ação "), (4.5, "é "), (4.8, "vida ")]
    assert g.vocal_channel == 1
    assert g.channel_volume == 0


def test_file_shape_matches_encore_expectations(tmp_path):
    p = write_guide(tmp_path / "X.guide.mid", NOTES, LINES, "Título", "Artista")
    mid = mido.MidiFile(str(p), charset="utf-8")
    assert mid.ticks_per_beat == 480 and mid.type == 1
    assert any(m.type == "set_tempo" and m.tempo == 500_000 for m in mid.tracks[0])
    guide = mid.tracks[1]
    lyric_texts = [m.text for m in guide if m.type == "lyrics"]
    assert lyric_texts[:2] == ["{#TITLE=Título}", "{#ARTIST=Artista}"]  # same track as the lyrics
    assert sum(1 for t in lyric_texts if not t.startswith("{#")) > 5
    assert any(m.type == "program_change" and m.program == 73 for m in guide)
    # raw bytes are UTF-8 so Encore's detectEncoding sees UTF-8
    assert "Ação".encode("utf-8") in p.read_bytes()


def test_japanese_furigana_and_no_spaces(tmp_path):
    lines = [[Word(1.0, "君"), Word(1.3, "の"), Word(1.5, "名"), Word(1.7, "は")],
             [Word(3.0, "夢"), Word(3.4, "を")]]
    g = read_guide(write_guide(tmp_path / "j.guide.mid", NOTES, lines, "t", "a"))
    assert [t for _, t in g.lyrics] == ["君[きみ]", "の", "名[な]", "は", "/夢[ゆめ]", "を"]


def test_too_few_words_is_refused(tmp_path):
    with pytest.raises(ValueError):
        write_guide(tmp_path / "x.guide.mid", NOTES, [[Word(1.0, "oh"), Word(2.0, "yeah")]], "t", "a")


def test_note_off_before_note_on_at_same_tick(tmp_path):
    g = read_guide(write_guide(tmp_path / "x.guide.mid", [Note(1.0, 1.5, 60), Note(1.5, 2.0, 60)], LINES, "t", "a"))
    assert g.notes == [Note(1.0, 1.5, 60), Note(1.5, 2.0, 60)]
