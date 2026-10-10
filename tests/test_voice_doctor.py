"""Tests for the local-only JARVIS voice doctor without ML/model imports."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jarvis_voice_doctor", ROOT / "scripts" / "voice_doctor.py")
doctor = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(doctor)


def _status(*, enabled=False, wav=False, packages=False, windows=True):
    return {"enabled": enabled, "reference_ok": wav,
            "dependencies_ok": packages, "can_enable": windows and wav and packages}


def test_json_does_not_expose_local_reference_path(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "voice_readiness", lambda: _status(enabled=False, wav=True, packages=True))
    monkeypatch.setattr(doctor, "_version", lambda name: "0.test" if name == "coqui-tts" else None)
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "C:/private/user/ffmpeg.exe")
    assert doctor.main(["--json"]) == 0
    emitted = capsys.readouterr().out
    report = json.loads(emitted)
    assert report["xtts_enabled"] is False
    assert report["reference_pcm_wav_valid"] is True
    assert report["required_modules_present"] is True
    assert report["ffmpeg_available"] is True
    assert "C:/private/user" not in emitted
    assert "reference_path" not in emitted
    assert "file" not in report


def test_strict_fails_without_prerequisites(monkeypatch):
    monkeypatch.setattr(doctor, "voice_readiness", lambda: _status())
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    assert doctor.main(["--strict", "--json"]) == 2


def test_hints_report_missing_ffmpeg_and_packages_not_sensitive_paths():
    sample = {
        "platform": "Windows",
        "python_supported_by_coqui": True,
        "ffmpeg_available": False,
        "reference_pcm_wav_valid": False,
        "required_modules_present": False,
        "xtts_enabled": False,
        "xtts_runtime_plausible": False,
    }
    advices = doctor.hints(sample)
    assert any("FFmpeg" in s for s in advices)
    assert any("torch" in s for s in advices)
    assert all("%LOCALAPPDATA%" not in s for s in advices)


def test_main_does_not_load_model(monkeypatch, capsys):
    from actions import jarvis_voice
    monkeypatch.setattr(doctor, "voice_readiness",
                        lambda: _status(enabled=False, wav=False, packages=False))
    monkeypatch.setattr(doctor, "_version", lambda _: None)

    def forbidden_model():
        raise AssertionError("voice doctor must NEVER download models")
    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)
    assert doctor.main(["--json"]) == 0
    assert "xtts_runtime_plausible" in capsys.readouterr().out


def test_runtime_probe_reports_errors_by_type_not_private_paths(monkeypatch):
    class FakeTorch:
        class cuda:
            @staticmethod
            def is_available():
                return True

    def fake_import(name):
        if name == "torch":
            return FakeTorch()
        raise RuntimeError("private home C:/Users/Personal/Secret")

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import)
    result = doctor.probe_runtime_imports()
    assert result["torch_import_ok"] is True
    assert result["cuda_available"] is True
    assert result["coqui_api_import_ok"] is False
    assert result["coqui_error_type"] == "RuntimeError"
    assert "Personal" not in str(result)


def test_strict_runtime_probe_rejects_broken_imports(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "voice_readiness",
                        lambda: _status(enabled=True, wav=True, packages=True))
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(doctor, "probe_runtime_imports",
                        lambda: {"torch_import_ok": True,
                                 "coqui_api_import_ok": False,
                                 "cuda_available": False})
    assert doctor.main(["--strict", "--json", "--probe-runtime"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["runtime_import_probe"]["coqui_api_import_ok"] is False
