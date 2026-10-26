import pytest

from encolibmg.queue_sources import parse_csv, parse_csv_text, parse_list, playlist_entries, split_name, tidy_title


def test_tidy_title():
    assert tidy_title("Paper Lanterns - Remastered 2011") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns - 2011 Remaster") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns (feat. Someone)") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns - Radio Edit") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns (Official Video)") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns - Live") == "Paper Lanterns - Live"  # a different song version: kept


def test_parse_list():
    text = "Neon Harbor - Paper Lanterns\n\n# a comment\n2. The Quiet Owls – Late Train Home\nCidade Azul\n"
    assert parse_list(text) == [
        {"artist": "Neon Harbor", "title": "Paper Lanterns"},
        {"artist": "The Quiet Owls", "title": "Late Train Home"},
        {"artist": "", "title": "Cidade Azul"},
    ]


def test_parse_exportify_csv(tmp_path):
    f = tmp_path / "liked.csv"
    f.write_text('"Track URI","Track Name","Artist Name(s)","Album Name","Duration (ms)"\n'
                 '"spotify:track:1","Paper Lanterns - Remastered 2011","Neon Harbor, Guest","Harbor","201500"\n'
                 '"spotify:track:2","Cidade Azul","Sol de Março","Azul","185000"\n', encoding="utf-8-sig")
    assert parse_csv(f) == [
        {"artist": "Neon Harbor", "title": "Paper Lanterns", "duration": 201.5},
        {"artist": "Sol de Março", "title": "Cidade Azul", "duration": 185.0},
    ]


def test_parse_simple_csv_semicolons_and_errors():
    assert parse_csv_text("artista;título\nSol de Março;Cidade Azul\n") == [
        {"artist": "Sol de Março", "title": "Cidade Azul"}]
    with pytest.raises(ValueError):
        parse_csv_text("foo,bar\n1,2\n")


def test_playlist_entries_uses_channel_as_artist():
    info = {"entries": [
        {"title": "Neon Harbor - Paper Lanterns (Official Video)", "channel": "NeonHarborVEVO"},
        {"title": "Late Train Home", "channel": "The Quiet Owls - Topic"},
        {"title": "[Deleted video]", "channel": None},
        None,
    ]}
    assert playlist_entries("https://www.youtube.com/playlist?list=x", extract=lambda u: info) == [
        {"artist": "Neon Harbor", "title": "Paper Lanterns"},
        {"artist": "The Quiet Owls", "title": "Late Train Home"},
    ]
    with pytest.raises(ValueError):
        playlist_entries("u", extract=lambda u: {"entries": []})


def test_split_name_keeps_dashes_in_words():
    assert split_name("Jay-Z - Song") == {"artist": "Jay-Z", "title": "Song"}


def test_video_tags_go_but_real_parentheses_stay():
    assert tidy_title("I Wanna Dance (Who Loves Me) (Official 4K Video)") == "I Wanna Dance (Who Loves Me)"
    assert tidy_title("Paper Lanterns [Lyric Video]") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns (Remastered 2009)") == "Paper Lanterns"
    assert tidy_title("Paper Lanterns (Part II)") == "Paper Lanterns (Part II)"
