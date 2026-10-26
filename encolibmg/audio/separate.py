"""Vocal/instrumental separation with Demucs, run as a subprocess.

Default is the fine-tuned htdemucs_ft (a bag of 4 models) with 2 random
shifts: noticeably cleaner instrumental than plain htdemucs, ~50 s per song
on an RTX-class GPU.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from threading import Event

from encolibmg.audio.ffmpeg import NO_WINDOW
from encolibmg.core.errors import Cancelled
from encolibmg.core.i18n import t

MODEL = "htdemucs_ft"
SHIFTS = 2
BAG_SIZE = {"htdemucs": 1, "htdemucs_ft": 4}
_PERCENT = re.compile(r"(\d{1,3})%\|")


class _Overall:
    """Demucs prints one 0-100% tqdm bar per model per shift; merge them."""

    def __init__(self, bars: int):
        self.bars = max(1, bars)
        self.done = 0
        self.last = 0

    def feed(self, pct: int) -> float:
        if pct < self.last:
            self.done += 1
        self.last = pct
        return min(0.99, (self.done + pct / 100) / self.bars)


def separate(wav: Path, work_dir: Path, cancel: Event | None = None, on_progress=None,
             model: str = MODEL, shifts: int = SHIFTS) -> tuple[Path, Path]:
    """Returns (instrumental, vocals) WAV paths inside work_dir."""
    wav, work_dir = Path(wav), Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", model,
           "--shifts", str(shifts), "-o", str(work_dir), str(wav)]
    overall = _Overall(BAG_SIZE.get(model, 1) * max(1, shifts))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        creationflags=NO_WINDOW,
    )
    if cancel is not None:
        def watch():
            # kills Demucs even while it is silent (model loading, writing files)
            while proc.poll() is None:
                if cancel.wait(0.5):
                    proc.kill()
                    return
        threading.Thread(target=watch, daemon=True).start()

    tail: deque[str] = deque(maxlen=40)
    buf = b""
    try:
        while True:
            chunk = proc.stderr.read1(256)
            if not chunk:
                break
            buf += chunk
            # tqdm redraws with \r, normal lines end with \n
            *parts, buf = re.split(rb"[\r\n]", buf)
            for p in parts:
                line = p.decode("utf-8", "replace").strip()
                if not line:
                    continue
                tail.append(line)
                m = _PERCENT.search(line)
                if m and on_progress:
                    on_progress(overall.feed(min(int(m.group(1)), 100)))
        proc.wait()
    except BaseException:
        proc.kill()
        proc.wait()
        raise

    if cancel is not None and cancel.is_set():
        raise Cancelled()
    if proc.returncode != 0:
        log = "\n".join(l for l in tail if not _PERCENT.search(l))
        raise RuntimeError(t("err.demucs_failed", code=proc.returncode, detail=log[-2000:]))

    out = work_dir / model / wav.stem
    inst, voc = out / "no_vocals.wav", out / "vocals.wav"
    if not (inst.exists() and voc.exists()):
        raise RuntimeError(t("err.demucs_no_output", path=out))
    return inst, voc
