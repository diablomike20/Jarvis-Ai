"""Optional real FreeCADCmd smoke test.

Run locally on Windows after installing FreeCAD:
    python scripts/verify_freecad.py

Runs a NEW temporary project. Never edits a user's existing .FCStd files.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from actions.freecad_plugin import FreeCADPluginAdapter, find_freecad_cmd


def main():
    binary = find_freecad_cmd()
    if not binary:
        raise SystemExit(
            "FreeCADCmd nem található. A teszt valós FreeCAD-telepítést igényel. "
            "Állítsd be a JARVIS_FREECAD_CMD változót."
        )
    with tempfile.TemporaryDirectory(prefix="jarvis-cad-smoke-") as tmp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = tmp
        try:
            engine = FreeCADPluginAdapter("freecad", binary)
            checks = [
                ("new_project", {"project": "smoke", "title": "JARVIS FreeCAD smoke"}),
                ("add_primitive", {"project": "smoke", "kind": "box", "name": "Base",
                                   "length": 50, "width": 40, "height": 15}),
                ("add_primitive", {"project": "smoke", "kind": "cylinder", "name": "Hole",
                                   "radius": 8, "height": 15, "position": [25, 20, 0]}),
                ("boolean", {"project": "smoke", "mode": "cut",
                             "name": "DrilledPart", "left": "Base", "right": "Hole"}),
                ("sketch_pad", {"project": "smoke", "name": "TestPad",
                                "width": 30, "height": 10, "depth": 5}),
                ("inspect_project", {"project": "smoke"}),
                ("export", {"project": "smoke", "name": "drilled", "format": "step",
                             "objects": ["DrilledPart"]}),
                ("export", {"project": "smoke", "name": "drilled", "format": "stl",
                             "objects": ["DrilledPart"]}),
            ]
            for name, params in checks:
                result = engine.call_tool(name, params)
                if result.get("isError"):
                    raise RuntimeError(f"FAILED {name}: {result}")
                print(f"OK {name}: {str(result.get('structuredContent'))[:240]}")
            workspace = Path(tmp) / "BrahmaAI" / "cad_studio"
            for path in (
                workspace / "smoke.FCStd",
                workspace / "exports" / "drilled.step",
                workspace / "exports" / "drilled.stl",
            ):
                if not path.exists() or path.stat().st_size == 0:
                    raise AssertionError(f"Az elvárt FreeCAD fájl hiányzik: {path}")
            print("FreeCADCmd smoke: OK. Native FCStd, STEP és STL kész.")
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
