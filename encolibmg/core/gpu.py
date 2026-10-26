"""Which NVIDIA cards the AI steps (Demucs, CREPE, MMS) can use.

install.bat installs the CUDA build of PyTorch whenever it finds an NVIDIA card, but that build only has code for
cards from the GTX 10 series (Pascal, compute capability 6.1) on. On an older card PyTorch still says CUDA is
available and then fails mid-song, so such cards are hidden and everything runs on the processor instead.
"""

from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger(__name__)

MIN_CAPABILITY = (6, 1)  # oldest architecture in the PyTorch build install.bat installs (sm_61)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def nvidia_capability() -> tuple[int, int] | None:
    """Compute capability of the first NVIDIA card, e.g. (12, 0); None without a card or driver."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
        major, minor = out.stdout.strip().splitlines()[0].strip().split(".")
        return int(major), int(minor)
    except Exception:
        return None


def choose_device(env=os.environ) -> str:
    """'gpu', 'cpu' (no usable NVIDIA card) or 'cpu-old-gpu' (card too old: hidden from PyTorch and Demucs).

    Respects a CUDA_VISIBLE_DEVICES the user already set. Must run before torch is imported; the Demucs
    subprocess inherits the environment.
    """
    if "CUDA_VISIBLE_DEVICES" in env:
        return "cpu" if env["CUDA_VISIBLE_DEVICES"] in ("", "-1") else "gpu"
    cap = nvidia_capability()
    if cap is None:
        return "cpu"
    if cap < MIN_CAPABILITY:
        env["CUDA_VISIBLE_DEVICES"] = "-1"
        log.warning("NVIDIA card with compute capability %d.%d is too old for PyTorch: using the processor", *cap)
        return "cpu-old-gpu"
    return "gpu"
