"""Per-session localhost approval broker for the JARVIS Windows MCP executor.

The Claude CLI's can_use_tool approval alone is not an executor authorization.
For desktop tools a user-approved request creates one scoped, expiring grant.
The MCP process must consume that exact grant before touching Windows.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_PREFIX = "mcp__brahma_windows__"
_MAX_BODY = 65536


def _canonical(arguments: dict) -> str:
    if not isinstance(arguments, dict):
        raise TypeError("tool arguments must be an object")
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class PermissionBroker:
    """Ephemeral, per-ClaudeSession, deny-by-default execution gate."""

    def __init__(self, ttl: float = 120.0):
        self.ttl = float(ttl)
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.Lock()
        self._grants: dict[str, tuple[str, str, float]] = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if self.path != "/authorize" or length < 1 or length > _MAX_BODY:
                    self._reply(400, False)
                    return
                supplied = self.headers.get("X-Brahma-Token", "")
                if not secrets.compare_digest(supplied, outer.token):
                    self._reply(403, False)
                    return
                try:
                    packet = json.loads(self.rfile.read(length))
                    name = packet["name"]
                    arguments = packet["arguments"]
                    if not isinstance(name, str):
                        raise ValueError("tool name must be text")
                    allowed = outer.consume(name, arguments)
                except (ValueError, TypeError, KeyError, UnicodeError):
                    self._reply(400, False)
                    return
                self._reply(200, allowed)

            def _reply(self, status: int, allowed: bool):
                body = json.dumps({"allow": allowed}).encode("ascii")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass  # no arguments or credentials in logs

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def grant(self, tool_name: str, arguments: dict) -> str | None:
        if not isinstance(tool_name, str) or not tool_name.startswith(_PREFIX):
            return None
        native_name = tool_name[len(_PREFIX):]
        if not native_name.startswith("desktop_"):
            return None
        key = uuid.uuid4().hex
        payload = _canonical(arguments)
        with self._lock:
            self._grants[key] = (native_name, payload, time.monotonic() + self.ttl)
        return key

    def revoke(self, grant_id: str | None):
        if grant_id:
            with self._lock:
                self._grants.pop(grant_id, None)

    def consume(self, name: str, arguments: dict) -> bool:
        try:
            payload = _canonical(arguments)
        except (TypeError, ValueError):
            return False
        now = time.monotonic()
        with self._lock:
            for key, (tool, expected, expires) in list(self._grants.items()):
                if expires <= now:
                    del self._grants[key]
                    continue
                if tool == name and secrets.compare_digest(expected, payload):
                    del self._grants[key]
                    return True
        return False

    def environment(self) -> dict[str, str]:
        return {"BRAHMA_MCP_BROKER_PORT": str(self.port),
                "BRAHMA_MCP_BROKER_TOKEN": self.token}

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        with self._lock:
            self._grants.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
