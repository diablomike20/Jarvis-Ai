"""JARVIS Creative Studio: bridge to PhotoCraft, LightCraft and FilmCraft engines.

Each editor already exposes an MCP server. This adapter runs its *headless*
CLI locally via stdio, so the user can use hundreds of genuine editor commands
without embedding three incompatible Rust UIs or copying any third-party code.

Safety:
- no shell execution; only explicitly configured CLI executables
- PhotoCraft's file access is restricted to a per-user workspace by MCP roots
- all mutating MCP tools/commands require a real JARVIS HUD confirmation
- tool names are checked against tools/list; no arbitrary unregistered RPC
- responses are size-limited before passing them back to an LLM
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from core.user_paths import get_user_data_dir

APP_BINARIES = {
    "photocraft": ("PHOTOCRAFT", "photocraft-cli"),
    "lightcraft": ("LIGHTCRAFT", "lightcraft-cli"),
    "filmcraft": ("FILMCRAFT", "filmcraft-cli"),
}

# A discoverable catalogue, not a promise every particular binary supports
# every individual operation. tools/list returns the definitive capabilities.
CAPABILITY_CATALOGUE = {
    "photocraft": [
        "PSD megnyitása és mentése", "rétegek", "rétegmaszkok",
        "szöveg- és vektorrétegek", "ecsetek és kijelölések", "szűrők",
        "színkorrekció és görbék", "rétegeffektek", "átméretezés",
        "vágás és transzformáció", "képexport", "kötegelt képműveletek",
    ],
    "lightcraft": [
        "RAW/JPEG képek importálása", "fotók katalogizálása", "keresés és címkézés",
        "értékelés és válogatás", "expozíció és fehéregyensúly",
        "kontraszt és színek", "színkeverő és görbék", "presetek",
        "képkivágás és egyenesítés", "helyi maszkok", "zajszűrés",
        "részletkiemelés", "kötegelt fotóexport", "metaadatok",
    ],
    "filmcraft": [
        "videó és hang importálása", "projekt és bin kezelés",
        "többsávos idővonal", "klipdarabolás és vágás", "átmenetek",
        "színkorrekció és LUT-ok", "videóeffektek", "kulcsképkockák",
        "szövegek és feliratok", "hangkeverés és effektek",
        "hangerő-normalizálás", "feliratfájlok", "képkocka-előnézet",
        "formátumváltás", "projekt export és videórenderelés",
    ],
}

# Strict, narrow allowlist. Everything else (even a supposedly reversible
# edit) requires the user's *UI* confirmation, not an LLM-generated boolean.
READ_ONLY_TOOLS = {
    "photocraft": frozenset({
        "list_commands", "doc_inspect", "document_inspect", "session_inspect",
        "session_info", "render_preview", "inspect", "command_list",
    }),
    "lightcraft": frozenset({
        "list_commands", "list_controls", "query_photos", "get_develop",
        "render_photo", "inspect_ui", "list_widgets", "cmd_library_info",
        "cmd_photo_inspect", "cmd_presets_list",
    }),
    "filmcraft": frozenset({
        "command_list", "doc_inspect", "project_inspect",
        "sequence_inspect", "render_preview", "render_frame",
        "ui_inspect", "ui_elements",
    }),
}

_DEFAULT_TIMEOUT = 45.0
_MAX_INPUT_BYTES = 64 * 1024
_MAX_OUTPUT_CHARS = 12000
_SESSIONS: dict[str, "_McpSession"] = {}
_SESSIONS_LOCK = threading.Lock()


def _workspace() -> Path:
    folder = get_user_data_dir() / "creative_studio"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _binary_path(app: str) -> str | None:
    env_name, binary_name = APP_BINARIES[app]
    override = os.environ.get("JARVIS_" + env_name + "_CLI", "").strip()
    if override:
        path = Path(override).expanduser()
        # Avoid treating untrusted command lines (executable + flags) as paths.
        return str(path.resolve()) if path.is_file() else None
    found = shutil.which(binary_name)
    if found:
        return found

    # A convenient default for sibling clones built with cargo --release.
    base = Path(__file__).resolve().parents[1]
    for root in (base.parent / app, base / "craft" / app):
        suffix = ".exe" if os.name == "nt" else ""
        candidate = root / "target" / "release" / (binary_name + suffix)
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def _launch_args(app: str, binary: str) -> list[str]:
    workspace = _workspace()
    if app == "photocraft":
        # Capabilities granted to the Rust PhotoCraft server, not just a
        # Python-side string check. No access outside this folder.
        return [binary, "mcp",
                "--automation-read-root", str(workspace),
                "--automation-write-root", str(workspace)]
    if app == "lightcraft":
        return [binary, "mcp", "--compact", "--library",
                str(workspace / "lightcraft-library")]
    return [binary, "mcp"]


class _McpSession:
    def __init__(self, app: str, binary: str):
        self.app = app
        self.binary = binary
        self.lock = threading.RLock()
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._counter = 0
        self._tools: dict[str, dict] | None = None
        self._stderr_tail: list[str] = []
        self.process = subprocess.Popen(
            _launch_args(app, binary), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True,
                         name="jarvis-mcp-" + app).start()
        threading.Thread(target=self._read_stderr, daemon=True,
                         name="jarvis-mcp-errors-" + app).start()
        self._rpc(
            "initialize",
            {"protocolVersion": "2025-03-26", "capabilities": {},
             "clientInfo": {"name": "Jarvis-Creative-Studio", "version": "0.1"}},
            timeout=20,
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    self._responses.put(item)
            except (ValueError, UnicodeError):
                continue

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr_tail.append(line.strip()[:300])
            del self._stderr_tail[:-12]

    def _send(self, obj: dict) -> None:
        if self.process.poll() is not None:
            raise RuntimeError(f"{self.app} editor CLI has stopped.")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _rpc(self, method: str, params: dict, timeout: float = _DEFAULT_TIMEOUT):
        with self.lock:
            self._counter += 1
            identifier = self._counter
            self._send({"jsonrpc": "2.0", "id": identifier,
                        "method": method, "params": params})
            deadline = time.monotonic() + timeout
            while True:
                seconds = deadline - time.monotonic()
                if seconds <= 0:
                    raise TimeoutError(f"{self.app}: {method} exceeded {timeout}s.")
                try:
                    item = self._responses.get(timeout=min(seconds, 0.5))
                except queue.Empty:
                    if self.process.poll() is not None:
                        detail = "; ".join(self._stderr_tail[-4:])
                        raise RuntimeError(f"{self.app} CLI exited: {detail}")
                    continue
                if item.get("id") != identifier:
                    # Server notifications and unrelated messages are not the
                    # response to the current request.
                    continue
                if "error" in item:
                    raise RuntimeError(str(item["error"])[:1500])
                return item.get("result") or {}

    def list_tools(self) -> dict[str, dict]:
        if self._tools is None:
            found: dict[str, dict] = {}
            cursor = None
            for _ in range(20):
                result = self._rpc("tools/list", {"cursor": cursor} if cursor else {})
                for tool in result.get("tools", []):
                    if isinstance(tool, dict) and isinstance(tool.get("name"), str):
                        found[tool["name"]] = tool
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            self._tools = found
        return self._tools

    def call_tool(self, tool: str, arguments: dict):
        if tool not in self.list_tools():
            raise ValueError(
                f"Az '{tool}' eszköz nem található a {self.app} MCP listájában. "
                "Előbb kérd le az elérhető parancsokat."
            )
        return self._rpc("tools/call", {"name": tool, "arguments": arguments},
                         timeout=180.0)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()


def _session(app: str) -> _McpSession:
    binary = _binary_path(app)
    if binary is None:
        _, exe = APP_BINARIES[app]
        raise FileNotFoundError(
            f"{app} motor még nincs telepítve. Telepítsd a '{exe}' binárist, "
            f"vagy állítsd be a JARVIS_{APP_BINARIES[app][0]}_CLI környezeti változót."
        )
    with _SESSIONS_LOCK:
        existing = _SESSIONS.get(app)
        if existing and existing.binary == binary and existing.process.poll() is None:
            return existing
        if existing:
            existing.close()
        created = _McpSession(app, binary)
        _SESSIONS[app] = created
        return created


def close_all() -> None:
    with _SESSIONS_LOCK:
        for session in _SESSIONS.values():
            session.close()
        _SESSIONS.clear()


atexit.register(close_all)


def _public_result(app: str, tool: str, result: Any) -> str:
    """Strip binary image data and keep LLM responses small."""
    if isinstance(result, dict):
        clean = {}
        for key, value in result.items():
            if key == "content" and isinstance(value, list):
                clean[key] = [
                    {k: v for k, v in item.items()
                     if k not in ("data", "blob") and
                        (k != "text" or len(str(v)) < _MAX_OUTPUT_CHARS)}
                    if isinstance(item, dict) else str(item)[:300]
                    for item in value[:12]
                ]
            else:
                clean[key] = value
        result = clean
    body = json.dumps(result, ensure_ascii=False, default=str)
    if len(body) > _MAX_OUTPUT_CHARS:
        body = body[:_MAX_OUTPUT_CHARS] + '… [további tartalom levágva]'
    return f"{app}/{tool}: {body}"


def creative_studio(parameters: dict | None = None, player=None) -> str:
    """Entry point for the built-in Jarvis tool declaration.

    Operations: catalogue, status, discover, inspect (read-only MCP tool),
    execute and batch (require HUD confirmation unless all tools are read-only).
    """
    params = parameters or {}
    app = str(params.get("app", "all")).strip().lower()
    operation = str(params.get("operation", "catalogue")).strip().lower()
    if app not in APP_BINARIES and app != "all":
        return "Válassz: photocraft, lightcraft vagy filmcraft."

    if operation == "catalogue":
        apps = APP_BINARIES if app == "all" else (app,)
        return json.dumps(
            {name: {"areas": CAPABILITY_CATALOGUE[name],
                    "cli_available": _binary_path(name) is not None}
             for name in apps}, ensure_ascii=False
        )
    if operation == "status":
        apps = APP_BINARIES if app == "all" else (app,)
        return json.dumps(
            {name: {"cli": _binary_path(name),
                    "running": name in _SESSIONS and
                               _SESSIONS[name].process.poll() is None}
             for name in apps}, ensure_ascii=False
        )

    if app == "all":
        return "Ehhez egy konkrét szerkesztőt kell kiválasztani."

    try:
        session = _session(app)
        if operation == "discover":
            keyword = str(params.get("filter", "")).lower().strip()
            limit = max(1, min(60, int(params.get("limit", 25))))
            matched = [
                {"name": name, "description": str(info.get("description", ""))[:180],
                 "read_only": name in READ_ONLY_TOOLS[app]}
                for name, info in session.list_tools().items()
                if not keyword or keyword in (name + " " + str(info.get("description", ""))).lower()
            ]
            return json.dumps(
                {"app": app, "total_matches": len(matched), "tools": matched[:limit]},
                ensure_ascii=False,
            )
        if operation == "batch":
            steps = params.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
                return "A batch 1-8 lépést fogad listában."
            available = session.list_tools()
            prepared = []
            for entry in steps:
                if not isinstance(entry, dict):
                    return "Minden lépésnek JSON-objektumnak kell lennie."
                tool_name = entry.get("tool")
                tool_args = entry.get("arguments", {})
                if not isinstance(tool_name, str) or tool_name not in available:
                    return f"Nem létező MCP eszköz: {tool_name}."
                if not isinstance(tool_args, dict):
                    return "Minden arguments mezőnek JSON-objektumnak kell lennie."
                prepared.append((tool_name, tool_args))
            if len(json.dumps(steps, ensure_ascii=False, default=str)) > _MAX_INPUT_BYTES:
                return "Túl hosszú batch."
            def run_batch():
                results = []
                for tool_name, tool_args in prepared:
                    result = session.call_tool(tool_name, tool_args)
                    results.append(_public_result(app, tool_name, result))
                    if isinstance(result, dict) and result.get("isError"):
                        break
                return "\n".join(results)
            if all(name in READ_ONLY_TOOLS[app] for name, _ in prepared):
                return run_batch()
            from core.confirm import request
            return request(
                "creative-batch-" + app, f"Creative Studio: {app} batch",
                f"Engedélyezed ezt a {len(prepared)} lépéses műveletet? "
                + ", ".join(name for name, _ in prepared), run_batch,
            )
        if operation not in ("execute", "inspect"):
            return "Műveletek: catalogue, status, discover, inspect, execute, batch."

        tool = str(params.get("tool", "")).strip()
        args = params.get("arguments", {})
        if not tool or not isinstance(args, dict):
            return "Add meg az MCP tool nevét és egy JSON argumentum-objektumot."
        if len(json.dumps(args, ensure_ascii=False, default=str)) > _MAX_INPUT_BYTES:
            return "A parancs paraméterei túl nagyok."
        if tool not in session.list_tools():
            return f"Nincs ilyen MCP eszköz a(z) {app} programban: {tool}."

        read_only = tool in READ_ONLY_TOOLS[app]
        if operation == "inspect" and not read_only:
            return "Az inspect csak bizonyítottan olvasó műveletre használható."

        if read_only:
            return _public_result(app, tool, session.call_tool(tool, args))

        # Model-supplied "confirmed": true is intentionally ignored.
        from core.confirm import request
        return request(
            "creative-studio-" + app,
            f"Creative Studio: {app}",
            f"Engedélyezed a(z) {app} szerkesztőműveletet: {tool}? "
            f"Paraméterek: {json.dumps(args, ensure_ascii=False)[:900]}",
            lambda: _public_result(app, tool, session.call_tool(tool, args)),
        )
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        return f"Creative Studio hiba ({app}): {exc}"
