"""Sync screen (vocal waveform + lyric timing, save/undo) and the guide preview."""

from __future__ import annotations

import shutil
from collections import OrderedDict
from pathlib import Path

import numpy as np

from encolibmg.audio.convert import duration as media_duration
from encolibmg.audio.decode import decode_mono
from encolibmg.guide.midi import read_guide
from encolibmg.core.i18n import t as tr
from encolibmg.library import AUDIO_EXTS, VIDEO_EXTS
from encolibmg.lyrics.match import read_lrc
from encolibmg.lyrics.sync import Line, format_lrc, parse_lrc, vocal_onset
from encolibmg.core.paths import backup_file, latest_backup
from encolibmg.webui.api.core import ApiCore, api

WAVE_SR = 8000      # the waveform only needs the envelope: mono 8 kHz is plenty
PEAK_RATE = 25      # waveform points per second (40 ms), enough for the 12 s zoom
PEAK_MAX = 15000
PEAK_CACHE = 8      # tracks kept in memory (each entry is ~a few hundred KB of JSON-ready floats)


def waveform(path: Path, channel: int) -> dict:
    """Normalized peaks + where the singing starts, from one channel (-1 = both)."""
    x = np.abs(decode_mono(path, channel, WAVE_SR))
    n = len(x)
    buckets = int(min(PEAK_MAX, max(1, round(n / WAVE_SR * PEAK_RATE))))
    edges = np.linspace(0, n, buckets + 1).astype(int)
    peaks = np.maximum.reduceat(x, edges[:-1]) if n else np.zeros(1)
    peaks = peaks / (peaks.max() or 1.0)
    return {"duration": n / WAVE_SR, "rate": buckets / (n / WAVE_SR) if n else PEAK_RATE,
            "peaks": [round(float(v), 3) for v in peaks], "onset": vocal_onset(x, WAVE_SR)}


class SyncApi(ApiCore):
    def _init_areas(self):
        super()._init_areas()
        self._peaks: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    def _peaks_for(self, path: Path, channel: int) -> dict:
        key, mtime = f"{path}:{channel}", path.stat().st_mtime
        hit = self._peaks.get(key)
        if hit and hit[0] == mtime:
            self._peaks.move_to_end(key)
            return hit[1]
        out = waveform(path, channel)
        self._peaks[key] = (mtime, out)
        while len(self._peaks) > PEAK_CACHE:
            self._peaks.popitem(last=False)
        return out

    @staticmethod
    def _lines(lrc: Path) -> list[dict]:
        return [{"ms": l.ms, "text": l.text} for l in parse_lrc(read_lrc(lrc))]

    @api
    def sync_load(self, base: str):
        t = self._track(base)
        lrc = t.file_with({".lrc"})
        if lrc is None:
            raise ValueError(tr("err.no_lrc"))
        mp = t.multiplex_file
        audio = mp or t.file_with(AUDIO_EXTS) or t.file_with(VIDEO_EXTS)
        info = self._peaks_for(audio, 1 if mp else -1)  # Multiplex: the right channel is the vocals
        return {"base": t.base, "artist": t.artist, "title": t.title, "audio": self._url(audio),
                "multiplexed": bool(mp), "has_guide": t.has_guide, "has_backup": latest_backup(lrc.name) is not None,
                "lines": self._lines(lrc), **info}

    @api
    def sync_save(self, base: str, lines: list[dict]):
        t = self._track(base)
        lrc = t.file_with({".lrc"})
        backup_file(lrc)
        lrc.write_text(format_lrc([Line(int(l["ms"]), str(l["text"])) for l in lines]), encoding="utf-8",
                       newline="\n")
        self._emit("library", {})
        return {"has_guide": t.has_guide, "lines": self._lines(lrc)}

    @api
    def sync_undo(self, base: str):
        lrc = self._track(base).file_with({".lrc"})
        bak = latest_backup(lrc.name)
        if bak is None:
            raise LookupError(tr("err.no_backup"))
        shutil.copy2(bak, lrc)
        bak.unlink()
        return {"lines": self._lines(lrc), "has_backup": latest_backup(lrc.name) is not None}

    # --- guide preview --------------------------------------------------------------------------
    @api
    def guide_load(self, base: str):
        t = self._track(base)
        gpath = next((f for f in t.files if ".guide." in f.name.lower() or ".melody." in f.name.lower()), None)
        if gpath is None:
            raise LookupError(tr("err.no_guide"))
        g = read_guide(gpath)
        mp = t.multiplex_file
        audio = mp or t.file_with(AUDIO_EXTS)
        return {"base": t.base, "artist": t.artist, "title": t.title, "audio": self._url(audio),
                "multiplexed": bool(mp), "duration": media_duration(audio) if audio else None,
                "notes": [[n.start, n.end, n.pitch] for n in g.notes],
                "lyrics": [[s, text] for s, text in g.lyrics]}
