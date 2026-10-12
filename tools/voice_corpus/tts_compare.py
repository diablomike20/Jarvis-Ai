#!/usr/bin/env python3
"""Private A/B evaluation runner for Hungarian JARVIS TTS.

This is an isolated EXPERIMENT, not a production JARVIS runtime integration.
All reference/outputs must live outside the public Git checkout.
Neither engine nor the benchmark uploads private audio to an online API.
Models and Python dependencies must be installed by the user.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TESTS = [
    ("neutral", "A rendszerek készen állnak, uram."),
    ("confirmation", "Természetesen. Máris intézkedem."),
    ("analytical", "A rendszer állapotát ellenőriztem. Rendellenességet nem észleltem."),
    ("warning", "Uram, egy váratlan folyamat indult el. Javaslom az ellenőrzését."),
    ("numbers", "A processzor terhelése huszonhét százalék, a memóriahasználat nyolc gigabájt."),
    ("technical", "A Claude Code és az OpenRouter kapcsolata helyreállt."),
]


def outside_git(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == PROJECT_ROOT or resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError("Private data path is inside the JARVIS repository.")
    return resolved


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def wave_stats(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
        width = wav.getsampwidth()
        if frames <= 0 or rate <= 0 or channels <= 0:
            raise ValueError(f"Invalid WAV output: {path}")
        if width not in (2, 3, 4):
            raise ValueError(f"Unexpected PCM WAV format: {width} bytes/sample")
        return {
            "duration_s": round(frames / rate, 4),
            "sample_rate": rate, "channels": channels,
            "sample_width_bytes": width, "frames": frames,
        }


def read_transcript(path: Path | None, required: bool) -> str | None:
    if path is None:
        if required:
            raise ValueError("F5 requires --reference-transcript with manually verified exact words.")
        return None
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8-sig").strip()
    if required and (not text or len(text) > 1000):
        raise ValueError("F5 reference transcript must have 1-1000 verified characters.")
    return text


def device_name(choice: str) -> str:
    if choice in ("cpu", "cuda"):
        return choice
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        # For dry-run or partial environments, model import is later.
        return "cpu"


def load_f5(args):
    checkpoint = Path(args.f5_checkpoint or "").expanduser()
    vocabulary = Path(args.f5_vocab or "").expanduser()
    if not checkpoint.is_file() or not vocabulary.is_file():
        raise FileNotFoundError(
            "F5 requires existing --f5-checkpoint model_last_final.safetensors "
            "and --f5-vocab vocab.txt. These are separate downloads from "
            "Maxdorger29/f5-tts-hungarian.")
    try:
        import soundfile as sf
        from f5_tts.api import F5TTS
    except ImportError as exc:
        raise RuntimeError("Install F5-TTS dependencies in an isolated Python environment.") from exc
    model = F5TTS(model="F5TTS_v1_Base",
                  ckpt_file=str(checkpoint),
                  vocab_file=str(vocabulary),
                  device=device_name(args.device),
                  use_ema=True)
    def synth(reference: Path, transcript: str | None, text: str, outfile: Path) -> None:
        signal, rate, _ = model.infer(
            ref_file=str(reference), ref_text=transcript, gen_text=text)
        sf.write(str(outfile), signal, rate, subtype="PCM_16")
    return synth


def load_xtts(args):
    if not args.allow_xtts_model_download:
        raise ValueError(
            "XTTS model may be downloaded automatically. "
            "Pass --allow-xtts-model-download after reviewing its model license.")
    try:
        from TTS.api import TTS
    except ImportError as exc:
        raise RuntimeError("Install coqui-tts and compatible PyTorch in isolated Python env.") from exc
    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device_name(args.device))
    def synth(reference: Path, transcript: str | None, text: str, outfile: Path) -> None:
        model.tts_to_file(text=text, speaker_wav=[str(reference)],
                          language="hu", file_path=str(outfile), split_sentences=True)
    return synth


def validate_inputs(args) -> tuple[Path, Path, str | None]:
    private_dir = outside_git(Path(args.workspace))
    reference = outside_git(Path(args.reference))
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if reference.suffix.lower() != ".wav":
        raise ValueError("Convert reference to mono WAV first using corpus preparation tool.")
    info = wave_stats(reference)
    if info["duration_s"] < 3 or info["duration_s"] > 30:
        raise ValueError("Use a manually verified 3-30 s reference (5-15 s preferred).")
    transcript = read_transcript(
        outside_git(Path(args.reference_transcript)) if args.reference_transcript else None,
        required="f5" in args.engines)
    if args.rounds < 1 or args.rounds > 5:
        raise ValueError("--rounds must be 1..5.")
    if args.test_limit < 1 or args.test_limit > len(DEFAULT_TESTS):
        raise ValueError("--test-limit outside known test set.")
    if "f5" in args.engines:
        if not args.f5_checkpoint or not args.f5_vocab:
            raise ValueError("F5 requires --f5-checkpoint and --f5-vocab.")
        for name in (args.f5_checkpoint, args.f5_vocab):
            if not Path(name).expanduser().is_file():
                raise FileNotFoundError(name)
    return private_dir, reference, transcript


def run_benchmark(args) -> int:
    workspace, reference, transcript = validate_inputs(args)
    plan = {
        "dry_run": bool(args.dry_run),
        "engines": args.engines,
        "device": device_name(args.device),
        "reference_duration_s": wave_stats(reference)["duration_s"],
        "reference_sha256": sha256(reference),
        "reference_transcript_present": bool(transcript),
        "tests": DEFAULT_TESTS[:args.test_limit],
        "rounds": args.rounds,
        "external_audio_upload": False,
        "note": "Voice quality and actor identity are NOT certified by this tool.",
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    workspace.mkdir(parents=True, exist_ok=True)
    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_dir = workspace / "evaluation" / f"ab_{batch}"
    if result_dir.exists():
        raise FileExistsError(result_dir)
    result_dir.mkdir(parents=True)
    records: list[dict] = []
    for engine in args.engines:
        start_load = time.perf_counter()
        try:
            synthesizer = (load_f5 if engine == "f5" else load_xtts)(args)
            loading_s = time.perf_counter() - start_load
        except Exception as exc:
            records.append({"engine": engine, "status": "model_load_error",
                            "error_type": type(exc).__name__, "error": str(exc)[:400]})
            continue
        for r in range(args.rounds):
            for idx, (style, text) in enumerate(DEFAULT_TESTS[:args.test_limit], start=1):
                wav_path = result_dir / f"{engine}_{r+1}_{idx:02d}_{style}.wav"
                record = {"engine": engine, "round": r + 1, "test_id": idx,
                          "style": style, "text": text,
                          "reference_sha256": plan["reference_sha256"],
                          "model_load_s": round(loading_s, 3),
                          "audio_file": wav_path.name}
                started = time.perf_counter()
                try:
                    synthesizer(reference, transcript, text, wav_path)
                    elapsed = time.perf_counter() - started
                    stats = wave_stats(wav_path)
                    record.update({
                        "status": "generated_unreviewed", "generation_s": round(elapsed, 3),
                        "realtime_factor": round(elapsed / stats["duration_s"], 3),
                        "audio": stats, "audio_sha256": sha256(wav_path)})
                except Exception as exc:
                    wav_path.unlink(missing_ok=True)
                    record.update({"status": "error", "error_type": type(exc).__name__,
                                   "error": str(exc)[:400]})
                records.append(record)
    (result_dir / "benchmark.json").write_text(
        json.dumps({"plan": plan, "results": records}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"Saved benchmark: {result_dir / 'benchmark.json'}")
    counts = {e: sum(1 for rec in records
                     if rec.get("engine") == e and rec.get("status") == "generated_unreviewed")
              for e in args.engines}
    print("Generated WAV counts:", counts)
    print("Listen and rate identity, pronunciation, style and quality; no scores are invented.")
    return 0 if all(v > 0 for v in counts.values()) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True,
                        help="PRIVATE directory outside Git checkout.")
    parser.add_argument("--reference", required=True, help="3-30 s verified WAV file")
    parser.add_argument("--reference-transcript",
                        help="UTF-8 file containing EXACT spoken Hungarian reference text")
    parser.add_argument("--engines", nargs="+", choices=["f5", "xtts"],
                        default=["f5", "xtts"])
    parser.add_argument("--f5-checkpoint")
    parser.add_argument("--f5-vocab")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--allow-xtts-model-download", action="store_true")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--test-limit", type=int, default=len(DEFAULT_TESTS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run_benchmark(args))
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
