"""Native, private Hungarian F5-TTS adapter for the installed JARVIS application.

The public model is obtained separately, only after the user explicitly approves
its CC-BY-NC-4.0 terms. Private reference audio is NEVER uploaded or committed.
No HTTP listener, no hard-coded C:\Asszisztens paths, no developer virtualenv.
"""
from __future__ import annotations

import importlib.util
import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from core.user_paths import get_user_data_dir

MODEL_REPO = "Maxdorger29/f5-tts-hungarian"
MODEL_FILES = ("model_last_final.safetensors", "vocab.txt")
MIN_MODEL_BYTES = 100_000_000


class F5ModelError(RuntimeError):
    """Deliberately sanitized to avoid exposing any user's private paths."""


def model_dir() -> Path:
    return get_user_data_dir() / "models" / "f5-tts-hungarian"


def model_paths() -> tuple[Path, Path]:
    root = model_dir()
    return root / MODEL_FILES[0], root / MODEL_FILES[1]


def assets_ready() -> bool:
    checkpoint, vocab = model_paths()
    try:
        return (checkpoint.is_file() and checkpoint.stat().st_size > MIN_MODEL_BYTES
                and vocab.is_file() and 20 <= vocab.stat().st_size <= 100_000)
    except OSError:
        return False


def runtime_available() -> bool:
    try:
        return all(importlib.util.find_spec(mod) is not None
                   for mod in ("torch", "torchaudio", "f5_tts", "soundfile", "numpy"))
    except (ImportError, AttributeError, ValueError):
        return False


def download_model(*, user_approved: bool) -> bool:
    """Download only publicly licensed model weights after GUI confirmation.

    No reference audio, reference text, credentials or user data leave the PC.
    The hub's own cache uses safe download/resume semantics.
    """
    if not user_approved:
        return False
    try:
        from huggingface_hub import hf_hub_download
        root = model_dir()
        root.mkdir(parents=True, exist_ok=True)
        for filename in MODEL_FILES:
            hf_hub_download(
                repo_id=MODEL_REPO, filename=filename, local_dir=str(root),
            )
        if not assets_ready():
            raise F5ModelError("A letöltött F5 magyar modell nem teljes.")
        return True
    except F5ModelError:
        raise
    except Exception:
        raise F5ModelError("Nem sikerült a magyar F5 modell helyi letöltése.") from None


@contextmanager
def _compatible_audio_loader():
    """F5 inference workaround, scoped to generation (not permanent global patch)."""
    import torch
    import torchaudio
    import soundfile as sf

    original = torchaudio.load

    def patched(path, **kwargs):
        data, rate = sf.read(str(path), dtype="float32")
        if data.ndim == 1:
            data = data[None, :]
        else:
            data = data.T
        return torch.from_numpy(data), rate

    torchaudio.load = patched
    try:
        yield
    finally:
        torchaudio.load = original


@lru_cache(maxsize=1)
def _load_f5():
    import torch
    from f5_tts.api import F5TTS

    checkpoint, vocab = model_paths()
    return F5TTS(
        model="F5TTS_v1_Base",
        ckpt_file=str(checkpoint),
        vocab_file=str(vocab),
        device="cuda" if torch.cuda.is_available() else "cpu",
        use_ema=True,
    )


def synthesize_f5(text: str, reference: Path, transcript: str, output: Path) -> None:
    """Generate a local PCM WAV using the user's confirmed reference transcript."""
    import soundfile as sf

    if not assets_ready() or not runtime_available():
        raise F5ModelError("A helyi F5 modell vagy a hangmotor hiányzik.")
    if not reference.is_file() or not 3 <= len(transcript.strip()) <= 2500:
        raise F5ModelError("Az F5 referenciahang és annak pontos átirata szükséges.")
    if not text.strip():
        raise F5ModelError("Nincs felolvasandó szöveg.")

    try:
        with _compatible_audio_loader():
            model = _load_f5()
            wav, sample_rate, _ = model.infer(
                ref_file=str(reference),
                ref_text=transcript.strip(),
                gen_text=text.strip(),
            )
        sf.write(str(output), wav, sample_rate, format="WAV", subtype="PCM_16")
    except Exception:
        raise F5ModelError("A helyi F5 magyar beszédgenerálás sikertelen.") from None
