"""Unit tests for Qt bridge without PyQt imports, browser or actual audio."""
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
from qt_bridge_contract import (  # noqa: E402
    ALLOWED_STATES, STATUS_JS, make_js_command, normalize_audio, normalize_state
)


class QtBridgeContractTests(unittest.TestCase):
    def test_all_states_are_supported(self):
        for state in ALLOWED_STATES:
            self.assertEqual(normalize_state(state), state)

    def test_aliases_and_unknown_fall_back(self):
        self.assertEqual(normalize_state(" responding "), "SPEAKING")
        self.assertEqual(normalize_state("WAKE"), "LISTENING")
        self.assertEqual(normalize_state("none"), "IDLE")
        self.assertEqual(normalize_state(None), "IDLE")

    def test_audio_clamped_and_nonfinite(self):
        for value, expected in [(-5, 0), (0.5, 0.5), (3, 1), ("bad", 0), (None, 0),
                                (float("nan"), 0), (float("inf"), 0)]:
            self.assertEqual(normalize_audio(value), expected)

    def test_js_escaping_never_interpolates_unknown_input(self):
        attacker = "SPEAKING');window.hacked=true;//"
        command = make_js_command(attacker, 0.7)
        self.assertNotIn("hacked", command)
        self.assertIn(json.dumps("IDLE"), command)
        self.assertIn("0.7000", command)

    def test_no_network_or_file_access_in_contract(self):
        self.assertNotIn("fetch(", STATUS_JS)
        self.assertNotIn("XMLHttpRequest", STATUS_JS)
        self.assertNotIn("eval(", make_js_command("LISTENING", 0.5))

    def test_status_only_reads_demo_selectors(self):
        self.assertIn("current-state", STATUS_JS)
        self.assertIn("fps_ui_raf", STATUS_JS)
        self.assertIn("canvas_width", STATUS_JS)


if __name__ == "__main__":
    unittest.main()
