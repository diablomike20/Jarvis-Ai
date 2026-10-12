"""Local tests for experimental film-style effect previews without FFmpeg model downloads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

MODULE = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "voice_style_variants.py"
spec = importlib.util.spec_from_file_location("jarvis_voice_variants", MODULE)
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)


def make_wave(path: Path, seconds: int = 2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setframerate(24000)
        w.setsampwidth(2)
        w.writeframes(b"\x00\x00" * seconds * 24000)


class VoiceStyleVariantsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic_voice.wav"
        make_wave(self.source)
        self.target = self.root / "effects"

    def tearDown(self):
        self.temp.cleanup()

    def test_private_repository_protected(self):
        with self.assertRaises(ValueError):
            voice.private_path(str(voice.REPO_ROOT / "private_reference.wav"))

    def test_three_variants_are_distinct(self):
        self.assertEqual(len(voice.PRESETS), 3)
        self.assertNotEqual(voice.PRESETS["natural"], voice.PRESETS["jarvis_subtle"])
        self.assertNotEqual(voice.PRESETS["jarvis_subtle"], voice.PRESETS["jarvis_comms"])

    def test_dry_run_never_creates_files(self):
        report = voice.process(self.source, self.target, dry_run=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(len(report["variants"]), 3)
        self.assertFalse(report["authentic_movie_filter"])

    def test_unknown_preset_is_rejected(self):
        with self.assertRaises(ValueError):
            voice.process(self.source, self.target, presets=["studio_magic"])

    def test_does_not_overwrite_existing_output_dir(self):
        self.target.mkdir()
        with self.assertRaises(FileExistsError):
            voice.process(self.source, self.target)

    def test_mock_audio_processing_manifest(self):
        def fake_ffmpeg(args, **kwargs):
            make_wave(Path(args[-1]))
            return mock.Mock(returncode=0, stderr="")
        with mock.patch.object(voice.shutil, "which", return_value="ffmpeg"), mock.patch.object(
            voice.subprocess, "run", side_effect=fake_ffmpeg
        ):
            report = voice.process(self.source, self.target)
        self.assertEqual(len(report["variants"]), 3)
        self.assertTrue(all(r["status"] == "generated_unreviewed"
                            for r in report["variants"]))
        self.assertTrue((self.target / "variant_manifest.json").is_file())
        persisted = json.loads((self.target / "variant_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(persisted["authentic_movie_filter"])


if __name__ == "__main__":
    unittest.main()
