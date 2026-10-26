"""About the app itself: version, a notice when a new release is out, updating yt-dlp."""

from __future__ import annotations

from encolibmg import __version__, updates
from encolibmg.core.i18n import t as tr
from encolibmg.webui.api.core import ApiCore, api


class SystemApi(ApiCore):
    @api
    def app_info(self):
        return {"version": __version__, "ytdlp": updates.ytdlp_version(), "releases": updates.RELEASES_PAGE}

    @api
    def check_updates(self, force: bool = False):
        """At startup the page calls this without `force` (GitHub is asked at most once a day)."""
        return updates.check(force=bool(force))

    @api
    def update_ytdlp(self):
        return self._job(tr("job.update_ytdlp"), lambda p, c: updates.update_ytdlp(p), "update")
