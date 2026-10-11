"""Hermetic tests of JARVIS ↔ real Claude CLI transport.

No network or actual Claude API calls. Run: python -m unittest tests.test_claude_runtime
"""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.claude_runtime import (
    ClaudeSession, ClaudeRuntimeError, provider_env, resolve_cli, run_claude,
)


class _OpenPipe(io.StringIO):
    def close(self):
        # Keep content inspectable after the mocked subprocess shuts down.
        pass


class _FakeProcess:
    def __init__(self, events):
        self.pid = 12345
        self.stdin = _OpenPipe()
        self.stdout = io.StringIO("".join(json.dumps(x) + "\n" for x in events))
        self.stderr = io.StringIO("")
        self.exit_code = None

    def poll(self):
        return self.exit_code

    def wait(self, timeout=None):
        self.exit_code = 0
        return 0

    def terminate(self):
        self.exit_code = 0

    def kill(self):
        self.exit_code = -9


class TestClaudeRuntime(unittest.TestCase):
    def test_openrouter_provider_is_explicit_and_privacy_enabled(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-testing"}, clear=False):
            env = provider_env({}, "openrouter/free")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://openrouter.ai/api")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "sk-or-testing")
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")
        self.assertEqual(env["DISABLE_TELEMETRY"], "1")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")
        self.assertEqual(env["ANTHROPIC_DEFAULT_OPUS_MODEL"], "openrouter/free")

    def test_missing_api_key_fails_closed(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            with mock.patch("core.claude_runtime._read_json", return_value={}):
                with self.assertRaises(ClaudeRuntimeError):
                    provider_env({})

    def test_no_system_cli_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("core.claude_runtime._paths_from_settings", return_value=[Path(d) / "none.js"]):
                with self.assertRaises(ClaudeRuntimeError):
                    resolve_cli({})

    def test_permission_approval_round_trip(self):
        session = object.__new__(ClaudeSession)
        packets = []
        session._send = packets.append
        request = {
            "type": "control_request", "request_id": "req-123",
            "request": {"subtype": "can_use_tool", "tool_name": "Bash",
                        "input": {"command": "git status"}},
        }
        session.respond_permission(request, True)
        packet = packets.pop()
        self.assertEqual(packet["response"]["request_id"], "req-123")
        self.assertEqual(packet["response"]["response"]["behavior"], "allow")
        self.assertEqual(packet["response"]["response"]["updatedInput"]["command"], "git status")
        session.respond_permission(request, False)
        self.assertEqual(packets[-1]["response"]["response"]["behavior"], "deny")

    def test_reject_non_permission_controls(self):
        session = object.__new__(ClaudeSession)
        session._send = mock.Mock()
        with self.assertRaises(ValueError):
            session.respond_permission(
                {"request_id": "x", "request": {"subtype": "initialize"}}, True
            )
        session._send.assert_not_called()

    def test_jsonl_events_and_default_denial(self):
        request = {
            "type": "control_request", "request_id": "tool-1",
            "request": {"subtype": "can_use_tool",
                        "tool_name": "Bash", "input": {"command": "echo ok"}},
        }
        fake = _FakeProcess([
            {"type": "system", "session_id": "sess-1"},
            request,
            {"type": "result", "session_id": "sess-1", "result": "Done.", "is_error": False},
        ])
        events = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-testing"}):
                with mock.patch("core.claude_runtime.resolve_cli", return_value=Path(tmp) / "dist" / "cli.js"):
                    with mock.patch("core.claude_runtime.resolve_node", return_value="node"):
                        with mock.patch("core.claude_runtime._settings", return_value={}):
                            with mock.patch("core.claude_runtime.subprocess.Popen", return_value=fake):
                                # The fake Popen also intercepts subprocess.run's taskkill.
                                with mock.patch("core.claude_runtime._terminate_tree", side_effect=lambda proc: proc.terminate()):
                                    result = run_claude("Fix bug", tmp, on_event=events.append, timeout=5)
        self.assertEqual(result["text"], "Done.")
        self.assertEqual(result["session_id"], "sess-1")
        self.assertEqual(len(events), 3)
        input_lines = [json.loads(x) for x in fake.stdin.getvalue().splitlines()]
        self.assertEqual(input_lines[0]["message"]["content"], "Fix bug")
        self.assertEqual(input_lines[1]["response"]["response"]["behavior"], "deny")

    def test_turn_cap_validation(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("core.claude_runtime.resolve_cli", return_value=Path(d) / "cli.js"):
                with mock.patch("core.claude_runtime.resolve_node", return_value="node"):
                    with mock.patch("core.claude_runtime._settings", return_value={}):
                        with self.assertRaises(ValueError):
                            ClaudeSession(d, max_turns=0)


if __name__ == "__main__":
    unittest.main()
