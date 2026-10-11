"""Bidirectional process adapter for the *reconstructed* Claude Code CLI.

Runs the exact locally built dist/cli.js. Does not silently substitute the
official Claude CLI or Brahma's old pseudo-Claude development agent.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from core.user_paths import get_user_data_dir

OPENROUTER_URL = "https://openrouter.ai/api"
END = object()


class ClaudeRuntimeError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _settings() -> dict:
    return _read_json(get_user_data_dir() / "config" / "app_settings.json")


def _openrouter_key() -> str:
    env_key = os.environ.get("OPENROUTER_API_KEY", "")
    if env_key:
        return env_key.strip()
    return str(_read_json(get_user_data_dir() / "config" / "api_keys.json").get("openrouter_api_key") or "").strip()


def _paths_from_settings(settings: dict) -> list[Path]:
    # No generic "claude" PATH fallback: users explicitly chose their own build.
    roots = [Path(__file__).resolve().parent.parent]
    if getattr(sys, "_MEIPASS", None):
        roots.append(Path(sys._MEIPASS))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(get_user_data_dir())
    candidates = [
        os.environ.get("BRAHMA_CLAUDE_CLI"),
        settings.get("claude_code_entrypoint"),
    ]
    result = [Path(p).expanduser() for p in candidates if isinstance(p, str) and p.strip()]
    for root in roots:
        result.extend([
            root / "runtime" / "claude-code" / "dist" / "cli.js",
            root / "claude-code-source-build" / "dist" / "cli.js",
            root / "runtime" / "claude" / "cli.js",
        ])
    return result


def resolve_cli(settings: Optional[dict] = None) -> Path:
    for candidate in _paths_from_settings(settings or _settings()):
        if candidate.is_file() and candidate.suffix.lower() in (".js", ".mjs", ".cjs"):
            return candidate.resolve()
    raise ClaudeRuntimeError(
        "A rekonstruált Claude Code build nem található. Fordítsd le a "
        "claude-code-source-build tárolót, majd állítsd be a "
        "'claude_code_entrypoint' értéket a dist/cli.js fájlra."
    )


def resolve_node() -> str:
    override = os.environ.get("BRAHMA_CLAUDE_NODE", "")
    if override and Path(override).is_file():
        return override
    node_roots = [Path(sys.executable).resolve().parent, get_user_data_dir()]
    if getattr(sys, "_MEIPASS", None):
        node_roots.insert(0, Path(sys._MEIPASS))
    for root in node_roots:
        exe = root / "runtime" / "node" / ("node.exe" if os.name == "nt" else "node")
        if exe.is_file():
            return str(exe)
    node = shutil.which("node")
    if not node:
        raise ClaudeRuntimeError("Node.js >=20 szükséges a rekonstruált Claude Code futtatásához.")
    return node


def provider_env(settings: dict, model: Optional[str] = None) -> dict[str, str]:
    key = _openrouter_key()
    if not key:
        raise ClaudeRuntimeError("Hiányzik az OpenRouter API-kulcs (openrouter_api_key vagy OPENROUTER_API_KEY).")
    chosen = str(model or settings.get("claude_code_model") or "openrouter/free").strip()
    if not chosen:
        raise ClaudeRuntimeError("Üres Claude Code modellazonosító.")
    env = dict(os.environ)
    env.update({
        "ANTHROPIC_BASE_URL": OPENROUTER_URL,
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_API_KEY": "",
        "OPENROUTER_API_KEY": key,
        "ANTHROPIC_MODEL": chosen,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": chosen,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": chosen,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": chosen,
        "CLAUDE_CODE_SUBAGENT_MODEL": chosen,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
        "PYTHONIOENCODING": "utf-8",
    })
    # The subprocess may execute MCP child processes from a user's workspace:
    # let Python resolve Brahma's core package when running from sources.
    root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    overrides = settings.get("claude_code_feature_overrides")
    if isinstance(overrides, dict):
        env["BRAHMA_CLAUDE_FEATURE_OVERRIDES"] = json.dumps(overrides, ensure_ascii=False)
    return env


def _native_windows_mcp() -> Optional[dict]:
    """Create a local stdio MCP server backed by Brahma's Windows capabilities."""
    if os.name != "nt":
        return None
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve().with_name("BrahmaMcp.exe")
        if not executable.is_file():
            raise ClaudeRuntimeError("Hiányzó natív Windows híd: BrahmaMcp.exe")
        command, args = str(executable), []
    else:
        command, args = sys.executable, ["-m", "core.brahma_mcp_stdio"]
    return {"mcpServers": {"brahma_windows": {"command": command, "args": args}}}


def _terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        process.terminate()
        process.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()


