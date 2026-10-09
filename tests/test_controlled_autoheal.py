"""Auto-Heal may synthesize proposed changes but never self-apply without HUD approval."""
from pathlib import Path

from actions import auto_heal_engine as heal


def _setup(tmp_path, monkeypatch, source="def broken():\n    return 1 / 0\n"):
    root = tmp_path / "repo"
    target = root / "actions" / "example_action.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    cfg = tmp_path / "user" / "config"
    monkeypatch.setattr(heal, "BASE_DIR", root)
    monkeypatch.setattr(heal, "BACKUPS_DIR", cfg / "patch_backups")
    monkeypatch.setattr(heal, "PATCH_HISTORY_FILE", cfg / "patch_history.json")
    monkeypatch.setattr(heal, "CONFIG_DIR", cfg)
    monkeypatch.setattr(
        heal.AutoHealEngine, "_synthesize_patch_code",
        lambda **kwargs: {
            "success": True,
            "explanation": "Fixed division by zero.",
            "target_chunk": "    return 1 / 0",
            "replacement_chunk": "    return 1",
        },
    )
    traceback = (
        'Traceback (most recent call last):\n'
        f'  File "{target}", line 2, in broken\n'
        "ZeroDivisionError: division by zero"
    )
    return target, traceback


def test_autoheal_never_changes_file_before_confirm(tmp_path, monkeypatch):
    target, tb = _setup(tmp_path, monkeypatch)
    callbacks = []
    import core.confirm
    monkeypatch.setattr(core.confirm, "request",
                        lambda key, title, description, job:
                        callbacks.append(job) or "[CONFIRMATION_PENDING]")
    original = target.read_text(encoding="utf-8")
    result = heal.auto_heal({"action": "heal", "traceback": tb})
    assert result == "[CONFIRMATION_PENDING]"
    assert target.read_text(encoding="utf-8") == original
    assert not heal.BACKUPS_DIR.exists()
    applied = callbacks.pop()()
    assert "alkalmazva" in applied
    assert "return 1\n" in target.read_text(encoding="utf-8")
    assert heal.BACKUPS_DIR.exists()
    assert "rolled back" in heal.auto_heal({"action": "rollback"}).lower()
    assert target.read_text(encoding="utf-8") == original


def test_autoheal_rejects_source_changed_after_review(tmp_path, monkeypatch):
    target, tb = _setup(tmp_path, monkeypatch)
    callbacks = []
    import core.confirm
    monkeypatch.setattr(core.confirm, "request",
                        lambda key, title, description, job: callbacks.append(job) or "pending")
    assert heal.auto_heal({"action": "heal", "traceback": tb}) == "pending"
    target.write_text(target.read_text() + "# external edit\n", encoding="utf-8")
    assert "megváltozott" in callbacks[0]()
    assert "return 1 / 0" in target.read_text(encoding="utf-8")


def test_autoheal_dry_run_even_if_caller_requests_immediate_patch(tmp_path, monkeypatch):
    target, tb = _setup(tmp_path, monkeypatch)
    proposal = heal.AutoHealEngine.heal_traceback(tb, dry_run=False)
    assert proposal["success"] and proposal["dry_run"]
    assert "return 1 / 0" in target.read_text(encoding="utf-8")


def test_autoheal_protected_core_is_not_modified(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    main_file = root / "main.py"
    root.mkdir()
    main_file.write_text("def broken():\n    return 1 / 0\n", encoding="utf-8")
    monkeypatch.setattr(heal, "BASE_DIR", root)
    traceback = f'  File "{main_file}", line 2, in broken\nZeroDivisionError: division by zero'
    proposal = heal.AutoHealEngine.heal_traceback(traceback)
    assert not proposal["success"]


def test_autoheal_cannot_edit_python_outside_jarvis_root(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "private.py"
    outside.write_text("def broken():\n    return 1 / 0\n", encoding="utf-8")
    monkeypatch.setattr(heal, "BASE_DIR", repo)
    traceback = f'  File "{outside}", line 2, in broken\nZeroDivisionError: division by zero'
    assert not heal.AutoHealEngine.heal_traceback(traceback)["success"]
