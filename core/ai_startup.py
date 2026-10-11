"""Pure startup policy for JARVIS: independent of GUI, microphone or Gemini.

A configured OpenRouter-only installation must NEVER be stopped by an absent
Gemini key. No API requests are made by the readiness checks.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def has_ai_credentials(keys: Mapping[str, Any]) -> bool:
    return bool(str(keys.get("gemini_api_key") or "").strip()
                or str(keys.get("openrouter_api_key") or "").strip())


def choose_startup_backend(settings: Mapping[str, Any], keys: Mapping[str, Any]) -> str:
    """Return 'Local', 'OpenRouter', 'Gemini' or 'Unconfigured'.

    Explicit offline/local mode remains valid even without a cloud key.
    A missing preferred key can use the *other configured* provider, but
    never silently choose a new unrelated AI model.
    """
    preferred = str(settings.get("default_ai_provider") or "Gemini").strip()
    gemini = bool(str(keys.get("gemini_api_key") or "").strip())
    openrouter = bool(str(keys.get("openrouter_api_key") or "").strip())
    if settings.get("offline_mode_enabled") or preferred == "Local":
        return "Local"
    if preferred == "OpenRouter" and openrouter:
        return "OpenRouter"
    if preferred in {"Gemini", "Google Gemini"} and gemini:
        return "Gemini"
    if openrouter:
        return "OpenRouter"
    if gemini:
        return "Gemini"
    return "Unconfigured"
