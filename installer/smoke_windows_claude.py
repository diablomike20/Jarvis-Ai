"""Offline functional smoke tests for an assembled Brahma/Claude Windows folder.

Checks actual packaged Node + Claude CLI execution and the companion MCP
process JSON-RPC handshake. No OpenRouter key and no user GUI session needed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def find_under(base: Path, relative: str) -> Path:
    for root in (base, base / "_internal"):
        candidate = root / Path(relative)
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Missing packaged runtime: {relative}")


def run_check(dist: Path) -> dict:
    gui = dist / "BrahmaEvo.exe"
    mcp = dist / "BrahmaMcp.exe"
    if not gui.is_file() or not mcp.is_file():
        raise RuntimeError("BrahmaEvo.exe or BrahmaMcp.exe missing from package")

    # Regression guard: the full original Brahma application must be present.
    # The new installer is more compressed than the historical installer,
    # so validate actual contents rather than guessing from archive size.
    app_roots = [dist / "_internal", dist]
    required = [
        "assets/web_background/index.html",
        "core/prompt.txt",
        "actions",
        "memory",
        "plugins",
        "features",
        "brahma_connect",
        "dashboard/static",
        "smart_home",
        "actions/creative_studio.py",
        "actions/freecad_plugin.py",
        "actions/jarvis_voice.py",
        "actions/local_stt.py",
        "core/claude_runtime.py",
        "core/claude_permission_broker.py",
    ]
    missing = [name for name in required
               if not any((root / name).exists() for root in app_roots)]
    if missing:
        raise RuntimeError("Original Brahma content missing: " + ", ".join(missing))

    # Exact original JARVIS delivery HUD (do not swap to an unrequested orb).
    import hashlib
    hud = find_under(dist, "assets/web_background/index.html").read_bytes().replace(b"\r\n", b"\n")
    hud_blob = hashlib.sha1(b"blob " + str(len(hud)).encode() + b"\0" + hud).hexdigest()
    if hud_blob != "81eca8399c0e92206ac79b88d8e62dbdad3a3a0c":
        raise RuntimeError("Original approved delivery HUD bytes changed")

    node = find_under(dist, "runtime/node/node.exe")
    cli = find_under(dist, "runtime/claude-code/dist/cli.js")
    manifest_path = find_under(dist, "runtime/claude-code/dist/claude-feature-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compiled = manifest.get("enabledCompileGates") or []
    if manifest.get("buildStatus") != "built-not-runtime-tested" or len(compiled) < 50:
        raise RuntimeError("Reconstructed Claude max-feature manifest not present or too small")

    env = dict(os.environ)
    env.update({
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
    })
    cli_version = subprocess.run(
        [str(node), str(cli), "--version"],
        cwd=str(dist), env=env, text=True, capture_output=True, timeout=40,
        check=True,
    )
    if "2.1.88" not in cli_version.stdout:
        raise RuntimeError(f"Unexpected reconstructed Claude version: {cli_version.stdout[:180]}")

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "jarvis-package-smoke", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "desktop_type", "arguments": {"text": "UNAUTHORIZED"}}},
    ]
    env.pop("BRAHMA_MCP_BROKER_PORT", None)
    env.pop("BRAHMA_MCP_BROKER_TOKEN", None)
    mcp_run = subprocess.run(
        [str(mcp)],
        input="".join(json.dumps(x) + "\n" for x in requests),
        text=True, capture_output=True, cwd=str(dist), env=env, timeout=45, check=True,
    )
    responses = [json.loads(line) for line in mcp_run.stdout.splitlines() if line.strip()]
    if len(responses) != 3:
        raise RuntimeError(f"MCP expected 3 JSON-RPC responses, got {len(responses)}")
    if responses[0].get("result", {}).get("serverInfo", {}).get("name") != "brahma-windows":
        raise RuntimeError("Wrong packaged MCP server")
    names = {tool["name"] for tool in responses[1].get("result", {}).get("tools", [])}
    if not {"desktop_screenshot", "desktop_click", "desktop_drag", "desktop_type"}.issubset(names):
        raise RuntimeError("Packaged native Windows MCP tools missing")

    denial = responses[2].get("result", {})
    if denial.get("isError") is not True:
        raise RuntimeError("Packaged Windows MCP executed tool without JARVIS approval")

    return {
        "compiled_feature_gates": len(compiled),
        "native_windows_mcp_tools": len(names),
        "original_brahma_content_verified": required,
        "packaged_files": sum(1 for item in dist.rglob("*") if item.is_file()),
        "packaged_bytes": sum(item.stat().st_size for item in dist.rglob("*") if item.is_file()),
        "claude_cli_version": cli_version.stdout.strip(),
        "source_build_audit": manifest.get("reconstructedNativePackages", {}),
        "notes": "No cloud model call or GUI click included in smoke test.",
    }


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/BrahmaEvo").resolve()
    print(json.dumps(run_check(folder), indent=2, ensure_ascii=False))
