"""Zero-dependency checks for the Hungarian JARVIS A/B benchmark tool.

Mocked inference creates synthetic silence, not an imitation of anyone's voice.
Does not load models, download anything, or send private references remotely.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import wave

FILE = Path(__file__).resolve().parents[1] / "tools" / "voice_corpus" / "tts_compare.py"
spec = importlib.util.spec_from_file_location("jarvis_tts_compare", FILE)
comp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comp)


def make_wav(path, seconds=5, sample_rate=24000):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(b"\0\0" * int(seconds * sample_rate))


class HungarianTTSABTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ref = self.root / "reference.wav"
        make_wav(self.ref)
        self.ref_text = self.root / "reference.txt"
        self.ref_text.write_text("Ellenőrzött magyar tesztátirat.", encoding="utf-8")
        self.model = self.root / "model_last_final.safetensors"
        self.model.write_bytes(b"synthetic-test-only")
        self.vocab = self.root / "vocab.txt"
        self.vocab.write_text("test", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def args(self, engines=None, dry=True):
        return SimpleNamespace(
            workspace=str(self.root / "private_output"),
            reference=str(self.ref),
            reference_transcript=str(self.ref_text),
            engines=engines or ["f5", "xtts"],
            f5_checkpoint=str(self.model),
            f5_vocab=str(self.vocab),
            device="cpu",
            allow_xtts_model_download=False,
            test_limit=2,
            rounds=1,
            dry_run=dry,
        )

    def test_private_workspace_rejects_git_location(self):
        with self.assertRaises(ValueError):
            comp.outside_git(comp.PROJECT_ROOT / "tools" / "voice_corpus")

    def test_wave_stats_duration(self):
        data = comp.wave_stats(self.ref)
        self.assertAlmostEqual(data["duration_s"], 5)
        self.assertEqual(data["sample_rate"], 24000)

    def test_reference_text_required_for_f5(self):
        args = self.args(["f5"])
        args.reference_transcript = None
        with self.assertRaisesRegex(ValueError, "reference-transcript"):
            comp.validate_inputs(args)

    def test_reference_duration_must_be_useful(self):
        make_wav(self.ref, seconds=1)
        with self.assertRaisesRegex(ValueError, "3-30 s"):
            comp.validate_inputs(self.args())

    def test_dry_run_no_output(self):
        args = self.args()
        self.assertEqual(comp.run_benchmark(args), 0)
        self.assertFalse((self.root / "private_output").exists())

    def test_mocked_evaluation_writes_local_wavs_and_metrics(self):
        args = self.args(dry=False)

        def fake_load(_args):
            def fake_synth(_reference, _ref_text, _generated_text, dest):
                make_wav(dest, seconds=1)
            return fake_synth

        with mock.patch.object(comp, "load_f5", side_effect=fake_load), mock.patch.object(
                comp, "load_xtts", side_effect=fake_load):
            self.assertEqual(comp.run_benchmark(args), 0)
        out_dir = self.root / "private_output" / "evaluation"
        eval_dirs = list(out_dir.glob("ab_*"))
        self.assertEqual(len(eval_dirs), 1)
        report = json.loads((eval_dirs[0] / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["results"]), 4)
        self.assertTrue(all(x["status"] == "generated_unreviewed"
                            for x in report["results"]))
        self.assertTrue(all(x["audio_sha256"] for x in report["results"]))

    def test_model_import_error_recorded_no_false_success(self):
        args = self.args(["f5"], dry=False)
        with mock.patch.object(comp, "load_f5", side_effect=ImportError("GPU missing")):
            self.assertEqual(comp.run_benchmark(args), 1)
        report_path = next((self.root / "private_output" / "evaluation").glob(
            "ab_*/benchmark.json"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["results"][0]["status"], "model_load_error")


if __name__ == "__main__":
    unittest.main()
