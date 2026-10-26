"""Import screen: scan a folder (CDs, CDG packs, .zip, .kar), edit the preview, import."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from encolibmg import importer
from encolibmg.i18n import t as tr
from encolibmg.webui import views
from encolibmg.webui.api.core import ApiCore, api, step_text


class ImportApi(ApiCore):
    def _init_areas(self):
        super()._init_areas()
        self._items: list = []
        self._import_tmp: Path | None = None  # where .zip files are unpacked; /media may serve it for previews

    def _extra_roots(self) -> list[Path]:
        return super()._extra_roots() + ([self._import_tmp] if self._import_tmp else [])

    def _items_out(self) -> list[dict]:
        return [views.import_dict(it, n) for n, it in enumerate(self._items)]

    @api
    def import_pick(self):
        return self._pick_folder()

    @api
    def import_scan(self, folder: str):
        lib = self._need()
        if self._import_tmp:
            shutil.rmtree(self._import_tmp, ignore_errors=True)
        self._import_tmp = Path(tempfile.mkdtemp(prefix="encolibmg-import-"))
        self._refresh_roots()
        self._items = importer.scan_source(Path(folder), self._import_tmp)
        importer.mark_existing(lib, self._items)
        return self._items_out()

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
        return self._items_out()

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
                                                  on_progress=lambda s, f=None, l=label: progress(f"{l} · {step_text(s)}", f),
                                                  **kw)
                except Exception as e:
                    if type(e).__name__ == "Cancelled":
                        raise
                    out[n] = f"error:{e}"
                it.status, it.selected = out[n], False
            return {"results": out, "items": self._items_out()}
        return self._job(tr("job.import"), work, "import")
