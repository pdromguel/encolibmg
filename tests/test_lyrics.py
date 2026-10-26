from encolibmg.lyrics import lrclib
from encolibmg.lyrics.normalize import normalize_lrc


def test_time_formats():
    src = "[01:02]a\n[01:02.3]b\n[01:02.34]c\n[01:02.345]d\n"
    assert normalize_lrc(src) == "[01:02.00] a\n[01:02.30] b\n[01:02.34] c\n[01:02.34] d\n"


def test_multiple_stamps_split_and_sorted():
    src = "[00:20.00][00:05.00]refrão\n[00:10.00]verso\n"
    assert normalize_lrc(src) == "[00:05.00] refrão\n[00:10.00] verso\n[00:20.00] refrão\n"


def test_offset_tag_and_param():
    # [offset:+500] means lyrics appear 500 ms earlier
    src = "[offset:+500]\n[00:10.00]oi\n"
    assert normalize_lrc(src) == "[00:09.50] oi\n"
    assert normalize_lrc("[00:10.00]oi", offset_ms=1000) == "[00:09.00] oi\n"


def test_negative_time_clamped():
    assert normalize_lrc("[00:00.20]oi", offset_ms=500) == "[00:00.00] oi\n"


def test_strips_metadata_word_stamps_empty_lines_bom_crlf():
    src = "﻿[ar:Band]\r\n[ti:X]\r\n[00:01.00]<00:01.00>Some <00:01.50>words\r\n[00:02.00]\r\n[00:03.00]  here  \r\n"
    assert normalize_lrc(src) == "[00:01.00] Some words\n[00:03.00] here\n"


def test_minutes_over_99():
    assert normalize_lrc("[100:00.00]x") == "[100:00.00] x\n"


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return FakeResp(self.data)


RESULTS = [
    {"id": 1, "trackName": "Hello", "artistName": "Adele", "albumName": "25", "duration": 295.0,
     "instrumental": False, "plainLyrics": "Hello", "syncedLyrics": None},
    {"id": 2, "trackName": "Hello", "artistName": "Adele", "albumName": "25", "duration": 295.5,
     "instrumental": False, "plainLyrics": "Hello", "syncedLyrics": "[00:01.00]Hello"},
    {"id": 3, "trackName": "Hello (Instr.)", "artistName": "X", "albumName": None, "duration": 200,
     "instrumental": True, "plainLyrics": None, "syncedLyrics": None},
]


def test_search_maps_and_sorts_synced_first():
    s = FakeSession(RESULTS)
    res = lrclib.search("Adele Hello", session=s)
    assert [c.id for c in res] == [2, 1]  # instrumental dropped, synced first
    c = res[0]
    assert (c.artist, c.title, c.album, c.duration) == ("Adele", "Hello", "25", 295.5)
    assert c.synced == "[00:01.00]Hello"
    url, params, headers = s.calls[0]
    assert url.endswith("/api/search") and params == {"q": "Adele Hello"}
    assert "EncoLibMG" in headers["User-Agent"]


def test_search_prefers_exact_artist_and_title():
    def item(id_, artist, title):
        return {"id": id_, "trackName": title, "artistName": artist, "albumName": "", "duration": 1,
                "syncedLyrics": "[00:01.00]x"}

    s = FakeSession([item(1, "Adele, Adele", "Hello"), item(2, "Adele", "Hello [Hello, 2015]"),
                     item(3, "adele", "hello")])
    assert [c.id for c in lrclib.search("Adele - Hello", session=s)] == [3, 2, 1]


def test_search_splits_artist_title_query():
    s = FakeSession([])
    lrclib.search("Adele - Hello", session=s)
    assert s.calls[0][1] == {"track_name": "Hello", "artist_name": "Adele"}
    assert s.calls[1][1] == {"q": "Adele Hello"}  # fuzzy fallback when nothing found
