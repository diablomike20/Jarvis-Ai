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
]


def _text(message: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": error}


def _int(value: Any, label: str, minimum: int = -100000, maximum: int = 100000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid integer parameter {label}")
    return value


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
