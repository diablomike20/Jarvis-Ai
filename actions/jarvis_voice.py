"""Optional local Hungarian XTTS voice cloning with an authorized reference recording.

No voice samples or generated speech leave the user's machine. The reference
WAV is deliberately stored in per-user local app data, never in the repository.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

from core.user_paths import get_user_data_dir

LOG = logging.getLogger("JarvisVoice")
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
REFERENCE_FILE_NAME = "jarvis_hu_authorized.wav"
_LANGUAGE = "hu"
_speech_lock = threading.Lock()


def reference_wav_path() -> Path:
    """Location of the user's own, licensed Hungarian voice reference."""
    override = os.environ.get("JARVIS_VOICE_REFERENCE", "").strip()
    if override:
        return Path(override).expanduser()
    return get_user_data_dir() / "voices" / REFERENCE_FILE_NAME


def is_configured() -> bool:
    """Never initialize XTTS unless an authorized reference has been provided."""
    reference = reference_wav_path()
    if not reference.is_file():
        return False
    try:
        from memory import config_manager
        settings = config_manager.load_settings() or {}
        return bool(settings.get("jarvis_voice_enabled", True))
    except Exception:
        return True


@lru_cache(maxsize=1)
def _load_model():
    """Load heavy optional packages only when custom speech is actually requested."""
    import torch
    from TTS.api import TTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    LOG.info("Initializing Hungarian XTTS on %s", device)
    return TTS(MODEL_NAME).to(device)


def speak_authorized_hungarian(text: str) -> bool:
    """Play text in the authorized local voice; False means use existing TTS.

    The recording must be provided by the user under an appropriate license.
    This feature does not download or embed any actor's voice recordings.
    """
    text = (text or "").strip()
    if not text or not is_configured() or os.name != "nt":
        return False

    # Serialize generation and playback, avoiding concurrent access to XTTS.
    with _speech_lock:
        output_path = None
        try:
            import winsound
            with tempfile.NamedTemporaryFile(prefix="jarvis_hu_", suffix=".wav",
                                             delete=False) as output:
                output_path = Path(output.name)

            _load_model().tts_to_file(
                text=text,
                speaker_wav=str(reference_wav_path()),
                language=_LANGUAGE,
                file_path=str(output_path),
                split_sentences=True,
            )
            winsound.PlaySound(
                str(output_path), winsound.SND_FILENAME | winsound.SND_NODEFAULT
            )
            return True
        except Exception as exc:
            LOG.warning("Local Hungarian XTTS unavailable; switching to fallback: %s", exc)
            return False
        finally:
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass
