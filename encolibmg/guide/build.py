"""Multiplex track → X.guide.mid next to it."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from threading import Event

from encolibmg.audio.player import SR, decode
from encolibmg.errors import Cancelled
from encolibmg.guide.align import MMSAligner, align_lyrics, line_windows
from encolibmg.guide.melody import detect_notes
from encolibmg.guide.midi import write_guide
from encolibmg.library import Library, Track
from encolibmg.lyrics.match import read_lrc
from encolibmg.lyrics.sync import parse_lrc
from encolibmg.paths import backup_file

log = logging.getLogger(__name__)
NOTE_WINDOW_PAD = 0.5  # s around each lyric line where melody notes are kept


@lru_cache(maxsize=1)
def default_aligner() -> MMSAligner:
    return MMSAligner()  # ~1.2 GB model: load once per session


def guide_path(lib: Library, track: Track):
    return lib.path / f"{track.base}.guide.mid"


def build_guide(lib: Library, track: Track, on_progress=None, cancel: Event | None = None,
                aligner=None, f0_fn=None) -> tuple[Track, dict]:
    """Returns the refreshed track and alignment stats {'aligned', 'fallback', 'notes'}."""
    progress = on_progress or (lambda step, frac=None: None)
    mp3 = next((f for f in track.files if ".multiplexed." in f.name.lower()), None)
    lrc = track.file_with({".lrc"})
    if mp3 is None or lrc is None:
        raise ValueError("O guia precisa de uma faixa Multiplex com .lrc.")

    def check():
        if cancel is not None and cancel.is_set():
            raise Cancelled()

    progress("lendo áudio", None)
    vocals = decode(mp3)[:, 1]  # right channel = vocals
    lines = parse_lrc(read_lrc(lrc))
    duration = len(vocals) / SR
    windows = [(a - NOTE_WINDOW_PAD, b + NOTE_WINDOW_PAD) for a, b in line_windows(lines, duration)]
    check()

    progress("analisando melodia", None)
    notes = detect_notes(vocals, SR, windows, f0_fn=f0_fn)
    check()

    progress("alinhando letra", 0.0)
    words, stats = align_lyrics(vocals, SR, lines, [n.start for n in notes], aligner or default_aligner(),
                                on_progress=lambda f: progress("alinhando letra", f))
    check()

    progress("salvando guia", None)
    dest = guide_path(lib, track)
    tmp = dest.with_name(f".{dest.name}.tmp")
    write_guide(tmp, notes, words, track.title, track.artist)
    if dest.exists():
        backup_file(dest)
    os.replace(tmp, dest)
    stats = {**stats, "notes": len(notes)}
    log.info("guide for %s: %s", track.base, stats)
    return next(t for t in lib.scan() if t.base.lower() == track.base.lower()), stats
