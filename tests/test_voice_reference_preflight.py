"""No-download, no-audio-upload unit checks for reference diagnostics."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

FILE = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "analyze_reference.py"
spec = importlib.util.spec_from_file_location("jarvis_reference_preflight", FILE)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


class ReferencePreflightTests(unittest.TestCase):
    def test_reject_private_audio_inside_public_repo(self):
        with self.assertRaises(ValueError):
            ref.private_file(str(ref.REPO / "tools" / "voice_corpus" / "README_HU.md"))

    def test_silence_intervals(self):
        log = """
[silencedetect] silence_start: 1.1
[silencedetect] silence_end: 2.6 | silence_duration: 1.5
[silencedetect] silence_start: 8.0
"""
        self.assertEqual(ref.silence_intervals(log, 10.0), [
            {"start_s": 1.1, "end_s": 2.6}, {"start_s": 8.0, "end_s": 10.0}
        ])

    def test_metadata_and_volume_parsing_are_not_voice_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / "dummy.raw"
            sample.write_bytes(b"not-a-real-audio-file-test-content")
            ffprobe = json.dumps({
                "format": {"duration": "11.0"},
                "streams": [{"codec_type": "audio", "channels": 1}]
            })
            logs = """
[Parsed_volumedetect_0] mean_volume: -23.2 dB
[Parsed_volumedetect_0] max_volume: -3.1 dB
[Parsed_silencedetect_1] silence_start: 3.0
[Parsed_silencedetect_1] silence_end: 4.0 | silence_duration: 1.0
"""
            with mock.patch.object(ref, "execute", side_effect=[(ffprobe, ""), ("", logs)]):
                result = ref.preflight(sample)
            self.assertEqual(result["mean_volume_db"], -23.2)
            self.assertEqual(result["max_volume_db"], -3.1)
            self.assertEqual(result["approx_nonsilent_s"], 10.0)
            self.assertIn("NOT a speech/actor detector", result["warning"])


if __name__ == "__main__":
    unittest.main()
