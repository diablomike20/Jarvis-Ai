"""Safety and integration-contract tests for the FreeCAD source plugin.

Does not require FreeCADCmd: actual geometry execution must be checked with
FreeCAD installed on Windows after these tests pass.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from actions import freecad_plugin as cad
from actions import source_plugins as registry
from actions import source_intent


def _installed_adapter(tmp_path, monkeypatch):
    fake_exe = tmp_path / "FreeCADCmd.exe"
    fake_exe.write_bytes(b"harmless test executable")
    monkeypatch.setenv("JARVIS_FREECAD_CMD", str(fake_exe))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    registry.close_all()
    adapter = registry._session(registry.installed()["freecad"])
    return adapter


def test_freecad_is_fourth_registered_editor_and_works_in_list(monkeypatch):
    monkeypatch.delenv("JARVIS_FREECAD_CMD", raising=False)
    manifests = registry.installed()
    assert manifests["freecad"]["adapter"] == "freecad_headless"
    assert manifests["freecad"]["enabled"]
    result = json.loads(registry.source_plugins({"action": "list"}))
    assert "freecad" in result
    assert result["freecad"]["name"] == "FreeCAD"


def test_freecad_recognizes_hungarian_and_english_voice_names():
    assert source_intent.match_source_plugin(
        "JARVIS, FreeCAD, készíts egy parametrikus modellt"
    ) == "freecad"
    assert source_intent.match_source_plugin(
        "JARVIS, szabad cad, adj hozzá egy hengert"
    ) == "freecad"
    assert source_intent.match_source_plugin(
        "Vajon hány csillag van az égen?"
    ) is None


def test_cli_discovery_requires_no_running_freecad(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    tools = adapter.list_tools()
    assert {"new_project", "import_fcstd", "add_primitive", "sketch_pad",
            "boolean", "transform", "remove_object", "inspect_project",
            "export"} <= set(tools)
    assert tools["export"]["inputSchema"]["properties"]["format"]["enum"]


def test_model_cannot_run_python_or_invented_tools(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Ismeretlen FreeCAD"):
        adapter.call_tool("run_python", {"code": "import os"})
    with pytest.raises(ValueError, match="Ismeretlen paraméter"):
        adapter.call_tool("new_project", {"project": "demo", "python": "exec(...)"})
    with pytest.raises(ValueError):
        adapter.call_tool("new_project", {"project": "../../malicious"})


@pytest.mark.parametrize("bad", [
    {"kind": "box", "name": "Box", "length": 2, "height": 4},
    {"kind": "sphere", "name": "Sphere", "radius": -3},
    {"kind": "cylinder", "name": "Cyl", "radius": 2, "height": float("nan")},
    {"kind": "box", "name": "Box", "length": 1, "width": 1, "height": 2,
     "position": [0, 0, "oops"]},
])
def test_invalid_geometry_is_rejected_before_engine_execution(bad):
    with pytest.raises(ValueError):
        cad._validate("add_primitive", {"project": "demo", **bad})


def test_parametric_box_and_pad_schema():
    box = cad._validate("add_primitive", {
        "project": "demo", "name": "Box", "kind": "box",
        "length": 10, "width": 20, "height": 30,
        "position": [0, 0, 5],
    })
    assert box["height"] == 30 and box["position"] == [0.0, 0.0, 5.0]
    sketch = cad._validate("sketch_pad", {
        "project": "demo", "name": "Solid",
        "width": 25, "height": 15, "depth": 2.5,
    })
    assert sketch["depth"] == 2.5


def test_cone_accepts_flat_end_with_zero_radius():
    cone = cad._validate("add_primitive", {
        "project": "demo", "name": "Cone", "kind": "cone",
        "radius1": 0, "radius2": 12, "height": 24,
    })
    assert cone["radius1"] == 0


def test_boolean_and_export_cannot_use_arbitrary_paths():
    with pytest.raises(ValueError):
        cad._validate("boolean", {
            "project": "demo", "name": "Output", "left": "Left",
            "right": "Right", "mode": "python",
        })
    with pytest.raises(ValueError):
        cad._validate("export", {
            "project": "demo", "name": "../file",
            "format": "step",
        })


def test_explicit_hud_confirmation_before_freecad_call(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(adapter, "_invoke", lambda job, root: calls.append(job) or {
        "isError": False, "structuredContent": {"project": job["project_file"]},
    })
    pending = []
    from core import confirm
    monkeypatch.setattr(confirm, "request",
                        lambda key, title, description, job: pending.append(job) or
                        "[CONFIRMATION_PENDING]")
    result = registry.source_plugins({
        "action": "execute", "plugin": "freecad",
        "tool": "new_project", "arguments": {"project": "my_first_design"},
        "confirmed": True,  # LLM-provided flag must not bypass consent.
    })
    assert result.startswith("[CONFIRMATION_PENDING]")
    assert calls == []
    pending[0]()
    assert len(calls) == 1
    assert calls[0]["operation"] == "new_project"


def test_explicit_user_project_is_saved_as_fcstd_inside_workspace(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    jobs = []
    monkeypatch.setattr(adapter, "_invoke",
                        lambda job, root: jobs.append(job) or
                        {"isError": False, "structuredContent": {"ok": True}})
    adapter.call_tool("new_project", {"project": "chair_design"})
    job = jobs[0]
    assert Path(job["project_file"]).name == "chair_design.FCStd"
    assert Path(job["project_file"]).parent == cad._workspace()
    assert Path(job["workspace"]) == cad._workspace()


def test_freecad_project_list_and_import_fcstd_file(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    existing = tmp_path / "source_model.FCStd"
    with ZipFile(existing, "w") as z:
        z.writestr("Document.xml", "<Document/>")
    info = adapter.call_tool("import_fcstd", {
        "project": "imported_design", "source_path": str(existing),
    })
    assert info["isError"] is False
    assert (cad._workspace() / "imported_design.FCStd").exists()
    projects = adapter.call_tool("list_projects", {})
    assert "imported_design" in projects["structuredContent"]["projects"]
    with pytest.raises(ValueError, match="Már létezik"):
        adapter.call_tool("import_fcstd", {
            "project": "imported_design", "source_path": str(existing),
        })


def test_freecad_rejects_fake_fcstd_import(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    forged = tmp_path / "invalid.FCStd"
    forged.write_text("not an FCStd archive", encoding="utf-8")
    with pytest.raises(ValueError, match="nem érvényes"):
        adapter.call_tool("import_fcstd", {
            "project": "bad_project", "source_path": str(forged),
        })


def test_headless_engine_receives_only_static_worker_with_json_job(tmp_path, monkeypatch):
    adapter = _installed_adapter(tmp_path, monkeypatch)
    seen = {}
    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["shell"] = kwargs.get("shell")
        p = Path(kwargs["env"]["JARVIS_FREECAD_REQUEST"])
        job = json.loads(p.read_text(encoding="utf-8"))
        seen["job"] = job
        result = Path(kwargs["env"]["JARVIS_FREECAD_RESULT"])
        result.write_text(json.dumps({
            "isError": False, "structuredContent": {"echo_operation": job["operation"]},
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(cad.subprocess, "run", fake_run)
    output = adapter.call_tool("new_project", {"project": "MyPart"})
    assert seen["argv"] == [adapter.binary, str(cad._WORKER)]
    assert seen["shell"] is False
    assert seen["job"]["operation"] == "new_project"
    assert output["structuredContent"]["echo_operation"] == "new_project"


def test_unavailable_freecad_is_reported_without_attempted_run(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_FREECAD_CMD", str(tmp_path / "missing.exe"))
    result = registry.source_plugins({
        "action": "discover", "plugin": "freecad",
    })
    assert "source plugin hiba" in result.lower()
    assert "FreeCAD" in result


def test_freecad_worker_uses_real_freecad_api_without_evaluating_model_code():
    script = cad._WORKER.read_text(encoding="utf-8")
    assert "import FreeCAD as App" in script
    assert "PartDesign::Pad" in script
    assert "Part.export(" in script
    assert "eval(" not in script and "exec(" not in script
