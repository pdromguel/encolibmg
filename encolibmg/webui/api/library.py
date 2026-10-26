"""App, language, library and per-track actions, and the library settings (manifest)."""

from __future__ import annotations

import os
from pathlib import Path

from encolibmg import __version__, pipeline
from encolibmg.core import i18n
from encolibmg.audio.convert import duration as media_duration
from encolibmg.guide.build import build_guide
from encolibmg.core.i18n import t as tr
from encolibmg.library import AUDIO_EXTS, VIDEO_EXTS, Library, inside
from encolibmg.library.manifest import FLAGS, ensure_additional, flag_value, read_manifest, set_flag, write_manifest
from encolibmg.core.paths import load_config, save_config
from encolibmg.webui import serialize
from encolibmg.webui.api.core import ApiCore, api, step_text


class LibraryApi(ApiCore):
    # --- language -------------------------------------------------------------------
    @api
    def i18n(self):
        """Current language, the saved setting ("auto" or a language) and the full catalog."""
        return {"lang": i18n.language(), "setting": load_config().get("language", "auto"),
                "supported": list(i18n.SUPPORTED), "catalog": i18n.catalog(i18n.language())}

    @api
    def set_language(self, setting: str):
        if setting != "auto" and setting not in i18n.SUPPORTED:
            raise ValueError(setting)
        cfg = load_config()
        cfg["language"] = setting
        save_config(cfg)
        i18n.set_language(setting)
        return self.i18n()["data"]

    # --- app / library ------------------------------------------------------------
    @api
    def state(self):
        lib = self._lib
        tracks = lib.scan() if lib else []
        return {"version": __version__, "job": self._jobs.snapshot(),
                "library": {"path": str(lib.path), "title": lib.title} if lib else None,
                "stats": serialize.stats(tracks)}

    @api
    def library_pick(self):
        picked = self._pick_folder()
        if not picked:
            return None
        p = Path(picked)
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
        self._set_library(Library.create(folder, title.strip() or tr("name.default_library")))
        return self.state()["data"]

    @api
    def tracks(self):
        return [serialize.track_dict(t) for t in self._need().scan()]

    @api
    def open_folder(self, rel: str = ""):
        """Opens a folder of the library in Explorer. Never a file: startfile would run it."""
        target = inside(self._need().path, rel)
        if not target.is_dir():
            raise ValueError(tr("err.only_folders"))
        os.startfile(target)
        return True

    @api
    def open_url(self, url: str):
        """Opens YouTube links in the system browser (nothing else is allowed)."""
        import webbrowser
        from urllib.parse import urlsplit

        host = urlsplit(url).hostname or ""
        if urlsplit(url).scheme != "https" or not (host == "youtu.be" or host.endswith("youtube.com")):
            raise ValueError(tr("err.only_youtube"))
        webbrowser.open(url)
        return True

    # --- track actions -------------------------------------------------------------------
    @api
    def track_rename(self, base: str, artist: str, title: str):
        t = self._need().rename_track(self._track(base), artist, title)
        self._emit("library", {})
        return serialize.track_dict(t)

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
        return self._job(tr("job.multiplex", base=t.base), lambda p, c: serialize.track_dict(
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
                    _, st = build_guide(lib, t, lambda s, f=None, l=label: progress(f"{l} · {step_text(s)}", f), cancel)
                    out.append({"base": t.base, "stats": st})
                except Exception as e:
                    if type(e).__name__ == "Cancelled":
                        raise
                    out.append({"base": t.base, "error": str(e)})
            return out
        return self._job(tr("job.guide"), work, "guide")

    @api
    def find_clip(self, base: str):
        t = self._track(base)
        audio = t.file_with(AUDIO_EXTS)
        dur = media_duration(audio) if audio else None
        vids = pipeline.find_clip(t.artist, t.title)
        self._videos.update({v.id: v for v in vids})
        return {"duration": dur, "videos": [serialize.video_dict(v, dur) for v in vids]}

    @api
    def add_clip(self, base: str, video_id: str):
        lib, t, v = self._need(), self._track(base), self._videos[video_id]
        return self._job(tr("job.clip", base=t.base), lambda p, c: serialize.track_dict(pipeline.add_clip(lib, t, v, p, c)))

    @api
    def media(self, base: str, which: str = "audio"):
        t = self._track(base)
        if which == "video":
            return self._url(t.file_with(VIDEO_EXTS))
        return self._url(t.multiplex_file or t.file_with(AUDIO_EXTS) or t.file_with(VIDEO_EXTS))

    # --- settings ---------------------------------------------------------------------------------------
    @api
    def settings_get(self):
        data = read_manifest(self._need().path)
        return {"title": data.get("title", ""), "description": data.get("description", ""),
                "flags": [{"key": k, "label": tr(label), "value": flag_value(data, k)} for k, label, _ in FLAGS]}

    @api
    def settings_save(self, payload: dict):
        lib = self._need()
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError(tr("err.empty_name"))
        data = read_manifest(lib.path)
        data["title"], data["description"] = title, str(payload.get("description", "")).strip()
        for f in payload.get("flags", []):
            set_flag(data, f["key"], bool(f["value"]))
        ensure_additional(data)
        write_manifest(lib.path, data)
        return self.state()["data"]
