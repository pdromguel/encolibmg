"""Add screen: search synced lyrics, download a full track or a karaoke video (MTV)."""

from __future__ import annotations

from encolibmg import pipeline, youtube
from encolibmg.i18n import t as tr
from encolibmg.lyrics import lrclib
from encolibmg.webui import views
from encolibmg.webui.api.core import ApiCore, api


class AddApi(ApiCore):
    def _init_areas(self):
        super()._init_areas()
        self._lyrics: dict[int, lrclib.LyricsCandidate] = {}
        self._videos: dict[str, youtube.VideoCandidate] = {}  # also used by clips and background videos

    @api
    def search_lyrics(self, query: str):
        res = lrclib.search(query)
        self._lyrics.update({c.id: c for c in res})
        return [views.lyrics_dict(c) for c in res]

    @api
    def add_song(self, lyrics_id: int, make_guide: bool = True):
        lib, cand = self._need(), self._lyrics[int(lyrics_id)]
        return self._job(f"{cand.artist} - {cand.title}", lambda p, c: views.track_dict(
            pipeline.add_song(lib, cand, p, c, make_guide=make_guide)), "add")

    @api
    def find_mtv(self, artist: str, title: str):
        vids = pipeline.find_mtv(artist, title)
        self._videos.update({v.id: v for v in vids})
        return [views.video_dict(v) for v in vids]

    @api
    def add_mtv(self, artist: str, title: str, video_id: str):
        lib, v = self._need(), self._videos[video_id]
        return self._job(tr("job.mtv", artist=artist, title=title), lambda p, c: views.track_dict(
            pipeline.add_mtv(lib, artist, title, v, p, c)), "add")
