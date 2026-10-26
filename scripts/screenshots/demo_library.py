"""Builds a demo EncoreLibrary for screenshots: invented artists and songs, original placeholder lyrics,
generated audio, a real MIDI guide. Nothing in it comes from real recordings or real songs.

    python scripts/screenshots/demo_library.py OUT_FOLDER
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from encolibmg.audio.multiplex import make_multiplex  # noqa: E402
from encolibmg.guide.align import Word  # noqa: E402
from encolibmg.guide.melody import Note  # noqa: E402
from encolibmg.guide.midi import write_guide  # noqa: E402
from encolibmg.library import Library  # noqa: E402
from encolibmg.library.tags import write_tags  # noqa: E402
from encolibmg.lyrics.sync import Line, format_lrc  # noqa: E402

SR = 22050
MAIN = ("Neon Harbor", "Paper Lanterns")
# (start s, [(word, midi pitch, length s)]) — an invented song, written for this demo
MAIN_SONG = [
    (3.0, [("Paper", 64, .45), ("lanterns", 67, .7), ("on", 69, .35), ("the", 67, .3), ("water", 64, 1.1)]),
    (7.0, [("drifting", 62, .6), ("slowly", 64, .6), ("past", 65, .4), ("the", 64, .3), ("pier", 60, 1.2)]),
    (11.0, [("every", 64, .5), ("light", 67, .6), ("a", 69, .3), ("little", 71, .5), ("promise", 72, 1.1)]),
    (15.0, [("that", 71, .4), ("the", 69, .3), ("morning", 67, .8), ("will", 65, .4), ("be", 64, .4), ("here", 64, 1.4)]),
    (20.0, [("hold", 67, .6), ("the", 69, .3), ("string", 71, .7), ("and", 69, .3), ("let", 67, .4), ("it", 65, .3),
            ("rise", 64, 1.3)]),
    (24.5, [("over", 62, .5), ("rooftops", 64, .8), ("into", 65, .5), ("skies", 67, 1.5)]),
]
DURATION = 30.0

# the rest of the library: (artist, title, kind, lyric lines)
OTHERS = [
    ("The Quiet Owls", "Late Train Home", "multiplex", ["counting windows on the late train", "city humming in the rain"]),
    ("Sol de Março", "Cidade Azul", "audio", ["luzes acesas na cidade azul", "o vento canta de norte a sul"]),
    ("Velvet Static", "Satellite Hearts", "multiplex", ["tuning in to a far-off station", "static turning into song"]),
    ("Kumo Station", "Hoshi no Michi", "mtv", []),
    ("Marigold Avenue", "Summer Postcards", "audio", ["sending postcards to the ocean", "writing back in grains of sand"]),
    ("Paper Moons", "Orbit", "orphan", []),
    ("Lighthouse Choir", "Northern Lights", "multiplex", ["green and silver over the harbor", "we were singing all night long"]),
]


def tone(freq: float, seconds: float, amp: float = .25) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    env = np.minimum(1, np.minimum(t / .03, (seconds - t) / .08)).clip(0, 1)
    return amp * env * (np.sin(2 * np.pi * freq * t) + .3 * np.sin(4 * np.pi * freq * t))


def hz(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def pad(seconds: float, roots=(48, 53, 55, 48)) -> np.ndarray:
    """A soft chord loop as the 'instrumental'."""
    out = np.zeros(int(seconds * SR))
    bar = 4.0
    for k in range(int(seconds / bar) + 1):
        r = roots[k % len(roots)]
        chord = sum(tone(hz(n), bar, .08) for n in (r, r + 4, r + 7))
        a = int(k * bar * SR)
        out[a:a + len(chord)] += chord[: max(0, len(out) - a)]
    return out


def main_song(lib: Library, tmp: Path):
    voc, notes, lines, lrc = np.zeros(int(DURATION * SR)), [], [], []
    for start, words in MAIN_SONG:
        t, line_words = start, []
        lrc.append(Line(int(start * 1000), " ".join(w for w, _, _ in words)))
        for word, pitch, length in words:
            seg = tone(hz(pitch), length * .92, .3)
            a = int(t * SR)
            voc[a:a + len(seg)] += seg
            notes.append(Note(t, t + length * .92, pitch))
            line_words.append(Word(t, word))
            t += length
        lines.append(line_words)
    write_multiplex(lib, tmp, MAIN, pad(DURATION), voc)
    base = f"{MAIN[0]} - {MAIN[1]}"
    (lib.path / f"{base}.lrc").write_text(format_lrc(lrc), encoding="utf-8", newline="\n")
    write_guide(lib.path / f"{base}.guide.mid", notes, lines, MAIN[1], MAIN[0])


def write_multiplex(lib: Library, tmp: Path, name: tuple[str, str], inst: np.ndarray, voc: np.ndarray):
    i, v = tmp / "inst.wav", tmp / "voc.wav"
    sf.write(i, np.stack([inst, inst], 1), SR)
    sf.write(v, np.stack([voc, voc], 1), SR)
    dest = lib.path / f"{name[0]} - {name[1]}.multiplexed.mp3"
    make_multiplex(i, v, dest)
    write_tags(dest, *name)


def simple_vocals(seconds: float, lines: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    voc = np.zeros(int(seconds * SR))
    for k in range(lines):
        t = 2.0 + k * 5.0
        for _ in range(6):
            seg = tone(hz(int(rng.integers(60, 72))), .45, .3)
            a = int(t * SR)
            voc[a:a + len(seg)] += seg
            t += .5
    return voc


def others(lib: Library, tmp: Path):
    for n, (artist, title, kind, words) in enumerate(OTHERS):
        base = f"{artist} - {title}"
        seconds = 14.0
        if kind == "multiplex":
            write_multiplex(lib, tmp, (artist, title), pad(seconds, (45 + n, 50 + n, 52 + n, 45 + n)),
                            simple_vocals(seconds, len(words), n))
        elif kind in ("audio", "orphan"):
            mix = pad(seconds) + simple_vocals(seconds, 2, n)
            wav = tmp / "mix.wav"
            sf.write(wav, np.stack([mix, mix], 1), SR)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "192k", str(lib.path / f"{base}.mp3")],
                           check=True)
            write_tags(lib.path / f"{base}.mp3", artist, title)
        elif kind == "mtv":
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=8",
                            "-f", "lavfi", "-i", "sine=f=330:d=8", "-pix_fmt", "yuv420p", "-shortest",
                            str(lib.path / f"{base}.mp4")], check=True)
        if words:
            lrc = [Line(int((2.0 + k * 5.0) * 1000), w) for k, w in enumerate(words)]
            (lib.path / f"{base}.lrc").write_text(format_lrc(lrc), encoding="utf-8", newline="\n")


def build(folder: Path) -> Path:
    lib = Library.create(folder / "EncoreLibrary", "Demo Karaoke Night")
    with tempfile.TemporaryDirectory() as t:
        main_song(lib, Path(t))
        others(lib, Path(t))
    return lib.path


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
