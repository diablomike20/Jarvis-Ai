"""Generic source-plugin tests using a real, temporary and harmless Python CLI.

No Craft app, Rust compiler, network connection, or installer is needed.
"""
import json
import sys

import pytest

from actions import source_plugins as registry
from actions import source_intent


def cli_manifest(tmp_path, monkeypatch):
    plugin_id = "test-cli"
    base = tmp_path / "manifests"
    directory = base / plugin_id
    directory.mkdir(parents=True)
    script = tmp_path / "dummy_source.py"
    script.write_text(
        "import json, sys\n"
        "print(json.dumps({'arguments': sys.argv[1:]}, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "id": plugin_id,
        "name": "Test CLI",
        "source_url": "https://github.com/example/test-cli",
        "adapter": "cli_commands",
        "enabled": True,
        "aliases": ["teszt parancsmodul"],
        "executable_env": "JARVIS_TEST_CLI",
        "commands": [
            {
                "name": "echo",
                "description": "Receive a Hungarian message as a CLI argument.",
                "args": [str(script), "{message}"],
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                "timeout_seconds": 10,
            },
            {
                "name": "version",
                "description": "Show local program version, no arguments.",
                "args": [str(script), "--version"],
                "parameters": {
                    "type": "object", "properties": {}, "required": [],
                },
            },
        ],
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(registry, "SOURCE_ROOT", base)
    monkeypatch.setenv("JARVIS_TEST_CLI", sys.executable)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    registry.close_all()
    return manifest, path


def test_generic_cli_can_be_registered_without_main_code_edit(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    found = registry.installed()
    assert found["test-cli"]["adapter"] == "cli_commands"
    assert found["test-cli"]["enabled"]
    available = json.loads(registry.source_plugins({"action": "list"}))
    assert available["test-cli"]["cli_available"] is True
    assert available["test-cli"]["aliases"] == ["teszt parancsmodul"]


def test_cli_discovery_returns_manifest_declarations(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    data = json.loads(registry.source_plugins({
        "plugin": "test-cli", "action": "discover", "filter": "echo",
    }))
    assert data["total"] == 1
    assert data["tools"][0]["name"] == "echo"
    assert data["tools"][0]["input_schema"]["required"] == ["message"]


def test_cli_never_executes_before_real_hud_confirmation(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    from core import confirm
    pending = []
    monkeypatch.setattr(confirm, "request",
                        lambda key, title, details, job: pending.append(job) or
                        "[CONFIRMATION_PENDING]")
    result = registry.source_plugins({
        "plugin": "test-cli", "action": "execute",
        "tool": "echo", "arguments": {"message": "Üdvözlöm, uram!"},
        "confirmed": True,
    })
    assert result == "[CONFIRMATION_PENDING]"
    assert len(pending) == 1
    response = pending[0]()
    assert "Üdvözlöm, uram!" in response
    assert '"isError": false' in response


def test_cli_does_not_interpret_shell_metacharacters(tmp_path, monkeypatch):
    manifest, path = cli_manifest(tmp_path, monkeypatch)
    adapter = registry._session(registry.installed()["test-cli"])
    text = "hello; echo PWNED | whoami"
    result = adapter.call_tool("echo", {"message": text})
    obj = result["structuredContent"]["json"]
    assert obj["arguments"] == [text]


def test_cli_rejects_option_injection(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    adapter = registry._session(registry.installed()["test-cli"])
    with pytest.raises(ValueError, match="nem kezdődhet"):
        adapter.call_tool("echo", {"message": "--force"})


def test_cli_rejects_unknown_args_and_unlisted_commands(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    adapter = registry._session(registry.installed()["test-cli"])
    with pytest.raises(ValueError, match="Ismeretlen paraméterek"):
        adapter.call_tool("echo", {"message": "hello", "shell": "anything"})
    with pytest.raises(ValueError, match="Ismeretlen source parancs"):
        adapter.call_tool("not-in-manifest", {})


@pytest.mark.parametrize("bad_args", [
    ["--convert", "prefix-{file}"],
    ["--convert", "{undeclared}"],
])
def test_manifest_rejects_bad_command_templates(tmp_path, monkeypatch, bad_args):
    _, path = cli_manifest(tmp_path, monkeypatch)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["commands"][0]["args"] = bad_args
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(registry.SourcePluginError):
        registry._read_manifest(path)


def test_manifest_rejects_unknown_schema_version(tmp_path, monkeypatch):
    _, path = cli_manifest(tmp_path, monkeypatch)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = 42
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(registry.SourcePluginError, match="manifest-verzió"):
        registry._read_manifest(path)


def test_source_alias_recognized_without_substring_collisions(tmp_path, monkeypatch):
    cli_manifest(tmp_path, monkeypatch)
    assert source_intent.match_source_plugin(
        "JARVIS, teszt parancsmodul: mutasd a funkciókat"
    ) == "test-cli"
    assert source_intent.match_source_plugin("ilyen a tesztem ma") is None


def test_batch_stops_when_a_cli_step_fails(tmp_path, monkeypatch):
    manifest, path = cli_manifest(tmp_path, monkeypatch)
    # A purposely failing command is a trusted test fixture, not arbitrary AI.
    fail_script = tmp_path / "fails.py"
    fail_script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    manifest["commands"].append({
        "name": "fail", "description": "Controlled test failure",
        "args": [str(fail_script)],
        "parameters": {"type": "object", "properties": {}, "required": []},
    })
    path.write_text(json.dumps(manifest), encoding="utf-8")
    from core import confirm
    callbacks = []
    monkeypatch.setattr(confirm, "request",
                        lambda key, title, detail, cb: callbacks.append(cb) or "pending")
    res = registry.source_plugins({
        "action": "batch", "plugin": "test-cli",
        "steps": [
            {"tool": "fail", "arguments": {}},
            {"tool": "echo", "arguments": {"message": "SHOULD-NOT-RUN"}},
        ],
    })
    assert res == "pending"
    output = callbacks[0]()
    assert '"isError": true' in output
    assert "SHOULD-NOT-RUN" not in output
