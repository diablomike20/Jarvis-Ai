"""Standalone local Windows Qt WebEngine test window for JARVIS Orb Lab.

Only opens the previously built experiments/jarvis-orb-web-demo/dist bundle.
Does not import JARVIS main.py, rewrite UI code, load any private samples,
expose a LAN endpoint, or automatically install anything.

Windows:
  cd experiments/jarvis-orb-web-demo
  npm install && npm run build
  python -m pip install PyQt6 PyQt6-WebEngine
  python tools/qt_orb_lab.py
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from qt_bridge_contract import (
    ALLOWED_STATES, STATUS_JS, make_js_command, normalize_audio, normalize_state
)

LOGGER = logging.getLogger("jarvis_orb_lab")


class LoopbackHandler(SimpleHTTPRequestHandler):
    """Serve only a fixed build directory on loopback, never repository roots."""

    def log_message(self, format_string, *args):
        LOGGER.info(format_string, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def open_bundle_server(build_directory: Path):
    """Return (server, thread) with a random localhost-only listening port."""
    directory = build_directory.resolve(strict=True)
    if not (directory / "index.html").is_file():
        raise FileNotFoundError(f"No production bundle at: {directory}")
    handler = partial(LoopbackHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, name="orb-lab-http", daemon=True)
    worker.start()
    return server, worker


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Private Qt WebEngine orb demo (local only)")
    default_dist = Path(__file__).resolve().parents[1] / "dist"
    parser.add_argument("--dist", type=Path, default=default_dist, help="Vite-built demo dist directory")
    args = parser.parse_args(argv)

    try:
        server, worker = open_bundle_server(args.dist)
    except (FileNotFoundError, OSError) as exc:
        parser.error(f"Build missing: {exc}. Run 'npm install' and 'npm run build'.")
    # Import Qt after validation. Never disable the Chromium sandbox or GPU flags.
    try:
        from PyQt6.QtCore import QTimer, QUrl
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QComboBox, QSlider
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except ImportError as exc:
        server.shutdown()
        server.server_close()
        raise SystemExit("Install PyQt6 and PyQt6-WebEngine in your local Windows Python environment.") from exc

    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("JARVIS AI — Isolated Qt Orb Lab (no production changes)")
    window.resize(1280, 880)
    layout = QVBoxLayout(window)
    row = QHBoxLayout()
    layout.addLayout(row)

    state_select = QComboBox()
    state_select.addItems(sorted(ALLOWED_STATES))
    state_select.setCurrentText("IDLE")
    row.addWidget(QLabel("JARVIS state:"))
    row.addWidget(state_select)

    audio_slider = QSlider(Qt.Orientation.Horizontal)
    audio_slider.setRange(0, 100)
    audio_slider.setValue(0)
    row.addWidget(QLabel("Simulated audio:"))
    row.addWidget(audio_slider)

    cycle_button = QPushButton("Test conversation cycle")
    row.addWidget(cycle_button)

    detail = QLabel("Starting private localhost-only browser ...")
    layout.addWidget(detail)
    view = QWebEngineView(window)
    layout.addWidget(view, 1)
    current_load = {"ok": False}
    metrics = {"state": "IDLE", "audio": 0}
    planned = []
    closed = {"value": False}

    def dispatch():
        if not current_load["ok"] or closed["value"]:
            return
        metrics["state"] = normalize_state(state_select.currentText())
        metrics["audio"] = normalize_audio(audio_slider.value() / 100)
        view.page().runJavaScript(make_js_command(metrics["state"], metrics["audio"]))

    def on_status(value):
        if closed["value"] or not value:
            return
        try:
            result = json.loads(value)
            detail.setText(
                "Orb browser: "
                f"state={result.get('state')}   UI RAF={result.get('fps_ui_raf')} "
                f"p95={result.get('p95_ui_frame_ms')}   "
                f"canvas={result.get('canvas_width')}×{result.get('canvas_height')}   "
                f"visible={result.get('visibility')}. "
                "(UI metrics ≠ renderer/GPU FPS)"
            )
        except (TypeError, ValueError, AttributeError):
            detail.setText("Orb browser: waiting for status telemetry")

    def check_status():
        if current_load["ok"] and not closed["value"]:
            view.page().runJavaScript(STATUS_JS, on_status)

    def on_loaded(ok):
        current_load["ok"] = bool(ok)
        if ok:
            dispatch()
            check_status()
        else:
            detail.setText("Failed to load localhost-only Vite bundle. Check local build.")

    def run_cycle():
        # QTimer-only automation; no actual audio recording or synthesis.
        for timer in planned:
            timer.stop()
            timer.deleteLater()
        planned.clear()

        for ms, state, volume in (
            (0, "LISTENING", 52), (2000, "THINKING", 0),
            (4000, "SPEAKING", 79), (6500, "SUCCESS", 0),
            (7800, "IDLE", 0),
        ):
            timer = QTimer(window)
            timer.setSingleShot(True)

            def step(next_state=state, next_volume=volume):
                if closed["value"]:
                    return
                state_select.setCurrentText(next_state)
                audio_slider.setValue(next_volume)
                dispatch()

            timer.timeout.connect(step)
            timer.start(ms)
            planned.append(timer)

    def cleanup():
        closed["value"] = True
        for timer in planned:
            timer.stop()
        server.shutdown()
        server.server_close()

    state_select.currentTextChanged.connect(lambda _: dispatch())
    audio_slider.valueChanged.connect(lambda _: dispatch())
    cycle_button.clicked.connect(run_cycle)
    view.loadFinished.connect(on_loaded)
    timer = QTimer(window)
    timer.timeout.connect(check_status)
    timer.start(1500)
    app.aboutToQuit.connect(cleanup)

    url = QUrl(f"http://127.0.0.1:{server.server_address[1]}/index.html")
    view.load(url)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
