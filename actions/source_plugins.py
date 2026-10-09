"""JARVIS Source Plugins: integrate reviewed source repositories as modular abilities.

A plugin is a small manifest and a reviewed adapter, not a magical auto-build
of arbitrary GitHub code. Installed MCP-compatible CLIs can be connected without
modifying Jarvis again; other kinds of source need a purpose-built adapter.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import threading
from pathlib import Path

from actions.creative_studio import _McpSession, creative_studio
from core.user_paths import get_user_data_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "integrations" / "sources"
BUILTIN_EDITORS = {"photocraft", "lightcraft", "filmcraft"}
_ALLOWED_ADAPTERS = {"creative_studio", "mcp_stdio"}
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_ENV_PATTERN = re.compile(r"^JARVIS_[A-Z][A-Z0-9_]*_CLI$")
_sessions: dict[str, tuple[str, _McpSession]] = {}
_lock = threading.RLock()


class SourcePluginError(RuntimeError):
    """Known, user-facing source integration failure."""


def _manifest_paths():
    if not SOURCE_ROOT.is_dir():
        return
    root = SOURCE_ROOT.resolve()
    for item in sorted(SOURCE_ROOT.glob("*/manifest.json")):
        # Untrusted symlinks must not load manifests outside the plugin folder.
        if item.is_symlink() or item.parent.is_symlink():
            continue
        if not item.resolve().is_relative_to(root):
            continue
        yield item


def _read_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourcePluginError(f"Érvénytelen manifest: {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise SourcePluginError("A manifestnek JSON-objektumnak kell lennie.")
    plugin_id = data.get("id")
    adapter = data.get("adapter")
    if not isinstance(plugin_id, str) or not _ID_PATTERN.fullmatch(plugin_id):
        raise SourcePluginError(f"Érvénytelen pluginazonosító: {plugin_id!r}")
    if path.parent.name != plugin_id:
        raise SourcePluginError(f"A mappanév nem egyezik az azonosítóval: {plugin_id}")
    if adapter not in _ALLOWED_ADAPTERS:
        raise SourcePluginError(f"Nem támogatott adapter: {adapter}")
    if adapter == "creative_studio" and plugin_id not in BUILTIN_EDITORS:
        raise SourcePluginError("A creative_studio adapter csak a három ellenőrzött szerkesztőhöz használható.")
    if adapter == "mcp_stdio":
        variable = data.get("executable_env")
        arguments = data.get("args", ["mcp"])
        if not isinstance(variable, str) or not _ENV_PATTERN.fullmatch(variable):
            raise SourcePluginError("Az MCP pluginhoz JARVIS_*_CLI környezeti változó kell.")
        if (not isinstance(arguments, list) or len(arguments) > 25 or
                not all(isinstance(a, str) and 0 < len(a) <= 300 for a in arguments)):
            raise SourcePluginError("Az args mezőnek rövid sztringek listájának kell lennie.")
    data["enabled"] = data.get("enabled") is True
    data["name"] = str(data.get("name") or plugin_id)[:80]
    return data


def installed() -> dict[str, dict]:
    """Only manifests deliberately placed in the local Jarvis tree are trusted."""
    discovered = {}
    for path in _manifest_paths():
        try:
            manifest = _read_manifest(path)
            discovered[manifest["id"]] = manifest
        except SourcePluginError as exc:
            print(f"[Jarvis Source Plugins] {path}: {exc}")
    return discovered


def _binary_for(manifest: dict) -> str | None:
    from actions.creative_studio import _binary_path
    if manifest["adapter"] == "creative_studio":
        return _binary_path(manifest["id"])
    raw = os.environ.get(manifest["executable_env"], "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_file():
        return None
    # Avoid passing shell expressions. A binary path is not a command line.
    return str(path.resolve())


def _session(manifest: dict) -> _McpSession:
    plugin_id = manifest["id"]
    binary = _binary_for(manifest)
    if not binary:
        raise SourcePluginError(
            f"{manifest['name']} CLI nincs beállítva. "
            + (f"Állítsd be: {manifest['executable_env']}"
               if manifest["adapter"] == "mcp_stdio" else
               "Telepítsd a szerkesztő parancssori motorját.")
        )
    argv = [binary] + list(manifest.get("args", ["mcp"]))
    with _lock:
        cached = _sessions.get(plugin_id)
        signature = json.dumps(argv)
        if cached and cached[0] == signature and cached[1].process.poll() is None:
            return cached[1]
        if cached:
            cached[1].close()
        try:
            session = _McpSession(plugin_id, binary, command=argv)
        except Exception as exc:
            raise SourcePluginError(f"Az MCP-szerver nem indult: {exc}") from exc
        _sessions[plugin_id] = (signature, session)
        return session


def close_all():
    with _lock:
        for _, session in _sessions.values():
            session.close()
        _sessions.clear()


atexit.register(close_all)


def _safe_response(plugin_id: str, tool: str, result: object) -> str:
    """Avoid flooding the AI context with raw images or huge server outputs."""
    from actions.creative_studio import _public_result
    return _public_result(plugin_id, tool, result)


def source_plugins(parameters: dict | None = None, player=None) -> str:
    """Catalogue, status, inspect and execute installed source integrations.

    The AI never enables, installs or upgrades third-party code. Every MCP tool
    call must be explicitly accepted on the user's trusted confirmation HUD.
    """
    params = parameters or {}
    action = str(params.get("action") or "list").lower().strip()
    plugin_id = str(params.get("plugin") or "").lower().strip()
    manifests = installed()

    if action == "list":
        return json.dumps({
            key: {
                "name": m["name"], "source_url": m.get("source_url", ""),
                "adapter": m["adapter"], "enabled": m["enabled"],
                "cli_available": bool(_binary_for(m)),
                "capabilities": m.get("capabilities", []),
            }
            for key, m in manifests.items()
        }, ensure_ascii=False)
    if plugin_id not in manifests:
        return "Ismeretlen source-plugin. Az elérhető integrációkat a list művelet mutatja."
    manifest = manifests[plugin_id]
    if not manifest["enabled"]:
        return (f"A(z) {manifest['name']} plugin le van tiltva. "
                "Engedélyezéshez a helyi manifestet kell tudatosan módosítani.")

    if manifest["adapter"] == "creative_studio":
        action_map = {
            "status": "status", "discover": "discover",
            "inspect": "inspect", "execute": "execute", "batch": "batch",
        }
        if action not in action_map:
            return "Műveletek: list, status, discover, inspect, execute, batch."
        return creative_studio({
            "app": plugin_id, "operation": action_map[action],
            "tool": params.get("tool"), "arguments": params.get("arguments") or {},
            "steps": params.get("steps"), "filter": params.get("filter") or "",
            "limit": params.get("limit", 25),
        }, player=player)

    if action == "status":
        return json.dumps({
            "plugin": plugin_id, "enabled": True,
            "cli_available": bool(_binary_for(manifest)),
            "running": (plugin_id in _sessions and
                        _sessions[plugin_id][1].process.poll() is None),
        }, ensure_ascii=False)
    if action not in {"discover", "inspect", "execute", "batch"}:
        return "Műveletek: list, status, discover, inspect, execute, batch."

    try:
        session = _session(manifest)
        tools = session.list_tools()
        if action == "discover":
            query = str(params.get("filter") or "").lower()
            max_tools = max(1, min(60, int(params.get("limit", 25))))
            entries = [{
                "name": key, "description": str(value.get("description", ""))[:200],
                "input_schema": value.get("inputSchema", {}),
            } for key, value in tools.items()
               if not query or query in key.lower() or
               query in str(value.get("description", "")).lower()]
            return json.dumps({
                "plugin": plugin_id, "total": len(entries), "tools": entries[:max_tools],
            }, ensure_ascii=False, default=str)[:12000]

        if action == "batch":
            steps = params.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
                return "A batch 1-8 lépést tartalmazhat."
        else:
            steps = [{"tool": params.get("tool"),
                      "arguments": params.get("arguments", {})}]
        prepared = []
        for step in steps:
            if not isinstance(step, dict):
                return "A műveletnek JSON-objektumnak kell lennie."
            tool = step.get("tool")
            args = step.get("arguments")
            if not isinstance(tool, str) or tool not in tools:
                return f"Ismeretlen MCP-eszköz: {tool}"
            if not isinstance(args, dict):
                return "Az arguments mezőnek JSON-objektumnak kell lennie."
            prepared.append((tool, args))
        if len(json.dumps(steps, ensure_ascii=False, default=str)) > 65536:
            return "A művelet túl hosszú."
        if action == "inspect":
            # For unknown source repositories, a tool name/annotation does not
            # prove it is harmless, therefore confirmation is still mandatory.
            pass

        def execute():
            lines = []
            for tool, args in prepared:
                result = session.call_tool(tool, args)
                lines.append(_safe_response(plugin_id, tool, result))
                if isinstance(result, dict) and result.get("isError"):
                    break
            return "\n".join(lines)

        from core.confirm import request
        return request(
            f"source-{plugin_id}", f"Source plugin: {manifest['name']}",
            "Engedélyezed az alábbi MCP-műveleteket? "
            + ", ".join(tool for tool, _ in prepared),
            execute,
        )
    except (SourcePluginError, ValueError, RuntimeError, OSError,
            TimeoutError) as exc:
        return f"Source plugin hiba ({plugin_id}): {exc}"
