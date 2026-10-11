"""Unit checks for the embedded PhotoCraft/LightCraft/FilmCraft bridge.

No Rust binaries or Windows UI are needed here. Live end-to-end editing still
requires all three engines built on the target machine.
"""
import json
from pathlib import Path

import pytest

from actions import creative_studio as studio
from actions import creative_intent as intent


class FakeEditorSession:
    def __init__(self, names):
        self.tools = {name: {"name": name, "description": "test"} for name in names}
        self.called = []

    def list_tools(self):
        return self.tools

    def call_tool(self, name, args):
        self.called.append((name, args))
        return {"isError": False, "structuredContent": {"ok": True, "name": name}}


def test_catalogue_lists_all_three_editors(monkeypatch):
    monkeypatch.setattr(studio, "_binary_path", lambda app: None)
    result = json.loads(studio.creative_studio({"app": "all", "operation": "catalogue"}))
    assert set(result) == {"photocraft", "lightcraft", "filmcraft"}
    assert len(result["photocraft"]["areas"]) >= 10
    assert len(result["lightcraft"]["areas"]) >= 10
    assert len(result["filmcraft"]["areas"]) >= 10


def test_no_cli_is_reported_not_launched(monkeypatch):
    monkeypatch.setattr(studio, "_binary_path", lambda app: None)
    answer = studio.creative_studio({"app": "filmcraft", "operation": "discover"})
    assert "filmcraft" in answer and "telepítve" in answer
    assert "FILMCRAFT_CLI" in answer


def test_photocraft_cli_is_sandboxed_to_working_root(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    args = studio._launch_args("photocraft", "/somewhere/photocraft-cli")
    assert args[1] == "mcp"
    assert "--automation-read-root" in args
    assert "--automation-write-root" in args
    read_root = Path(args[args.index("--automation-read-root") + 1])
    write_root = Path(args[args.index("--automation-write-root") + 1])
    assert read_root == write_root
    assert read_root.is_dir()


def test_lightcraft_cli_uses_headless_library(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    args = studio._launch_args("lightcraft", "lightcraft-cli")
    assert args[:3] == ["lightcraft-cli", "mcp", "--compact"]
    assert "--library" in args


def test_discover_restricts_results_and_reports_real_tool_names(monkeypatch):
    session = FakeEditorSession({"list_controls", "set_develop", "export"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    result = json.loads(studio.creative_studio({
        "app": "lightcraft", "operation": "discover", "filter": "develop",
    }))
    assert result["total_matches"] == 1
    assert result["tools"][0]["name"] == "set_develop"


def test_read_only_is_executed_without_confirmation(monkeypatch):
    session = FakeEditorSession({"list_controls"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    output = studio.creative_studio({
        "app": "lightcraft", "operation": "inspect",
        "tool": "list_controls", "arguments": {},
    })
    assert session.called == [("list_controls", {})]
    assert "list_controls" in output


def test_mutating_tool_waits_for_real_hud_confirmation(monkeypatch):
    session = FakeEditorSession({"set_develop"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    pending = []
    def fake_request(key, title, description, job):
        pending.append((key, title, description, job))
        return "[CONFIRMATION_PENDING] Confirm on HUD."
    import core.confirm
    monkeypatch.setattr(core.confirm, "request", fake_request)
    result = studio.creative_studio({
        "app": "lightcraft", "operation": "execute", "tool": "set_develop",
        "arguments": {"values": {"light.exposure": 0.7}},
        "confirmed": True,  # model-generated flag must have NO effect
    })
    assert "[CONFIRMATION_PENDING]" in result
    assert session.called == []
    assert "set_develop" in pending[0][2]
    pending[0][3]()
    assert session.called == [("set_develop", {"values": {"light.exposure": 0.7}})]


def test_model_cannot_call_unregistered_tool(monkeypatch):
    session = FakeEditorSession({"query_photos"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    msg = studio.creative_studio({
        "app": "lightcraft", "operation": "execute",
        "tool": "file_delete_everything", "arguments": {},
    })
    assert "Nincs ilyen" in msg
    assert session.called == []


def test_batch_requires_one_confirmation(monkeypatch):
    session = FakeEditorSession({"media_import", "command_run"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    pending = []
    import core.confirm
    monkeypatch.setattr(core.confirm, "request",
                        lambda key, title, desc, work: pending.append(work) or "pending")
    result = studio.creative_studio({
        "app": "filmcraft", "operation": "batch", "steps": [
            {"tool": "media_import", "arguments": {"text": "C:/project/video.mp4"}},
            {"tool": "command_run", "arguments": {"id": "edit.undo", "params": {}}},
        ],
    })
    assert result == "pending"
    assert session.called == []
    assert len(pending) == 1
    pending[0]()
    assert len(session.called) == 2


def test_batch_rejects_unknown_step_before_confirmation(monkeypatch):
    session = FakeEditorSession({"media_import"})
    monkeypatch.setattr(studio, "_session", lambda app: session)
    response = studio.creative_studio({
        "app": "filmcraft", "operation": "batch", "steps": [
            {"tool": "media_import", "arguments": {}},
            {"tool": "invented_tool", "arguments": {}},
        ],
    })
    assert "Nem létező" in response and session.called == []


@pytest.mark.parametrize("utterance,app", [
    ("JARVIS, nyisd meg a PhotoCraft szerkesztőt", "photocraft"),
    ("JARVIS, állítsd a videó idővonalát", "filmcraft"),
    ("JARVIS, javítsd fel a RAW fotómat", "lightcraft"),
    ("Milyen parancsai vannak a LightCraftnak?", "lightcraft"),
    ("Szia, milyen az időjárás?", None),
])
def test_hungarian_creative_intent(utterance, app):
    assert intent.recognize_creative_intent(utterance) == app


def test_direct_planner_only_executes_discovered_tool(monkeypatch):
    session = FakeEditorSession({"list_controls", "set_develop"})
    monkeypatch.setattr(intent, "_session", lambda app: session)
    monkeypatch.setattr(studio, "_session", lambda app: session)
    monkeypatch.setattr(studio, "_binary_path", lambda app: "/bin/available")
    import llm_client
    monkeypatch.setattr(llm_client.client, "chat_json",
                        lambda *a, **kw: {"tool": "unlisted_command", "arguments": {}})
    answer = intent.handle_creative_text("LightCraft, állítsd be az expozíciót")
    assert "nem létező" in answer.lower()
    assert not session.called
