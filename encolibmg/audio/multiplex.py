"""Build an Encore "Multiplex" track.

Encore starts playback panned fully left (multiplexPan = -1) and the UI
labels left/right as Instrumental/Vocal, so: left = instrumental, right = vocals.
"""

import subprocess
from pathlib import Path

from encolibmg.audio import loudness

FFMPEG = "ffmpeg"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ffmpeg(cmd: list[str], what: str) -> None:
    proc = subprocess.run([FFMPEG, "-v", "error", "-y", *cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao {what}:\n{proc.stderr[-2000:]}")


def make_multiplex(instrumental: Path, vocals: Path, dest: Path, normalize: bool = True) -> Path:
    """Mixes to a lossless intermediate first so loudness gain costs no extra encode."""
    dest = Path(dest)
    graph = (
        "[0:a]pan=mono|c0=0.5*c0+0.5*c1[l];"
        "[1:a]pan=mono|c0=0.5*c0+0.5*c1[r];"
        "[l][r]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[a]"
    )
    mixed = dest.with_name(dest.stem + ".mix.wav")
    _ffmpeg(["-i", str(instrumental), "-i", str(vocals), "-filter_complex", graph, "-map", "[a]",
             "-c:a", "pcm_f32le", str(mixed)], "mixar o multiplex")
    try:
        gain = loudness.gain_for(loudness.measure(mixed)) if normalize else 0.0
        _ffmpeg(["-i", str(mixed), "-af", f"volume={gain:.2f}dB",
                 "-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3", str(dest)],
                "codificar o mp3")
    finally:
        mixed.unlink(missing_ok=True)
    if normalize:
        loudness.mark_mp3(dest)
    return dest
