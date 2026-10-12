"""Offline tests for the optional Hungarian ASR draft; no Whisper model downloaded."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest import mock

MOD = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "local_transcribe_hu.py"
spec = importlib.util.spec_from_file_location("jarvis_local_transcribe", MOD)
asr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asr)


class LocalTranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "test.wav"
        self.source.write_bytes(b"synthetic-test-data")

    def tearDown(self):
        self.tmp.cleanup()

    def test_private_file_path(self):
        with self.assertRaises(ValueError):
            asr.private_path(str(asr.REPO / "test.wav"))

    def test_missing_input_fails(self):
        with self.assertRaises(FileNotFoundError):
            asr.transcribe(self.root / "missing.wav", self.root / "out")

    def test_model_outside_allowlist_fails(self):
        with self.assertRaises(ValueError):
            asr.transcribe(self.source, self.root / "out", model="arbitrary")

    def test_draft_flag_only_and_exact_file_hash(self):
        class FakeModel:
            def __init__(self, *args, **kwargs):
                pass
            def transcribe(self, *args, **kwargs):
                seg = SimpleNamespace(start=0.2, end=2.1,
                                      text=" Teszt mondat. ",
                                      avg_logprob=-0.1, no_speech_prob=0.01)
                return iter([seg]), SimpleNamespace(language_probability=0.97)
        fake_package = ModuleType("faster_whisper")
        fake_package.WhisperModel = FakeModel
        with mock.patch.dict(sys.modules, {"faster_whisper": fake_package}):
            report = asr.transcribe(self.source, self.root / "out")
        self.assertFalse(report["speaker_identity_verified"])
        self.assertFalse(report["transcript_verified"])
        self.assertEqual(report["segments"][0]["text"], "Teszt mondat.")
        self.assertTrue((self.root / "out" / "draft_segments.json").is_file())
        raw = json.loads((self.root / "out" / "draft_segments.json").read_text())
        self.assertEqual(raw["language_requested"], "hu")

    def test_preserve_existing_draft(self):
        out = self.root / "out"
        out.mkdir()
        with self.assertRaises(FileExistsError):
            asr.transcribe(self.source, out)


if __name__ == "__main__":
    unittest.main()
