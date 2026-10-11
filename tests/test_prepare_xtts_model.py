"""No-model CI unit tests for explicit public XTTS cache warmup."""
import importlib.util
from pathlib import Path

from actions import jarvis_voice

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "prepare_xtts_model", ROOT / "scripts" / "prepare_xtts_model.py"
)
setup = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(setup)


def test_model_download_never_occurs_implicitly(monkeypatch, capsys):
    def forbidden_model():
        raise AssertionError("unexpected model download")

    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)
    assert setup.prepare_model(approved=False) is False
    assert setup.main([]) == 2


def test_interactive_windows_cache_warmup_can_be_selected(monkeypatch, capsys):
    counter = {"calls": 0}
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)

    def fake_load():
        counter["calls"] += 1
        return object()

    monkeypatch.setattr(jarvis_voice, "_load_model", fake_load)
    assert setup.main(["--download"]) == 0
    assert counter["calls"] == 1
    assert "hangmintát" in capsys.readouterr().out


def test_runtime_errors_do_not_expose_private_paths(monkeypatch, capsys):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)

    def failing_load():
        raise RuntimeError("secret user C:/Users/Private/voice.wav")
    monkeypatch.setattr(jarvis_voice, "_load_model", failing_load)
    assert setup.main(["--download"]) == 1
    out = capsys.readouterr().out
    assert "RuntimeError" in out
    assert "Private" not in out


def test_unsupported_platform_never_loads_model(monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: False)
    def forbidden_model():
        raise AssertionError("unsupported platform")
    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)
    assert setup.main(["--download"]) == 1
