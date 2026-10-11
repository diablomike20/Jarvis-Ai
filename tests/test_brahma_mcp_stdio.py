"""Self-contained MCP protocol smoke tests; no GUI or cloud dependencies."""
import io
import json
import unittest
from unittest import mock

from core import brahma_mcp_stdio as mcp


class TestBrahmaMcp(unittest.TestCase):
    def test_initialize_and_ping(self):
        result = mcp.dispatch({"method": "initialize"})
        self.assertEqual(result["serverInfo"]["name"], "brahma-windows")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(mcp.dispatch({"method": "ping"}), {})

    def test_notifications_have_no_response(self):
        self.assertIsNone(mcp.dispatch({"method": "notifications/initialized"}))

    def test_windows_only_tools_advertised(self):
        with mock.patch.object(mcp.os, "name", "nt"):
            names = {x["name"] for x in mcp.dispatch({"method": "tools/list"})["tools"]}
        self.assertIn("desktop_screenshot", names)
        self.assertIn("desktop_click", names)
        with mock.patch.object(mcp.os, "name", "posix"):
            self.assertEqual(mcp.dispatch({"method": "tools/list"})["tools"], [])

    def test_unknown_tool_rejected(self):
        bad = mcp.dispatch({"method": "tools/call", "params": {"name": "delete_all", "arguments": {}}})
        self.assertTrue(bad["isError"])

    def test_denies_windows_tools_on_linux(self):
        with mock.patch.object(mcp.os, "name", "posix"):
            result = mcp.dispatch({"method": "tools/call", "params": {
                "name": "desktop_click", "arguments": {"x": 1, "y": 2}
            }})
        self.assertTrue(result["isError"])

    def test_stdio_protocol_roundtrip(self):
        incoming = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n" +
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n" +
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        outgoing = io.StringIO()
        with mock.patch.object(mcp.sys, "stdin", incoming):
            with mock.patch.object(mcp.sys, "stdout", outgoing):
                mcp.serve()
        results = [json.loads(x) for x in outgoing.getvalue().splitlines()]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[1]["id"], 2)


if __name__ == "__main__":
    unittest.main()
