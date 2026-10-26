import subprocess

import pytest
import requests

from encolibmg import updates


class Resp:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class Session:
    def __init__(self, resp=None, error=None):
        self.resp, self.error, self.calls = resp, error, 0

    def get(self, *a, **k):
        self.calls += 1
        if self.error:
            raise self.error
        return self.resp


RELEASE = {"tag_name": "v1.0.0", "html_url": "https://github.com/pdromguel/encolibmg/releases/tag/v1.0.0",
           "name": "EncoLibMG 1.0.0"}


def test_parse_version():
    assert updates.parse_version("v1.2.10") > updates.parse_version("1.2.9")
    assert updates.parse_version("0.10.0") > updates.parse_version("0.9.0")
    assert updates.parse_version("1.0.0-beta") == (1, 0, 0)


def test_latest_release_and_offline():
    assert updates.latest_release(Session(Resp(200, RELEASE)))["version"] == "1.0.0"
    assert updates.latest_release(Session(Resp(404))) is None          # no release published yet
    assert updates.latest_release(Session(error=requests.ConnectionError())) is None


def test_check_once_a_day(monkeypatch):
    monkeypatch.setattr(updates, "__version__", "0.9.0")
    s = Session(Resp(200, RELEASE))
    res = updates.check(session=s, now=lambda: 1000.0)
    assert res["newer"] and res["latest"] == "1.0.0" and res["url"].endswith("v1.0.0")
    again = updates.check(session=s, now=lambda: 1000.0 + 3600)       # an hour later: remembered, not asked
    assert again == res and s.calls == 1
    updates.check(session=s, now=lambda: 1000.0 + 3600, force=True)  # "Check now" always asks
    assert s.calls == 2
    monkeypatch.setattr(updates, "__version__", "1.0.0")
    assert not updates.check(session=s, now=lambda: 1000.0 + 3600)["newer"]


def test_update_ytdlp(monkeypatch):
    versions = iter(["2025.1.1", "2025.6.30"])
    monkeypatch.setattr(updates, "ytdlp_version", lambda: next(versions))
    calls = []
    monkeypatch.setattr(updates.subprocess, "run",
                        lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    assert updates.update_ytdlp() == {"before": "2025.1.1", "after": "2025.6.30", "changed": True}
    assert calls[0][1:] == ["-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp"]


def test_update_ytdlp_failure_is_readable(monkeypatch):
    monkeypatch.setattr(updates, "ytdlp_version", lambda: "2025.1.1")
    monkeypatch.setattr(updates.subprocess, "run",
                        lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "ERROR: no internet\n"))
    with pytest.raises(RuntimeError, match="no internet"):
        updates.update_ytdlp()
