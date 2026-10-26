"""Methods the UI calls through `window.pywebview.api.*`.

Every public method returns {"ok": True, "data": ...} or {"ok": False, "error": ..., "kind": ...}.
Heavy work goes through JobManager and answers {"job": id}; the result arrives as a `job` event.
Private attributes start with "_" so pywebview does not expose them.
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from encolibmg import __version__, checker, importer, pipeline, soundfont, visual, youtube
from encolibmg.audio.convert import duration as media_duration
from encolibmg.audio.player import SR, decode
from encolibmg.errors import AlreadyExists
from encolibmg.guide.build import build_guide
from encolibmg.guide.midi import read_guide
from encolibmg.library import AUDIO_EXTS, VIDEO_EXTS, Library, LibraryError, Track, inside
from encolibmg.lyrics import lrclib
from encolibmg.lyrics.match import read_lrc
from encolibmg.lyrics.sync import Line, format_lrc, parse_lrc, vocal_onset
from encolibmg.manifest import FLAGS, ensure_additional, flag_value, read_manifest, set_flag, write_manifest
from encolibmg.paths import backup_file, latest_backup, load_config, save_config
from encolibmg.webui import views

log = logging.getLogger(__name__)
PEAK_RATE = 25      # waveform points per second (40 ms), enough for the 12 s zoom
PEAK_MAX = 15000


class NoLibrary(Exception):
    pass


def api(fn):
    """Uniform envelope + logging for every bridge call."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": fn(self, *args, **kwargs)}
        except Exception as e:  # the UI shows the message; details go to the log
            kind = type(e).__name__
            if kind not in ("NoLibrary", "Busy", "AlreadyExists", "NoAudioMatch", "LibraryError", "ValueError",
                            "KeyError", "LookupError", "FileExistsError"):
                log.exception("api %s failed", fn.__name__)
            msg = str(e).strip("'\"") or kind
            return {"ok": False, "error": msg, "kind": kind}
    return wrapper


