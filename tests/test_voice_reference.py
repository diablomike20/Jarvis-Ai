"""Isolated tests: only synthetic audio; do not invoke real ffmpeg, torch, XTTS."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from actions import voice_reference


def _write_wav(path: Path, seconds: float = 5.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * int(seconds * 24000))


@pytest.fixture
def private_dir(tmp_path, monkeypatch):
    home = tmp_path / "private_home"
    monkeypatch.setattr(voice_reference, "get_user_data_dir", lambda: home)
    return home


def _simulate_ffmpeg(monkeypatch, *, seconds=5, status=0):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if status == 0:
            _write_wav(Path(command[-1]), seconds)
        return SimpleNamespace(returncode=status)

    monkeypatch.setattr(voice_reference.shutil, "which", lambda _: "fake_ffmpeg")
    monkeypatch.setattr(voice_reference.subprocess, "run", run)
    return calls


def test_converts_local_mp3_into_private_pcm_wav(private_dir, tmp_path, monkeypatch):
    source = tmp_path / "authorized source.mp3"
    source.write_bytes(b"mock mp3; no decoding is performed")
    calls = _simulate_ffmpeg(monkeypatch)
    result = voice_reference.prepare_reference(source, start_seconds=12)
    assert result == private_dir / "voices" / "jarvis_hu_authorized.wav"
    assert voice_reference._check_pcm_clip(result)
    assert source.read_bytes().startswith(b"mock mp3")
    command, options = calls[0]
    assert command[0] == "fake_ffmpeg"
    assert command[command.index("-ss") + 1] == "12"
    assert command[command.index("-t") + 1] == "25"
    assert options["shell"] is False
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is subprocess.DEVNULL
    assert options["stderr"] is subprocess.DEVNULL
    assert not list(result.parent.glob(".jarvis_reference_*"))


def test_conversion_error_preserves_existing_reference(private_dir, tmp_path, monkeypatch):
    old = voice_reference.target_reference_path()
    _write_wav(old, 4)
    before = old.read_bytes()
    source = tmp_path / "new_voice.wav"
    _write_wav(source)
    _simulate_ffmpeg(monkeypatch, status=1)
    with pytest.raises(voice_reference.ReferencePreparationError):
        voice_reference.prepare_reference(source)
    assert old.read_bytes() == before
    assert not list(old.parent.glob(".jarvis_reference_*"))


def test_invalid_short_clip_never_overwrites_existing_reference(private_dir, tmp_path, monkeypatch):
    old = voice_reference.target_reference_path()
    _write_wav(old)
    original = old.read_bytes()
    source = tmp_path / "very_short.wav"
    _write_wav(source, 1)
    _simulate_ffmpeg(monkeypatch, seconds=1)
    with pytest.raises(voice_reference.ReferencePreparationError):
        voice_reference.prepare_reference(source)
    assert old.read_bytes() == original


def test_rejects_invalid_extension_without_starting_ffmpeg(private_dir, tmp_path, monkeypatch):
    data = tmp_path / "private.txt"
    data.write_bytes(b"abc")
    def no_exec(*args, **kwargs):
        raise AssertionError("subprocess must not run")
    monkeypatch.setattr(voice_reference.subprocess, "run", no_exec)
    with pytest.raises(voice_reference.ReferencePreparationError):
        voice_reference.prepare_reference(data)


def test_rejects_bad_start_time(private_dir, tmp_path, monkeypatch):
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"some content")
    for value in (-1, 3601, 10.5, True):
        with pytest.raises(voice_reference.ReferencePreparationError):
            voice_reference.prepare_reference(path, start_seconds=value)


def test_no_ffmpeg_reports_necessary_local_dependency(private_dir, tmp_path, monkeypatch):
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"some content")
    monkeypatch.setattr(voice_reference.shutil, "which", lambda name: None)
    with pytest.raises(voice_reference.ReferencePreparationError, match="FFmpeg"):
        voice_reference.prepare_reference(path)


def test_same_input_as_output_not_modified(private_dir, monkeypatch):
    path = voice_reference.target_reference_path()
    _write_wav(path)
    previous = path.read_bytes()
    _simulate_ffmpeg(monkeypatch)
    with pytest.raises(voice_reference.ReferencePreparationError):
        voice_reference.prepare_reference(path)
    assert path.read_bytes() == previous


def test_windows_timeout_does_not_leave_partial_private_audio(private_dir, tmp_path, monkeypatch):
    source = tmp_path / "audio.mp3"
    source.write_bytes(b"mock")
    monkeypatch.setattr(voice_reference.shutil, "which", lambda name: "fake_ffmpeg")

    def time_out(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial private output")
        raise subprocess.TimeoutExpired(command, 90)

    monkeypatch.setattr(voice_reference.subprocess, "run", time_out)
    with pytest.raises(voice_reference.ReferencePreparationError):
        voice_reference.prepare_reference(source)
    assert not voice_reference.target_reference_path().exists()
    assert not list((private_dir / "voices").glob(".jarvis_reference_*"))


def test_actual_gui_has_local_consent_and_background_worker():
    import ast
    ui = Path(__file__).resolve().parents[1] / "ui.py"
    code = ui.read_text(encoding="utf-8")
    tree = ast.parse(code)
    classes = {c.name: c for c in tree.body if isinstance(c, ast.ClassDef)}
    assert "HungarianVoiceImportWorker" in classes
    methods = {
        fn.name for fn in classes["SystemConnectivityPage"].body
        if isinstance(fn, ast.FunctionDef)
    }
    assert "_import_hu_voice_reference" in methods
    assert "_on_hu_voice_import_completed" in methods
    assert "Fájl" not in code or "QFileDialog.getOpenFileName" in code
    assert "QMessageBox.question" in code
