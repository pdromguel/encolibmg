"""YouTube search and download through yt-dlp."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from yt_dlp import YoutubeDL

from encolibmg.errors import Cancelled

MAX_DURATION_DIFF = 8.0
UNWANTED = ["karaoke", "instrumental", "cover", "live", "ao vivo", "8d", "slowed",
            "sped up", "nightcore", "reverb", "remix", "acoustic", "acústico"]


@dataclass
class VideoCandidate:
    id: str
    title: str
    channel: str
    duration: float | None
    url: str


def search(query: str, n: int = 10) -> list[VideoCandidate]:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in info.get("entries") or []:
        if not e or not e.get("id"):
            continue
        dur = e.get("duration")
        out.append(VideoCandidate(
            id=e["id"],
            title=e.get("title") or "",
            channel=e.get("channel") or e.get("uploader") or "",
            duration=float(dur) if dur else None,
            url=f"https://www.youtube.com/watch?v={e['id']}",
        ))
    return out


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I) is not None


def pick_audio(cands: list[VideoCandidate], target: float, query: str = "") -> VideoCandidate | None:
    """Closest duration to the synced lyrics, skipping karaoke/live/remix versions."""
    banned = [w for w in UNWANTED if not _has_word(query, w)]
    ok = [
        c for c in cands
        if c.duration is not None
        and abs(c.duration - target) <= MAX_DURATION_DIFF
        and not any(_has_word(c.title, w) for w in banned)
    ]
    return min(ok, key=lambda c: abs(c.duration - target), default=None)


def _progress_hook(cancel: Event | None, on_progress):
    def hook(d):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                on_progress(d.get("downloaded_bytes", 0) / total)
    return hook


def _run(url: str, opts: dict, cancel, on_progress) -> None:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            "progress_hooks": [_progress_hook(cancel, on_progress)], **opts}
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        # yt-dlp wraps exceptions raised inside hooks
        if cancel is not None and cancel.is_set():
            raise Cancelled() from e
        raise


def download_audio(url: str, dest_dir: Path, cancel: Event | None = None, on_progress=None) -> Path:
    """Best audio stream converted to WAV (what Demucs reads best)."""
    dest_dir = Path(dest_dir)
    _run(url, {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }, cancel, on_progress)
    return dest_dir / "source.wav"


def download_video(url: str, dest_dir: Path, cancel: Event | None = None, on_progress=None,
                   video_only: bool = False, section: tuple[float, float] | None = None) -> Path:
    """Up to 1080p, H.264/AAC in MP4 so Encore's Chromium player handles it.

    `video_only` is for clips behind a Multiplex track: Encore plays them muted.
    `section` (start, end) in seconds downloads only that part (scenic videos are often hours long).
    """
    dest_dir = Path(dest_dir)
    if video_only:
        opts = {"format": "bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]/bv*"}
    else:
        opts = {"format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
                "merge_output_format": "mp4"}
    if section:
        from yt_dlp.utils import download_range_func

        opts["download_ranges"] = download_range_func(None, [section])
        opts["force_keyframes_at_cuts"] = True
    _run(url, {**opts, "outtmpl": str(dest_dir / "video.%(ext)s")}, cancel, on_progress)
    found = sorted(dest_dir.glob("video.*"))
    if not found:
        raise RuntimeError("O download do vídeo não gerou arquivo.")
    return found[0]
