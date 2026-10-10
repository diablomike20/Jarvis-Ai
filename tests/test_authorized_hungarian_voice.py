"""Offline unit tests for the opt-in Hungarian XTTS route. No Coqui/Torch/audio required."""
import ast
import sys
import threading
import types
import wave
from pathlib import Path

import pytest

from actions import jarvis_voice


def make_wav(path, seconds=4, sample_rate=16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * int(sample_rate * seconds))


@pytest.fixture
def reference(tmp_path, monkeypatch):
    path = tmp_path / "private" / "authorized.wav"
    make_wav(path)
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(path))
    monkeypatch.setattr(jarvis_voice, "get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    return path


def set_enabled(monkeypatch, enabled, offline=False):
    from memory import config_manager
    monkeypatch.setattr(
        config_manager, "load_settings",
        lambda: {"jarvis_voice_enabled": enabled, "offline_mode_enabled": offline},
    )


def fake_winsound(monkeypatch, on_play=None):
    module = types.ModuleType("winsound")
    module.SND_FILENAME = 0x20000
    module.SND_NODEFAULT = 2
    module.SND_ASYNC = 1
    calls = []

    def play(path, flags):
        calls.append((path, flags))
        if path is not None and on_play:
            on_play()
    module.PlaySound = play
    monkeypatch.setitem(sys.modules, "winsound", module)
    return calls


def test_default_is_off_even_with_authorized_reference(reference, monkeypatch):
    set_enabled(monkeypatch, False)
    assert jarvis_voice.is_configured() is False
    assert jarvis_voice.speak_authorized_hungarian("Üdvözöllek!") is False


def test_settings_failure_never_auto_enables(reference, monkeypatch):
    from memory import config_manager

    def failing_load():
        raise RuntimeError("simulated config failure")
    monkeypatch.setattr(config_manager, "load_settings", failing_load)
    assert not jarvis_voice.is_configured()


def test_missing_or_bad_reference_fails_closed(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    reference.unlink()
    assert not jarvis_voice.is_configured()
    reference.write_bytes(b"not a PCM WAV")
    assert not jarvis_voice.is_configured()
    assert not jarvis_voice.speak_authorized_hungarian("Tilos indulni.")


def test_wrong_extension_is_rejected(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    bad = reference.with_suffix(".mp3")
    bad.write_bytes(reference.read_bytes())
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(bad))
    assert not jarvis_voice.is_configured()


def test_local_synthesis_and_cleanup(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    calls = fake_winsound(monkeypatch)
    generated = []

    class FakeXTTS:
        def tts_to_file(self, **kwargs):
            generated.append(kwargs)
            make_wav(Path(kwargs["file_path"]), seconds=0.05)
    monkeypatch.setattr(jarvis_voice, "_load_model", lambda: FakeXTTS())
    assert jarvis_voice.is_configured()
    assert jarvis_voice.speak_authorized_hungarian("A rendszerek működnek.") is True
    assert generated[0]["language"] == "hu"
    assert generated[0]["speaker_wav"] == str(reference)
    assert generated[0]["text"] == "A rendszerek működnek."
    assert not Path(generated[0]["file_path"]).exists()
    assert str(jarvis_voice.get_user_data_dir()) in generated[0]["file_path"]
    assert any(path is not None for path, _ in calls)
    assert calls[-1] == (None, 0)


def test_model_failure_uses_existing_fallback(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    fake_winsound(monkeypatch)

    def failed_model():
        raise RuntimeError("fake model absent")
    monkeypatch.setattr(jarvis_voice, "_load_model", failed_model)
    assert jarvis_voice.speak_authorized_hungarian("Hiba.") is False
    temp_dir = jarvis_voice.get_user_data_dir() / "voices" / "temp"
    assert list(temp_dir.glob("xtts_*.wav")) == []


def test_stop_during_generation_does_not_fallback_or_play(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    calls = fake_winsound(monkeypatch)

    class FakeSlowModel:
        def tts_to_file(self, **kwargs):
            jarvis_voice.stop_authorized_hungarian()
            make_wav(Path(kwargs["file_path"]), seconds=0.05)
    monkeypatch.setattr(jarvis_voice, "_load_model", lambda: FakeSlowModel())
    assert jarvis_voice.speak_authorized_hungarian("Ne beszélj.") is True
    assert all(path is None for path, _ in calls)


def test_stop_during_playback_interrupts(reference, monkeypatch):
    set_enabled(monkeypatch, True)
    calls = fake_winsound(monkeypatch, on_play=jarvis_voice.stop_authorized_hungarian)

    class FakeXTTS:
        def tts_to_file(self, **kwargs):
            make_wav(Path(kwargs["file_path"]), seconds=1)
    monkeypatch.setattr(jarvis_voice, "_load_model", lambda: FakeXTTS())
    assert jarvis_voice.speak_authorized_hungarian("Megállítva.") is True
    assert any(path is not None for path, _ in calls)
    assert any(path is None for path, _ in calls)


def _isolated_router(name):
    """Compile only a real repository function to avoid GUI-only imports in CI."""
    source = (Path(__file__).resolve().parent.parent /
              "actions" / "attention_monitor.py").read_text(encoding="utf-8")
    node = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    namespace = {
        "_speak_lock": threading.Lock(),
        "_speak_sapi_male": lambda text: None,
        "_cleanup_current_audio": lambda: None,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<speech-router>", "exec"), namespace)
    return namespace


def test_router_prefers_opted_in_xtts_over_offline_sapi(reference, monkeypatch):
    set_enabled(monkeypatch, True, offline=True)
    hits = []
    monkeypatch.setattr(jarvis_voice, "speak_authorized_hungarian", lambda text: hits.append(("xtts", text)) or True)
    scope = _isolated_router("_speak_edge_native")
    scope["_speak_sapi_male"] = lambda text: hits.append(("sapi", text))
    scope["_speak_edge_native"]("Magyar beszéd")
    assert hits == [("xtts", "Magyar beszéd")]


def test_offline_xtts_failure_falls_back_only_to_local_sapi(reference, monkeypatch):
    set_enabled(monkeypatch, True, offline=True)
    hits = []
    monkeypatch.setattr(jarvis_voice, "speak_authorized_hungarian", lambda text: False)
    scope = _isolated_router("_speak_edge_native")
    scope["_speak_sapi_male"] = lambda text: hits.append(text)
    scope["_speak_edge_native"]("Helyi mód")
    assert hits == ["Helyi mód"]


def test_stop_is_wired_to_xtts_and_edge_cleanup(reference, monkeypatch):
    hits = []
    monkeypatch.setattr(jarvis_voice, "stop_authorized_hungarian", lambda: hits.append("xtts-stop"))
    scope = _isolated_router("stop_native_speech")
    scope["_cleanup_current_audio"] = lambda: hits.append("edge-stop")
    scope["stop_native_speech"]()
    assert hits == ["xtts-stop", "edge-stop"]

def test_queue_rechecks_user_opt_in_before_synthesis(reference, monkeypatch):
    """Disabling XTTS while waiting for a lock must suppress queued speech."""
    from memory import config_manager
    calls = {"loads": 0}

    def settings():
        calls["loads"] += 1
        return {"jarvis_voice_enabled": calls["loads"] == 1}

    monkeypatch.setattr(config_manager, "load_settings", settings)
    fake_winsound(monkeypatch)
    def forbidden_model():
        raise AssertionError("Cancelled voice must never load a model")
    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)
    assert jarvis_voice.speak_authorized_hungarian("A felhasználó kikapcsolta a hangot.") is False
    assert calls["loads"] >= 2


def test_stop_cancels_queued_xtts_without_playing_fallback(reference, monkeypatch):
    """A STOP during waiting lock cancels future synthesis, not Edge fallback."""
    set_enabled(monkeypatch, True)
    calls = fake_winsound(monkeypatch)

    def forbidden_model():
        raise AssertionError("Queued voice must not load a model after STOP")
    monkeypatch.setattr(jarvis_voice, "_load_model", forbidden_model)

    class InterruptingLock:
        def __enter__(self):
            jarvis_voice.stop_authorized_hungarian()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(jarvis_voice, "_speech_lock", InterruptingLock())
    assert jarvis_voice.speak_authorized_hungarian("Késleltetett, már törölt mondat.") is True
    assert all(path is None for path, flags in calls)


def test_stop_invalidates_only_prior_requests(reference, monkeypatch):
    """STOP before invoking a NEW request must not permanently mute JARVIS."""
    set_enabled(monkeypatch, True)
    calls = fake_winsound(monkeypatch)
    jarvis_voice.stop_authorized_hungarian()

    class FakeXTTS:
        def tts_to_file(self, **kwargs):
            make_wav(Path(kwargs["file_path"]), seconds=0.05)

    monkeypatch.setattr(jarvis_voice, "_load_model", lambda: FakeXTTS())
    assert jarvis_voice.speak_authorized_hungarian("Új kérés.") is True
    assert any(path is not None for path, flags in calls)
