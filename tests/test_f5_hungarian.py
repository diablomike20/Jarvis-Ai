"""Contract tests for native F5 Hungarian voice in the real JARVIS EXE.

All audio and model files are synthetic; no network, licensed private voice,
torch inference, or real 672 MB checkpoint is ever used during CI.
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from actions import f5_hungarian, jarvis_voice


@pytest.fixture
def local_model(tmp_path, monkeypatch):
    private = tmp_path / "private"
    monkeypatch.setattr(f5_hungarian, "get_user_data_dir", lambda: private)
    return private


def test_model_unavailable_and_download_never_automatic(local_model, monkeypatch):
    assert f5_hungarian.assets_ready() is False
    assert f5_hungarian.download_model(user_approved=False) is False
    assert not list(local_model.rglob("*.safetensors"))


def test_local_model_files_require_checkpoint_and_vocab(local_model):
    ckpt, vocab = f5_hungarian.model_paths()
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    with ckpt.open("wb") as handle:
        handle.truncate(f5_hungarian.MIN_MODEL_BYTES + 1)
    assert f5_hungarian.assets_ready() is False
    vocab.write_text("a\nb\nc\ná\né\nő\n", encoding="utf-8")
    assert f5_hungarian.assets_ready() is True


def test_f5_user_opt_in_download_does_not_access_voice_files(local_model, monkeypatch):
    calls = []
    fake_hub = types.ModuleType("huggingface_hub")

    def fake_download(*, repo_id, filename, local_dir):
        calls.append((repo_id, filename, local_dir))
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if filename.endswith(".safetensors"):
            with path.open("wb") as fh:
                fh.truncate(f5_hungarian.MIN_MODEL_BYTES + 1)
        else:
            path.write_text("Hungarian vocabulary text\n", encoding="utf-8")
        return str(path)

    fake_hub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    assert f5_hungarian.download_model(user_approved=True) is True
    assert [x[1] for x in calls] == list(f5_hungarian.MODEL_FILES)
    assert all(x[0] == f5_hungarian.MODEL_REPO for x in calls)
    assert not list(local_model.rglob("*.wav"))


def test_f5_selected_requires_exact_reference_transcript(tmp_path, monkeypatch):
    from memory import config_manager
    reference = tmp_path / "voice.wav"
    import wave
    with wave.open(str(reference), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * (24000 * 5))
    monkeypatch.setenv("JARVIS_VOICE_REFERENCE", str(reference))
    monkeypatch.setattr(jarvis_voice, "_is_windows", lambda: True)
    monkeypatch.setattr(config_manager, "load_settings", lambda: {
        "jarvis_voice_enabled": True,
        "jarvis_voice_engine": "f5",
        "jarvis_f5_reference_text": "",
    })
    assert jarvis_voice.is_configured() is False
    monkeypatch.setattr(f5_hungarian, "runtime_available", lambda: True)
    monkeypatch.setattr(f5_hungarian, "assets_ready", lambda: True)
    assert jarvis_voice.voice_readiness()["can_enable"] is False
    assert "átirat" in jarvis_voice.voice_readiness()["reason"]

    monkeypatch.setattr(config_manager, "load_settings", lambda: {
        "jarvis_voice_enabled": True,
        "jarvis_voice_engine": "f5",
        "jarvis_f5_reference_text": "Ez a referencia pontos szövege.",
    })
    assert jarvis_voice.is_configured()
    assert jarvis_voice.voice_readiness()["can_enable"] is True


def test_f5_path_uses_real_javris_speech_gate_and_xtts_remains_selectable():
    src = (Path(__file__).resolve().parents[1] / "actions" / "jarvis_voice.py").read_text("utf-8")
    tree = ast.parse(src)
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {"speak_authorized_hungarian", "_load_model", "voice_engine"}.issubset(functions)
    assert 'synthesize_f5(' in src
    assert '"xtts"' in src


def test_gemini_live_original_voice_fallback_and_f5_gui_controls():
    root = Path(__file__).resolve().parents[1]
    main = (root / "main.py").read_text("utf-8")
    ui = (root / "ui.py").read_text("utf-8")
    assert "client.aio.live.connect(" in main
    assert "speak_authorized_hungarian(utterance)" in main
    assert "fallback_pcm" in main
    assert 'self.audio_in_queue.put_nowait, audio' in main
    assert 'self._hu_voice_engine_picker.addItem("F5-TTS Hungarian' in ui
    assert "jarvis_f5_reference_text" in ui
    assert "HungarianVoiceSetupWorker" in ui
    assert 'JARVIS Python környezet hiányzik' not in ui


def test_f5_error_never_leaks_private_paths(local_model, monkeypatch):
    fake_hub = types.ModuleType("huggingface_hub")

    def failing_download(**kwargs):
        raise RuntimeError("C:/Users/Private/voice.wav")

    fake_hub.hf_hub_download = failing_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    with pytest.raises(f5_hungarian.F5ModelError) as exc:
        f5_hungarian.download_model(user_approved=True)
    assert "Private" not in str(exc.value)
