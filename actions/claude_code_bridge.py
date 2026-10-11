"""JARVIS ↔ reconstructed Claude Code bridge (not an imitation agent)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.user_paths import get_user_data_dir
from core.claude_runtime import ClaudeRuntimeError, probe_claude_runtime, run_claude

SETTINGS_PATH = get_user_data_dir() / "config" / "app_settings.json"


def _load_settings() -> dict[str, Any]:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _selected_workspace(parameters: dict[str, Any]) -> str:
    # Explicit user paths are authoritative (and are validated by caller).
    direct = (
        parameters.get("workspace_path")
        or parameters.get("project_dir")
        or parameters.get("output_dir")
    )
    if direct:
        return str(direct).strip()
    configured = str(_load_settings().get("developer_mode_workspace") or "").strip()
    # Machine-specific settings checked into the old repository must not
    # break installs on other users' Windows profiles.
    if configured and Path(configured).expanduser().is_dir():
        return configured
    return str(Path.home() / "Desktop" / "BrahmaProjects")


def run_developer_mode_request(parameters: dict[str, Any], speak=None) -> str:
    """Use the actual source build, keeping its native planning/tool/agent loop.

    Integration control:
      action=status     -> no-network readiness check
      _on_claude_event  -> optional event callback (not part of JSON tool schema)
      _approve_tool     -> optional human authorization callback
      session_id        -> resume a previous session, if present
      engine=brahma_legacy -> explicitly request the old development agent
    """
    params = dict(parameters or {})
    if params.get("engine") == "brahma_legacy":
        from actions.brahma_dev_agent import run_dev_agent
        return run_dev_agent(params, speak=speak)

    if str(params.get("action") or "").lower() in {"status", "probe"}:
        return json.dumps(probe_claude_runtime(), ensure_ascii=False)

    description = str(
        params.get("description")
        or params.get("brief")
        or params.get("query")
        or params.get("prompt")
        or ""
    ).strip()
    if not description:
        return "Claude Code: adj meg feladatot (description, brief, prompt vagy query)."

    workspace = Path(_selected_workspace(params)).expanduser()
    # Avoid creating arbitrary user-provided paths implicitly.
    if not workspace.exists():
        default_dir = Path.home() / "Desktop" / "BrahmaProjects"
        if workspace != default_dir:
            return f"Claude Code: a megadott munkakönyvtár nem létezik: {workspace}"
        workspace.mkdir(parents=True, exist_ok=True)
    if not workspace.is_dir():
        return f"Claude Code: nem könyvtár: {workspace}"

    event_handler = params.get("_on_claude_event")
    approval_handler = params.get("_approve_tool")
    timeout = float(params.get("timeout") or 300)
    timeout = min(max(timeout, 10), 3600)
    turns = params.get("max_turns")
    max_turns = int(turns) if turns is not None else None

    try:
        result = run_claude(
            description, workspace,
            model=params.get("model"),
            timeout=timeout,
            max_turns=max_turns,
            resume=params.get("session_id"),
            on_event=event_handler if callable(event_handler) else None,
            approve_tool=approval_handler if callable(approval_handler) else None,
        )
        answer = result["text"] or "Claude Code befejezte a munkát, de nem adott szöveges összefoglalót."
        session = result.get("session_id")
        if session:
            answer += f"\n\n[Claude session: {session}]"
        return answer
    except (ClaudeRuntimeError, TimeoutError, ValueError, OSError) as exc:
        # Never silently fall back to a different agent and claim Claude ran.
        return f"Claude Code integrációs hiba: {exc}"
