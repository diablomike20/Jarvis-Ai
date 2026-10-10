"""Regression guards for the COMPLETE JARVIS installed Windows application.

No microphone access, Gemini key, cloud inference or private voice audio in CI.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _method(source: str, class_name: str, method_name: str) -> str:
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    func = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == method_name)
    return ast.get_source_segment(source, func)


def test_gemini_live_original_microphone_and_key_fail_closed():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from google import genai" in main
    assert "client.aio.live.connect(model=LIVE_MODEL" in main
    assert "tg.create_task(self._listen_audio())" in main
    assert "tg.create_task(self._receive_audio())" in main
    assert "tg.create_task(self._play_audio())" in main
    mic = _method(main, "BrahmaLive", "_listen_audio")
    assert "sd.InputStream(" in mic
    assert "self.out_queue.put_nowait" in mic
    run = _method(main, "BrahmaLive", "run")
    assert "Gemini Live nem indul" in run
    assert 'self.ui.set_state("IDLE")' in run


def test_custom_voice_used_for_gemini_turns_and_announcements():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    recv = _method(main, "BrahmaLive", "_receive_audio")
    speak = _method(main, "BrahmaLive", "speak")
    assert "turn_local_voice = None" in recv
    assert 'voice_status["enabled"] and voice_status["can_enable"]' in recv
    assert "buffered_gemini_pcm" in recv
    assert "speak_authorized_hungarian(utterance)" in recv
    assert "fallback_pcm" in recv
    assert "speak_authorized_hungarian(text)" in speak
    assert "_speak_edge_native(text)" in speak


def test_offline_real_microphone_test_wired_into_javascript_free_qt_ui():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    worker = _method(ui, "JarvisMicrophoneTestWorker", "run")
    assert "sd.InputStream(" in worker
    assert "stream.read(1024)" in worker
    assert "self.completed.emit(*result)" in worker
    assert "Mikrofon próba (3 s)" in ui
    assert "self._mic_test_btn.clicked.connect(self._start_jarvis_mic_test)" in ui


def test_authorized_hungarian_model_and_original_background_preserved():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    assert "F5-TTS Hungarian" in ui
    assert "XTTS-v2" in ui
    assert "jarvis_f5_reference_text" in ui
    assert "jarvis_orb_enabled" not in ui
    assert (ROOT / "assets" / "web_background" / "index.html").exists()


def test_user_supplied_jARVIS_ico_is_real_and_used_in_exe_and_setup():
    icon = (ROOT / "assets" / "JARVIS_AI_Logo.ico").read_bytes()
    assert icon[:6] == b"\x00\x00\x01\x00\x04\x00"
    assert len(icon) > 2048
    spec = (ROOT / "installer" / "BrahmaEvo.spec").read_text("utf-8")
    setup = (ROOT / "installer" / "JARVIS_AI_Windows.iss").read_text("utf-8")
    assert "icon=os.path.join(cwd, 'assets/JARVIS_AI_Logo.ico')" in spec
    assert "SetupIconFile=..\\assets\\JARVIS_AI_Logo.ico" in setup
