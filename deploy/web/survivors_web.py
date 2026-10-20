"""Static file server for the Survivors web build.

Loopback only: Tailscale Funnel is the way in. Serves a precompressed `<file>.gz`
when the browser accepts gzip, with the right type for .wasm. No directory listing,
GET/HEAD only, nothing outside the web root.
"""
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = os.path.realpath(os.environ.get("WEB_ROOT", "/opt/survivors-web/www"))
HOST = os.environ.get("WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEB_PORT", "8771"))

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/octet-stream", ".pck")


class Handler(BaseHTTPRequestHandler):
    server_version = "SurvivorsWeb"

    def _resolve(self):
        rel = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
        full = os.path.realpath(os.path.join(ROOT, rel))
        if full != ROOT and not full.startswith(ROOT + os.sep):
            return None
        return full if os.path.isfile(full) else None

    def _serve(self, head_only):
        full = self._resolve()
        if full is None:
            self.send_error(404)
            return
        gz = full + ".gz"
        use_gz = "gzip" in self.headers.get("Accept-Encoding", "") and os.path.isfile(gz)
        path = gz if use_gz else full
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Vary", "Accept-Encoding")
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
        # The page and service worker must always be rechecked; the big files are revalidated cheaply.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if head_only:
            return
        sent = 0
        started = time.monotonic()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)
                    sent += len(chunk)
        except OSError as e:
            sys.stderr.write("ABORT %s sent=%d/%d after=%.1fs err=%r ua=%s\n" % (
                self.path, sent, size, time.monotonic() - started, e, self.headers.get("User-Agent", "-")[:80]))
            return
        sys.stderr.write("DONE %s sent=%d gz=%s after=%.1fs ua=%s\n" % (
            self.path, sent, use_gz, time.monotonic() - started, self.headers.get("User-Agent", "-")[:80]))

    def do_GET(self):
        self._serve(False)

    def do_HEAD(self):
        self._serve(True)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
