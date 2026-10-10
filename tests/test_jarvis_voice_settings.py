"""Contract tests for the real JARVIS Hungarian XTTS settings page.

No PyQt runtime, private voice data, voice cloning or model downloads.
"""
import ast
import importlib.util
from pathlib import Path

import pytest

from actions import jarvis_voice
from memory import config_manager


@pytest.fixture
def reference(tmp_path, monkeypatch):
    import wave
    path = tmp_path / "consented.wav"
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * (16000 * 4))
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(path))
    return path


def _mock_deps(monkeypatch, installed):
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda package: object() if installed else None,
    )


def test_voice_settings_default_off_and_no_model_load(reference, monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {})
    _mock_deps(monkeypatch, True)

    def forbidden_model():
        raise AssertionError("No model download allowed in readiness checks")
    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)
    status = jarvis_voice.voice_readiness()
    assert status["can_enable"] is True
    assert status["enabled"] is False
    assert "consented" not in str(status)


def test_voice_settings_missing_runtime_never_claims_ready(reference, monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {"jarvis_voice_enabled": True})
    _mock_deps(monkeypatch, False)
    status = jarvis_voice.voice_readiness()
    assert status["enabled"] is True
    assert status["can_enable"] is False
    assert status["dependencies_ok"] is False


def test_voice_settings_missing_reference_never_claims_ready(reference, monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {"jarvis_voice_enabled": True})
    _mock_deps(monkeypatch, True)
    reference.unlink()
    status = jarvis_voice.voice_readiness()
    assert status["reference_ok"] is False
    assert status["can_enable"] is False
    assert not jarvis_voice.is_configured()


def test_voice_settings_unsupported_os_never_claims_ready(reference, monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: False)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {"jarvis_voice_enabled": True})
    _mock_deps(monkeypatch, True)
    status = jarvis_voice.voice_readiness()
    assert status["can_enable"] is False
    assert status["windows"] is False


def test_ready_status_does_not_show_sensitive_reference_location(reference, monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {"jarvis_voice_enabled": True})
    _mock_deps(monkeypatch, True)
    status = jarvis_voice.voice_readiness()
    assert status["can_enable"] is True
    assert str(reference) not in str(status)


def test_actual_ui_has_explicit_consent_and_test_worker():
    ui_path = Path(__file__).resolve().parents[1] / "ui.py"
    tree = ast.parse(ui_path.read_text(encoding="utf-8"))
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "HungarianVoiceTestWorker" in classes
    ui = classes["SystemConnectivityPage"]
    methods = {n.name: n for n in ui.body if isinstance(n, ast.FunctionDef)}
    for method in ("_refresh_hu_voice_controls", "_on_hu_voice_toggled",
                   "_test_hu_voice", "_on_hu_voice_test_completed"):
        assert method in methods
    code = ui_path.read_text(encoding="utf-8")
    assert "jarvis_voice_enabled" in code
    assert "QMessageBox.question" in code
    assert "stop_authorized_hungarian" in code
    assert 'self._hu_voice_enabled_btn = self._mk_toggle(' in code


def test_private_voice_workers_do_not_outlive_qthread_shutdown():
    """Ensure slow, user-consented model initialization is a daemon task."""
    source = (Path(__file__).resolve().parents[1] / "ui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "_DaemonVoiceWorker" in classes
    for worker in ("HungarianVoiceImportWorker", "HungarianVoiceTestWorker"):
        bases = classes[worker].bases
        assert len(bases) == 1
        assert isinstance(bases[0], ast.Name)
        assert bases[0].id == "_DaemonVoiceWorker"
    core = ast.get_source_segment(source, classes["_DaemonVoiceWorker"])
    assert "daemon=True" in core
    assert "threading.Thread(" in core
    assert "self.finished.emit()" in core


def test_runtime_setup_in_real_audio_settings_is_explicitly_approved():
    source = (Path(__file__).resolve().parents[1] / "ui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SystemConnectivityPage")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_launch_hu_voice_setup")
    body = ast.get_source_segment(source, method)
    assert "QMessageBox.question(" in body
    assert "StandardButton.Yes" in body
    assert 'choice != QMessageBox.StandardButton.Yes' in body
    assert "subprocess.Popen(" in body
    assert "CREATE_NEW_CONSOLE" in body
    assert "setup_hungarian_voice.ps1" in body
    assert "get_user_data_dir" not in body
    assert 'self._hu_voice_setup_btn.clicked.connect(self._launch_hu_voice_setup)' in source
