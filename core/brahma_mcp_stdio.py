"""Minimal Model Context Protocol stdio server for native Brahma Windows tools.

JSON-RPC 2.0 over UTF-8 JSONL. The bridge is intentionally self-contained
(no separate MCP Python dependency) and only offers desktop tools on Windows.
All tool calls still pass through Claude's MCP/tool permission system.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from urllib.request import Request, urlopen
from typing import Any

SERVER_NAME = "brahma-windows"
PROTOCOL_VERSION = "2025-03-26"

TOOLS = [
    {
        "name": "desktop_screenshot",
        "description": "Capture the current Windows desktop as a PNG image.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "desktop_click",
        "description": "Click a point on the Windows desktop.",
        "inputSchema": {"type": "object", "properties": {
            "x": {"type": "integer"}, "y": {"type": "integer"},
            "button": {"type": "string", "enum": ["left", "middle", "right"], "default": "left"},
        }, "required": ["x", "y"]},
    },
    {
        "name": "desktop_move",
        "description": "Move the mouse cursor.",
        "inputSchema": {"type": "object", "properties": {
            "x": {"type": "integer"}, "y": {"type": "integer"},
        }, "required": ["x", "y"]},
    },
    {
        "name": "desktop_type",
        "description": "Type text into the focused window; get permission before writing.",
        "inputSchema": {"type": "object", "properties": {
            "text": {"type": "string", "maxLength": 10000},
        }, "required": ["text"]},
    },
    {
        "name": "desktop_hotkey",
        "description": "Press a Windows keyboard shortcut (for example ctrl+shift+s).",
        "inputSchema": {"type": "object", "properties": {
            "keys": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
        }, "required": ["keys"]},
    },
    {
        "name": "desktop_scroll",
        "description": "Scroll vertically using the mouse.",
        "inputSchema": {"type": "object", "properties": {
            "amount": {"type": "integer", "minimum": -100, "maximum": 100},
        }, "required": ["amount"]},
    },
    {
        "name": "desktop_double_click",
        "description": "Double click a Windows desktop coordinate.",
        "inputSchema": {"type": "object", "properties": {
            "x": {"type": "integer"}, "y": {"type": "integer"},
        }, "required": ["x", "y"]},
    },
    {
        "name": "desktop_drag",
        "description": "Drag from one coordinate to another with the left mouse button.",
        "inputSchema": {"type": "object", "properties": {
            "start_x": {"type": "integer"}, "start_y": {"type": "integer"},
            "end_x": {"type": "integer"}, "end_y": {"type": "integer"},
        }, "required": ["start_x", "start_y", "end_x", "end_y"]},
    },
    {
        "name": "desktop_display_geometry",
        "description": "Return the size of the primary Windows screen.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "desktop_frontmost_window",
        "description": "Identify the current active Windows window title.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "desktop_running_apps",
        "description": "List running Windows processes (process id and name).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "desktop_installed_apps",
        "description": "List applications registered in Windows uninstall registry.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _text(message: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": error}


def _int(value: Any, label: str, minimum: int = -100000, maximum: int = 100000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid integer parameter {label}")
    return value


def _executor_permission(name: str, args: dict) -> bool:
    """A tool is never executed based only on its self-declared MCP parameters.

    This one-time grant is issued by the JARVIS UI after Claude's structured
    can_use_tool request; standalone/misconfigured MCP processes fail closed.
    """
    port = os.environ.get("BRAHMA_MCP_BROKER_PORT", "")
    token = os.environ.get("BRAHMA_MCP_BROKER_TOKEN", "")
    if not token or not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        return False
    try:
        payload = json.dumps({"name": name, "arguments": args}, ensure_ascii=False).encode("utf-8")
        if len(payload) > 65536:
            return False
        req = Request(
            f"http://127.0.0.1:{port}/authorize",
            data=payload,
            headers={"X-Brahma-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=3.0) as response:
            result = json.loads(response.read(1024))
        return result.get("allow") is True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _desktop_tool(name: str, args: dict) -> dict:
    if os.name != "nt":
        return _text("Brahma desktop tools are only supported on Windows.", True)
    # Import lazily: MCP initialize/tools/list should work without GUI libraries.
    import pyautogui

    # Move-to-corner emergency stop must never be disabled.
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08

    if name == "desktop_screenshot":
        output = io.BytesIO()
        pyautogui.screenshot().save(output, "PNG")
        return {"content": [{"type": "image", "data": base64.b64encode(output.getvalue()).decode("ascii"),
                             "mimeType": "image/png"}]}
    if name == "desktop_click":
        x, y = _int(args.get("x"), "x"), _int(args.get("y"), "y")
        button = args.get("button", "left")
        if button not in ("left", "middle", "right"):
            raise ValueError("Invalid mouse button")
        pyautogui.click(x=x, y=y, button=button)
        return _text("Clicked.")
    if name == "desktop_move":
        pyautogui.moveTo(_int(args.get("x"), "x"), _int(args.get("y"), "y"))
        return _text("Moved.")
    if name == "desktop_type":
        value = args.get("text")
        if not isinstance(value, str) or len(value) > 10000:
            raise ValueError("Invalid text")
        pyautogui.write(value, interval=0.005)
        return _text("Typed.")
    if name == "desktop_hotkey":
        keys = args.get("keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 6:
            raise ValueError("Invalid hotkey")
        allowed = {"ctrl", "alt", "shift", "win", "tab", "enter", "esc", "space", "backspace",
                   "delete", "up", "down", "left", "right", "home", "end", "a", "c", "v", "x",
                   "z", "s", "f", "p", "t", "w", "n", "f4", "f5", "f11", "f12"}
        if any(not isinstance(k, str) or k.lower() not in allowed for k in keys):
            raise ValueError("Unsupported hotkey; explicit allowlist applies")
        pyautogui.hotkey(*(k.lower() for k in keys))
        return _text("Hotkey pressed.")
    if name == "desktop_scroll":
        pyautogui.scroll(_int(args.get("amount"), "amount", -100, 100))
        return _text("Scrolled.")
    if name == "desktop_double_click":
        pyautogui.doubleClick(_int(args.get("x"), "x"), _int(args.get("y"), "y"), interval=0.15)
        return _text("Double-clicked.")
    if name == "desktop_drag":
        pyautogui.moveTo(_int(args.get("start_x"), "start_x"),
                         _int(args.get("start_y"), "start_y"))
        pyautogui.dragTo(_int(args.get("end_x"), "end_x"),
                         _int(args.get("end_y"), "end_y"), duration=0.4)
        return _text("Dragged.")
    if name == "desktop_display_geometry":
        width, height = pyautogui.size()
        return _text(json.dumps({"display": "primary", "width": width, "height": height}))
    if name == "desktop_frontmost_window":
        import pygetwindow
        window = pygetwindow.getActiveWindow()
        return _text(json.dumps({"title": window.title if window else ""}, ensure_ascii=False))
    if name == "desktop_running_apps":
        import psutil
        processes = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                processes.append({"pid": p.info["pid"], "name": p.info["name"]})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if len(processes) >= 150:
                break
        return _text(json.dumps(processes, ensure_ascii=False))
    if name == "desktop_installed_apps":
        import winreg
        collected = set()
        reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for arch in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, reg_path, 0, winreg.KEY_READ | arch) as root:
                        count = winreg.QueryInfoKey(root)[0]
                        for index in range(count):
                            try:
                                key = winreg.EnumKey(root, index)
                                with winreg.OpenKey(root, key) as item:
                                    name, _ = winreg.QueryValueEx(item, "DisplayName")
                                    if isinstance(name, str) and name.strip():
                                        collected.add(name.strip())
                            except OSError:
                                continue
                except OSError:
                    continue
        return _text(json.dumps(sorted(collected)[:250], ensure_ascii=False))
    return _text(f"Unknown Brahma tool: {name}", True)


def dispatch(message: dict) -> dict | None:
    method = message.get("method")
    if method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return {"protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS if os.name == "nt" else []}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name not in {tool["name"] for tool in TOOLS} or not isinstance(args, dict):
            return _text("Unknown tool or invalid arguments.", True)
        try:
            if not _executor_permission(name, args):
                return _text("JARVIS authorization required or expired for desktop tool.", True)
            return _desktop_tool(name, args)
        except Exception as exc:
            # No stack traces or potentially private inputs in protocol output.
            return _text(f"Desktop tool failed: {type(exc).__name__}", True)
    return {"_rpc_error": {"code": -32601, "message": "Method not found"}}


def serve() -> None:
    inp, out = sys.stdin, sys.stdout
    if inp is None or out is None:
        raise RuntimeError("MCP stdio requires redirected stdin/stdout.")
    for line in inp:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                continue
            request_id = message.get("id")
            result = dispatch(message)
            if request_id is None or result is None:
                continue
            if "_rpc_error" in result:
                response = {"jsonrpc": "2.0", "id": request_id, "error": result["_rpc_error"]}
            else:
                response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, TypeError):
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Invalid JSON-RPC request"}}
        out.write(json.dumps(response, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    serve()
