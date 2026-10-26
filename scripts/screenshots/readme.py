"""Regenerates the README screenshots and the animated demo from the demo library (both languages).

    python scripts/screenshots/readme.py            → docs/screens/<lang>/*.png and docs/screens/demo.gif

Opens the real window several times (it takes a couple of minutes) and plays the audio muted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCREENS = ROOT / "docs" / "screens"
MAIN = "Neon Harbor - Paper Lanterns"

S = "window.__encolib.store"
P = "window.__encolib.player"
RESULTS = json.dumps([
    {"id": 1, "artist": "Neon Harbor", "title": "Paper Lanterns", "album": "Harbor Lights", "duration": 30, "synced": True},
    {"id": 2, "artist": "Neon Harbor", "title": "Paper Lanterns (Live)", "album": "Night Shift", "duration": 34, "synced": True},
    {"id": 3, "artist": "Neon Harbor", "title": "Paper Lanterns (Acoustic)", "album": "", "duration": 31, "synced": False},
    {"id": 4, "artist": "Neon Harbour", "title": "Paper Lanterns", "album": "Singles", "duration": 30, "synced": True},
])
FAKE_JOB = (f"{S}.set({{job: {{id: 99, label: '{MAIN}', key: 'step.separate', kind: 'add', frac: 0.62, "
            f"step: window.__encolib.t('step.separate')}}}})")


def steps() -> list[str]:
    return [
        "wait:1",
        # home: replay the wordmark assembling
        "go:library", "wait:1", "go:home", "frames:home:8:180", "wait:2", "shot:home",
        # add: invented search results + a job in progress (no network needed)
        f"js:{S}.setView('add', {{query: '{MAIN}', results: {RESULTS}, loading: false, autorun: false}})",
        f"js:{FAKE_JOB}", "go:add", "wait:1.2", "shot:add",
        f"js:{S}.set({{job: null}})",
        # library with the track panel open
        f"js:{S}.setView('library', {{selected: '{MAIN}'}})", "go:library", "wait:1.5", "shot:library",
        # sync: playhead in the second line
        f"js:{P}.audio.muted = true", f"go:sync/{MAIN}", "wait:2.5",
        f"js:{P}.seek(7.9); {S}.setView('sync', {{sel: 1}})", "wait:0.6", "shot:sync",
        f"js:{P}.seek(10.6); {P}.play()", "frames:sync:10:200", f"js:{P}.pause()",
        # guide preview: lyrics filling word by word
        f"go:guide/{MAIN}", "wait:2.5", f"js:{P}.seek(12.2)", "wait:0.6", "shot:guide",
        f"js:{P}.seek(11.0); {P}.play()", "frames:guide:14:200", f"js:{P}.pause()",
        # check finds the track without lyrics
        "go:check", "wait:1", "js:document.querySelector('.page-head .btn.lg').click()", "wait:3", "shot:check",
        "frames:check:2:300",
        "go:import", "wait:1",  # back to a quiet screen before closing
    ]


def capture(lang: str, lib: Path, out: Path):
    env = {**os.environ, "ENCOLIB_TEST_LIB": str(lib), "ENCOLIB_LANG": lang, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(HERE / "app.py"), str(out), *steps()], env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    errors = [l for l in proc.stdout.splitlines() if l.startswith("JS errors")]
    print(lang, errors or proc.stdout[-500:] + proc.stderr[-1500:])


def gif(frames: list[tuple[Path, int]], dest: Path, width: int = 960):
    imgs = []
    for path, _ in frames:
        im = Image.open(path).convert("RGB")
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        imgs.append(im)
    # one shared palette keeps the dark UI clean and the file small
    pal = imgs[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    q[0].save(dest, save_all=True, append_images=q[1:], duration=[d for _, d in frames], loop=0, optimize=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lib = Path(subprocess.run([sys.executable, str(HERE / "demo_library.py"), str(tmp / "demo")],
                                  capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
        for lang in ("en", "pt-BR"):
            # a fresh copy each run: the Check screen and the player must not see the other run's changes
            run_lib = tmp / f"lib-{lang}" / "EncoreLibrary"
            shutil.copytree(lib, run_lib)
            out = tmp / f"shots-{lang}"
            capture(lang, run_lib, out)
            dest = SCREENS / lang
            dest.mkdir(parents=True, exist_ok=True)
            for name in ("home", "add", "library", "sync", "guide", "check"):
                shutil.copy(out / f"{name}.png", dest / f"{name}.png")
            if lang == "en":
                seq = [(out / f"home-{k:02d}.png", 140) for k in range(8)] + [(out / "home.png", 1600),
                       (out / "add.png", 2200), (out / "library.png", 2200)]
                seq += [(out / f"sync-{k:02d}.png", 200) for k in range(10)]
                seq += [(out / f"guide-{k:02d}.png", 200) for k in range(14)] + [(out / "check.png", 2400)]
                gif(seq, SCREENS / "demo.gif")
    print("done:", SCREENS)


if __name__ == "__main__":
    main()
