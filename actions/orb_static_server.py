"""Ship the genuine React/Three.js Orb in the main JARVIS Qt interface.

One loopback-only HTTP server per process. No external bind, proxy, upload,
commands or internet. The built bundle must be included in the Windows setup.
"""
from __future__ import annotations

import atexit
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_lock = threading.Lock()
_server = None
_server_root = None


class OrbStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def start_embedded_orb(dist: Path) -> str:
    """Return a localhost URL for the embedded production Orb.

    Raises FileNotFoundError when a genuine Vite bundle is not installed,
    allowing JARVIS to keep its original background unchanged.
    """
    global _server, _server_root
    dist = Path(dist).resolve(strict=True)
    if not (dist / "index.html").is_file() or not (dist / "assets").is_dir():
        raise FileNotFoundError("Compiled JARVIS Orb bundle missing")
    with _lock:
        if _server is not None:
            if _server_root != dist:
                raise RuntimeError("JARVIS Orb already serving another directory")
        else:
            handler = partial(OrbStaticHandler, directory=str(dist))
            _server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            _server.daemon_threads = True
            _server_root = dist
            threading.Thread(
                target=_server.serve_forever, name="jarvis-orb-loopback", daemon=True
            ).start()
            atexit.register(close_embedded_orb)
        return "http://127.0.0.1:{}/index.html?embed=1".format(
            _server.server_address[1]
        )


def close_embedded_orb() -> None:
    global _server, _server_root
    with _lock:
        server = _server
        _server = None
        _server_root = None
    if server is not None:
        server.shutdown()
        server.server_close()
