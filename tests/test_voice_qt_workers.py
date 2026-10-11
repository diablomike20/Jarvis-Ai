"""Exercise real PyQt6 QObject signal delivery for GUI voice workers.

The source class is extracted from the actual ui.py AST to avoid importing
whole JARVIS GUI/Windows external dependencies. No microphone, FFmpeg,
Coqui model, private sample or external network.
"""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path

import pytest


def test_real_qt_signal_cross_thread_with_daemon_voice_worker():
    qt = pytest.importorskip("PyQt6.QtCore")
    source = (Path(__file__).resolve().parents[1] / "ui.py").read_text(encoding="utf-8")
    node = next(
        item for item in ast.parse(source).body
        if isinstance(item, ast.ClassDef) and item.name == "_DaemonVoiceWorker"
    )
    globals_for_test = {
        "QObject": qt.QObject,
        "pyqtSignal": qt.pyqtSignal,
        "threading": threading,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<real-qt-worker>", "exec"),
         globals_for_test)
    Base = globals_for_test["_DaemonVoiceWorker"]

    class SyntheticWorker(Base):
        def run(self):
            time.sleep(0.04)

    app = qt.QCoreApplication.instance() or qt.QCoreApplication([])
    delivered = []
    worker = SyntheticWorker()
    worker.finished.connect(lambda: delivered.append(threading.current_thread() is threading.main_thread()))
    worker.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and not delivered:
        app.processEvents()
        time.sleep(0.01)

    assert delivered == [True], "Signal must be delivered to GUI thread"
    assert not worker.isRunning()
