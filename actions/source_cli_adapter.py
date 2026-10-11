"""Adapter for reviewed source projects that offer commands but no MCP server.

A source manifest defines a small, explicit command registry. The LLM cannot
supply executable names, flag names, shell snippets or command templates.
Only the parameter values within a reviewed command may vary, and JARVIS'
existing trusted CONFIRM/CANCEL UI gates execution.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from core.user_paths import get_user_data_dir

_TOKEN = re.compile(r"^\{([a-zA-Z][a-zA-Z0-9_]{0,63})\}$")
_MAX_OUTPUT = 12_000


class CliCommandAdapter:
    """One-shot CLI commands exposed through the same interface as MCP tools."""

    def __init__(self, plugin_id: str, executable: str, manifest: dict):
        self.plugin_id = plugin_id
        self.executable = str(Path(executable).resolve())
        self.commands = {item["name"]: item for item in manifest["commands"]}
        self._closed = False
        # Preserve the existing registry's session-liveness contract.
        self.process = self

    def poll(self) -> int | None:
        return 0 if self._closed else None

    def close(self) -> None:
        self._closed = True

    def list_tools(self) -> dict[str, dict]:
        return {
            name: {
                "name": name,
                "description": item["description"],
                "inputSchema": item["parameters"],
            }
            for name, item in self.commands.items()
        }

    @staticmethod
    def _coerce(name: str, value: Any, spec: dict) -> str:
        kind = spec.get("type")
        if kind == "string":
            if not isinstance(value, str):
                raise ValueError(f"'{name}' szöveges paramétert vár.")
            if not value or len(value) > 2048 or "\x00" in value or "\n" in value:
                raise ValueError(f"'{name}': érvénytelen szöveges paraméter.")
            # A dash-prefixed positional parameter could be parsed as an
            # additional CLI option; reject it even though shell=False.
            if value.startswith("-"):
                raise ValueError(f"'{name}': a paraméter nem kezdődhet '-' jellel.")
            converted = value
        elif kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"'{name}' egész számot vár.")
            converted = str(value)
        elif kind == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"'{name}' számot vár.")
            import math
            if not math.isfinite(value):
                raise ValueError(f"'{name}' csak véges szám lehet.")
            converted = str(value)
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"'{name}' logikai értéket vár.")
            converted = "true" if value else "false"
        else:
            raise ValueError(f"'{name}' ismeretlen paramétertípus.")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"'{name}' értéke nem szerepel az engedélyezett listában.")
        if kind in ("integer", "number"):
            if "minimum" in spec and value < spec["minimum"]:
                raise ValueError(f"'{name}' túl kicsi.")
            if "maximum" in spec and value > spec["maximum"]:
                raise ValueError(f"'{name}' túl nagy.")
        return converted

    def _argv(self, item: dict, args: dict) -> list[str]:
        schema = item["parameters"]
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        if not isinstance(args, dict):
            raise ValueError("A paramétereknek JSON-objektumnak kell lenniük.")
        unknown = set(args) - set(properties)
        if unknown:
            raise ValueError("Ismeretlen paraméterek: " + ", ".join(sorted(unknown)))
        missing = required - set(args)
        if missing:
            raise ValueError("Hiányzó paraméterek: " + ", ".join(sorted(missing)))
        argv = [self.executable]
        for token in item["args"]:
            match = _TOKEN.fullmatch(token)
            if match:
                field = match.group(1)
                argv.append(self._coerce(field, args[field], properties[field]))
            else:
                argv.append(token)
        return argv

    def call_tool(self, tool: str, arguments: dict):
        if self._closed:
            raise RuntimeError("A source adapter már leállt.")
        if tool not in self.commands:
            raise ValueError(f"Ismeretlen source parancs: {tool}")
        item = self.commands[tool]
        argv = self._argv(item, arguments)
        workspace = get_user_data_dir() / "source_workspaces" / self.plugin_id
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                argv, shell=False, cwd=str(workspace),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=item.get("timeout_seconds", 45),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"A(z) {tool} parancs időtúllépés miatt leállt.") from exc
        payload = {
            "exit_code": result.returncode,
            "stdout": result.stdout[:_MAX_OUTPUT],
            "stderr": result.stderr[:_MAX_OUTPUT],
        }
        if result.stdout:
            try:
                payload["json"] = json.loads(result.stdout[:_MAX_OUTPUT])
            except (ValueError, UnicodeError):
                pass
        return {"isError": result.returncode != 0, "structuredContent": payload}
