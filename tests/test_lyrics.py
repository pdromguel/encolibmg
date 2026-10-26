import pytest

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


def _cand(i, artist, title, duration=200.0, synced=True):
    from encolibmg.lyrics.lrclib import LyricsCandidate

    return LyricsCandidate(i, artist, title, "", duration, "[00:01.00] la\n" if synced else None, None)


def test_find_by_name_needs_a_real_match():
    from encolibmg.lyrics.match import find_by_name

    cands = [_cand(1, "Someone Else", "Paper Lanterns"),          # wrong artist
             _cand(2, "Neon Harbor", "Paper Lanterns", synced=False),
             _cand(3, "Neon Harbor", "Paper Lanterns (Live)"),
             _cand(4, "Neon Harbor", "Paper Lanterns")]
    pick = find_by_name("Neon Harbor", "Paper Lanterns", search=lambda q: cands)
    assert pick.id == 4  # synced, right artist, not the live version
    assert find_by_name("Neon Harbor", "Late Train Home", search=lambda q: cands) is None


def test_find_by_name_live_when_asked_and_duration():
    from encolibmg.lyrics.match import find_by_name

    cands = [_cand(3, "Neon Harbor", "Paper Lanterns (Live)", 260.0), _cand(4, "Neon Harbor", "Paper Lanterns", 200.0)]
    assert find_by_name("Neon Harbor", "Paper Lanterns (Live)", search=lambda q: cands).id == 3
    assert find_by_name("Neon Harbor", "Paper Lanterns", duration=259.0, search=lambda q: cands).id == 3
    assert find_by_name("Neon Harbor", "Paper Lanterns", duration=120.0, search=lambda q: cands) is None


def test_find_by_name_without_artist_and_with_accents():
    from encolibmg.lyrics.match import find_by_name

    cands = [_cand(5, "Sol de Março", "Cidade Azul"), _cand(6, "Sol de Março & Convidado", "Cidade Azul - Remastered")]
    assert find_by_name("", "Cidade Azul", search=lambda q: cands).id == 5
    assert find_by_name("sol de marco", "cidade azul", search=lambda q: cands).id == 5


class FlakySession:
    """Answers with the given HTTP statuses in turn (an exception class means a dropped connection)."""

    def __init__(self, statuses, data=()):
        self.statuses, self.data, self.calls = list(statuses), list(data), 0

    def get(self, url, params=None, headers=None, timeout=None):
        import requests

        self.calls += 1
        status = self.statuses.pop(0) if self.statuses else 200
        if isinstance(status, type):
            raise status("connection dropped")
        resp = requests.Response()
        resp.status_code, resp._content = status, b"[]"
        resp.json = lambda: self.data
        return resp


def test_lrclib_retries_short_outages(monkeypatch):
    import requests

    waits = []
    monkeypatch.setattr(lrclib.time, "sleep", waits.append)
    s = FlakySession([502, requests.ConnectionError], data=RESULTS)
    assert [c.id for c in lrclib.search("Adele Hello", session=s)] == [2, 1]
    assert s.calls == 3 and waits == list(lrclib.RETRY_WAITS)


def test_lrclib_busy_means_nothing_found(monkeypatch):
    """LRCLIB answers 503 'server is busy' for searches with no match: after one retry it's an empty result."""
    monkeypatch.setattr(lrclib.time, "sleep", lambda s: None)
    s = FlakySession([503, 503, 503, 503])
    assert lrclib.search("Zz - Made Up", session=s) == []
    assert s.calls == 4  # two tries for the field search, two for the free-text fallback
    assert lrclib.search("Adele Hello", session=FlakySession([503], data=RESULTS))  # a single 503 is retried


def test_lrclib_gives_a_clear_error_when_down(monkeypatch):
    import requests

    monkeypatch.setattr(lrclib.time, "sleep", lambda s: None)
    with pytest.raises(lrclib.LyricsUnavailable, match="502"):
        lrclib.search("Adele Hello", session=FlakySession([502, 502, 502]))
    with pytest.raises(lrclib.LyricsUnavailable, match="ConnectionError"):
        lrclib.search("Adele Hello", session=FlakySession([requests.ConnectionError] * 3))
    with pytest.raises(Exception) as e:  # a 404 is not retried
        lrclib.search("Adele Hello", session=FlakySession([404]))
    assert not isinstance(e.value, lrclib.LyricsUnavailable)


def test_find_by_name_prefers_the_common_version_without_a_duration():
    from encolibmg.lyrics.match import find_by_name

    cands = [_cand(1, "Neon Harbor", "Paper Lanterns", 510.0),   # an extended mix, listed first
             _cand(2, "Neon Harbor", "Paper Lanterns", 241.0),
             _cand(3, "Neon Harbor", "Paper Lanterns", 242.0),
             _cand(4, "Neon Harbor", "Paper Lanterns", 240.5)]
    assert find_by_name("Neon Harbor", "Paper Lanterns", search=lambda q: cands).duration in (240.5, 241.0, 242.0)
