"""Offline REAL reconstructed Claude CLI stdin/stdout acceptance test.

Runs the actual generated Node CLI against a disposable localhost Anthropic
Messages SSE fixture. Unlike mocked subprocess unit tests, this exercises the
real CLI parser, model transport, stream-json and result production. It does
NOT prove compatibility with every free cloud or local model.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MARKER = "JARVIS_SOURCE_BUILD_SSE_OK"


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length or 0))
        except (ValueError, TypeError):
            request = {}
        if self.path.startswith("/v1/messages/count_tokens"):
            return self._send_json({"input_tokens": 10})
        if "/messages" not in self.path:
            return self._send_json({"error": {"type": "not_found_error", "message": "Unknown path"}}, 404)
        model = request.get("model") or "jarvis-stub"
        if not request.get("stream"):
            return self._send_json({
                "id": "msg_jarvis_fixture", "type": "message", "role": "assistant",
                "model": model, "content": [{"type": "text", "text": MARKER}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            })
        events = [
            ("message_start", {"type": "message_start", "message": {
                "id": "msg_jarvis_fixture", "type": "message", "role": "assistant",
                "model": model, "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 0}}}),
            ("content_block_start", {"type": "content_block_start", "index": 0,
                "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": MARKER}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 5}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        data = "".join("event: " + event + "\ndata: " + json.dumps(message) + "\n\n"
                       for event, message in events).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self):
        self._send_json({"data": []})

    def _send_json(self, obj, status=200):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, format, *args):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if not args.cli.is_file():
        parser.error("Compiled Claude CLI is missing: " + str(args.cli))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = dict(os.environ)
        env.update({
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "ANTHROPIC_AUTH_TOKEN": "jarvis-local",
            "ANTHROPIC_API_KEY": "",
            "ANTHROPIC_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "jarvis-local-stub",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
            "CI": "1",
        })
        env.pop("OPENROUTER_API_KEY", None)
        packet = json.dumps({
            "type": "user", "session_id": "",
            "message": {"role": "user", "content": "Reply with " + MARKER},
            "parent_tool_use_id": None,
        }) + "\n"
        with tempfile.TemporaryDirectory(prefix="jarvis-local-cli-") as cwd:
            result = subprocess.run(
                [args.node, str(args.cli.resolve()), "--print", "--verbose",
                 "--input-format", "stream-json", "--output-format", "stream-json",
                 "--permission-prompt-tool", "stdio", "--model", "jarvis-local-stub"],
                input=packet, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd,
                timeout=args.timeout,
            )
        messages = []
        for line in result.stdout.splitlines():
            try:
                v = json.loads(line)
                if isinstance(v, dict):
                    messages.append(v)
            except ValueError:
                pass
        completed = [m for m in messages if m.get("type") == "result"]
        ok = result.returncode == 0 and any(MARKER in str(m.get("result") or "") for m in completed)
        print(json.dumps({
            "stage": "actual_compiled_cli_local_sse",
            "status": "PASS" if ok else "FAIL",
            "process_returncode": result.returncode,
            "event_types": [m.get("type") for m in messages],
            "result_event_present": bool(completed),
            "expected_fixture_token": ok,
            "stderr_tail": result.stderr[-1000:] if not ok else "",
        }, ensure_ascii=False))
        return 0 if ok else 1
    except subprocess.TimeoutExpired:
        print(json.dumps({"stage": "actual_compiled_cli_local_sse", "status": "TIMEOUT"}))
        return 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    sys.exit(main())
