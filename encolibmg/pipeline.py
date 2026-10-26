"""Glue: turns a lyrics choice (or a karaoke video) into files in the library.

Everything is built in a hidden temp folder inside the library (same drive,
so the final move is instant) and only moved to the root at the very end,
so a failure or cancel never leaves a half-made track behind.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from typing import Callable

from send2trash import send2trash

from encolibmg import youtube
from encolibmg.audio import ffmpeg
from encolibmg.audio.multiplex import make_multiplex
from encolibmg.audio.separate import separate
from encolibmg.core.errors import AlreadyExists, Cancelled, NoAudioMatch
from encolibmg.guide.build import build_guide
from encolibmg.library import AUDIO_EXTS, Library, Track, base_name
from encolibmg.lyrics.lrclib import LyricsCandidate
from encolibmg.lyrics.match import read_lrc
from encolibmg.lyrics.normalize import normalize_lrc
from encolibmg.library.tags import write_tags
from encolibmg.core.i18n import t

log = logging.getLogger(__name__)
Progress = Callable[[str, "float | None"], None]


def _noop(step, frac=None):
    pass


@contextmanager
def _workdir(lib: Library):
    d = Path(tempfile.mkdtemp(prefix=".encore-tmp-", dir=lib.path))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _check(cancel: Event | None):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _finish(lib: Library, files: list[Path], base: str) -> Track:
    for f in files:
        shutil.move(str(f), str(lib.path / f.name))
    return next(t for t in lib.scan() if t.base.lower() == base.lower())


def find_audio(artist: str, title: str, duration: float) -> youtube.VideoCandidate:
    for q in (f"{artist} {title} audio", f"{artist} {title}"):
        pick = youtube.pick_audio(youtube.search(q), duration, query=q)
        if pick:
            return pick
    raise NoAudioMatch(
        t("err.no_audio_match", duration=f"{int(duration // 60)}:{int(duration % 60):02d}")
    )


def find_mtv(artist: str, title: str) -> list[youtube.VideoCandidate]:
    return youtube.search(f"{artist} {title} karaoke")


def _with_guide(lib: Library, track: Track, make_guide: bool, on_progress: Progress,
                cancel: Event | None) -> Track:
    """The guide is a bonus: the track is already in the library, so a failure or cancel here keeps it."""
    if not make_guide:
        return track
    try:
        return build_guide(lib, track, on_progress, cancel)[0]
    except Cancelled:
        log.info("guide cancelled for %s", track.base)
    except Exception:
        log.exception("guide failed for %s", track.base)
    return track


def add_song(lib: Library, lyr: LyricsCandidate, on_progress: Progress = _noop,
             cancel: Event | None = None, make_guide: bool = True) -> Track:
    """Multiplex MP3 (L instrumental / R vocals) + normalized LRC."""
    base = base_name(lyr.artist, lyr.title)
    if lib.exists(base):
        raise AlreadyExists(t("err.already_exists", base=base))
    if not lyr.synced:
        raise ValueError(t("err.not_synced"))
    lrc_text = normalize_lrc(lyr.synced)

    on_progress("step.search_audio", None)
    video = find_audio(lyr.artist, lyr.title, lyr.duration)
    log.info("audio for %s: %s (%s)", base, video.url, video.duration)
    _check(cancel)

    with _workdir(lib) as tmp:
        on_progress("step.download", 0.0)
        wav = youtube.download_audio(video.url, tmp, cancel, lambda f: on_progress("step.download", f))
        _check(cancel)
        files = _build_multiplex(tmp, wav, base, lyr.artist, lyr.title, lrc_text, on_progress, cancel)
        on_progress("step.save", None)
        track = _finish(lib, files, base)
    return _with_guide(lib, track, make_guide, on_progress, cancel)


def _build_multiplex(tmp: Path, wav: Path, base: str, artist: str, title: str, lrc_text: str,
                     on_progress: Progress, cancel: Event | None) -> list[Path]:
    """Separation → multiplex mp3 (normalized, tagged) + lrc, all inside `tmp`."""
    on_progress("step.separate", 0.0)
    inst, voc = separate(wav, tmp / "stems", cancel, lambda f: on_progress("step.separate", f))
    _check(cancel)
    on_progress("step.mix", None)
    mp3 = make_multiplex(inst, voc, tmp / f"{base}.multiplexed.mp3")
    write_tags(mp3, artist, title)
    lrc = tmp / f"{base}.lrc"
    lrc.write_text(lrc_text, encoding="utf-8", newline="\n")
    _check(cancel)
    return [mp3, lrc]


def _decode_wav(src: Path, tmp: Path) -> Path:
    wav = tmp / "source.wav"
    ffmpeg.run(["-i", str(src), "-map", "0:a:0", "-c:a", "pcm_s16le", str(wav)], "err.read_audio",
               detail_chars=800, name=src.name)
    return wav


def track_from_local(lib: Library, audio: Path, artist: str, title: str, lrc_text: str,
                     on_progress: Progress = _noop, cancel: Event | None = None,
                     make_guide: bool = True) -> Track:
    """Multiplex + LRC from a file you already have (keeps your source quality)."""
    base = base_name(artist, title)
    if lib.exists(base):
        raise AlreadyExists(t("err.already_exists", base=base))
    with _workdir(lib) as tmp:
        on_progress("step.read_audio", None)
        wav = _decode_wav(Path(audio), tmp)
        files = _build_multiplex(tmp, wav, base, artist, title, normalize_lrc(lrc_text), on_progress, cancel)
        on_progress("step.save", None)
        track = _finish(lib, files, base)
    return _with_guide(lib, track, make_guide, on_progress, cancel)


def convert_to_multiplex(lib: Library, track: Track, on_progress: Progress = _noop,
                         cancel: Event | None = None, make_guide: bool = True) -> Track:
    """'Audio + LRC' → 'Multiplex + LRC' in place; the old audio goes to the Recycle Bin."""
    audio = next((f for f in track.files if f.suffix.lower() in AUDIO_EXTS
                  and ".multiplexed." not in f.name.lower()), None)
    lrc = track.file_with({".lrc"})
    if audio is None or lrc is None or track.multiplexed:
        raise ValueError(t("err.not_audio_lrc"))
    with _workdir(lib) as tmp:
        on_progress("step.read_audio", None)
        wav = _decode_wav(audio, tmp)
        mp3, _ = _build_multiplex(tmp, wav, track.base, track.artist, track.title,
                                        normalize_lrc(read_lrc(lrc)), on_progress, cancel)
        on_progress("step.save", None)
        send2trash(str(audio))
        shutil.move(str(mp3), str(lib.path / mp3.name))
    track = next(t for t in lib.scan() if t.base.lower() == track.base.lower())
    return _with_guide(lib, track, make_guide, on_progress, cancel)


def find_clip(artist: str, title: str) -> list[youtube.VideoCandidate]:
    return youtube.search(f"{artist} {title} official video")


def add_clip(lib: Library, track: Track, video: youtube.VideoCandidate, on_progress: Progress = _noop,
             cancel: Event | None = None) -> Track:
    """Video-only background for a Multiplex track (Encore plays it muted)."""
    if track.has_video:
        raise AlreadyExists(t("err.has_video", base=track.base))
    with _workdir(lib) as tmp:
        on_progress("step.download_clip", 0.0)
        src = youtube.download_video(video.url, tmp, cancel, lambda f: on_progress("step.download_clip", f),
                                     video_only=True)
        _check(cancel)
        on_progress("step.save", None)
        dest = tmp / f"{track.base}{src.suffix.lower()}"
        src.rename(dest)
        return _finish(lib, [dest], track.base)


def add_mtv(lib: Library, artist: str, title: str, video: youtube.VideoCandidate,
            on_progress: Progress = _noop, cancel: Event | None = None) -> Track:
    base = base_name(artist, title)
    if lib.exists(base):
        raise AlreadyExists(t("err.already_exists", base=base))
    with _workdir(lib) as tmp:
        on_progress("step.download_video", 0.0)
        src = youtube.download_video(video.url, tmp, cancel, lambda f: on_progress("step.download_video", f))
        _check(cancel)
        on_progress("step.save", None)
        dest = tmp / f"{base}{src.suffix.lower()}"
        src.rename(dest)
        return _finish(lib, [dest], base)
