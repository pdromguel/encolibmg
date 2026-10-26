"""How long the heavy steps take on this PC, for a 4-minute song (generated, no real music).

    python scripts/benchmark.py          # uses the NVIDIA GPU if there is one
    python scripts/benchmark.py --cpu    # forces the processor, to compare

Times vocal separation (Demucs) and the MIDI guide (CREPE melody + MMS word alignment). Downloads, which depend
on your connection, are not included. Run it once first so the AI models are already downloaded.
"""

from __future__ import annotations

import os
import sys

if "--cpu" in sys.argv:
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # before torch is imported anywhere

import platform  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "screenshots"))

from demo_library import SR, hz, pad, tone  # noqa: E402

from encolibmg.audio.multiplex import make_multiplex  # noqa: E402
from encolibmg.audio.separate import separate  # noqa: E402
from encolibmg.guide.build import build_guide  # noqa: E402
from encolibmg.library import Library  # noqa: E402
from encolibmg.lyrics.sync import Line, format_lrc  # noqa: E402

SECONDS = 240.0
WORDS = "la na da lo ma".split()  # placeholder syllables, one sung note each


def song() -> tuple[np.ndarray, np.ndarray, list[Line]]:
    rng = np.random.default_rng(1)
    voc, lines = np.zeros(int(SECONDS * SR)), []
    for k, start in enumerate(np.arange(4.0, SECONDS - 6, 5.0)):
        t = start
        lines.append(Line(int(start * 1000), " ".join(WORDS)))
        for _ in WORDS:
            seg = tone(hz(int(rng.integers(60, 72))), .55, .3)
            a = int(t * SR)
            voc[a:a + len(seg)] += seg
            t += .6
    return pad(SECONDS), voc, lines


def ram_used_mb() -> int:
    """RAM in use on the whole PC (Windows), in MB."""
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    m = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return (m.ullTotalPhys - m.ullAvailPhys) // 2**20


class Peaks:
    """Peak extra GPU memory and RAM while a step runs (whole PC, minus what was in use before)."""

    def __init__(self):
        self.base = self.peak = self._used()
        self.on = self.base is not None
        self.ram_base = self.ram_peak = ram_used_mb()
        self._stop = threading.Event()

    @staticmethod
    def _used() -> int | None:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout
            return int(out.split()[0])
        except Exception:
            return None

    def __enter__(self):
        def loop():
            while not self._stop.wait(0.3):
                u = self._used() if self.on else None
                if u is not None:
                    self.peak = max(self.peak, u)
                self.ram_peak = max(self.ram_peak, ram_used_mb())
        threading.Thread(target=loop, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._stop.set()

    def gpu(self) -> str:
        return f"{(self.peak - self.base) / 1024:.1f} GB" if self.on else "-"

    def ram(self) -> str:
        return f"{(self.ram_peak - self.ram_base) / 1024:.1f} GB"


def describe() -> str:
    import torch

    cpu = platform.processor() or platform.machine()
    try:
        cpu = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"],
                             capture_output=True, text=True, timeout=15).stdout.strip() or cpu
    except Exception:
        pass
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none (CPU)"
    return f"CPU: {cpu}\nGPU: {gpu}  ·  PyTorch {torch.__version__}"


def main():
    print(describe(), f"\nSong: {SECONDS / 60:.0f} min (generated)\n")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        inst, voc, lines = song()
        mix = tmp / "mix.wav"
        sf.write(mix, np.stack([inst + voc, inst + voc], 1), SR)

        rows = []
        with Peaks() as v:
            t0 = time.perf_counter()
            separate(mix, tmp / "sep")
            rows.append(("Vocal separation (Demucs htdemucs_ft)", time.perf_counter() - t0, v.gpu(), v.ram()))

        lib = Library.create(tmp / "EncoreLibrary", "Benchmark")
        i, w = tmp / "i.wav", tmp / "v.wav"
        sf.write(i, np.stack([inst, inst], 1), SR)
        sf.write(w, np.stack([voc, voc], 1), SR)
        make_multiplex(i, w, lib.path / "Benchmark - Song.multiplexed.mp3")
        (lib.path / "Benchmark - Song.lrc").write_text(format_lrc(lines), encoding="utf-8", newline="\n")
        track = lib.scan()[0]
        with Peaks() as v:
            t0 = time.perf_counter()
            build_guide(lib, track)
            rows.append(("MIDI guide (CREPE + MMS)", time.perf_counter() - t0, v.gpu(), v.ram()))

    total = sum(r[1] for r in rows)
    width = max(len(r[0]) for r in rows) + 2
    print(f"{'Step':<{width}}{'Time':>10}{'GPU memory':>14}{'RAM':>10}")
    for name, sec, gpu, ram in rows:
        print(f"{name:<{width}}{sec / 60:>8.1f} min{gpu:>14}{ram:>10}")
    print(f"{'Total per song (plus download)':<{width}}{total / 60:>8.1f} min")


if __name__ == "__main__":
    main()
