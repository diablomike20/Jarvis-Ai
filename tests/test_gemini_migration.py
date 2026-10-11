"""No real API calls or audio devices required for these migration tests."""
import json
import types

import numpy as np
import or_client
from actions.local_stt import SpeechSegmenter, transcribe_pcm
from llm_client import UnifiedAIClient


def test_only_zero_price_router_selected_by_default():
    assert or_client.TEXT_MODELS == ["openrouter/free"]
    assert or_client.VISION_MODELS == ["openrouter/free"]


def test_openrouter_reload_key_after_initialization(monkeypatch):
    key = {"value": ""}
    monkeypatch.setattr(or_client, "_load_api_key", lambda: key["value"])
    client = or_client.OpenRouterClient()
    key["value"] = "sk-or-test"
    captured = {}

    class Response:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "Szia!"}}]}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(or_client.requests, "post", fake_post)
    assert client.chat("Szia") == "Szia!"
    assert captured["headers"]["Authorization"] == "Bearer sk-or-test"
    assert captured["json"]["model"] == "openrouter/free"


def test_image_requests_select_free_router(monkeypatch):
    client = or_client.OpenRouterClient()
    models = []
    def fake_call(model, messages, max_tokens, temperature, response_format=None):
        models.append(model)
        return "Látok egy képet."
    monkeypatch.setattr(client, "_call", fake_call)
    assert client.vision("Mi ez?", "dGVzdA==", "image/jpeg") == "Látok egy képet."
    assert models == ["openrouter/free"]


def test_offline_mode_never_calls_openrouter(monkeypatch, tmp_path):
    settings = tmp_path / "app_settings.json"
    settings.write_text(json.dumps({
        "default_ai_provider": "OpenRouter",
        "offline_mode_enabled": True,
        "local_ai_model": "qwen2.5:3b",
    }), encoding="utf-8")
    import llm_client
    monkeypatch.setattr(llm_client, "SETTINGS_PATH", settings)
    client = UnifiedAIClient()
    assert client._provider == "Local"
    monkeypatch.setattr(client, "_local_chat_completion",
                        lambda messages, temperature=0.7, response_format=None: "Helyi válasz.")
    def unwanted_call(*args, **kwargs):
        raise AssertionError("No cloud calls allowed when offline")
    monkeypatch.setattr(llm_client.openrouter_client, "chat", unwanted_call)
    assert client.chat("Szia") == "Helyi válasz."


def test_ptt_capture_on_release_and_bounded_memory():
    capture = SpeechSegmenter(sample_rate=16000, max_seconds=2)
    frame = b"\x00\x01" * 1600  # 100 milliseconds
    for _ in range(7):
        assert capture.feed(frame, active=True, voiced=True, ptt=True, held=True) is None
    result = capture.feed(frame, active=True, voiced=False, ptt=True, held=False)
    assert result is not None and len(result) >= 16000
    assert capture.feed(frame, active=True, voiced=False, ptt=True, held=False) is None


def test_open_mic_collects_until_silence():
    capture = SpeechSegmenter(sample_rate=16000, silence_seconds=0.2)
    frame = b"\x00\x01" * 1600
    for _ in range(6):
        assert capture.feed(frame, active=True, voiced=True, ptt=False, held=False) is None
    assert capture.feed(frame, active=True, voiced=False, ptt=False, held=False) is None
    result = capture.feed(frame, active=True, voiced=False, ptt=False, held=False)
    assert result is not None


def test_hungarian_transcription_forced_and_audio_normalized(monkeypatch):
    seen = {}
    class FakeModel:
        def transcribe(self, samples, **kwargs):
            seen["samples"] = samples
            seen.update(kwargs)
            return ([types.SimpleNamespace(text=" Jó napot, uram! ")], None)
    from actions import local_stt
    monkeypatch.setattr(local_stt, "_get_model", lambda: FakeModel())
    pcm = np.full(16000, 12000, dtype="<i2").tobytes()
    assert transcribe_pcm(pcm) == "Jó napot, uram!"
    assert seen["language"] == "hu"
    assert np.isclose(seen["samples"][0], 12000 / 32768)
