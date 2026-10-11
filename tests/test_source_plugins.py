"""Tests of the generic, reviewed-source integration foundation.

No third-party executable, network calls, voice device or editing models are used.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from actions import source_plugins as registry
from actions import source_intent


def install_manifest(tmp_path, plugin_id="my-tool", *, enabled=True,
                     adapter="mcp_stdio", args=None):
    directory = tmp_path / plugin_id
    directory.mkdir(parents=True)
    payload = {
        "schema_version": 1, "id": plugin_id, "name": "My Tool",
        "source_url": "https://github.com/example/my-tool",
        "adapter": adapter, "enabled": enabled,
        "executable_env": "JARVIS_MY_TOOL_CLI",
        "args": ["mcp"] if args is None else args,
        "capabilities": ["Testable custom source plugin"],
    }
    (directory / "manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return directory / "manifest.json"


class FakeMcp:
    def __init__(self):
        self.called = []
        self.process = SimpleNamespace(poll=lambda: None)

    def list_tools(self):
        return {
            "hello": {"name": "hello", "description": "Respond to requests"},
            "file_mutate": {"name": "file_mutate", "description": "Modify data"},
        }

    def call_tool(self, name, args):
        self.called.append((name, args))
        return {"structuredContent": {"ok": True, "tool": name}, "isError": False}

    def close(self):
        pass


def test_bundled_manifests_include_three_editors_and_disabled_example():
    installed = registry.installed()
    assert {"photocraft", "lightcraft", "filmcraft", "example-mcp"} <= set(installed)
    assert all(installed[x]["adapter"] == "creative_studio"
               for x in ("photocraft", "lightcraft", "filmcraft"))
    assert installed["example-mcp"]["enabled"] is False


def test_register_new_source_without_editing_python_code(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    found = registry.installed()
    assert found["my-tool"]["adapter"] == "mcp_stdio"
    assert found["my-tool"]["enabled"]
    assert "my-tool" in registry.source_plugins({"action": "list"})


def test_plugin_manifest_directory_must_equal_id(tmp_path, monkeypatch):
    path = install_manifest(tmp_path, "my-tool")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["id"] = "another-name"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    assert registry.installed() == {}


def test_disabled_plugin_never_started(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool", enabled=False)
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    monkeypatch.setattr(registry, "_session",
                        lambda _: pytest.fail("Must not start disabled plugin"))
    output = registry.source_plugins({"action": "discover", "plugin": "my-tool"})
    assert "le van tiltva" in output


def test_generic_executable_requires_real_local_file(tmp_path, monkeypatch):
    path = install_manifest(tmp_path, "my-tool")
    manifest = registry._read_manifest(path)
    monkeypatch.delenv("JARVIS_MY_TOOL_CLI", raising=False)
    assert registry._binary_for(manifest) is None
    binary = tmp_path / "my-tool.exe"
    binary.write_bytes(b"stub")
    monkeypatch.setenv("JARVIS_MY_TOOL_CLI", str(binary))
    assert registry._binary_for(manifest) == str(binary.resolve())


def test_source_status_no_spawn(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    monkeypatch.delenv("JARVIS_MY_TOOL_CLI", raising=False)
    result = json.loads(registry.source_plugins({
        "action": "status", "plugin": "my-tool",
    }))
    assert result["enabled"] is True
    assert result["cli_available"] is False


def test_generic_discover_real_mcp_names(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    server = FakeMcp()
    monkeypatch.setattr(registry, "_session", lambda manifest: server)
    info = json.loads(registry.source_plugins({
        "action": "discover", "plugin": "my-tool", "filter": "hello",
    }))
    assert info["total"] == 1
    assert info["tools"][0]["name"] == "hello"


def test_even_read_only_looking_third_party_tool_requires_hud(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    server = FakeMcp()
    monkeypatch.setattr(registry, "_session", lambda manifest: server)
    requests = []
    import core.confirm
    monkeypatch.setattr(core.confirm, "request",
        lambda key, title, detail, cb: requests.append(cb) or "[CONFIRMATION_PENDING]")
    result = registry.source_plugins({
        "action": "inspect", "plugin": "my-tool", "tool": "hello",
        "arguments": {}, "confirmed": True,
    })
    assert result == "[CONFIRMATION_PENDING]"
    assert server.called == []
    requests[0]()
    assert server.called == [("hello", {})]


def test_new_mcp_plugin_cannot_invoke_unknown_tool(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    server = FakeMcp()
    monkeypatch.setattr(registry, "_session", lambda manifest: server)
    output = registry.source_plugins({
        "action": "execute", "plugin": "my-tool",
        "tool": "rm_rf", "arguments": {},
    })
    assert "Ismeretlen" in output
    assert not server.called


def test_mutating_batch_requires_one_real_user_confirmation(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    server = FakeMcp()
    monkeypatch.setattr(registry, "_session", lambda manifest: server)
    requests = []
    import core.confirm
    monkeypatch.setattr(core.confirm, "request",
        lambda key, title, detail, cb: requests.append(cb) or "pending")
    result = registry.source_plugins({
        "action": "batch", "plugin": "my-tool",
        "steps": [{"tool": "hello", "arguments": {}},
                  {"tool": "file_mutate", "arguments": {"value": 5}}],
    })
    assert result == "pending" and not server.called
    requests[0]()
    assert [row[0] for row in server.called] == ["hello", "file_mutate"]


def test_creative_plugin_delegates_to_existing_engine(monkeypatch):
    spy = []
    monkeypatch.setattr(registry, "creative_studio",
                        lambda params, player=None: spy.append(params) or "ok")
    result = registry.source_plugins({
        "action": "discover", "plugin": "photocraft", "filter": "layer",
    })
    assert result == "ok"
    assert spy[0]["app"] == "photocraft"
    assert spy[0]["operation"] == "discover"


def test_source_intent_conservatively_matches_installed_ids(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    assert source_intent.match_source_plugin("JARVIS, My Tool mit tud?") == "my-tool"
    assert source_intent.match_source_plugin("JARVIS, milyen idő van?") is None
    assert source_intent.match_source_plugin("Sorold fel a source pluginokat") == "all"


def test_source_intent_denies_hallucinated_tool_names(tmp_path, monkeypatch):
    install_manifest(tmp_path, "my-tool")
    monkeypatch.setattr(registry, "SOURCE_ROOT", tmp_path)
    server = FakeMcp()
    monkeypatch.setattr(registry, "_session", lambda manifest: server)
    import llm_client
    monkeypatch.setattr(llm_client.client, "chat_json",
                        lambda *args, **kwargs: {"tool": "fabricated", "arguments": {}})
    answer = source_intent.execute_source_text("My Tool, szerkeszd az adatokat!")
    assert "nem szerepel" in answer
    assert server.called == []
