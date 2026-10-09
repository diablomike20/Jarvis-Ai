"""FreeCAD's real Python API worker, executed by FreeCADCmd in headless mode.

This file is shipped as part of the JARVIS source module. It is NOT evaluated
from the AI prompt: every supported operation is explicitly implemented here.

The parent adapter validates all inputs and asks for HUD confirmation on writes.
Files are confined to the selected local CAD project within Jarvis' data dir.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import FreeCAD as App
import Part


def _shape_information(obj):
    row = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
    }
    if hasattr(obj, "Shape"):
        shape = obj.Shape
        if not shape.isNull():
            row["volume_mm3"] = round(shape.Volume, 6)
            row["area_mm2"] = round(shape.Area, 6)
            row["solid_count"] = len(shape.Solids)
            bbox = shape.BoundBox
            row["bounds_mm"] = {
                "x": round(bbox.XLength, 5),
                "y": round(bbox.YLength, 5),
                "z": round(bbox.ZLength, 5),
            }
    if hasattr(obj, "Placement"):
        p = obj.Placement.Base
        row["position_mm"] = [round(p.x, 5), round(p.y, 5), round(p.z, 5)]
    return row


def _open_project(path):
    if not path.is_file():
        raise ValueError("A FreeCAD-projekt még nem létezik: " + path.name)
    return App.openDocument(str(path))


def _new_project(path, options):
    if path.exists():
        raise ValueError("Ez a projekt már létezik: " + path.name)
    doc = App.newDocument("JarvisCAD")
    doc.Label = str(options.get("title") or path.stem)[:100]
    doc.recompute()
    doc.saveAs(str(path))
    return {"project": path.name, "objects": 0}


def _add_primitive(doc, args):
    kind = args["kind"]
    types = {
        "box": "Part::Box",
        "cylinder": "Part::Cylinder",
        "sphere": "Part::Sphere",
        "cone": "Part::Cone",
    }
    obj = doc.addObject(types[kind], args["name"])
    obj.Label = args["name"]
    if kind == "box":
        obj.Length, obj.Width, obj.Height = (
            args["length"], args["width"], args["height"]
        )
    elif kind == "cylinder":
        obj.Radius, obj.Height = args["radius"], args["height"]
    elif kind == "sphere":
        obj.Radius = args["radius"]
    elif kind == "cone":
        obj.Radius1, obj.Radius2, obj.Height = (
            args["radius1"], args["radius2"], args["height"]
        )
    xyz = args.get("position", [0, 0, 0])
    obj.Placement.Base = App.Vector(*xyz)
    return obj


def _sketch_pad(doc, args):
    # A genuinely editable parametric PartDesign Pad, with an underlying sketch.
    import Sketcher  # noqa: F401
    body = doc.addObject("PartDesign::Body", args["name"])
    body.Label = args["name"]
    sketch = body.newObject("Sketcher::SketchObject", args["name"] + "_Sketch")
    w, h = args["width"], args["height"]
    corners = [
        App.Vector(0, 0, 0), App.Vector(w, 0, 0),
        App.Vector(w, h, 0), App.Vector(0, h, 0),
    ]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(corners[i], corners[(i + 1) % 4]), False)
    pad = body.newObject("PartDesign::Pad", args["name"] + "_Pad")
    pad.Profile = sketch
    pad.Length = args["depth"]
    body.Placement.Base = App.Vector(*args.get("position", [0, 0, 0]))
    return body


def _combine(doc, args):
    type_name = {
        "fuse": "Part::Fuse",
        "cut": "Part::Cut",
        "common": "Part::Common",
    }[args["mode"]]
    left = doc.getObject(args["left"])
    right = doc.getObject(args["right"])
    if left is None or right is None:
        raise ValueError("A két megadott 3D-objektumnak léteznie kell.")
    if left.Name == right.Name:
        raise ValueError("Egy objektum nem kombinálható önmagával.")
    obj = doc.addObject(type_name, args["name"])
    obj.Base, obj.Tool = left, right
    return obj


def _transform(doc, args):
    obj = doc.getObject(args["name"])
    if obj is None or not hasattr(obj, "Placement"):
        raise ValueError("Nem létező vagy nem transzformálható 3D-objektum.")
    obj.Placement = App.Placement(
        App.Vector(*args["position"]),
        App.Rotation(App.Vector(0, 0, 1), args.get("z_angle_degrees", 0)),
    )
    return obj


def _export(doc, root, args):
    extension = args["format"]
    path = root / "exports" / (args["name"] + "." + extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not args.get("overwrite", False):
        raise ValueError("A kimeneti fájl már létezik. Adj meg más nevet vagy overwrite=true értéket.")
    requested = args.get("objects") or []
    if requested:
        objs = [doc.getObject(name) for name in requested]
        if any(obj is None for obj in objs):
            raise ValueError("Nem létező export-objektum neve.")
    else:
        # Prefer terminal solids in boolean chains; skip body children where
        # the parent body's Shape is already exported.
        candidate_objs = [obj for obj in doc.Objects if hasattr(obj, "Shape")]
        linked_children = set()
        for obj in candidate_objs:
            if obj.TypeId in ("PartDesign::Body", "Part::Fuse", "Part::Cut", "Part::Common"):
                for child in getattr(obj, "OutList", []):
                    linked_children.add(child.Name)
        objs = [obj for obj in candidate_objs if obj.Name not in linked_children]
    objs = [obj for obj in objs if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    if not objs:
        raise ValueError("Nincs exportálható 3D-geometria a projektben.")
    if extension in ("step", "stp", "iges", "igs", "brep"):
        Part.export(objs, str(path))
    elif extension in ("stl", "obj"):
        import Mesh
        Mesh.export(objs, str(path))
    else:
        raise ValueError("Nem támogatott exportformátum.")
    return {
        "path": str(path), "format": extension,
        "objects": [o.Name for o in objs], "size_bytes": path.stat().st_size,
    }


def handle(job):
    op = job["operation"]
    args = job["arguments"]
    project_file = Path(job["project_file"])
    project_root = Path(job["workspace"])
    if op == "new_project":
        return _new_project(project_file, args)

    doc = _open_project(project_file)
    try:
        if op == "inspect_project":
            doc.recompute()
            return {
                "project": project_file.name,
                "label": doc.Label,
                "objects": [_shape_information(o) for o in doc.Objects[:200]],
                "truncated": len(doc.Objects) > 200,
            }
        if op == "add_primitive":
            obj = _add_primitive(doc, args)
        elif op == "sketch_pad":
            obj = _sketch_pad(doc, args)
        elif op == "boolean":
            obj = _combine(doc, args)
        elif op == "transform":
            obj = _transform(doc, args)
        elif op == "remove_object":
            obj = doc.getObject(args["name"])
            if obj is None:
                raise ValueError("A törlendő objektum nem létezik.")
            doc.removeObject(obj.Name)
            obj = None
        elif op == "export":
            doc.recompute()
            return _export(doc, project_root, args)
        else:
            raise ValueError("Ismeretlen FreeCAD művelet.")

        doc.recompute()
        if obj is not None and hasattr(obj, "Shape") and obj.Shape.isNull():
            raise ValueError("A művelet üres vagy hibás geometriát hozott létre.")
        doc.save()
        return {"project": project_file.name,
                "result": _shape_information(obj) if obj is not None else
                {"removed": args["name"]}}
    finally:
        App.closeDocument(doc.Name)


def main():
    result_file = Path(os.environ["JARVIS_FREECAD_RESULT"])
    try:
        with open(os.environ["JARVIS_FREECAD_REQUEST"], encoding="utf-8") as handle_file:
            job = json.load(handle_file)
        payload = {"isError": False, "structuredContent": handle(job)}
    except Exception as error:
        payload = {
            "isError": True,
            "structuredContent": {
                "error": str(error)[:1000],
                "exception": type(error).__name__,
            },
        }
    result_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
