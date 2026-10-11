"""Local Hungarian speech recognition for Jarvis, without Google/Gemini APIs.

The small multilingual faster-whisper model runs on the user's computer.
Its weights may need to be downloaded once; audio is then transcribed locally.
"""
from __future__ import annotations

import importlib.util
import os
from functools import lru_cache

import numpy as np

DEFAULT_MODEL = "base"
DEFAULT_LANGUAGE = "hu"


def is_available() -> bool:
    """Report whether the optional offline speech recognizer is installed."""
    return importlib.util.find_spec("faster_whisper") is not None


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel
    size = os.environ.get("JARVIS_WHISPER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    # CPU int8 works without CUDA; GPU may be selected separately after validation.
    return WhisperModel(size, device="cpu", compute_type="int8")


def transcribe_pcm(pcm: bytes, sample_rate: int = 16000) -> str:
    """Transcribe 16-bit mono PCM sampled at 16kHz to Hungarian text."""
    if sample_rate != 16000:
        raise ValueError("Expected 16 kHz mono PCM; resample before calling.")
    if not pcm or len(pcm) < sample_rate * 2 // 2:
        return ""
    waveform = np.frombuffer(pcm[:len(pcm) // 2 * 2], dtype="<i2")
    samples = waveform.astype(np.float32) / 32768.0
    segments, _ = _get_model().transcribe(
        samples, language=DEFAULT_LANGUAGE, beam_size=2,
        vad_filter=True, condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


class SpeechSegmenter:
    """Simple RMS-driven endpoint detector with bounded memory.

    The caller makes the voiced decision per frame. PTT users get their
    utterance on key release; open-mic users get it after a short silence.
    """
    def __init__(self, sample_rate: int = 16000, min_seconds: float = 0.5,
                 silence_seconds: float = 0.7, max_seconds: float = 18.0):
        self._min_bytes = int(sample_rate * 2 * min_seconds)
        self._silence_bytes = int(sample_rate * 2 * silence_seconds)
        self._max_bytes = int(sample_rate * 2 * max_seconds)
        self._audio = bytearray()
        self._quiet_bytes = 0

    def reset(self) -> None:
        self._audio.clear()
        self._quiet_bytes = 0

    def _finish(self) -> bytes | None:
        speech = bytes(self._audio) if len(self._audio) >= self._min_bytes else None
        self.reset()
        return speech

    def feed(self, frame: bytes, *, active: bool, voiced: bool,
             ptt: bool, held: bool) -> bytes | None:
        if not active:
            self.reset()
            return None

        if ptt:
            if not held:
                return self._finish() if self._audio else None
            self._audio.extend(frame)
            return self._finish() if len(self._audio) >= self._max_bytes else None

        if voiced:
            self._audio.extend(frame)
            self._quiet_bytes = 0
        elif self._audio:
            self._audio.extend(frame)
            self._quiet_bytes += len(frame)
        if self._audio and (self._quiet_bytes >= self._silence_bytes or
                            len(self._audio) >= self._max_bytes):
            return self._finish()
        return None
