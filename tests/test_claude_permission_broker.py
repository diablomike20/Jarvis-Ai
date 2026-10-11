"""Executable offline regression tests for the actual JARVIS permission broker."""
import json
import os
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.claude_permission_broker import PermissionBroker
from core import brahma_mcp_stdio as mcp
from core.claude_runtime import ClaudeSession


class TestPermissionBroker(unittest.TestCase):
    def test_end_to_end_one_time_authorization_and_replay_denial(self):
        with PermissionBroker() as broker:
            args = {"x": 12, "y": 33}
            with mock.patch.dict(os.environ, broker.environment()):
                # No user permission: the real MCP dispatcher refuses execution.
                with mock.patch.object(mcp, "_desktop_tool") as execute:
                    denied = mcp.dispatch({"method": "tools/call", "params": {
                        "name": "desktop_click", "arguments": args}})
                    self.assertTrue(denied["isError"])
                    execute.assert_not_called()

                    session = object.__new__(ClaudeSession)
                    session._broker = broker
                    session._send = mock.Mock()
                    session.respond_permission({
                        "request_id": "real-control-1",
                        "request": {
                            "subtype": "can_use_tool",
                            "tool_name": "mcp__brahma_windows__desktop_click",
                            "input": args,
                        },
                    }, True)
                    execute.return_value = {"isError": False, "content": []}
                    first = mcp.dispatch({"method": "tools/call", "params": {
                        "name": "desktop_click", "arguments": args}})
                    self.assertFalse(first["isError"])
                    self.assertEqual(execute.call_count, 1)

                    # A grant is consumed exactly once.
                    replay = mcp.dispatch({"method": "tools/call", "params": {
                        "name": "desktop_click", "arguments": args}})
                    self.assertTrue(replay["isError"])
                    self.assertEqual(execute.call_count, 1)

    def test_argument_and_tool_binding(self):
        with PermissionBroker() as broker:
            broker.grant("mcp__brahma_windows__desktop_click", {"x": 1, "y": 2})
            self.assertFalse(broker.consume("desktop_click", {"x": 100, "y": 2}))
            self.assertFalse(broker.consume("desktop_move", {"x": 1, "y": 2}))
            self.assertTrue(broker.consume("desktop_click", {"y": 2, "x": 1}))

    def test_expiry_and_revocation(self):
        with PermissionBroker(ttl=-1) as broker:
            broker.grant("mcp__brahma_windows__desktop_type", {"text": "hello"})
            self.assertFalse(broker.consume("desktop_type", {"text": "hello"}))
        with PermissionBroker() as broker:
            key = broker.grant("mcp__brahma_windows__desktop_type", {"text": "x"})
            broker.revoke(key)
            self.assertFalse(broker.consume("desktop_type", {"text": "x"}))

    def test_bad_token_and_no_token_fail_closed(self):
        with PermissionBroker() as broker:
            broker.grant("mcp__brahma_windows__desktop_type", {"text": "test"})
            with mock.patch.dict(os.environ, {"BRAHMA_MCP_BROKER_PORT": str(broker.port),
                                             "BRAHMA_MCP_BROKER_TOKEN": "wrong"}):
                self.assertFalse(mcp._executor_permission("desktop_type", {"text": "test"}))
            with mock.patch.dict(os.environ, {"BRAHMA_MCP_BROKER_PORT": "",
                                             "BRAHMA_MCP_BROKER_TOKEN": ""}):
                self.assertFalse(mcp._executor_permission("desktop_type", {"text": "test"}))
            self.assertTrue(broker.consume("desktop_type", {"text": "test"}))

    def test_non_desktop_grant_not_issued(self):
        with PermissionBroker() as broker:
            self.assertIsNone(broker.grant("Bash", {"command": "echo ok"}))
            self.assertIsNone(broker.grant("mcp__untrusted__desktop_click", {"x": 1}))
            self.assertIsNone(broker.grant("mcp__brahma_windows__file_delete", {"path": "x"}))

    def test_denial_cannot_create_grant(self):
        with PermissionBroker() as broker:
            session = object.__new__(ClaudeSession)
            session._broker = broker
            session._send = mock.Mock()
            req = {"request_id": "req", "request": {"subtype": "can_use_tool",
                   "tool_name": "mcp__brahma_windows__desktop_click",
                   "input": {"x": 10, "y": 10}}}
            session.respond_permission(req, False)
            self.assertEqual(session._send.call_args.args[0]["response"]["response"]["behavior"], "deny")
            self.assertFalse(broker.consume("desktop_click", {"x": 10, "y": 10}))

    def test_send_failure_rolls_back_grant(self):
        with PermissionBroker() as broker:
            session = object.__new__(ClaudeSession)
            session._broker = broker
            session._send = mock.Mock(side_effect=BrokenPipeError("closed"))
            req = {"request_id": "req", "request": {"subtype": "can_use_tool",
                   "tool_name": "mcp__brahma_windows__desktop_click",
                   "input": {"x": 10, "y": 10}}}
            with self.assertRaises(BrokenPipeError):
                session.respond_permission(req, True)
            self.assertFalse(broker.consume("desktop_click", {"x": 10, "y": 10}))

    def test_missing_permission_broker_denies_direct_mcp(self):
        with mock.patch.dict(os.environ,
                {"BRAHMA_MCP_BROKER_PORT": "", "BRAHMA_MCP_BROKER_TOKEN": ""}):
            with mock.patch.object(mcp, "_desktop_tool") as execute:
                result = mcp.dispatch({"method": "tools/call", "params": {
                    "name": "desktop_type", "arguments": {"text": "not authorized"}}})
                self.assertTrue(result["isError"])
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
