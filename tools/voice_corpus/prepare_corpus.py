#!/usr/bin/env python3
"""Prepare a PRIVATE, human-verified Hungarian JARVIS dialogue corpus.

Only the tooling lives in Git. Run this on media the user is authorized to
process; never commit the original media, extracted dialogue or transcripts.
Python 3.11+; requires ffmpeg and ffprobe on PATH.
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


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STYLES = {"neutral", "confirmation", "analytical", "warning", "urgent", "ironic"}


def workspace_dir(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if path == REPOSITORY_ROOT or path.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Private voice workspace MUST be outside the Git repository.")
    return path


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", value):
        raise ValueError("ID: 2-64 characters; lowercase a-z first, then a-z/0-9/_/-.")
    return value


def required_binary(program: str) -> str:
    path = shutil.which(program)
    if not path:
        raise RuntimeError(f"Missing {program}; install FFmpeg and add it to PATH.")
    return path


def run(argv: list[str], timeout: int = 180) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            check=False, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-1800:]}")
    return result.stdout


def probe_audio(path: Path) -> dict:
    data = run([required_binary("ffprobe"), "-v", "error",
                "-show_entries", "format=duration,format_name:"
                "stream=index,codec_type,codec_name,channels,channel_layout,sample_rate:stream_tags=language",
                "-of", "json", str(path)], timeout=90)
    return json.loads(data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def initialize(ws: Path) -> None:
    for folder in ("dialogue", "segments", "metadata", "evaluation"):
        (ws / folder).mkdir(parents=True, exist_ok=True)
    print(f"Private workspace ready: {ws}")


def register(ws: Path, identifier: str, source: Path) -> None:
    initialize(ws)
    item = {
        "id": safe_id(identifier),
        "file_path": str(source),
        "sha256": sha256_file(source),
        "probe": probe_audio(source),
        "registered_utc": datetime.now(timezone.utc).isoformat(),
        "rights_note": "User reports permission for private JARVIS voice research.",
        "actor_verified": False,
        "source_role": "UNVERIFIED until a human listens to the actual dialogue",
    }
    location = ws / "metadata" / f"{identifier}.source.json"
    if location.exists():
        raise FileExistsError(f"Source already registered: {location}")
    location.write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Registered: {location}")
    print("Audio streams:")
    for stream in item["probe"].get("streams", []):
        if stream.get("codec_type") == "audio":
            print(f"  stream={stream.get('index')} {stream.get('codec_name')}, "
                  f"{stream.get('channels')}ch, {stream.get('channel_layout', '?')}, "
                  f"lang={stream.get('tags', {}).get('language', '?')}")


def extract(ws: Path, identifier: str, source: Path, stream: int, mode: str) -> None:
    initialize(ws)
    safe_id(identifier)
    info = probe_audio(source)
    audio_streams = [s for s in info.get("streams", [])
                     if s.get("codec_type") == "audio"]
    if stream < 0 or stream >= len(audio_streams):
        raise ValueError(f"audio stream selector {stream} invalid; "
                         f"valid range 0..{len(audio_streams)-1}")
    selected = audio_streams[stream]
    if mode == "center" and int(selected.get("channels") or 0) < 3:
        raise ValueError("Center extraction requires multichannel audio; use mono.")
    output = ws / "dialogue" / f"{identifier}_{mode}.wav"
    cmd = [required_binary("ffmpeg"), "-hide_banner", "-loglevel", "error",
           "-nostdin", "-n", "-i", str(source), "-map", f"0:a:{stream}", "-vn"]
    if mode == "center":
        # FC is explicitly mapped; ffmpeg errors if input lacks this channel.
        # An FC channel may still contain music/effects; NEVER assume clean voice.
        cmd.extend(["-af", "pan=mono|c0=FC"])
    elif mode == "mono":
        cmd.extend(["-ac", "1"])
    elif mode != "preserve":
        raise ValueError(f"Unknown mode {mode}")
    cmd.extend(["-c:a", "pcm_s24le", "-ar", "48000", str(output)])
    run(cmd, timeout=2400)
    print(f"Extracted local working WAV: {output}")
    print("Human listening/actor verification is mandatory before cutting.")


def template(ws: Path, identifier: str) -> None:
    initialize(ws)
    safe_id(identifier)
    path = ws / "metadata" / f"{identifier}.segments.csv"
    if path.exists():
        raise FileExistsError(path)
    with path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=[
            "start", "end", "text", "style", "actor_verified", "rights_checked", "notes"])
        writer.writeheader()
    print(f"Created EMPTY template: {path}")
    print("start/end use seconds; verify actor, transcribe manually; yes/yes required.")


def cut(ws: Path, identifier: str, source: Path, csv_file: Path) -> None:
    initialize(ws)
    safe_id(identifier)
    if not csv_file.is_file():
        raise FileNotFoundError(csv_file)
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("No verified segments supplied.")
    manifest = ws / "metadata" / f"{identifier}.manifest.jsonl"
    if manifest.exists():
        raise FileExistsError("Manifest already exists. Review it; avoid duplicate cuts.")
    prepared: list[tuple[Path, list[str], dict]] = []
    for idx, row in enumerate(rows, start=1):
        try:
            a = float(row["start"])
            b = float(row["end"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Row {idx}: invalid start/end") from exc
        if not (a >= 0 and b > a and 1 <= b-a <= 30):
            raise ValueError(f"Row {idx}: expected a 1-30 sec interval")
        if (row.get("actor_verified") or "").strip().lower() != "yes":
            raise ValueError(f"Row {idx}: actor_verified must be yes (human check)")
        if (row.get("rights_checked") or "").strip().lower() != "yes":
            raise ValueError(f"Row {idx}: rights_checked must be yes")
        text = (row.get("text") or "").strip()
        if not text:
            raise ValueError(f"Row {idx}: verified Hungarian transcript required")
        style = (row.get("style") or "neutral").strip().lower() or "neutral"
        if style not in STYLES:
            raise ValueError(f"Row {idx}: unknown style {style!r}")
        destination = ws / "segments" / f"{identifier}_{idx:04d}_{style}.wav"
        if destination.exists():
            raise FileExistsError(destination)
        cmd = [required_binary("ffmpeg"), "-hide_banner", "-loglevel", "error",
               "-nostdin", "-n", "-ss", f"{a:.3f}", "-i", str(source),
               "-t", f"{b-a:.3f}", "-vn", "-ar", "24000",
               "-ac", "1", "-c:a", "pcm_s16le", str(destination)]
        record = {
            "segment_id": f"{identifier}_{idx:04d}", "source_id": identifier,
            "path": str(destination), "source_path": str(source),
            "start_s": a, "end_s": b, "text": text, "style": style,
            "actor_verified": True, "rights_checked": True,
            "quality_status": "pending_listening_review",
            "notes": (row.get("notes") or "").strip()
        }
        prepared.append((destination, cmd, record))
    # Validate every row before executing any cut.
    records = []
    try:
        for output, cmd, record in prepared:
            run(cmd, timeout=180)
            record["sha256"] = sha256_file(output)
            records.append(record)
    except Exception:
        for output, _, _ in prepared:
            output.unlink(missing_ok=True)
        raise
    manifest.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records),
        encoding="utf-8")
    print(f"Prepared {len(records)} segments and manifest: {manifest}")
    print("Manual quality review is STILL required before model training.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True,
                        help="Private folder OUTSIDE repository, e.g. %%LOCALAPPDATA%%/JarvisAI/voice_private")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    p = subs.add_parser("register")
    p.add_argument("--id", required=True)
    p.add_argument("--input", type=Path, required=True)
    p = subs.add_parser("extract")
    p.add_argument("--id", required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--audio-stream", type=int, default=0,
                   help="0-based ordinal of audio streams, NOT global stream index")
    p.add_argument("--mode", choices=["center", "mono", "preserve"], default="center")
    p = subs.add_parser("template")
    p.add_argument("--id", required=True)
    p = subs.add_parser("cut")
    p.add_argument("--id", required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    try:
        ws = workspace_dir(args.workspace)
        if args.command == "init":
            initialize(ws)
        elif args.command == "register":
            register(ws, args.id, args.input.expanduser().resolve())
        elif args.command == "extract":
            extract(ws, args.id, args.input.expanduser().resolve(),
                    args.audio_stream, args.mode)
        elif args.command == "template":
            template(ws, args.id)
        elif args.command == "cut":
            cut(ws, args.id, args.input.expanduser().resolve(), args.csv.expanduser().resolve())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
