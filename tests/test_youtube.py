from encolibmg import youtube
from encolibmg.youtube import VideoCandidate, pick_audio


def v(title, dur, id_="x"):
    return VideoCandidate(id=id_, title=title, channel="c", duration=dur, url=f"https://youtu.be/{id_}")


def test_pick_closest_duration():
    cands = [v("Song (Official Audio)", 200, "a"), v("Song", 203, "b"), v("Song HQ", 199.5, "c")]
    assert pick_audio(cands, 199).id == "c"


def test_pick_ignores_far_durations():
    assert pick_audio([v("Song", 220)], 200) is None


def test_pick_ignores_unwanted_versions():
    cands = [v("Song (Karaoke Version)", 200, "k"), v("Song LIVE at Wembley", 200, "l"),
             v("Song slowed + reverb", 200, "s"), v("Song", 205, "ok")]
    assert pick_audio(cands, 200).id == "ok"


def test_pick_allows_word_present_in_query():
    assert pick_audio([v("Song (Live)", 200, "l")], 200, query="Song live").id == "l"


def test_pick_skips_missing_duration():
    assert pick_audio([v("Song", None)], 200) is None


def test_search_maps_entries(monkeypatch):
    seen = {}

    class FakeYDL:
        def __init__(self, opts):
            seen["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, q, download=False):
            seen["q"] = q
            return {"entries": [
                {"id": "abc", "title": "T", "channel": "C", "duration": 180.0},
                None,
                {"id": "def", "title": "U", "uploader": "D", "duration": None},
            ]}

    monkeypatch.setattr(youtube, "YoutubeDL", FakeYDL)
    res = youtube.search("Adele Hello audio", n=5)
    assert seen["q"] == "ytsearch5:Adele Hello audio"
    assert seen["opts"]["extract_flat"]
    assert [(r.id, r.channel, r.duration) for r in res] == [("abc", "C", 180.0), ("def", "D", None)]
    assert res[0].url == "https://www.youtube.com/watch?v=abc"
