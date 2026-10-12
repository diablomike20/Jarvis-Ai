#!/usr/bin/env python3
"""Bootstrap the PROVIDED MaRecord MP3 into a private, inspectable voice dataset.

No transcription, speaker verification, API calls, remote uploads or model training.
Only requires Python 3.11+ and ffmpeg/ffprobe installed on PATH.

Do NOT label candidate clips as approved/training-ready until a human hears them,
verifies the speaker, reads the EXACT transcript and checks rights for that source.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]


def protect_private_dir(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path == REPO or path.is_relative_to(REPO):
        raise ValueError("Private audio must be OUTSIDE the public JARVIS repository.")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def command(binary: str, args: list[str], timeout: int = 600) -> tuple[str, str]:
    exe = shutil.which(binary)
    if not exe:
        raise RuntimeError(f"Required utility {binary} is missing. Install FFmpeg.")
    result = subprocess.run(
        [exe, *args], text=True, capture_output=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{binary} failed: {result.stderr[-1400:]}")
    return result.stdout, result.stderr


def parse_silences(ffmpeg_stderr: str, duration: float) -> list[tuple[float, float]]:
    """Parse silencedetect chronologically, without assuming equal list lengths."""
    result: list[tuple[float, float]] = []
    current_start: float | None = None
    for line in ffmpeg_stderr.splitlines():
        match_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if match_start:
            current_start = float(match_start.group(1))
            continue
        match_end = re.search(r"silence_end:\s*([0-9.]+)", line)
        if match_end and current_start is not None:
            end = float(match_end.group(1))
            if 0 <= current_start < end:
                result.append((current_start, min(duration, end)))
            current_start = None
    if current_start is not None and current_start < duration:
        result.append((current_start, duration))
    return result


def propose_candidates(
    duration: float,
    silences: list[tuple[float, float]],
    min_seconds: float = 4.0,
    max_seconds: float = 12.0,
    max_clips: int = 8,
) -> list[tuple[float, float]]:
    """Propose segments between silence intervals, NOT necessarily voice."""
    if not (duration > 0 and 0 < min_seconds <= max_seconds):
        raise ValueError("Invalid duration or clip settings.")
    speech_like: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in sorted(silences):
        start = min(duration, max(cursor, start))
        end = min(duration, max(start, end))
        if start > cursor:
            speech_like.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        speech_like.append((cursor, duration))

    # Join short intervals separated by a natural small pause, up to 0.65 s.
    merged: list[tuple[float, float]] = []
    for start, end in speech_like:
        if merged and start - merged[-1][1] <= 0.65 and end - merged[-1][0] <= max_seconds:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    clips: list[tuple[float, float]] = []
    for begin, end in merged:
        remaining = end - begin
        if remaining < min_seconds:
            continue
        t = begin
        while t + min_seconds <= end and len(clips) < max_clips:
            clip_end = min(end, t + max_seconds)
            clips.append((round(t, 3), round(clip_end, 3)))
            t = clip_end
        if len(clips) >= max_clips:
            break
    return clips


def analyze(source: Path, out_root: Path, max_clips: int = 8) -> dict:
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
        raise ValueError("Supported inputs: MP3, WAV, M4A, FLAC, OGG.")
    if not 0 <= max_clips <= 24:
        raise ValueError("--max-clips must be between 0 and 24.")
    if source.is_relative_to(REPO):
        raise ValueError("Do not keep the private original audio in the public repository.")
    digest = sha256_file(source)
    final_dir = protect_private_dir(str(out_root)) / ("marecord_" + digest[:12])
    if final_dir.exists():
        raise FileExistsError(f"Existing analysis preserved; refusing overwrite: {final_dir}")

    stdout, _ = command("ffprobe", [
        "-v", "error", "-show_entries",
        "format=duration,format_name,bit_rate,size:"
        "stream=index,codec_type,codec_name,sample_rate,channels,channel_layout",
        "-of", "json", str(source)
    ])
    metadata = json.loads(stdout)
    duration = float(metadata.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise ValueError("Invalid/unavailable file duration.")
    if not any(s.get("codec_type") == "audio" for s in metadata.get("streams", [])):
        raise ValueError("No audio stream found.")

    # Analyze ORIGINAL compressed file (no lossy recompression).
    _, logs = command("ffmpeg", [
        "-hide_banner", "-nostdin", "-i", str(source), "-map", "0:a:0", "-vn",
        "-af", "volumedetect,silencedetect=noise=-35dB:d=0.35",
        "-f", "null", "-"
    ], timeout=1200)
    silences = parse_silences(logs, duration)
    candidates = propose_candidates(duration, silences, max_clips=max_clips)

    def get_volume(label: str) -> float | None:
        match = re.search(rf"\b{label}:\s*(-?(?:[0-9.]+|inf))\s*dB", logs)
        return float(match.group(1)) if match else None

    final_dir.mkdir(parents=True, exist_ok=False)
    wav = final_dir / "full_reference_24k_mono.wav"
    command("ffmpeg", [
        "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1",
        "-ar", "24000", "-c:a", "pcm_s16le", str(wav)
    ], timeout=1200)

    records = []
    for i, (start, end) in enumerate(candidates, 1):
        clip = final_dir / f"candidate_{i:02d}_{start:.2f}s.wav"
        command("ffmpeg", [
            "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-ss", f"{start:.3f}", "-i", str(source),
            "-t", f"{end-start:.3f}", "-map", "0:a:0", "-vn",
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(clip)
        ])
        records.append({
            "wav_file": clip.name, "start_s": start, "end_s": end,
            "exact_hungarian_transcript": "",
            "speaker_verified": "no", "quality_verified": "no",
            "style": "unreviewed", "usable_for_model": "no",
        })

    with (final_dir / "review_candidates.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        columns = [
            "wav_file", "start_s", "end_s", "exact_hungarian_transcript",
            "speaker_verified", "quality_verified", "style", "usable_for_model"
        ]
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    report = {
        "status": "technical_preflight_completed; speaker NOT verified",
        "original_file": source.name,
        "original_path": str(source),
        "original_size_bytes": source.stat().st_size,
        "original_sha256": digest,
        "measured_utc": datetime.now(timezone.utc).isoformat(),
        "ffprobe": metadata,
        "duration_s": round(duration, 3),
        "mean_volume_db": get_volume("mean_volume"),
        "max_volume_db": get_volume("max_volume"),
        "silence_threshold_db": -35,
        "silences": [{"start": a, "end": b} for a, b in silences],
        "full_reference_wav": wav.name,
        "candidate_wavs": [item["wav_file"] for item in records],
        "warning": (
            "The silence detector cannot tell human speech from music/FX, "
            "identify a person or transcribe Hungarian. Every candidate is "
            "UNVERIFIED until heard and transcribed."
        ),
    }
    (final_dir / "technical_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Original: {source.name} ({duration:.2f} sec)")
    print(f"Prepared full mono 24k WAV: {wav}")
    print(f"Created {len(records)} unreviewed candidate WAVs: {final_dir}")
    print("Do not use for voice cloning until the clip and transcript are verified.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Existing MaRecord MP3 on the local Windows PC")
    parser.add_argument("--output-dir", required=True, help="Private folder OUTSIDE the JARVIS Git repository")
    parser.add_argument("--max-clips", type=int, default=8)
    args = parser.parse_args()
    try:
        analyze(Path(args.input).expanduser().resolve(),
                protect_private_dir(args.output_dir), args.max_clips)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