class ClaudeSession:
    """Long-lived JSONL subprocess: submit turns, receive events, answer controls.

    Caller controls tool authorizations using respond_permission(). No automatic
    elevation to bypassPermissions and no implicit permission approval.
    """
    def __init__(self, workspace: str | Path, model: Optional[str] = None,
                 max_turns: Optional[int] = None, resume: Optional[str] = None):
        self.settings = _settings()
        self.workspace = Path(workspace).expanduser().resolve()
        if not self.workspace.is_dir():
            raise ClaudeRuntimeError(f"Claude workspace nem létezik: {self.workspace}")
        cli = resolve_cli(self.settings)
        node = resolve_node()
        model_name = str(model or self.settings.get("claude_code_model") or "openrouter/free")
        cmd = [
            node, str(cli), "--print", "--verbose",
            "--input-format", "stream-json", "--output-format", "stream-json",
            "--permission-prompt-tool", "stdio", "--model", model_name,
        ]
        if max_turns is not None:
            if not 1 <= max_turns <= 10000:
                raise ValueError("max_turns must be in the interval 1..10000")
            cmd += ["--max-turns", str(max_turns)]
        if resume:
            cmd += ["--resume", str(resume)]
        if self.settings.get("claude_code_windows_mcp", True):
            native_mcp = _native_windows_mcp()
            if native_mcp:
                cmd += ["--mcp-config", json.dumps(native_mcp)]
        self._process = subprocess.Popen(
            cmd, cwd=str(self.workspace), env=provider_env(self.settings, model_name),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        self._queue: queue.Queue = queue.Queue()
        self._stderr: list[str] = []
        self._write_lock = threading.Lock()
        self.session_id: Optional[str] = None
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._err_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._err_reader.start()

    @property
    def process_id(self) -> int:
        return self._process.pid

    @property
    def alive(self) -> bool:
        return self._process.poll() is None

    @property
    def errors(self) -> str:
        # Prevent key disclosure through exception messages.
        joined = "\n".join(self._stderr[-40:])
        return joined.replace(_openrouter_key(), "[REDACTED]") if _openrouter_key() else joined

    def _read_stdout(self) -> None:
        try:
            for line in self._process.stdout:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        if value.get("session_id"):
                            self.session_id = value["session_id"]
                        self._queue.put(value)
                    else:
                        self._queue.put({"type": "unparsed", "value": value})
                except ValueError:
                    self._queue.put({"type": "log", "message": line.rstrip()})
        finally:
            self._queue.put(END)

    def _read_stderr(self) -> None:
        for line in self._process.stderr:
            self._stderr.append(line.rstrip()[:2000])
            if len(self._stderr) > 100:
                self._stderr.pop(0)

    def _send(self, obj: dict) -> None:
        with self._write_lock:
            if self._process.poll() is not None or self._process.stdin is None:
                raise ClaudeRuntimeError("Claude subprocess már nem fut.")
            self._process.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self._process.stdin.flush()

    def submit(self, prompt: str) -> None:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A Claude-prompt nem lehet üres.")
        self._send({
            "type": "user", "session_id": self.session_id or "",
            "message": {"role": "user", "content": prompt},
            "parent_tool_use_id": None,
        })

    def respond_permission(self, request: dict, allow: bool,
                           reason: str = "Brahma user approval required") -> None:
        request_id = request.get("request_id")
        body = request.get("request")
        if not isinstance(request_id, str) or not isinstance(body, dict):
            raise ValueError("Invalid Claude control request")
        if body.get("subtype") != "can_use_tool":
            raise ValueError("Only can_use_tool control requests are handled here")
        tool_input = body.get("input") if isinstance(body.get("input"), dict) else {}
        decision = (
            {"behavior": "allow", "updatedInput": tool_input}
            if allow else {"behavior": "deny", "message": reason}
        )
        self._send({
            "type": "control_response",
            "response": {"subtype": "success", "request_id": request_id, "response": decision},
        })

    def events(self, timeout: float = 300) -> Iterator[dict]:
        """Yield structured events; raises TimeoutError rather than hanging forever."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Claude event stream timed out")
            try:
                event = self._queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                if not self.alive and not self._reader.is_alive():
                    return
                continue
            if event is END:
                return
            yield event

    def cancel(self) -> None:
        _terminate_tree(self._process)

    def close(self) -> None:
        if self._process.stdin and not self._process.stdin.closed:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        if self.alive:
            self.cancel()
        self._reader.join(timeout=1)
        self._err_reader.join(timeout=1)

    def __enter__(self) -> "ClaudeSession":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def run_claude(prompt: str, workspace: str | Path, *,
               model: Optional[str] = None, timeout: float = 300,
               max_turns: Optional[int] = None, resume: Optional[str] = None,
               on_event: Optional[Callable[[dict], Any]] = None,
               approve_tool: Optional[Callable[[dict], bool]] = None) -> dict:
    """One-shot convenience. The raw ClaudeSession API supports multiple turns.

    Permission requests are denied unless the caller has an explicit approval
    callback. Event callbacks can update Brahma's task UI in real time.
    """
    result = None
    with ClaudeSession(workspace, model=model, max_turns=max_turns, resume=resume) as session:
        session.submit(prompt)
        for event in session.events(timeout=timeout):
            if on_event:
                on_event(event)
            if event.get("type") == "control_request":
                request = event.get("request") or {}
                if request.get("subtype") == "can_use_tool":
                    allow = bool(approve_tool(event)) if approve_tool else False
                    session.respond_permission(event, allow)
            if event.get("type") == "result":
                result = event
                break
        if not result:
            raise ClaudeRuntimeError("Claude nem adott result eseményt. " + session.errors[:1400])
        if result.get("is_error"):
            raise ClaudeRuntimeError("Claude hiba: " + str(result.get("result") or session.errors)[:1400])
        return {"text": str(result.get("result") or ""), "session_id": session.session_id,
                "usage": result.get("usage"), "result": result}


def probe_claude_runtime() -> dict:
    """No network calls and no model requests; suitable for diagnostics."""
    settings = _settings()
    try:
        cli = resolve_cli(settings)
        node = resolve_node()
        key_present = bool(_openrouter_key())
        native_mcp_ready = True
        if settings.get("claude_code_windows_mcp", True) and os.name == "nt":
            try:
                _native_windows_mcp()
            except ClaudeRuntimeError:
                native_mcp_ready = False
        return {
            "ready": key_present and native_mcp_ready,
            "cli": str(cli), "node": node,
            "windows_native_mcp_ready": native_mcp_ready,
            "openrouter_key_configured": key_present,
            "model": settings.get("claude_code_model", "openrouter/free"),
            "provider": "OpenRouter",
            "note": "Build availability only; native features and model compatibility require tests.",
        }
    except ClaudeRuntimeError as exc:
        return {"ready": False, "reason": str(exc)}
