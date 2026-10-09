"""Hungarian JARVIS-inspired speech profile; no actor voice clone.

This module only defines synthetic speech settings and uses no voice recordings.
The selected Edge voice requires an Internet connection.  Windows SAPI remains
the offline fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_EDGE_VOICE = "hu-HU-TamasNeural"
STYLE_JARVIS = "jarvis_hu"
STYLE_NATURAL = "natural_hu"


@dataclass(frozen=True)
class EdgeVoiceProfile:
    voice: str
    rate: str
    pitch: str
    volume: str


def _bounded_adjustment(value: object, suffix: str, limit: int, fallback: str) -> str:
    """Avoid invalid SSML values and extreme pitch/speed settings."""
    if not isinstance(value, str):
        return fallback
    match = re.fullmatch(r"([+-])(\d+)" + re.escape(suffix), value.strip())
    if not match or int(match.group(2)) > limit:
        return fallback
    return value.strip()


def edge_voice_profile(settings: dict | None = None) -> EdgeVoiceProfile:
    """Construct the profile from app settings, preserving safe defaults."""
    if settings is None:
        try:
            from memory import config_manager
            settings = config_manager.load_settings() or {}
        except Exception:
            settings = {}

    style = (settings.get("tts_style") or STYLE_JARVIS)
    if style == STYLE_NATURAL:
        default_rate, default_pitch = "+0%", "+0Hz"
    else:
        default_rate, default_pitch = "-9%", "-8Hz"

    voice = settings.get("tts_voice") or DEFAULT_EDGE_VOICE
    if not isinstance(voice, str) or not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z0-9]+Neural", voice):
        voice = DEFAULT_EDGE_VOICE

    return EdgeVoiceProfile(
        voice=voice,
        rate=_bounded_adjustment(settings.get("tts_rate", default_rate), "%", 40, default_rate),
        pitch=_bounded_adjustment(settings.get("tts_pitch", default_pitch), "Hz", 30, default_pitch),
        volume=_bounded_adjustment(settings.get("tts_volume", "+0%"), "%", 50, "+0%"),
    )
