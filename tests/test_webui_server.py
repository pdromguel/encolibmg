import urllib.error
import urllib.request

import pytest

from encolibmg.webui.server import UIServer


@pytest.fixture
def srv(tmp_path):
    static = tmp_path / "static"
    (static / "js").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (static / "js" / "app.js").write_text("export const a = 1;", encoding="utf-8")
    lib = tmp_path / "Lib"
    lib.mkdir()
    (lib / "Águas de Março #2.mp3").write_bytes(bytes(range(256)) * 4)
    (tmp_path / "secret.txt").write_text("no")
    s = UIServer(static)
    s.start()
    s.allow(lib)
    yield s, lib, tmp_path
    s.stop()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_token_required(srv):
    s, *_ = srv
    assert get(s.base_url + "/")[0] == 403
    status, headers, body = get(f"{s.base_url}/?t={s.token}")
    assert status == 200 and b"<title>x</title>" in body
    assert "elt=" in headers.get("Set-Cookie", "")


def test_static_with_cookie_and_mime(srv):
    s, *_ = srv
    status, headers, body = get(s.base_url + "/js/app.js", {"Cookie": f"elt={s.token}"})
    assert status == 200 and headers["Content-Type"].startswith("text/javascript")
    assert get(s.base_url + "/js/../../secret.txt", {"Cookie": f"elt={s.token}"})[0] in (403, 404)


def test_media_range_with_accents_and_hash(srv):
    s, lib, _ = srv
    url = s.media_url(lib / "Águas de Março #2.mp3")
    status, headers, body = get(url)
    assert status == 200 and len(body) == 1024 and headers["Accept-Ranges"] == "bytes"
    status, headers, body = get(url, {"Range": "bytes=10-19"})
    assert status == 206 and body == bytes(range(10, 20))
    assert headers["Content-Range"] == "bytes 10-19/1024"
    status, _, body = get(url, {"Range": "bytes=1000-"})
    assert status == 206 and len(body) == 24


def test_media_outside_allowed_roots_is_forbidden(srv):
    s, lib, tmp = srv
    assert get(s.media_url(tmp / "secret.txt"))[0] == 403
    sneaky = s.media_url(lib / "Águas de Março #2.mp3").replace("Lib/", "Lib/../")
    assert get(sneaky.replace("%C3%81guas", "..%2Fsecret.txt"))[0] in (403, 404)


def test_media_needs_token(srv):
    s, lib, _ = srv
    url = s.media_url(lib / "Águas de Março #2.mp3").split("?")[0]
    assert get(url)[0] == 403
