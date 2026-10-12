"""Offline unit checks for the private corpus preparation utility.

Run: python -m unittest discover -s tests -p 'test_voice_corpus_prep.py'
No model downloads, GitHub API calls, media, or FFmpeg needed.
"""
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "prepare_corpus.py"
spec = importlib.util.spec_from_file_location("voice_corpus_prep", FILE)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class VoiceCorpusTests(unittest.TestCase):
    def test_rejects_workspace_inside_repository(self):
        with self.assertRaises(ValueError):
            prep.workspace_dir(str(prep.REPOSITORY_ROOT / "private_bad"))

    def test_safe_source_id(self):
        self.assertEqual(prep.safe_id("ironman3_hu"), "ironman3_hu")
        for value in ("../secret", "X", "foo/../../etc", "a b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    prep.safe_id(value)

    def test_template_starts_empty_and_is_private(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Path(root) / "voice-private"
            prep.template(ws, "ironman3_hu")
            template = ws / "metadata" / "ironman3_hu.segments.csv"
            with template.open(encoding="utf-8-sig", newline="") as inp:
                rows = list(csv.DictReader(inp))
            self.assertEqual(rows, [])
            with self.assertRaises(FileExistsError):
                prep.template(ws, "ironman3_hu")

    def test_refuses_unverified_actor_before_any_ffmpeg_call(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Path(root) / "voice-private"
            prep.template(ws, "ironman3_hu")
            csv_file = ws / "metadata" / "ironman3_hu.segments.csv"
            with csv_file.open("a", encoding="utf-8", newline="") as out:
                writer = csv.writer(out)
                writer.writerow(["10", "20", "Ellenőrizetlen tesztmondat", "neutral",
                                 "no", "yes", "not checked"])
            with self.assertRaisesRegex(ValueError, "actor_verified"):
                prep.cut(ws, "ironman3_hu", ws / "missing.wav", csv_file)
            self.assertFalse((ws / "metadata" / "ironman3_hu.manifest.jsonl").exists())

    def test_refuses_missing_rights_check(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Path(root) / "voice-private"
            prep.template(ws, "ironman3_hu")
            csv_file = ws / "metadata" / "ironman3_hu.segments.csv"
            with csv_file.open("a", encoding="utf-8", newline="") as out:
                csv.writer(out).writerow(["12", "21", "Teszt", "warning", "yes", "no", ""])
            with self.assertRaisesRegex(ValueError, "rights_checked"):
                prep.cut(ws, "ironman3_hu", ws / "missing.wav", csv_file)

    def test_rejects_invalid_time_interval(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Path(root) / "voice-private"
            prep.template(ws, "ironman3_hu")
            csv_file = ws / "metadata" / "ironman3_hu.segments.csv"
            with csv_file.open("a", encoding="utf-8", newline="") as out:
                csv.writer(out).writerow(["18", "11", "Teszt", "warning", "yes", "yes", ""])
            with self.assertRaisesRegex(ValueError, "1-30 sec"):
                prep.cut(ws, "ironman3_hu", ws / "missing.wav", csv_file)


if __name__ == "__main__":
    unittest.main()
