"""Optional, opt-in local Hungarian XTTS-v2 speech using an authorized WAV.

The reference stays in the user's local data directory (or an explicitly chosen
local path). The XTTS dependencies are optional and imported only on demand.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import wave
from functools import lru_cache
from pathlib import Path

from core.user_paths import get_user_data_dir

LOG = logging.getLogger("JarvisVoice")
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
REFERENCE_FILE_NAME = "jarvis_hu_authorized.wav"
_LANGUAGE = "hu"
_speech_lock = threading.Lock()
_state_lock = threading.Lock()
_active_cancel: threading.Event | None = None
_stop_epoch = 0  # Invalidates utterances already queued when STOP is pressed.


def reference_wav_path() -> Path:
    override = os.environ.get("JARVIS_VOICE_REFERENCE", "").strip()
    return Path(override).expanduser() if override else (
        get_user_data_dir() / "voices" / REFERENCE_FILE_NAME
    )


def _valid_reference_wav(path: Path) -> bool:
    """Require a plausible uncompressed PCM WAV, not a renamed MP3."""
    if path.suffix.lower() != ".wav" or not path.is_file():
        return False
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            rate = audio.getframerate()
            seconds = audio.getnframes() / max(1, rate)
            return (
                audio.getcomptype() == "NONE"
                and channels in (1, 2)
                and audio.getsampwidth() in (2, 3, 4)
                and 8000 <= rate <= 96000
                and 3 <= seconds <= 120
            )
    except (OSError, EOFError, wave.Error, ValueError):
        return False


def is_configured() -> bool:
    """No file-presence-based auto-enablement: explicit user opt-in only."""
    try:
        from memory import config_manager
        settings = config_manager.load_settings() or {}
        if settings.get("jarvis_voice_enabled") is not True:
            return False
    except Exception:
        return False
    return _valid_reference_wav(reference_wav_path())


def _is_windows() -> bool:
    return os.name == "nt"


def voice_readiness() -> dict[str, bool | str]:
    """Cheap, side-effect-free status for the real JARVIS settings screen.

    This only inspects packages and the WAV header. It NEVER loads XTTS,
    contacts the network, plays speech, or discloses the private WAV path.
    """
    import importlib.util

    try:
        from memory import config_manager
        enabled = config_manager.load_settings().get("jarvis_voice_enabled") is True
    except Exception:
        enabled = False
    reference_ok = _valid_reference_wav(reference_wav_path())
    deps = {}
    for package in ("torch", "TTS"):
        try:
            deps[package] = importlib.util.find_spec(package) is not None
        except (ImportError, ValueError, AttributeError):
            deps[package] = False
    supported = _is_windows()
    can_enable = supported and reference_ok and all(deps.values())
    if not supported:
        reason = "A magyar XTTS hang csak Windows alatt támogatott."
    elif not reference_ok:
        reason = "Hiányzik az érvényes, engedélyezett PCM WAV referencia."
    elif not all(deps.values()):
        reason = "Hiányzik a torch vagy a coqui-tts (TTS) helyi függőség."
    elif enabled:
        reason = "Magyar XTTS bekapcsolva. Helyi hangpróba indítható."
    else:
        reason = "A helyi referencia és függőségek készen állnak."
    return {
        "enabled": enabled,
        "reference_ok": reference_ok,
        "dependencies_ok": all(deps.values()),
        "windows": supported,
        "can_enable": can_enable,
        "reason": reason,
    }


@lru_cache(maxsize=1)
def _load_model():
    """The first model download, if necessary, requires prior voice opt-in."""
    import torch
    from TTS.api import TTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    LOG.info("Initializing local Hungarian XTTS (%s)", device)
    return TTS(MODEL_NAME).to(device)


def stop_authorized_hungarian() -> None:
    """Interrupt current playback and invalidate work queued before STOP."""
    global _stop_epoch
    with _state_lock:
        _stop_epoch += 1
        cancel = _active_cancel
        if cancel is not None:
            cancel.set()
    if cancel is not None:
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except (ImportError, RuntimeError, OSError):
            pass


def _private_temp_dir() -> Path:
    directory = get_user_data_dir() / "voices" / "temp"
    directory.mkdir(parents=True, exist_ok=True)
    # Remove only old leftovers; never touch another active process's audio.
    for stale in directory.glob("xtts_*.wav"):
        try:
            if time.time() - stale.stat().st_mtime > 86400:
                stale.unlink()
        except OSError:
            pass
    return directory


def speak_authorized_hungarian(text: str) -> bool:
    """Return True when handled (including a deliberate stop), else fallback."""
    global _active_cancel
    text = (text or "").strip()
    if not text or not _is_windows() or not is_configured():
        return False

    # Each invocation captures STOP generation before waiting on the
    # speech lock. Without this, an already queued utterance could start
    # after the user presses STOP.
    with _state_lock:
        request_epoch = _stop_epoch
    with _speech_lock:
        if not is_configured():
            return False
        with _state_lock:
            if request_epoch != _stop_epoch:
                return True  # Deliberately cancelled: never fall back to Edge.
            cancel = threading.Event()
            _active_cancel = cancel
        output_path = None
        try:
            import winsound
            with tempfile.NamedTemporaryFile(
                prefix="xtts_", suffix=".wav", dir=_private_temp_dir(),
                delete=False,
            ) as output:
                output_path = Path(output.name)

            _load_model().tts_to_file(
                text=text,
                speaker_wav=str(reference_wav_path()),
                language=_LANGUAGE,
                file_path=str(output_path),
                split_sentences=True,
            )
            if cancel.is_set():
                return True  # Cancelled speech must NOT trigger the fallback.
            with wave.open(str(output_path), "rb") as generated:
                seconds = generated.getnframes() / max(1, generated.getframerate())
            winsound.PlaySound(
                str(output_path),
                winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC,
            )
            cancel.wait(seconds + 0.15)
            return True
        except Exception as exc:
            # Do not log private paths or text from an exception message.
            LOG.warning("Local XTTS failed (%s); using existing TTS", type(exc).__name__)
            return bool(cancel.is_set())
        finally:
            if output_path is not None:
                try:
                    import winsound
                    winsound.PlaySound(None, 0)
                except (ImportError, RuntimeError, OSError):
                    pass
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass
            with _state_lock:
                if _active_cancel is cancel:
                    _active_cancel = None
