"""Opt-in REAL model/CLI test against the user's free or local provider.

Run from JARVIS source after preparing the bundled Claude runtime:
    python scripts/verify_live_claude.py

Requires user's own OpenRouter free key or local Anthropic-compatible server.
Never uploads a secret, never auto-approves any tool, and never uses paid models.
The GitHub CI does NOT run this automatically.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.claude_runtime import ClaudeRuntimeError, probe_claude_runtime, run_claude  # noqa: E402

MARKER = "JARVIS_NEXTGEN_REAL_MODEL_OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="Live, free/local Claude Source Build model-response acceptance test")
    parser.add_argument("--workspace", type=Path, help="Existing workspace (defaults to a disposable temp directory)")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    preflight = probe_claude_runtime()
    print(json.dumps({
        "stage": "preflight",
        "engine": "user-owned-reconstructed-claude-source-build",
        "configured": preflight.get("ready", False),
        "model": preflight.get("model"),
        "provider": preflight.get("provider"),
        "readiness_scope": preflight.get("ready_scope"),
    }, ensure_ascii=False))
    if not preflight.get("ready"):
        print("Claude engine or provider is not configured. No network/model call was made.", file=sys.stderr)
        return 2

    tmp = None
    try:
        if args.workspace:
            workspace = args.workspace.expanduser().resolve()
            if not workspace.is_dir():
                raise ValueError("Workspace must be an existing directory.")
        else:
            tmp = tempfile.TemporaryDirectory(prefix="jarvis-live-source-build-")
            workspace = Path(tmp.name)

        events: dict[str, int] = {}
        def on_event(event: dict):
            name = str(event.get("type", "unknown"))
            events[name] = events.get(name, 0) + 1

        prompt = (
            "This is a harmless JARVIS integration acceptance test. "
            "Do not call tools and do not modify files. "
            "Reply with the exact uppercase token: " + MARKER
        )
        started = time.monotonic()
        answer = run_claude(
            prompt, workspace, timeout=args.timeout,
            max_turns=2, on_event=on_event,
            approve_tool=lambda event: False,  # Always deny tool side effects.
        )
        ok = MARKER in answer["text"]
        print(json.dumps({
            "stage": "live_source_build_model_response",
            "status": "PASS" if ok else "FAIL",
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "event_counts": events,
            "session_created": bool(answer.get("session_id")),
            "expected_marker_found": ok,
        }, ensure_ascii=False))
        return 0 if ok else 1
    except (ClaudeRuntimeError, TimeoutError, ValueError, OSError) as exc:
        # Never dump auth headers, environment variables or API tokens.
        print(json.dumps({
            "stage": "live_source_build_model_response",
            "status": "FAIL",
            "exception": type(exc).__name__,
            "note": "See local JARVIS application diagnostics; never publish logs with credentials.",
        }, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
