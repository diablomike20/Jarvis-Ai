"""PyInstaller startup diagnostics enabled only for explicit CI smoke run.

The report stays on the CI runner, never reads user data and is never bundled
with a voice sample. Normal JARVIS launches are left unchanged.
"""
from __future__ import annotations

import faulthandler
import os
import sys
import traceback

if "--smoke-imports" in sys.argv and os.environ.get("JARVIS_STARTUP_SMOKE_REPORT"):
    try:
        path = os.environ["JARVIS_STARTUP_SMOKE_REPORT"]
        _jarvis_smoke_stream = open(path, "w", encoding="utf-8", buffering=1)
        _jarvis_smoke_stream.write("frozen smoke: runtime hook entered\n")
        sys.stderr = _jarvis_smoke_stream
        sys.stdout = _jarvis_smoke_stream
        faulthandler.enable(file=_jarvis_smoke_stream, all_threads=True)
        faulthandler.dump_traceback_later(35, repeat=False, file=_jarvis_smoke_stream)

        def _jarvis_smoke_excepthook(exc_type, exc, tb):
            _jarvis_smoke_stream.write("frozen smoke: unhandled Python exception\n")
            traceback.print_exception(exc_type, exc, tb, file=_jarvis_smoke_stream)
            _jarvis_smoke_stream.flush()

        sys.excepthook = _jarvis_smoke_excepthook
    except OSError:
        pass
