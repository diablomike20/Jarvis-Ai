"""Unit tests for optional Hungarian authorized voice synthesis (no real model needed)."""
import sys
import types
from pathlib import Path

from actions import jarvis_voice


def test_without_reference_file_voice_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(tmp_path / "not-present.wav"))
    assert jarvis_voice.is_configured() is False
    assert jarvis_voice.speak_authorized_hungarian("Helló!") is False


def test_voice_generates_local_wav_and_cleans_up(tmp_path, monkeypatch):
    reference = tmp_path / "consented.wav"
    reference.write_bytes(b"reference-test-data")
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(reference))
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(jarvis_voice, "is_configured", lambda: True)

    calls = []
    class FakeSynthesizer:
        def tts_to_file(self, **kwargs):
            calls.append(dict(kwargs))
            Path(kwargs["file_path"]).write_bytes(b"RIFFfakeWAVE")

    monkeypatch.setattr(jarvis_voice, "_load_model", lambda: FakeSynthesizer())
    fake_winsound = types.ModuleType("winsound")
    fake_winsound.SND_FILENAME = 0x20000
    fake_winsound.SND_NODEFAULT = 0x0002
    fake_winsound.PlaySound = lambda path, flags: calls.append(("play", path, flags))
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)

    assert jarvis_voice.speak_authorized_hungarian("A rendszerek működnek.") is True
    assert calls[0]["language"] == "hu"
    assert calls[0]["speaker_wav"] == str(reference)
    assert calls[0]["text"] == "A rendszerek működnek."
    assert calls[1][0] == "play"
    assert Path(calls[0]["file_path"]).exists() is False


def test_model_failure_allows_fallback(tmp_path, monkeypatch):
    reference = tmp_path / "consented.wav"
    reference.write_bytes(b"reference-test-data")
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(reference))
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(jarvis_voice, "is_configured", lambda: True)
    def broken_model():
        raise RuntimeError("model not installed")
    monkeypatch.setattr(jarvis_voice, "_load_model", broken_model)
    fake_winsound = types.ModuleType("winsound")
    fake_winsound.SND_FILENAME = 0x20000
    fake_winsound.SND_NODEFAULT = 0x0002
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)
    assert jarvis_voice.speak_authorized_hungarian("Ellenőrzés") is False
