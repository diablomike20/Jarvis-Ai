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
import re
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
    message_requests_seen = 0
    request_paths = []
    scenario = 'normal'
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
        with self.lock:
            type(self).message_requests_seen += 1
            request_index = type(self).message_requests_seen
        if type(self).scenario == "overflow" and request_index == 1:
            return self._send_json({
                "type": "error",
                "error": {"type": "invalid_request_error", "message": "Prompt is too long"},
            }, 400)
        response_text = (
            "Summary of the user's goal: reply with the requested marker; no tools required."
            if type(self).scenario == "overflow" and request_index == 2 else MARKER
        )
        model = request.get("model") or "jarvis-stub"
        if not request.get("stream"):
            return self._send_json({
                "id": "msg_jarvis_fixture", "type": "message", "role": "assistant",
                "model": model, "content": [{"type": "text", "text": response_text}],
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
                "delta": {"type": "text_delta", "text": response_text}}),
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
    parser.add_argument("--scenario", choices=["normal", "overflow"], default="normal")
    args = parser.parse_args()
    if not args.cli.is_file():
        parser.error("Compiled Claude CLI is missing: " + str(args.cli))
    Fixture.scenario = args.scenario
    Fixture.requests_seen = 0
    Fixture.message_requests_seen = 0
    Fixture.request_paths = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = dict(os.environ)
        env.update({
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "ANTHROPIC_AUTH_TOKEN": "jarvis-local",
            "ANTHROPIC_API_KEY": "jarvis-local-fixture-only",
            "ANTHROPIC_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "jarvis-local-stub",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "jarvis-local-stub",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
            "CI": "1",
            "JARVIS_CLI_BOOT_TRACE": "1",
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
        with tempfile.TemporaryDirectory(prefix="jarvis-local-cli-", ignore_cleanup_errors=True) as cwd:
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

        # A --version fast-path can work while the actual CLI import is broken.
        # Probe --help (full CLI import) and one-shot text print only after FAIL.
        control_probes = {}
        if not finished:
            for label, argv in (
                ("help", ["--help"]),
                ("text_print", ["--print", "Reply with " + MARKER,
                                "--model", "jarvis-local-stub"]),
            ):
                try:
                    with tempfile.TemporaryDirectory(prefix="jarvis-cli-probe-", ignore_cleanup_errors=True) as probe_cwd:
                        probe = subprocess.run(
                            [args.node, str(args.cli.resolve()), *argv],
                            cwd=probe_cwd, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=25,
                        )
                    control_probes[label] = {
                        "exit_code": probe.returncode,
                        "stdout_len": len(probe.stdout),
                        "stdout_prefix": probe.stdout[:300].replace("jarvis-local", "[LOCAL]"),
                        "stderr_len": len(probe.stderr),
                        "stderr_prefix": probe.stderr[:300].replace("jarvis-local", "[LOCAL]"),
                    }
                except subprocess.TimeoutExpired:
                    control_probes[label] = {"timed_out": True}

        # In a debug-only unminified build, the stack points to an exact
        # generated bundle line. Expose only a few source-code lines (never
        # environment settings, HTTP headers or request bodies).
        failure_code_context = []
        stack_text = "".join(stderr_lines)
        locations = re.findall(r"cli[.]js:([0-9]+):([0-9]+)", stack_text)
        bundle_code = args.cli.resolve().parent / "cli.bundle" / "src" / "entrypoints" / "cli.js"
        if locations and bundle_code.is_file():
            target_line = int(locations[0][0])
            low, high = max(1, target_line - 3), target_line + 3
            if 0 < target_line < 5_000_000:
                try:
                    with bundle_code.open("r", encoding="utf-8", errors="replace") as code:
                        for line_no, body in enumerate(code, 1):
                            if low <= line_no <= high:
                                failure_code_context.append({
                                    "line": line_no, "code": body.strip()[:240],
                                })
                            if line_no >= high:
                                break
                except OSError:
                    failure_code_context = [{"note": "bundle read unavailable"}]

        # Structured evidence: no credentials or arbitrary request bodies.
        completed = [m for m in messages if m.get("type") == "result"]
        ok = (
            returncode == 0 and
            any(MARKER in str(m.get("result") or "") for m in completed) and
            (args.scenario != "overflow" or Fixture.message_requests_seen >= 3)
        )
        summary = {
            "stage": "actual_compiled_cli_local_sse",
            "scenario": args.scenario,
            "message_requests": Fixture.message_requests_seen,
            "status": "PASS" if ok else "FAIL",
            "process_returncode": returncode,
            "event_types": [m.get("type") for m in messages[:30]],
            "result_event_present": bool(completed),
            "result_errors": [str(e)[:240] for m in completed for e in (m.get("errors") or [])][:5],
            "result_subtypes": [m.get("subtype") for m in completed],
            "result_text": [str(m.get("result") or "")[:400] for m in completed],
            "assistant_models": [m.get("message", {}).get("model") for m in messages if m.get("type") == "assistant"],
            "assistant_content": [str(m.get("message", {}).get("content", ""))[:500] for m in messages if m.get("type") == "assistant"][:3],
            "expected_fixture_token": ok,
            "stdin_kept_open_until_result": finished,
            "timed_out": timed_out,
            "stdin_error": stdin_error,
            "failure_code_context": failure_code_context,
            "control_probes": control_probes,
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
