#!/usr/bin/env python3
"""Local first-pass Hungarian transcription of a provided MaRecord or movie clip.

Uses faster-whisper LOCALLY. First use downloads Whisper model weights,
never uploads the user's sound to a transcription service.
Output is a DRAFT, not an actor identity check and not a verified transcript.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]


def private_path(raw: str) -> Path:
    resolved = Path(raw).expanduser().resolve()
    if resolved == REPO or resolved.is_relative_to(REPO):
        raise ValueError("Private audio/transcript must remain outside Git checkout.")
    return resolved


def transcribe(source: Path, target_dir: Path, *, model="small", device="cpu") -> dict:
    source = private_path(str(source))
    target_dir = private_path(str(target_dir))
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in (".wav", ".mp3", ".flac", ".m4a", ".ogg"):
        raise ValueError("Unsupported audio extension")
    if model not in ("tiny", "base", "small", "medium", "large-v3-turbo"):
        raise ValueError("Unknown model size")
    if device not in ("cpu", "cuda"):
        raise ValueError("Device must be cpu/cuda")
    if target_dir.exists():
        raise FileExistsError("Use a fresh directory; private results never overwrite.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install local faster-whisper in an isolated environment.") from exc
    engine = WhisperModel(model, device=device,
                          compute_type="float16" if device == "cuda" else "int8")
    segments, meta = engine.transcribe(
        str(source), language="hu", vad_filter=True,
        word_timestamps=True, beam_size=5)
    # The iterator is lazy, evaluate all segments before writing results.
    rows = []
    for s in segments:
        rows.append({"start": round(float(s.start), 3), "end": round(float(s.end), 3),
                     "text": s.text.strip(),
                     "avg_logprob": getattr(s, "avg_logprob", None),
                     "no_speech_prob": getattr(s, "no_speech_prob", None)})
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {
        "source_file": source.name, "source_sha256": digest,
        "language_requested": "hu",
        "language_detected_probability": getattr(meta, "language_probability", None),
        "model": model, "device": device, "processed_utc": datetime.now(timezone.utc).isoformat(),
        "speaker_identity_verified": False,
        "transcript_verified": False,
        "note": "AI transcript only: listen, correct each word, mark the actor before using F5.",
        "segments": rows,
    }
    target_dir.mkdir(parents=True, exist_ok=False)
    (target_dir / "draft_segments.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (target_dir / "DRAFT_TRANSCRIPT_REVIEW_REQUIRED.txt").write_text(
        "\n".join(row["text"] for row in rows) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model", choices=["tiny", "base", "small", "medium", "large-v3-turbo"],
                   default="small")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    a = p.parse_args()
    try:
        report = transcribe(Path(a.input), Path(a.output_dir), model=a.model, device=a.device)
        print(f"Proposed {len(report['segments'])} Hungarian segments; manually verify.")
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
