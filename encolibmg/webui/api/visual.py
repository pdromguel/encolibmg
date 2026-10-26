"""Look & sound screen: background videos, idle images, intro video, score narrations, SoundFont."""

from __future__ import annotations

from pathlib import Path

from encolibmg import soundfont, visual, youtube
from encolibmg.i18n import t as tr
from encolibmg.webui import views
from encolibmg.webui.api.core import ApiCore, api

VIDEO_TYPES = "*.mp4;*.mkv;*.webm;*.avi;*.mov;*.wmv;*.m4v"


class VisualApi(ApiCore):
    def _visual(self) -> dict:
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
    def visual_state(self):
        return self._visual()

    # --- background videos -------------------------------------------------------------
    @api
    def bgv_category(self, action: str, name: str, new: str = ""):
        lib = self._need()
        {"add": lambda: visual.add_category(lib, name), "rename": lambda: visual.rename_category(lib, name, new),
         "remove": lambda: visual.remove_category(lib, name)}[action]()
        return self._visual()

    @api
    def bgv_add_files(self, category: str):
        files = self._open_files((f"{tr('dialog.videos')} ({VIDEO_TYPES})", f"{tr('dialog.all')} (*.*)"), True)
        if not files:
            return None
        lib = self._need()

        def work(progress, cancel):
            for n, f in enumerate(files):
                progress(tr("step.prepare_file", name=Path(f).name), n / len(files))
                visual.add_bgv_file(lib, category, Path(f))
            return len(files)
        return self._job(tr("job.bgv_files", category=category), work, "visual")

    @api
    def bgv_search(self, query: str):
        vids = youtube.search(query, n=15)
        self._videos.update({v.id: v for v in vids})
        return [views.video_dict(v) for v in vids]

    @api
    def bgv_add_video(self, category: str, video_id: str):
        lib, v = self._need(), self._videos[video_id]
        return self._job(tr("job.bgv_video", title=v.title[:40]),
                         lambda p, c: visual.add_bgv_video(lib, category, v, p, c), "visual")

    @api
    def bgv_remove(self, category: str, rel: str):
        visual.remove_bgv(self._need(), category, rel)
        return self._visual()

    # --- idle images, intro video, narrations ----------------------------------------------
    @api
    def bumper_add(self):
        for f in self._open_files((f"{tr('dialog.images')} (*.png;*.jpg;*.jpeg;*.webp;*.gif)",), True):
            visual.add_bumper(self._need(), Path(f))
        return self._visual()

    @api
    def bumper_remove(self, rel: str):
        visual.remove_bumper(self._need(), rel)
        return self._visual()

    @api
    def boot_set(self):
        files = self._open_files((f"{tr('dialog.videos')} (*.mp4;*.mkv;*.webm;*.avi;*.mov)",))
        if not files:
            return None
        lib = self._need()
        return self._job(tr("job.boot"), lambda p, c: visual.set_boot_video(lib, Path(files[0])), "visual")

    @api
    def boot_clear(self):
        visual.clear_boot_video(self._need())
        return self._visual()

    @api
    def narration_set(self, lo: int, hi: int):
        files = self._open_files((f"{tr('dialog.audio')} (*.mp3;*.wav;*.ogg;*.m4a;*.flac)",))
        if not files:
            return None
        visual.set_narration(self._need(), int(lo), int(hi), Path(files[0]))
        return self._visual()

    @api
    def narration_remove(self, lo: int, hi: int):
        visual.remove_narration(self._need(), int(lo), int(hi))
        return self._visual()

    # --- SoundFont -------------------------------------------------------------------------------
    @api
    def soundfont_pick(self):
        files = self._open_files(("SoundFont (*.sf2;*.sf3;*.dls)",))
        if files:
            soundfont.install_soundfont(self._need(), Path(files[0]))
        return self._visual()

    @api
    def soundfont_download(self):
        lib = self._need()
        return self._job(tr("job.soundfont"), lambda p, c: soundfont.download_generaluser(
            lib, lambda f: p("step.download_soundfont", f), c), "visual")

    @api
    def soundfont_remove(self):
        soundfont.remove_soundfont(self._need())
        return self._visual()
