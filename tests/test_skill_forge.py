"""Safe skill synthesis: no generated code execution before real HUD approval."""
from pathlib import Path
from unittest.mock import patch

from core.dynamic_registry import DynamicToolRegistry
from core.skill_crucible import SkillCrucible
from core.skill_forge import SkillForge


def _payload(name="forge_smoke_test", code=None):
    return {
        "success": True,
        "manifest": {
            "name": name,
            "description": "Forge smoke test",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
        "code": code or 'def execute(**kwargs):\n    return "forge smoke test passed"\n',
        "test_cases": [{"input": {}}],
    }


def _staging(tmp_path, payload):
    from contextlib import ExitStack
    stack = ExitStack()
    original_skills = DynamicToolRegistry._skills.copy()
    original_initialized = DynamicToolRegistry._initialized
    stack.enter_context(patch("core.dynamic_registry.FEATURES_DIR", tmp_path / "features"))
    stack.enter_context(patch("core.dynamic_registry.APPDATA_SKILLS_DIR", tmp_path / "vault"))
    stack.enter_context(patch("core.skill_forge.get_user_data_dir", return_value=tmp_path / "user"))
    stack.enter_context(patch.object(SkillForge, "_call_llm_synthesizer", return_value=payload))
    callbacks = []
    stack.enter_context(patch("core.confirm.request", side_effect=lambda key, title, detail, callback:
                              callbacks.append(callback) or "[CONFIRMATION_PENDING]"))
    return stack, callbacks, original_skills, original_initialized


def test_forge_stages_without_executing_generated_code(tmp_path):
    payload = _payload(code=(
        "def execute(**kwargs):\n"
        "    from pathlib import Path\n"
        f"    Path({str(tmp_path / 'ran.txt')!r}).write_text('executed')\n"
        "    return 'done'\n"
    ))
    stack, callbacks, old, old_initialized = _staging(tmp_path, payload)
    try:
        with stack:
            result = SkillForge.forge_skill("create harmless log", "forge_smoke_test")
            assert result["success"] and result["pending"]
            assert Path(result["review_path"]).exists()
            assert not (tmp_path / "ran.txt").exists()
            assert not (tmp_path / "features" / "forge_smoke_test").exists()
            assert not DynamicToolRegistry.has_tool("forge_smoke_test") if not DynamicToolRegistry._initialized else True
            activation = callbacks.pop()()
            assert "aktiválva" in activation
            assert (tmp_path / "ran.txt").exists()  # tests only AFTER approval
            assert DynamicToolRegistry.execute_sync("forge_smoke_test", {}) == "done"
    finally:
        DynamicToolRegistry._skills = old
        DynamicToolRegistry._initialized = old_initialized


def test_changed_draft_is_rejected_before_execution(tmp_path):
    payload = _payload(name="hash_check", code=(
        "def execute(**kwargs):\n"
        "    from pathlib import Path\n"
        f"    Path({str(tmp_path / 'ran.txt')!r}).write_text('executed')\n"
        "    return True\n"
    ))
    stack, callbacks, old, old_initialized = _staging(tmp_path, payload)
    try:
        with stack:
            result = SkillForge.forge_skill("hash check")
            p = Path(result["review_path"])
            p.write_text(p.read_text() + "\n# changed", encoding="utf-8")
            assert "megváltozott" in callbacks[0]()
            assert not (tmp_path / "ran.txt").exists()
            assert not (tmp_path / "features" / "hash_check").exists()
    finally:
        DynamicToolRegistry._skills = old
        DynamicToolRegistry._initialized = old_initialized


def test_existing_skill_not_overwritten(tmp_path):
    stack, callbacks, old, old_initialized = _staging(tmp_path, _payload())
    try:
        with stack:
            features = tmp_path / "features"
            features.mkdir()
            target = features / "forge_smoke_test.py"
            target.write_text("original", encoding="utf-8")
            result = SkillForge.forge_skill("new capability")
            assert not result["success"]
            assert target.read_text(encoding="utf-8") == "original"
            assert not callbacks
    finally:
        DynamicToolRegistry._skills = old
        DynamicToolRegistry._initialized = old_initialized


def test_forge_failing_runtime_test_stays_inactive(tmp_path):
    initial = _payload(name="broken_feature",
                       code='def execute(**kwargs):\n    return {"error": "Broken runtime"}\n')
    stack, callbacks, old, old_initialized = _staging(tmp_path, initial)
    try:
        with stack:
            result = SkillForge.forge_skill("broken feature")
            assert result["pending"]
            message = callbacks[0]()
            assert "tesztek nem sikerültek" in message
            assert not (tmp_path / "features" / "broken_feature").exists()
    finally:
        DynamicToolRegistry._skills = old
        DynamicToolRegistry._initialized = old_initialized


def test_forge_rejects_path_traversal_names(tmp_path):
    stack, callbacks, old, old_initialized = _staging(tmp_path, _payload(name="../../escape"))
    try:
        with stack:
            result = SkillForge.forge_skill("dangerous name")
            assert not result["success"]
            assert callbacks == []
    finally:
        DynamicToolRegistry._skills = old
        DynamicToolRegistry._initialized = old_initialized


def test_crucible_detects_error_dictionary_in_subprocess():
    broken_code = 'def execute(**kwargs):\n    return {"error": "SSL handshake failed"}\n'
    ok, msg, telemetry = SkillCrucible.run_sandbox_test(broken_code, [{"input": {}}])
    assert not ok
    assert "SSL handshake failed" in msg
    code = 'def execute(**kwargs):\n    return {"title": "Success", "summary": "Rendered"}\n'
    ok2, _, _ = SkillCrucible.run_sandbox_test(code, [{"input": {}}])
    assert ok2


def test_missing_dependencies_are_not_auto_installed(monkeypatch):
    invocations = []
    import core.skill_crucible as crucible
    original = crucible.subprocess.run

    def tracking(argv, **kwargs):
        invocations.append(argv)
        return original(argv, **kwargs)

    monkeypatch.setattr(crucible.subprocess, "run", tracking)
    ok, msg = SkillCrucible.resolve_dependencies(["definitely_unknown_dependency_123"])
    assert not ok and "Hiányzó" in msg
    assert not any("pip" in argv for argv in invocations)


def test_crucible_fails_closed_if_test_runner_returns_no_json(monkeypatch):
    import core.skill_crucible as crucible
    from types import SimpleNamespace
    monkeypatch.setattr(crucible.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout="noise only", stderr=""))
    ok, msg, _ = SkillCrucible.run_sandbox_test(
        "def execute(**kwargs): return True", [{"input": {}}],
    )
    assert not ok and "teszteredmény" in msg
