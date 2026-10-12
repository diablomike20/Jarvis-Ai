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
import queue
import time
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MARKER = "JARVIS_SOURCE_BUILD_SSE_OK"


class Fixture(BaseHTTPRequestHandler):
    requests_seen = 0
    request_paths = []
    lock = threading.Lock()

    def do_POST(self):
        with self.lock:
            type(self).requests_seen += 1
            type(self).request_paths.append(self.path[:120])
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
        # Keep stdin open until the SDK emits a result. subprocess.run(input=...)
        # closes stdin as soon as the single JSONL message has been sent; that
        # is not representative of JARVIS's long-lived bidirectional session.
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_queue: queue.Queue[str | None] = queue.Queue()
        finished = False
        timed_out = False
        stdin_error = ""
        with tempfile.TemporaryDirectory(prefix="jarvis-local-cli-") as cwd:
            process = subprocess.Popen(
                [args.node, str(args.cli.resolve()), "--print", "--verbose",
                 "--input-format", "stream-json", "--output-format", "stream-json",
                 "--permission-prompt-tool", "stdio", "--model", "jarvis-local-stub"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", env=env, cwd=cwd,
                bufsize=1,
            )
            def read_stdout():
                for line in process.stdout:
                    stdout_queue.put(line)
                stdout_queue.put(None)

            def read_stderr():
                for line in process.stderr:
                    stderr_lines.append(line)

            out_thread = threading.Thread(target=read_stdout, daemon=True)
            err_thread = threading.Thread(target=read_stderr, daemon=True)
            out_thread.start()
            err_thread.start()
            messages: list[dict] = []
            try:
                process.stdin.write(packet)
                process.stdin.flush()
                # Do not close stdin here: control_request/control_response
                # must remain possible during a complete CLI turn.
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    try:
                        line = stdout_queue.get(timeout=0.25)
                    except queue.Empty:
                        if process.poll() is not None and not out_thread.is_alive():
                            break
                        continue
                    if line is None:
                        break
                    stdout_lines.append(line)
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(value, dict):
                        messages.append(value)
                        if value.get("type") == "result":
                            finished = True
                            break
                else:
                    timed_out = True
            except (BrokenPipeError, OSError) as exc:
                stdin_error = type(exc).__name__
            finally:
                if process.stdin and not process.stdin.closed:
                    try:
                        process.stdin.close()
                    except OSError:
                        pass
                if process.poll() is None:
                    try:
                        process.wait(timeout=5 if finished else 1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                out_thread.join(timeout=2)
                err_thread.join(timeout=2)
            returncode = process.returncode

        # Structured evidence: no credentials or arbitrary request bodies.
        completed = [m for m in messages if m.get("type") == "result"]
        ok = (
            returncode == 0 and
            any(MARKER in str(m.get("result") or "") for m in completed)
        )
        summary = {
            "stage": "actual_compiled_cli_local_sse",
            "status": "PASS" if ok else "FAIL",
            "process_returncode": returncode,
            "event_types": [m.get("type") for m in messages[:30]],
            "result_event_present": bool(completed),
            "expected_fixture_token": ok,
            "stdin_kept_open_until_result": finished,
            "timed_out": timed_out,
            "stdin_error": stdin_error,
            "fixture_requests": Fixture.requests_seen,
            "fixture_paths": Fixture.request_paths[:12],
            "stdout_len": sum(len(x.encode("utf-8")) for x in stdout_lines),
            "stdout_prefix": "".join(stdout_lines)[:1200].replace("jarvis-local", "[LOCAL]"),
            "stderr_len": sum(len(x.encode("utf-8")) for x in stderr_lines),
            "stderr_tail": "".join(stderr_lines)[-1200:].replace("jarvis-local", "[LOCAL]"),
        }
        print(json.dumps(summary, ensure_ascii=False))
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
