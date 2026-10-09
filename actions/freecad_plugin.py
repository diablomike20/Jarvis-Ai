"""Native JARVIS FreeCAD plugin: headless CAD through FreeCADCmd + FreeCAD API.

The FreeCAD binary is expected to be locally installed. No other FreeCAD GUI
window needs to open. This adapter exposes reviewed geometry commands to the
generic JARVIS source-plugin registry, not arbitrary Python execution.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core.user_paths import get_user_data_dir

_PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "integrations" / "sources" / "freecad"
_WORKER = _PLUGIN_ROOT / "freecad_worker.py"
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_PROJECT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_LIMIT_MM = 100000.0

def _field(tp, description, **kwargs):
    return {"type": tp, "description": description, **kwargs}


def _tool(description, properties, required):
    return {"description": description, "inputSchema": {
        "type": "object", "properties": properties,
        "required": required, "additionalProperties": False,
    }}


PROJECT = _field("string", "Project name (letters/digits/dashes/underscore).")
OBJECT = _field("string", "FreeCAD object name, letters/digits/underscore.")
POS = _field("array", "Position [x,y,z] in mm.", items={"type": "number"}, minItems=3, maxItems=3)
POS_NUMBER = _field("number", "Finite dimension in mm, 0.001–100000.", minimum=0.001, maximum=_LIMIT_MM)

CAD_TOOLS = {
    "list_projects": _tool("List local JARVIS FreeCAD project files.", {}, []),
    "new_project": _tool("Create a new, empty native .FCStd FreeCAD project.",
                         {"project": PROJECT, "title": _field("string", "Friendly project title.")}, ["project"]),
    "import_fcstd": _tool("Copy an existing .FCStd document into the private JARVIS workspace (never overwrite).",
        {"project": PROJECT, "source_path": _field("string", "Full path to an existing .FCStd file.")},
        ["project", "source_path"]),
    "inspect_project": _tool("Inspect real FreeCAD object names, types, shape volumes and bounding boxes.",
                             {"project": PROJECT}, ["project"]),
    "add_primitive": _tool("Create editable parametric Part box, cylinder, sphere, cone.",
        {"project": PROJECT, "name": OBJECT,
         "kind": _field("string", "Shape type.", enum=["box", "cylinder", "sphere", "cone"]),
         "length": POS_NUMBER, "width": POS_NUMBER, "height": POS_NUMBER,
         "radius": POS_NUMBER, "radius1": POS_NUMBER, "radius2": POS_NUMBER,
         "position": POS}, ["project", "name", "kind"]),
    "sketch_pad": _tool("Create a parametric PartDesign body with rectangular sketch and a pad/extrusion.",
        {"project": PROJECT, "name": OBJECT,
         "width": POS_NUMBER, "height": POS_NUMBER, "depth": POS_NUMBER,
         "position": POS}, ["project", "name", "width", "height", "depth"]),
    "boolean": _tool("Create a parametric boolean union, subtraction or intersection of two objects.",
        {"project": PROJECT, "name": OBJECT,
         "left": OBJECT, "right": OBJECT,
         "mode": _field("string", "Boolean operator.", enum=["fuse", "cut", "common"])},
        ["project", "name", "left", "right", "mode"]),
    "transform": _tool("Reposition an existing object in millimetres and rotate around Z in degrees.",
        {"project": PROJECT, "name": OBJECT,
         "position": POS, "z_angle_degrees": _field("number", "Rotation around Z axis in degrees.")},
        ["project", "name", "position"]),
    "remove_object": _tool("Remove an object from the FreeCAD document (may affect dependents).",
                           {"project": PROJECT, "name": OBJECT}, ["project", "name"]),
    "export": _tool("Export real CAD shapes to STEP, IGES, BREP, STL or OBJ in the JARVIS export folder.",
        {"project": PROJECT, "name": OBJECT,
         "format": _field("string", "Export format.", enum=["step", "stp", "iges", "igs", "brep", "stl", "obj"]),
         "objects": _field("array", "Optional selected object names.", items=OBJECT, maxItems=100),
         "overwrite": _field("boolean", "Allow replacing an existing export (false by default).")},
        ["project", "name", "format"]),
}


def find_freecad_cmd() -> str | None:
    """Find locally available FreeCADCmd, without downloading FreeCAD."""
    specified = os.environ.get("JARVIS_FREECAD_CMD", "").strip()
    if specified:
        resolved = Path(specified).expanduser()
        return str(resolved.resolve()) if resolved.is_file() else None
    for binary in ("FreeCADCmd.exe", "freecadcmd", "FreeCADCmd"):
        found = shutil.which(binary)
        if found and Path(found).is_file():
            return str(Path(found).resolve())
    if os.name == "nt":
        for root in (os.environ.get("ProgramW6432"),
                     os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
            if not root:
                continue
            base = Path(root)
            for candidate in sorted(base.glob("FreeCAD*/bin/FreeCADCmd.exe"), reverse=True):
                if candidate.is_file():
                    return str(candidate.resolve())
            for candidate in sorted(base.glob("FreeCAD*/FreeCADCmd.exe"), reverse=True):
                if candidate.is_file():
                    return str(candidate.resolve())
    return None


def _workspace() -> Path:
    path = get_user_data_dir() / "cad_studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _name(value: Any, *, project=False) -> str:
    if not isinstance(value, str):
        raise ValueError("A név szöveg kell legyen.")
    if not (_PROJECT_NAME if project else _NAME).fullmatch(value):
        raise ValueError("Csak betűvel kezdődő rövid nevek, számok, kötőjel és aláhúzás engedélyezettek.")
    return value


def _number(value: Any, key: str, *, positive=True) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"A(z) {key} mezőnek véges számnak kell lennie.")
    n = float(value)
    if positive and not 0.001 <= n <= _LIMIT_MM:
        raise ValueError(f"A(z) {key} méret 0,001 és 100000 mm között lehet.")
    if not positive and not -_LIMIT_MM <= n <= _LIMIT_MM:
        raise ValueError(f"A(z) {key} pozíció kívül esik a megengedett tartományon.")
    return n


def _validate(operation: str, args: dict) -> dict:
    if operation not in CAD_TOOLS:
        raise ValueError("Ismeretlen FreeCAD eszköz: " + str(operation))
    if not isinstance(args, dict):
        raise ValueError("A paramétereknek JSON-objektumnak kell lenniük.")
    schema = CAD_TOOLS[operation]["inputSchema"]
    props = schema["properties"]
    if set(args) - set(props):
        raise ValueError("Ismeretlen paraméter: " + ", ".join(sorted(set(args) - set(props))))
    if set(schema["required"]) - set(args):
        raise ValueError("Hiányzó paraméter: " + ", ".join(sorted(set(schema["required"]) - set(args))))
    values: dict[str, Any] = {}
    for key, value in args.items():
        spec = props[key]
        kind = spec["type"]
        if key == "project":
            values[key] = _name(value, project=True)
        elif key in ("name", "left", "right"):
            values[key] = _name(value)
        elif key == "title":
            if not isinstance(value, str) or not 1 <= len(value) <= 100:
                raise ValueError("A projektnév túl hosszú vagy üres.")
            values[key] = value
        elif key == "source_path":
            if not isinstance(value, str) or not 1 <= len(value) <= 1024:
                raise ValueError("Érvénytelen import-útvonal.")
            values[key] = value
        elif "enum" in spec:
            if not isinstance(value, str) or value not in spec["enum"]:
                raise ValueError(f"Nem támogatott {key}: {value!r}")
            values[key] = value
        elif key == "position":
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise ValueError("A position mező pontosan 3 koordinátát vár.")
            values[key] = [_number(v, key, positive=False) for v in value]
        elif key == "objects":
            if not isinstance(value, list) or len(value) > 100:
                raise ValueError("Legfeljebb 100 objektum exportálható.")
            values[key] = [_name(v) for v in value]
        elif kind == "number":
            values[key] = _number(value, key, positive=(key != "z_angle_degrees"))
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"A(z) {key} logikai érték.")
            values[key] = value
        else:
            raise ValueError(f"Ismeretlen paramétertípus: {key}")

    if operation == "add_primitive":
        required = {
            "box": ("length", "width", "height"),
            "cylinder": ("radius", "height"),
            "sphere": ("radius",),
            "cone": ("radius1", "radius2", "height"),
        }[values["kind"]]
        if not all(k in values for k in required):
            raise ValueError("Hiányzó forma-paraméterek: " + ", ".join(k for k in required if k not in values))
        if values["kind"] == "cone" and values["radius1"] <= 0 and values["radius2"] <= 0:
            raise ValueError("A kúpnál legalább egy sugár legyen pozitív.")
    return values


def _project_file(workspace: Path, project: str) -> Path:
    return workspace / (project + ".FCStd")


class FreeCADPluginAdapter:
    """The interface used by JARVIS' generic source-plugin registry."""

    def __init__(self, plugin_id: str, binary: str):
        self.plugin_id = plugin_id
        self.binary = str(Path(binary).resolve())
        self._closed = False
        self.process = self   # same liveness interface as MCP session

    def poll(self) -> int | None:
        return 1 if self._closed else None

    def close(self):
        self._closed = True

    def list_tools(self):
        return {
            name: {"name": name, "description": details["description"],
                   "inputSchema": details["inputSchema"]}
            for name, details in CAD_TOOLS.items()
        }

    def _invoke(self, job: dict, workspace: Path) -> dict:
        if not _WORKER.is_file():
            raise RuntimeError("A FreeCAD-motor JARVIS-integrációs scriptje hiányzik.")
        with tempfile.TemporaryDirectory(prefix="freecad-", dir=str(workspace)) as temp:
            request_path = Path(temp) / "request.json"
            result_path = Path(temp) / "result.json"
            request_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
            env = os.environ.copy()
            env["JARVIS_FREECAD_REQUEST"] = str(request_path)
            env["JARVIS_FREECAD_RESULT"] = str(result_path)
            try:
                proc = subprocess.run(
                    [self.binary, str(_WORKER)],
                    cwd=str(workspace), env=env, shell=False,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("A FreeCAD motor nem válaszolt 120 másodpercen belül.") from exc
            if not result_path.is_file():
                return {"isError": True, "structuredContent": {
                    "error": "A FreeCADCmd nem adott géppel olvasható választ.",
                    "exit_code": proc.returncode,
                    "stderr": proc.stderr[-1200:],
                }}
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                raise RuntimeError("A FreeCAD motor érvénytelen JSON-választ adott.") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("isError"), bool):
                raise RuntimeError("A FreeCAD motor válaszformátuma érvénytelen.")
            if proc.returncode != 0:
                payload = {"isError": True, "structuredContent": {
                    "error": "FreeCADCmd process hiba.", "exit_code": proc.returncode,
                    "details": payload.get("structuredContent"),
                }}
            return payload

    def call_tool(self, tool: str, arguments: dict) -> dict:
        if self._closed:
            raise RuntimeError("A FreeCAD adapter leállt.")
        values = _validate(tool, arguments)
        workspace = _workspace()
        if tool == "list_projects":
            names = sorted(x.stem for x in workspace.glob("*.FCStd"))
            return {"isError": False, "structuredContent": {"projects": names[:200]}}
        project_file = _project_file(workspace, values["project"])
        if tool == "import_fcstd":
            source = Path(values["source_path"]).expanduser().resolve()
            if source.suffix.lower() != ".fcstd" or not source.is_file():
                raise ValueError("Csak már létező .FCStd FreeCAD-dokumentum importálható.")
            if source.stat().st_size > 100 * 1024 * 1024:
                raise ValueError("Az import fájlja túl nagy (max. 100 MB).")
            if project_file.exists():
                raise ValueError("Már létezik ilyen nevű JARVIS CAD-projekt.")
            shutil.copy2(source, project_file)
            return {"isError": False, "structuredContent": {
                "imported": project_file.name, "path": str(project_file),
            }}
        if tool != "new_project" and not project_file.is_file():
            raise ValueError("Nincs ilyen FreeCAD-projekt: " + values["project"])
        if tool == "new_project" and project_file.exists():
            raise ValueError("Ilyen nevű FreeCAD-projekt már létezik.")
        job = {
            "operation": tool, "arguments": values,
            "project_file": str(project_file), "workspace": str(workspace),
        }
        return self._invoke(job, workspace)
