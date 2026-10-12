#!/usr/bin/env python3
"""Local, no-cloud audio preflight for Hungarian JARVIS references.

Reports codec, duration, channel count, FFmpeg volume/silence diagnostics
and a SHA-256 without uploading/altering any reference audio.
Silence intervals are NOT speech recognition or speaker identification.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]


def private_file(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    if target == REPO or target.is_relative_to(REPO):
        raise ValueError("Audio reference cannot be under public Git checkout.")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for data in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def execute(binary: str, opts: list[str]) -> tuple[str, str]:
    exe = shutil.which(binary)
    if not exe:
        raise RuntimeError(f"{binary} unavailable; install FFmpeg and add to PATH.")
    result = subprocess.run([exe, *opts], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=240,
                            check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{binary} failed: {result.stderr[-1200:]}")
    return result.stdout, result.stderr


def silence_intervals(log: str, duration: float) -> list[dict]:
    # Normal ffmpeg silencedetect log has silence_start and silence_end lines.
    starts = re.findall(r"silence_start:\s*([0-9.]+)", log)
    ends = re.findall(r"silence_end:\s*([0-9.]+)", log)
    intervals: list[dict] = []
    for index, value in enumerate(starts):
        start = float(value)
        end = float(ends[index]) if index < len(ends) else duration
        if end >= start and 0 <= start <= duration:
            intervals.append({"start_s": round(start, 3), "end_s": round(min(end, duration), 3)})
    return intervals


def preflight(src: Path) -> dict:
    raw, _ = execute("ffprobe", ["-v", "error", "-show_entries",
        "format=duration,format_name,size,bit_rate:"
        "stream=index,codec_type,codec_name,channels,channel_layout,sample_rate",
        "-of", "json", str(src)])
    meta = json.loads(raw)
    duration = float(meta.get("format", {}).get("duration") or 0)
    if not duration > 0:
        raise ValueError("Unable to measure audio duration.")
    _, log = execute("ffmpeg", ["-hide_banner", "-nostdin", "-i", str(src),
        "-map", "0:a:0", "-vn", "-af",
        "volumedetect,silencedetect=noise=-35dB:d=0.40", "-f", "null", "-"])
    def volume(name: str):
        match = re.search(rf"\\b{name}:\\s*(-?(?:[0-9.]+|inf))\\s*dB", log)
        if not match:
            return None
        try:
            val = float(match.group(1))
            return round(val, 2) if val not in (float("inf"), float("-inf")) else None
        except ValueError:
            return None

    silences = silence_intervals(log, duration)
    quiet_s = sum(max(0, x["end_s"]-x["start_s"]) for x in silences)
    return {
        "file_name": src.name, "sha256": checksum(src),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "probe": meta, "duration_s": round(duration, 3),
        "mean_volume_db": volume("mean_volume"),
        "max_volume_db": volume("max_volume"),
        "silence_detection_threshold_db": -35,
        "silence_intervals": silences,
        "approx_nonsilent_s": round(max(0, duration - quiet_s), 3),
        "warning": "Nonsilent audio can be MUSIC/FX/other speakers; this is NOT a speech/actor detector.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--report", help="Optional JSON path outside Git checkout")
    args = p.parse_args()
    try:
        src = private_file(args.input)
        result = preflight(src)
        serialized = json.dumps(result, indent=2, ensure_ascii=False)
        if args.report:
            output = Path(args.report).expanduser().resolve()
            if output == REPO or output.is_relative_to(REPO):
                raise ValueError("Private report must not be written into Git checkout.")
            if output.exists():
                raise FileExistsError(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            print(f"Saved private JSON report to {output}")
        else:
            print(serialized)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
