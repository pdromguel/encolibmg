"""Local HTTP server for the UI: static files + library media with Range (seek in audio/video).

Listens on 127.0.0.1 only, on a random port, and every request must carry the
session token (cookie `elt`, set when the page loads, or `?t=` on media URLs).
Media is served only from the roots the app allows (the open library, import temp).
"""

from __future__ import annotations

import mimetypes
import re
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

MIME = {
    ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
    ".svg": "image/svg+xml", ".woff2": "font/woff2", ".json": "application/json", ".png": "image/png",
    ".ico": "image/x-icon", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".wav": "audio/wav",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
    ".lrc": "text/plain", ".mid": "audio/midi", ".kar": "audio/midi", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}
CHUNK = 256 * 1024


class UIServer:
    def __init__(self, static_dir: Path, token: str | None = None):
        self.static_dir = Path(static_dir).resolve()
        self.token = token or secrets.token_urlsafe(18)
        self.roots: list[Path] = []
        self._httpd: ThreadingHTTPServer | None = None
        self.base_url = ""

    # --- configuration ----------------------------------------------------------
    def allow(self, root: Path) -> None:
        root = Path(root).resolve()
        if root not in self.roots:
            self.roots.append(root)

    def set_roots(self, roots: list[Path]) -> None:
        self.roots = [Path(r).resolve() for r in roots]

    def media_url(self, path: Path) -> str:
        p = Path(path).resolve().as_posix()
        return f"{self.base_url}/media/{quote(p, safe='/:')}?t={self.token}"

    # --- lifecycle --------------------------------------------------------------------
    def start(self) -> str:
        server = self

        class Handler(_Handler):
            ui = server

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self.base_url

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()

    def allowed(self, p: Path) -> bool:
        return any(p == r or r in p.parents for r in self.roots)


class _Handler(BaseHTTPRequestHandler):
    ui: UIServer
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the console quiet
        pass

    def _token_ok(self, query: dict) -> bool:
        if query.get("t", [None])[0] == self.ui.token:
            return True
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return "elt" in cookie and cookie["elt"].value == self.ui.token

    def _send_plain(self, code: int, text: str = ""):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        if not self._token_ok(query):
            return self._send_plain(403, "forbidden")
        path = unquote(parts.path)
        if path.startswith("/media/"):
            target = Path(path[len("/media/"):]).resolve()
            if not self.ui.allowed(target):
                return self._send_plain(403, "forbidden")
            return self._file(target, cache=False)
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (self.ui.static_dir / rel).resolve()
        if self.ui.static_dir not in target.parents:
            return self._send_plain(403, "forbidden")
        self._file(target, cache=False, set_cookie=path in ("", "/"))

    def _file(self, target: Path, cache: bool, set_cookie: bool = False):
        if not target.is_file():
            return self._send_plain(404, "not found")
        size = target.stat().st_size
        ctype = MIME.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        rng = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        partial = bool(rng) and size > 0
        if partial:
            a, b = rng.group(1), rng.group(2)
            if a:
                start, end = int(a), int(b) if b else size - 1
            else:  # suffix range: last N bytes
                start = max(0, size - int(b))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        length = end - start + 1 if size else 0
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store" if not cache else "max-age=3600")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if set_cookie:
            self.send_header("Set-Cookie", f"elt={self.ui.token}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        if self.command == "HEAD" or not length:
            return
        try:
            with open(target, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass  # the player seeked or closed; normal
