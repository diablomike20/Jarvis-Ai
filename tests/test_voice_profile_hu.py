"""Tests for the JARVIS-inspired Hungarian synthetic voice preset."""
from actions.voice_profile import (
    DEFAULT_EDGE_VOICE,
    EdgeVoiceProfile,
    edge_voice_profile,
)


def test_default_profile_is_hungarian_male_and_measured():
    profile = edge_voice_profile({})
    assert profile == EdgeVoiceProfile(
        voice="hu-HU-TamasNeural",
        rate="-9%",
        pitch="-8Hz",
        volume="+0%",
    )
    assert profile.voice == DEFAULT_EDGE_VOICE


def test_natural_hungarian_preset_uses_neutral_delivery():
    profile = edge_voice_profile({"tts_style": "natural_hu"})
    assert profile.rate == "+0%"
    assert profile.pitch == "+0Hz"


def test_user_can_tune_voice_without_overly_extreme_settings():
    profile = edge_voice_profile({
        "tts_voice": "hu-HU-TamasNeural",
        "tts_rate": "-14%",
        "tts_pitch": "-12Hz",
        "tts_volume": "+5%",
    })
    assert profile.rate == "-14%"
    assert profile.pitch == "-12Hz"
    assert profile.volume == "+5%"


def test_invalid_values_fall_back_to_safe_hungarian_defaults():
    profile = edge_voice_profile({
        "tts_voice": "bad string",
        "tts_rate": "-999%",
        "tts_pitch": "this is not an offset",
        "tts_volume": "100",
    })
    assert profile.voice == DEFAULT_EDGE_VOICE
    assert profile.rate == "-9%"
    assert profile.pitch == "-8Hz"
    assert profile.volume == "+0%"