class Api:
    def __init__(self, server, jobs):
        self._server = server
        self._jobs = jobs
        self._window = None
        self._lib: Library | None = None
        self._lyrics: dict[int, lrclib.LyricsCandidate] = {}
        self._videos: dict[str, youtube.VideoCandidate] = {}
        self._issues: list = []
        self._items: list = []
        self._import_tmp: Path | None = None
        self._peaks: dict[str, tuple[float, dict]] = {}
        last = load_config().get("library")
        if last:
            try:
                self._set_library(Library.open(Path(last)))
            except LibraryError:
                log.warning("last library missing: %s", last)

    # --- internals ---------------------------------------------------------------
    def _emit(self, name: str, data: dict):
        if self._window is not None:
            import json

            self._window.evaluate_js(f"window.encolib && encolib.emit({json.dumps(name)}, {json.dumps(data)})")

    def _need(self) -> Library:
        if self._lib is None:
            raise NoLibrary("Abra ou crie uma biblioteca primeiro.")
        return self._lib

    def _set_library(self, lib: Library):
        self._lib = lib
        cfg = load_config()
        cfg["library"] = str(lib.path)
        save_config(cfg)
        self._refresh_roots()

    def _refresh_roots(self):
        roots = [self._lib.path] if self._lib else []
        if self._import_tmp:
            roots.append(self._import_tmp)
        self._server.set_roots(roots)

    def _track(self, base: str) -> Track:
        key = base.lower()
        for t in self._need().scan():
            if t.base.lower() == key:
                return t
        raise KeyError(f"A faixa '{base}' não está mais na biblioteca.")

    def _job(self, label: str, fn, kind: str = "job") -> dict:
        def wrapped(progress, cancel):
            try:
                return fn(progress, cancel)
            finally:
                self._emit("library", {})
        return {"job": self._jobs.start(label, wrapped, kind)}

    def _dialog(self, kind: int, multiple=False, types=()) -> list[str]:
        if self._window is None:
            return []
        res = self._window.create_file_dialog(kind, allow_multiple=multiple, file_types=types)
        return list(res or [])

    def _url(self, p: Path | None) -> str | None:
        return self._server.media_url(p) if p else None

    # --- app / library ------------------------------------------------------------
    @api
    def state(self):
        lib = self._lib
        tracks = lib.scan() if lib else []
        return {"version": __version__, "job": self._jobs.snapshot(),
                "library": {"path": str(lib.path), "title": lib.title} if lib else None,
                "stats": views.stats(tracks)}

    @api
    def library_pick(self):
        import webview

        paths = self._dialog(webview.FileDialog.FOLDER)
        if not paths:
            return None
        p = Path(paths[0])
        return {"path": str(p), "has_manifest": (p / "manifest.json").is_file(), "name": p.name}

    @api
    def library_open(self, path: str):
        self._set_library(Library.open(Path(path)))
        return self.state()["data"]

    @api
    def library_create(self, path: str, title: str):
        folder = Path(path)
        if folder.name.lower() != "encorelibrary" and not (folder / "manifest.json").exists():
            folder = folder / "EncoreLibrary"
        self._set_library(Library.create(folder, title.strip() or "Minha Biblioteca"))
        return self.state()["data"]

    @api
    def tracks(self):
        return [views.track_dict(t) for t in self._need().scan()]

    @api
    def open_folder(self, rel: str = ""):
        """Opens a folder of the library in Explorer. Never a file: startfile would run it."""
        target = inside(self._need().path, rel)
        if not target.is_dir():
            raise ValueError("Só pastas da biblioteca podem ser abertas.")
        os.startfile(target)
        return True

    @api
    def job_cancel(self):
        return self._jobs.cancel()

    @api
    def open_url(self, url: str):
        """Opens YouTube links in the system browser (nothing else is allowed)."""
        import webbrowser
        from urllib.parse import urlsplit

        host = urlsplit(url).hostname or ""
        if urlsplit(url).scheme != "https" or not (host == "youtu.be" or host.endswith("youtube.com")):
            raise ValueError("Só links do YouTube podem ser abertos.")
        webbrowser.open(url)
        return True

    # --- add ----------------------------------------------------------------------------
    @api
    def search_lyrics(self, query: str):
        res = lrclib.search(query)
        self._lyrics.update({c.id: c for c in res})
        return [views.lyrics_dict(c) for c in res]

    @api
    def add_song(self, lyrics_id: int, make_guide: bool = True):
        lib, cand = self._need(), self._lyrics[int(lyrics_id)]
        return self._job(f"{cand.artist} - {cand.title}", lambda p, c: views.track_dict(
            pipeline.add_song(lib, cand, p, c, make_guide=make_guide)), "add")

    @api
    def find_mtv(self, artist: str, title: str):
        vids = pipeline.find_mtv(artist, title)
        self._videos.update({v.id: v for v in vids})
        return [views.video_dict(v) for v in vids]

    @api
    def add_mtv(self, artist: str, title: str, video_id: str):
        lib, v = self._need(), self._videos[video_id]
        return self._job(f"MTV {artist} - {title}", lambda p, c: views.track_dict(
            pipeline.add_mtv(lib, artist, title, v, p, c)), "add")

    # --- library actions -------------------------------------------------------------------
    @api
    def track_rename(self, base: str, artist: str, title: str):
        t = self._need().rename_track(self._track(base), artist, title)
        self._emit("library", {})
        return views.track_dict(t)

    @api
    def track_remove(self, bases: list[str]):
        lib = self._need()
        for b in bases:
            lib.remove(self._track(b))
        self._emit("library", {})
        return len(bases)

    @api
    def track_convert(self, base: str):
        lib, t = self._need(), self._track(base)
        return self._job(f"Multiplex: {t.base}", lambda p, c: views.track_dict(
            pipeline.convert_to_multiplex(lib, t, p, c)))

    @api
    def track_guides(self, bases: list[str]):
        lib = self._need()
        tracks = [self._track(b) for b in bases]

        def work(progress, cancel):
            out = []
            for n, t in enumerate(tracks):
                label = f"{n + 1}/{len(tracks)} {t.base}" if len(tracks) > 1 else t.base
                try:
                    _, st = build_guide(lib, t, lambda s, f=None, l=label: progress(f"{l} · {s}", f), cancel)
                    out.append({"base": t.base, "stats": st})
                except Exception as e:
                    if type(e).__name__ == "Cancelled":
                        raise
                    out.append({"base": t.base, "error": str(e)})
            return out
        return self._job("Guia MIDI", work, "guide")

    @api
    def find_clip(self, base: str):
        t = self._track(base)
        audio = t.file_with(AUDIO_EXTS)
        dur = media_duration(audio) if audio else None
        vids = pipeline.find_clip(t.artist, t.title)
        self._videos.update({v.id: v for v in vids})
        return {"duration": dur, "videos": [views.video_dict(v, dur) for v in vids]}

    @api
    def add_clip(self, base: str, video_id: str):
        lib, t, v = self._need(), self._track(base), self._videos[video_id]
        return self._job(f"Clipe: {t.base}", lambda p, c: views.track_dict(pipeline.add_clip(lib, t, v, p, c)))

    @api
    def media(self, base: str, which: str = "audio"):
        t = self._track(base)
        if which == "video":
            return self._url(t.file_with(VIDEO_EXTS))
        mp = next((f for f in t.files if ".multiplexed." in f.name.lower()), None)
        return self._url(mp or t.file_with(AUDIO_EXTS) or t.file_with(VIDEO_EXTS))

    # --- sync -------------------------------------------------------------------------------
    def _peaks_for(self, path: Path, channel: int) -> dict:
        key = f"{path}:{channel}"
        mtime = path.stat().st_mtime
        hit = self._peaks.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        data = decode(path)
        x = np.abs(data[:, channel] if channel >= 0 else data.mean(axis=1))
        n = len(x)
        buckets = int(min(PEAK_MAX, max(1, round(n / SR * PEAK_RATE))))
        edges = np.linspace(0, n, buckets + 1).astype(int)
        peaks = np.maximum.reduceat(x, edges[:-1]) if n else np.zeros(1)
        peaks = peaks / (peaks.max() or 1.0)
        out = {"duration": n / SR, "rate": buckets / (n / SR) if n else PEAK_RATE,
               "peaks": [round(float(v), 3) for v in peaks]}
        onset = vocal_onset(data[:, channel] if channel >= 0 else data.mean(axis=1), SR)
        out["onset"] = onset
        self._peaks[key] = (mtime, out)
        return out

    @api
    def sync_load(self, base: str):
        t = self._track(base)
        lrc = t.file_with({".lrc"})
        if lrc is None:
            raise ValueError("Esta faixa não tem .lrc.")
        mp = next((f for f in t.files if ".multiplexed." in f.name.lower()), None)
        audio = mp or t.file_with(AUDIO_EXTS) or t.file_with(VIDEO_EXTS)
        info = self._peaks_for(audio, 1 if mp else -1)
        lines = parse_lrc(read_lrc(lrc))
        return {"base": t.base, "artist": t.artist, "title": t.title, "audio": self._url(audio),
                "multiplexed": bool(mp), "has_guide": t.has_guide, "has_backup": latest_backup(lrc.name) is not None,
                "lines": [{"ms": l.ms, "text": l.text} for l in lines], **info}

    @api
    def sync_save(self, base: str, lines: list[dict]):
        t = self._track(base)
        lrc = t.file_with({".lrc"})
        backup_file(lrc)
        lrc.write_text(format_lrc([Line(int(l["ms"]), str(l["text"])) for l in lines]), encoding="utf-8",
                       newline="\n")
        self._emit("library", {})
        return {"has_guide": t.has_guide, "lines": [{"ms": l.ms, "text": l.text} for l in parse_lrc(read_lrc(lrc))]}

    @api
    def sync_undo(self, base: str):
        lrc = self._track(base).file_with({".lrc"})
        bak = latest_backup(lrc.name)
        if bak is None:
            raise LookupError("Não há backup desta letra.")
        shutil.copy2(bak, lrc)
        bak.unlink()
        return {"lines": [{"ms": l.ms, "text": l.text} for l in parse_lrc(read_lrc(lrc))],
                "has_backup": latest_backup(lrc.name) is not None}

    # --- guide preview --------------------------------------------------------------------------
    @api
    def guide_load(self, base: str):
        t = self._track(base)
        gpath = next((f for f in t.files if ".guide." in f.name.lower() or ".melody." in f.name.lower()), None)
        if gpath is None:
            raise LookupError("Esta faixa ainda não tem guia MIDI.")
        g = read_guide(gpath)
        mp = next((f for f in t.files if ".multiplexed." in f.name.lower()), None)
        audio = mp or t.file_with(AUDIO_EXTS)
        return {"base": t.base, "artist": t.artist, "title": t.title, "audio": self._url(audio),
                "multiplexed": bool(mp), "duration": media_duration(audio) if audio else None,
                "notes": [[n.start, n.end, n.pitch] for n in g.notes],
                "lyrics": [[s, text] for s, text in g.lyrics]}

    # --- check -------------------------------------------------------------------------------------
    @api
    def check(self, loudness: bool = False):
        lib = self._need()

        def work(progress, cancel):
            progress("verificando", None)
            self._issues = checker.check(lib, include_loudness=loudness, cancel=cancel, on_progress=progress)
            return [views.issue_dict(i, n, lib) for n, i in enumerate(self._issues)]
        return self._job("Verificação da biblioteca", work, "check")

    @api
    def fix(self, ids: list[int]):
        lib, issues = self._need(), list(self._issues)
        todo = [int(i) for i in ids if 0 <= int(i) < len(issues) and issues[int(i)].fixable]

        def work(progress, cancel):
            out = {}
            for n, i in enumerate(todo):
                if cancel.is_set():
                    break
                progress(f"corrigindo {n + 1}/{len(todo)}", n / max(1, len(todo)))
                try:
                    out[i] = {"ok": True, "message": checker.fix(lib, issues[i])}
                except Exception as e:
                    out[i] = {"ok": False, "message": str(e) or type(e).__name__}
            return out
        return self._job("Correções", work, "fix")

    # --- import -------------------------------------------------------------------------------------
    @api
    def import_pick(self):
        import webview

        paths = self._dialog(webview.FileDialog.FOLDER)
        return paths[0] if paths else None

    @api
    def import_scan(self, folder: str):
        lib = self._need()
        if self._import_tmp:
            shutil.rmtree(self._import_tmp, ignore_errors=True)
        self._import_tmp = Path(tempfile.mkdtemp(prefix="encolibmg-import-"))
        self._refresh_roots()
        self._items = importer.scan_source(Path(folder), self._import_tmp)
        importer.mark_existing(lib, self._items)
        return [views.import_dict(it, n) for n, it in enumerate(self._items)]

    @api
    def import_edit(self, idx: int, artist: str | None = None, title: str | None = None,
                    selected: bool | None = None):
        it = self._items[int(idx)]
        if artist is not None or title is not None:
            it.artist = (artist if artist is not None else it.artist).strip() or it.artist
            it.title = (title if title is not None else it.title).strip() or it.title
            it.status, it.selected = "", True
            importer.mark_existing(self._need(), self._items)
        if selected is not None:
            it.selected = bool(selected)
        return [views.import_dict(x, n) for n, x in enumerate(self._items)]

    @api
    def import_run(self, opts: dict):
        lib = self._need()
        chosen = [(n, it) for n, it in enumerate(self._items) if it.selected]
        kw = {k: bool(opts.get(k, d)) for k, d in
              (("move", False), ("find_lyrics", True), ("make_multiplex", False), ("normalize", True))}

        def work(progress, cancel):
            out = {}
            for k, (n, it) in enumerate(chosen):
                if cancel.is_set():
                    break
                label = f"{k + 1}/{len(chosen)} {it.base}"
                progress(label, k / max(1, len(chosen)))
                try:
                    out[n] = importer.import_item(lib, it, cancel=cancel,
                                                  on_progress=lambda s, f=None, l=label: progress(f"{l} · {s}", f),
                                                  **kw)
                except Exception as e:
                    if type(e).__name__ == "Cancelled":
                        raise
                    out[n] = f"✖ {e}"
                it.status, it.selected = out[n], False
            return {"results": out, "items": [views.import_dict(x, i) for i, x in enumerate(self._items)]}
        return self._job("Importação", work, "import")

    # --- visual & sound ------------------------------------------------------------------------------
    @api
    def visual_state(self):
        lib = self._need()
        def entry(rel):
            p = lib.path / rel
            return {"rel": rel, "name": Path(rel).name, "url": self._url(p) if p.exists() else None,
                    "size": p.stat().st_size if p.exists() else 0}
        cats = [{"name": c["BGV_CATEGORY"], "videos": [entry(v) for v in c.get("BGV_LIST", [])]}
                for c in visual.bgv_categories(lib)]
        boot = visual.boot_video(lib)
        return {"categories": cats, "bumpers": [entry(b) for b in visual.bumpers(lib)],
                "boot": entry(boot) if boot else None,
                "narrations": [{**n, **entry(n["file"])} for n in visual.narrations(lib)],
                "soundfont": soundfont.current_soundfont(lib)}

    @api
    def bgv_category(self, action: str, name: str, new: str = ""):
        lib = self._need()
        {"add": lambda: visual.add_category(lib, name), "rename": lambda: visual.rename_category(lib, name, new),
         "remove": lambda: visual.remove_category(lib, name)}[action]()
        return self.visual_state()["data"]

    @api
    def bgv_add_files(self, category: str):
        import webview

        files = self._dialog(webview.FileDialog.OPEN, True,
                             ("Vídeos (*.mp4;*.mkv;*.webm;*.avi;*.mov;*.wmv;*.m4v)", "Todos (*.*)"))
        if not files:
            return None
        lib = self._need()

        def work(progress, cancel):
            for n, f in enumerate(files):
                progress(f"preparando {Path(f).name}", n / len(files))
                visual.add_bgv_file(lib, category, Path(f))
            return len(files)
        return self._job(f"Vídeos de fundo: {category}", work, "visual")

    @api
    def bgv_search(self, query: str):
        vids = youtube.search(query, n=15)
        self._videos.update({v.id: v for v in vids})
        return [views.video_dict(v) for v in vids]

    @api
    def bgv_add_video(self, category: str, video_id: str):
        lib, v = self._need(), self._videos[video_id]
        return self._job(f"Vídeo de fundo: {v.title[:40]}", lambda p, c: visual.add_bgv_video(lib, category, v, p, c),
                         "visual")

    @api
    def bgv_remove(self, category: str, rel: str):
        visual.remove_bgv(self._need(), category, rel)
        return self.visual_state()["data"]

    @api
    def bumper_add(self):
        import webview

        files = self._dialog(webview.FileDialog.OPEN, True, ("Imagens (*.png;*.jpg;*.jpeg;*.webp;*.gif)",))
        for f in files:
            visual.add_bumper(self._need(), Path(f))
        return self.visual_state()["data"]

    @api
    def bumper_remove(self, rel: str):
        visual.remove_bumper(self._need(), rel)
        return self.visual_state()["data"]

    @api
    def boot_set(self):
        import webview

        files = self._dialog(webview.FileDialog.OPEN, False, ("Vídeos (*.mp4;*.mkv;*.webm;*.avi;*.mov)",))
        if not files:
            return None
        lib = self._need()
        return self._job("Vídeo de abertura", lambda p, c: visual.set_boot_video(lib, Path(files[0])), "visual")

    @api
    def boot_clear(self):
        visual.clear_boot_video(self._need())
        return self.visual_state()["data"]

    @api
    def narration_set(self, lo: int, hi: int):
        import webview

        files = self._dialog(webview.FileDialog.OPEN, False, ("Áudio (*.mp3;*.wav;*.ogg;*.m4a;*.flac)",))
        if not files:
            return None
        visual.set_narration(self._need(), int(lo), int(hi), Path(files[0]))
        return self.visual_state()["data"]

    @api
    def narration_remove(self, lo: int, hi: int):
        visual.remove_narration(self._need(), int(lo), int(hi))
        return self.visual_state()["data"]

    @api
    def soundfont_pick(self):
        import webview

        files = self._dialog(webview.FileDialog.OPEN, False, ("SoundFont (*.sf2;*.sf3;*.dls)",))
        if files:
            soundfont.install_soundfont(self._need(), Path(files[0]))
        return self.visual_state()["data"]

    @api
    def soundfont_download(self):
        lib = self._need()
        return self._job("Baixando GeneralUser GS", lambda p, c: soundfont.download_generaluser(
            lib, lambda f: p("baixando SoundFont", f), c), "visual")

    @api
    def soundfont_remove(self):
        soundfont.remove_soundfont(self._need())
        return self.visual_state()["data"]

    # --- settings ---------------------------------------------------------------------------------------
    @api
    def settings_get(self):
        data = read_manifest(self._need().path)
        return {"title": data.get("title", ""), "description": data.get("description", ""),
                "flags": [{"key": k, "label": label, "value": flag_value(data, k)} for k, label, _ in FLAGS]}

    @api
    def settings_save(self, payload: dict):
        lib = self._need()
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("O nome não pode ficar vazio.")
        data = read_manifest(lib.path)
        data["title"], data["description"] = title, str(payload.get("description", "")).strip()
        for f in payload.get("flags", []):
            set_flag(data, f["key"], bool(f["value"]))
        ensure_additional(data)
        write_manifest(lib.path, data)
        return self.state()["data"]
