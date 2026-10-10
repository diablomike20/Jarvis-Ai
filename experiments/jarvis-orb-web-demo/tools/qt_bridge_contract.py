"""Pure, safe JavaScript bridge contract for the isolated Orb/Qt demonstration.

Does not import Qt, open a browser, contact any network, or touch production UI.
"""
from __future__ import annotations

import json
import math

ALLOWED_STATES = frozenset(
    {"IDLE", "LISTENING", "THINKING", "SPEAKING", "SUCCESS", "ERROR", "OFFLINE"}
)
ALIASES = {
    "ACTIVE": "LISTENING",
    "WAKE": "LISTENING",
    "LISTEN": "LISTENING",
    "PROCESSING": "THINKING",
    "RESPONDING": "SPEAKING",
    "TALKING": "SPEAKING",
    "ALERT": "ERROR",
    "FAILED": "ERROR",
    "SLEEPING": "IDLE",
}


def normalize_state(value: object) -> str:
    name = str(value or "").strip().upper()
    state = ALIASES.get(name, name)
    return state if state in ALLOWED_STATES else "IDLE"


def normalize_audio(value: object) -> float:
    try:
        number = float(value)
        return min(1.0, max(0.0, number)) if math.isfinite(number) else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def make_js_command(state: object, audio: object) -> str:
    """Only serializable state and a bounded finite level may reach runJavaScript.

    Never interpolates arbitrary expressions, source strings, or external URLs.
    """
    canonical = json.dumps(normalize_state(state))
    level = normalize_audio(audio)
    return (
        "if (typeof window.setBrahmaState === 'function') "
        f"window.setBrahmaState({canonical});"
        "if (typeof window.setAudioLevel === 'function') "
        f"window.setAudioLevel({level:.4f});"
    )


# Read-only performance/status probe. Values are UI RAF cadence, not GPU metrics.
STATUS_JS = """
(() => {
    const text = id => document.querySelector('[data-testid="' + id + '"]')?.textContent ?? '';
    const canvas = document.querySelector('[data-testid="orb-stage"] canvas');
    return JSON.stringify({
        state: text('current-state'), fps_ui_raf: text('fps'),
        p95_ui_frame_ms: text('p95'), webgl_label: text('webgl'),
        canvas_width: canvas?.width ?? 0, canvas_height: canvas?.height ?? 0,
        visibility: document.visibilityState
    });
})()
"""
