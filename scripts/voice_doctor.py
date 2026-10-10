"""JARVIS Hungarian voice preflight — safe local diagnostics, no model download.

Run from the SAME Python environment that launches JARVIS:
    python scripts/voice_doctor.py
    python scripts/voice_doctor.py --json
    python scripts/voice_doctor.py --strict

No reference audio content/path, personal data, source text or model weights
are printed. No microphone access, speech generation or network requests.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.jarvis_voice import voice_readiness  # noqa: E402


def _version(dist_name: str) -> str | None:
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def probe_runtime_imports() -> dict:
    """Import selected installed runtimes without loading/downloading models.

    Opt-in because importing Torch can take time. Errors are redacted to
    class names; Python tracebacks may contain private installation paths.
    """
    results = {"torch_import_ok": False, "coqui_api_import_ok": False, "cuda_available": False}
    try:
        torch = importlib.import_module("torch")
        results["torch_import_ok"] = True
        results["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as exc:
        results["torch_error_type"] = type(exc).__name__
    try:
        api = importlib.import_module("TTS.api")
        results["coqui_api_import_ok"] = bool(getattr(api, "TTS", None))
    except Exception as exc:
        results["coqui_error_type"] = type(exc).__name__
    return results


def inspect_environment() -> dict:
    """Read-only package presence test and private WAV header check."""
    readiness = voice_readiness()
    packages = {
        "coqui-tts": _version("coqui-tts"),
        "torch": _version("torch"),
        "torchaudio": _version("torchaudio"),
        "torchcodec": _version("torchcodec"),
        "PyQt6": _version("PyQt6"),
        "PyQt6-WebEngine": _version("PyQt6-WebEngine"),
    }
    correct_python = (3, 10) <= sys.version_info[:2] < (3, 15)
    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "python_supported_by_coqui": correct_python,
        "xtts_enabled": bool(readiness["enabled"]),
        "reference_pcm_wav_valid": bool(readiness["reference_ok"]),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "required_modules_present": bool(readiness["dependencies_ok"]),
        "xtts_runtime_plausible": bool(readiness["can_enable"]) and correct_python,
        "packages": packages,
        "note": "Package presence is NOT a verified model load or Windows speech test.",
    }


def hints(report: dict) -> list[str]:
    advice = []
    if report["platform"] != "Windows":
        advice.append("A JARVIS hangkimenet jelenleg csak Windows alatt támogatott.")
    if not report["python_supported_by_coqui"]:
        advice.append("A Coqui által támogatott Python 3.10–3.14 környezetet használj.")
    if not report["ffmpeg_available"]:
        advice.append("A helyi MP3/WAV importáláshoz telepíts FFmpeg-et és add a PATH-hoz.")
    if not report["reference_pcm_wav_valid"]:
        advice.append("Importálj engedélyezett PCM WAV-referenciát a JARVIS Audio beállításaiban.")
    if not report["required_modules_present"]:
        advice.append(
            "Ebben a Python-környezetben telepíts megfelelő torch/torchaudio "
            "és coqui-tts csomagokat a hivatalos telepítési útmutató szerint."
        )
    if not report["xtts_enabled"]:
        advice.append("Az XTTS kikapcsolva; csak tudatos jóváhagyással engedélyezd.")
    if report["xtts_runtime_plausible"]:
        advice.append("Az alapfeltételek rendben; a Windows hangpróba még szükséges.")
    return advice


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="JARVIS XTTS local-only preflight")
    parser.add_argument("--json", action="store_true", help="Machine-readable, sanitized status")
    parser.add_argument("--strict", action="store_true", help="Nonzero exit if prerequisites are missing")
    parser.add_argument("--probe-runtime", action="store_true", help="Import Torch and Coqui API locally without model load")
    args = parser.parse_args(argv)
    status = inspect_environment()
    if args.probe_runtime:
        status["runtime_import_probe"] = probe_runtime_imports()
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print("JARVIS magyar XTTS — helyi környezetellenőrzés")
        print("Platform:", status["platform"], "| Python:", status["python_version"])
        print("FFmpeg:", "van" if status["ffmpeg_available"] else "hiányzik")
        print("Privát PCM WAV:", "érvényes" if status["reference_pcm_wav_valid"] else "hiányzik/hibás")
        print("XTTS függőségek:", "észlelhetők" if status["required_modules_present"] else "hiányosak")
        print("Engedélyezve:", "igen" if status["xtts_enabled"] else "nem")
        if args.probe_runtime:
            print("Runtime importellenőrzés:", json.dumps(status["runtime_import_probe"], ensure_ascii=False))
        print("Javaslatok:")
        for advice in hints(status):
            print(" -", advice)
    ready = status["xtts_runtime_plausible"]
    if args.probe_runtime:
        probes = status["runtime_import_probe"]
        ready = ready and probes["torch_import_ok"] and probes["coqui_api_import_ok"]
    return 2 if args.strict and not ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
