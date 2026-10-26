"""Check screen: find what Encore would ignore or show wrong, and fix it."""

from __future__ import annotations

from encolibmg.library import checker
from encolibmg.core.i18n import t as tr
from encolibmg.webui import serialize
from encolibmg.webui.api.core import ApiCore, api


class CheckApi(ApiCore):
    def _init_areas(self):
        super()._init_areas()
        self._issues: list = []

    @api
    def check(self, loudness: bool = False):
        lib = self._need()

        def work(progress, cancel):
            progress("step.check", None)
            self._issues = checker.check(lib, include_loudness=loudness, cancel=cancel, on_progress=progress)
            return [serialize.issue_dict(i, n, lib) for n, i in enumerate(self._issues)]
        return self._job(tr("job.check"), work, "check")

    @api
    def fix(self, ids: list[int]):
        lib, issues = self._need(), list(self._issues)
        todo = [int(i) for i in ids if 0 <= int(i) < len(issues) and issues[int(i)].fixable]

        def work(progress, cancel):
            out = {}
            for n, i in enumerate(todo):
                if cancel.is_set():
                    break
                progress(tr("step.fixing", n=n + 1, total=len(todo)), n / max(1, len(todo)))
                try:
                    out[i] = {"ok": True, "message": checker.fix(lib, issues[i])}
                except Exception as e:
                    out[i] = {"ok": False, "message": str(e) or type(e).__name__}
            return out
        return self._job(tr("job.fix"), work, "fix")
