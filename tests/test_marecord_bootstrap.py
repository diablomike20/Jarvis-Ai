"""Offline tests for MaRecord reference bootstrap. Never use a real person's voice."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "bootstrap_marecord.py"
spec = importlib.util.spec_from_file_location("jarvis_marecord_bootstrap", SCRIPT)
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class MaRecordBootstrapTests(unittest.TestCase):
    def test_silence_intervals_from_ffmpeg(self):
        log = """
[silencedetect @ 1] silence_start: 0.5
[silencedetect @ 1] silence_end: 1.4 | silence_duration: 0.9
[silencedetect @ 1] silence_start: 18.0
"""
        self.assertEqual(audio.parse_silences(log, 20), [(0.5, 1.4), (18.0, 20)])

    def test_candidate_generation_only_suggests_unverified_windows(self):
        self.assertEqual(
            audio.propose_candidates(25, [(0, 1), (13, 14)], min_seconds=4,
                                     max_seconds=12, max_clips=3),
            [(1, 13), (14, 25)]
        )

    def test_long_continuous_signal_split_without_voice_claim(self):
        segments = audio.propose_candidates(39, [], max_seconds=12, max_clips=8)
        self.assertEqual(segments, [(0.0, 12.0), (12.0, 24.0), (24.0, 36.0)])
        self.assertTrue(all(end-start <= 12 for start, end in segments))

    def test_private_path_restriction(self):
        with self.assertRaises(ValueError):
            audio.protect_private_dir(str(audio.REPO / "assets" / "voice"))

    def test_source_nonexistent_fails_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                audio.analyze(Path(temp) / "missing.mp3", Path(temp) / "output")

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "marecord.mp3"
            original.write_bytes(b"test-not-mp3")
            digest = audio.sha256_file(original)
            (root / "private" / ("marecord_" + digest[:12])).mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                audio.analyze(original, root / "private")
