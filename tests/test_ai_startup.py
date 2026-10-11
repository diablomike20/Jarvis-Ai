"""Regression tests for a silent OpenRouter-only JARVIS installation.

The original UI required a Gemini key even when OpenRouter was configured,
and BrahmaLive.run() unconditionally connected to Gemini before starting
microphone capture. These cases MUST remain independently bootable.
"""
import unittest

from core.ai_startup import choose_startup_backend, has_ai_credentials


class TestAIStartup(unittest.TestCase):
    def test_openrouter_key_alone_is_ready(self):
        self.assertTrue(has_ai_credentials({"gemini_api_key": "", "openrouter_api_key": "sk-or-test"}))
        self.assertEqual(choose_startup_backend(
            {"default_ai_provider": "OpenRouter"},
            {"openrouter_api_key": "sk-or-test", "gemini_api_key": ""},
        ), "OpenRouter")

    def test_openrouter_recovers_old_gemini_default_without_key(self):
        self.assertEqual(choose_startup_backend(
            {},
            {"gemini_api_key": "", "openrouter_api_key": "sk-or-test"},
        ), "OpenRouter")

    def test_existing_gemini_install_still_works(self):
        self.assertEqual(choose_startup_backend(
            {"default_ai_provider": "Google Gemini"},
            {"gemini_api_key": "g-test", "openrouter_api_key": ""},
        ), "Gemini")

    def test_user_selection_respected_when_both_keys_exist(self):
        keys = {"gemini_api_key": "g-test", "openrouter_api_key": "sk-or-test"}
        self.assertEqual(choose_startup_backend({"default_ai_provider": "OpenRouter"}, keys), "OpenRouter")
        self.assertEqual(choose_startup_backend({"default_ai_provider": "Gemini"}, keys), "Gemini")

    def test_local_starts_without_cloud_credentials(self):
        self.assertEqual(choose_startup_backend({"default_ai_provider": "Local"}, {}), "Local")
        self.assertEqual(choose_startup_backend({"offline_mode_enabled": True}, {}), "Local")

    def test_no_key_is_explicit_unconfigured_not_silent(self):
        self.assertFalse(has_ai_credentials({}))
        self.assertEqual(choose_startup_backend({}, {}), "Unconfigured")

    def test_whitespace_keys_do_not_count(self):
        self.assertFalse(has_ai_credentials({"gemini_api_key": "  ", "openrouter_api_key": "\t"}))
        self.assertEqual(choose_startup_backend({}, {"gemini_api_key": "  "}), "Unconfigured")


if __name__ == "__main__":
    unittest.main()
