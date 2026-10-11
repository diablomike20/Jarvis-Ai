"""Jarvis AI visual branding regression tests.

Keep historic internal class names, file paths, Android packages, protocol
tokens, on-disk user data and crypto salt backward-compatible.
"""
import ast
from pathlib import Path

from core import identity as identity_mod


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_desktop_window_labels_show_jarvis_ai_not_brahma_evo():
    ui = read("ui.py")
    assert 'self.setWindowTitle("Jarvis AI")' in ui
    assert 'self._app.setApplicationDisplayName("Jarvis AI")' in ui
    assert '"BRAHMA EVO WORKSPACE"' not in ui
    assert 'Message Jarvis AI...' in ui
    assert 'Ask Jarvis AI anything...' in ui
    assert '"Brahma Evo is ready"' not in ui
    ast.parse(ui)


def test_desktop_supports_historic_assistant_prefix_in_existing_chat():
    ui = read("ui.py")
    assert 'low.startswith(("jarvis ai:", "brahma evo:"))' in ui
    assert 'raw.split(":", 1)[1].strip()' in ui


def test_dashboard_web_branding_keeps_encryption_salt():
    dashboard = read("dashboard/static/app.html")
    login = read("dashboard/static/login.html")
    assert "<title>Jarvis AI Remote</title>" in dashboard
    assert "<title>Jarvis AI Remote</title>" in login
    assert "BRAHMA EVO-DASHBOARD-v1" in dashboard  # persisted crypto compatibility
    assert "speaker === 'brahma evo'" in dashboard  # old conversation compatibility
    assert '<em>Jarvis AI</em>' in dashboard


def test_user_identity_migrates_old_default_but_preserves_custom(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(identity_mod, "get_base_dir", lambda: tmp_path)
    cfg = tmp_path / "config" / "identity.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({
        "assistant": {"name": "Brahma", "application_name": "Brahma Evo"},
    }), encoding="utf-8")
    old = identity_mod.IdentityService()
    assert old.get_assistant_name() == "Jarvis AI"
    assert old.get_application_name() == "Jarvis AI"
    cfg.write_text(json.dumps({
        "assistant": {"name": "Saját Asszisztens", "application_name": "Egyedi Név"}
    }), encoding="utf-8")
    custom = identity_mod.IdentityService()
    assert custom.get_assistant_name() == "Saját Asszisztens"
    assert custom.get_application_name() == "Egyedi Név"


def test_mobile_and_app_setup_branding():
    strings = read("brahma-connect-android/app/src/main/res/values/strings.xml")
    assert ">Jarvis AI Connect<" in strings
    assert "Brahma Evo Connect" not in strings
    assert "Jarvis AI" in read("brahma-connect-android/app/src/main/java/com/brahma/connect/ui/BrahmaConnectApp.kt")
    setup = read("installer/install_wizard.py")
    assert "Jarvis AI Setup" in setup
    assert "Brahma Evo Setup" not in setup


def test_main_system_persona_is_jarvis_ai():
    main = read("main.py")
    assert "You are Jarvis AI" in main
    assert "Brahma Evo:" not in main
    assert "Jarvis AI:" in main
    ast.parse(main)
