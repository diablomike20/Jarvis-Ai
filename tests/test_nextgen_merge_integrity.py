"""Guard against losing JARVIS features while merging real Claude support."""
import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_DELIVERY_HUD_BLOB = "81eca8399c0e92206ac79b88d8e62dbdad3a3a0c"


class NextgenMergeIntegrity(unittest.TestCase):
    def test_original_delivery_hud_is_unchanged(self):
        content = (ROOT / "assets/web_background/index.html").read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        self.assertEqual(git_blob, APPROVED_DELIVERY_HUD_BLOB)

    def test_all_critical_delivery_features_and_claude_runtime_present(self):
        names = [
            "actions/creative_studio.py", "actions/freecad_plugin.py",
            "actions/jarvis_voice.py", "actions/local_stt.py",
            "actions/source_cli_adapter.py", "core/claude_runtime.py",
            "core/claude_permission_broker.py", "core/brahma_mcp_stdio.py",
            "core/ai_startup.py", "installer/prepare_claude_runtime.ps1",
            "installer/BrahmaJARVIS_Claude.iss",
        ]
        for name in names:
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file(), name)

    def test_ui_and_live_agent_wiring_retained(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("class ClaudeEventRouter(QObject)", main)
        self.assertIn("register_claude_callbacks", main)
        self.assertIn("_approve_tool", main)
        self.assertIn("run_developer_mode_request", main)
        self.assertIn("_start_standalone_microphone", main)

    def test_free_model_failover_has_bounded_count(self):
        code = (ROOT / "or_client.py").read_text(encoding="utf-8")
        self.assertRegex(code, r"(?m)^MAX_FALLBACK_MODELS\s*=\s*[1-9]\d*")
        self.assertIn("if tried >= MAX_FALLBACK_MODELS:", code)

    def test_source_build_is_pinned_to_isolated_master_descendant(self):
        script = (ROOT / "installer/prepare_claude_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn("feature/jarvis-nextgen-working-runtime-20261011", script)
        self.assertIn("checkout --detach $ClaudeCommit", script)
        self.assertIn("build-safety.test.mjs", script)
        self.assertIn("brahma-source-provenance.json", script)

    def test_packager_requires_claude_in_full_build(self):
        script = (ROOT / "installer/BrahmaEvo.spec").read_text(encoding="utf-8")
        self.assertIn("BRAHMA_REQUIRE_CLAUDE_BUNDLE", script)
        self.assertIn("BrahmaMcp", script)


if __name__ == "__main__":
    unittest.main()
