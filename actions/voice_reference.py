"""Prepare a licensed, private XTTS reference clip on the user's own machine.

No internet, shell, installation, voice upload, ML inference or cloud service.
FFmpeg must already be on the user's PATH. Only writes a 25-second PCM WAV
to the existing per-user BrahmaAI voices directory, preserving app paths.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from core.user_paths import get_user_data_dir

REFERENCE_NAME = "jarvis_hu_authorized.wav"
CLIP_SECONDS = 12  # F5-TTS Hungarian recommends 5-15 seconds of reference.


class ReferencePreparationError(RuntimeError):
    """Safe messages only: do not expose private file names or paths."""


def target_reference_path() -> Path:
    return get_user_data_dir() / "voices" / REFERENCE_NAME


def _check_pcm_clip(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as audio:
            return (
                audio.getnchannels() == 1
                and audio.getsampwidth() == 2
                and audio.getframerate() == 24000
                and audio.getcomptype() == "NONE"
                and 3 <= audio.getnframes() / 24000 <= CLIP_SECONDS + 0.25
            )
    except (OSError, EOFError, wave.Error, ValueError):
        return False


def prepare_reference(source: str | Path, *, start_seconds: int = 0) -> Path:
    """Extract a short, standard WAV from a local consented MP3/WAV.

    Caller must obtain explicit permission confirmation BEFORE calling this.
    The source is never changed; the destination is replaced atomically only
    after a successful, header-validated conversion. Never print input paths.
    """
    source = Path(source).expanduser()
    if source.suffix.lower() not in {".wav", ".mp3"}:
        raise ReferencePreparationError("Csak helyi MP3 vagy WAV hangfájl választható.")
    if not source.is_file() or not source.stat().st_size:
        raise ReferencePreparationError("A kiválasztott helyi hangfájl nem olvasható.")
    if type(start_seconds) is not int or not 0 <= start_seconds <= 3600:
        raise ReferencePreparationError("A részlet kezdete 0–3600 másodperc lehet.")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, OSError, RuntimeError):
            ffmpeg = None

    dest = target_reference_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve() == dest.resolve():
            raise ReferencePreparationError(
                "A kiválasztott fájl már a célreferencia. Válassz másik forrásfájlt."
            )
    except OSError:
        raise ReferencePreparationError("A hangfájl útvonala nem ellenőrizhető.") from None

    tmp = None
    try:
        # Local per-user directory: avoid the machine-wide temp directory.
        with tempfile.NamedTemporaryFile(
            prefix=".jarvis_reference_", suffix=".wav",
            dir=dest.parent, delete=False
        ) as output:
            tmp = Path(output.name)
        if not ffmpeg:
            # Windows EXE can still import a ready PCM WAV without external tools.
            if source.suffix.lower() != ".wav":
                raise ReferencePreparationError(
                    "Az MP3 előkészítéshez hiányzik a beépített FFmpeg. Válassz PCM WAV-fájlt."
                )
            try:
                with wave.open(str(source), "rb") as inp:
                    if (inp.getnchannels(), inp.getsampwidth(), inp.getframerate(), inp.getcomptype()) != (
                        1, 2, 24000, "NONE"
                    ):
                        raise ReferencePreparationError("A WAV nem 24 kHz mono, 16 bites PCM.")
                    if inp.getnframes() < 3 * 24000:
                        raise ReferencePreparationError("A referencia minimum 3 másodperces legyen.")
                    inp.setpos(min(start_seconds * 24000, max(0, inp.getnframes() - 3 * 24000)))
                    payload = inp.readframes(CLIP_SECONDS * 24000)
                with wave.open(str(tmp), "wb") as out:
                    out.setnchannels(1)
                    out.setsampwidth(2)
                    out.setframerate(24000)
                    out.writeframes(payload)
            except (wave.Error, OSError, EOFError):
                raise ReferencePreparationError("A kiválasztott PCM WAV nem olvasható.") from None
            if not _check_pcm_clip(tmp):
                raise ReferencePreparationError("Nem sikerült a WAV referencia előkészítése.")
            os.replace(tmp, dest)
            tmp = None
            return dest

        command = [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-ss", str(start_seconds), "-i", str(source), "-t", str(CLIP_SECONDS),
            "-vn", "-ac", "1", "-ar", "24000",
            "-c:a", "pcm_s16le", "-y", str(tmp),
        ]
        try:
            result = subprocess.run(
                command, shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=90, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ReferencePreparationError("A helyi hangkonverzió nem fejeződött be.") from None

        if result.returncode != 0 or not _check_pcm_clip(tmp):
            raise ReferencePreparationError(
                "Nem sikerült érvényes 3–12 másodperces PCM WAV-részletet létrehozni."
            )
        # Staged write, no partial overwrite on error.
        os.replace(tmp, dest)
        tmp = None
        return dest
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
