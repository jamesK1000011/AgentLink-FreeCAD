# SPDX-License-Identifier: LGPL-2.1-or-later
# The document: new, open and save; its objects listed, read, set, renamed
# and deleted; recompute with each object's error; files imported and
# exported (read back to check); and a picture of the 3D view, which needs
# the FreeCAD window.

import difflib
import math
import os

import FreeCAD
import numpy as np
import Part

from .. import geometry as geo
from .. import paths, runners
from ..protocol import ToolError
from . import picks

GROUP = "doc"
INFO = "The document: new, open, save; objects listed, read, set, renamed, deleted; recompute; import and export files."

SOLID_FORMATS = {"step": ("step", "stp"), "iges": ("iges", "igs"), "brep": ("brep", "brp")}
MESH_FORMATS = {"stl": ("stl",), "obj": ("obj",), "3mf": ("3mf",), "ply": ("ply",), "off": ("off",), "amf": ("amf",),
                # read by meshformats, not FreeCAD's Mesh module
                "gltf": ("gltf", "glb"), "dae": ("dae",), "wrl": ("wrl", "vrml"), "3ds": ("3ds",)}
MORE_MESH = ("gltf", "dae", "wrl", "3ds")
# Read by FreeCAD's own importers first (glTF: Import's ReaderGltf; Collada
# and 3DS: BIM's importers, Collada needing pycollada); meshformats reads
# them where those are not here, and when units or up are given.
CORE_READERS = {"gltf": ("Import", "FreeCAD's glTF reader (Import)"), "dae": ("importDAE", "FreeCAD's Collada importer (importDAE)"),
                "3ds": ("import3DS", "FreeCAD's 3DS importer (import3DS)")}


def is_mesh(o):
    """A mesh object (Mesh::Feature and kin): a Mesh, no Shape."""
    return hasattr(o, "Mesh") and getattr(o, "Shape", None) is None


def core_scene(d, p, fmt, before):
    """(new objects, None) when FreeCAD's own importer read the file into d,
    else ([], why not)."""
    mod_name, _who = CORE_READERS[fmt]
    import importlib

    mod = None
    for name in (mod_name, "importers." + mod_name):
        try:
            mod = importlib.import_module(name)
            break
        except Exception:  # noqa: BLE001 - not in this build
            continue
    if mod is None:
        return [], f"{mod_name} is not in this FreeCAD"
    try:
        mod.insert(p, d.Name)
    except Exception as e:  # noqa: BLE001 - a missing dependency (pycollada) or a file it cannot read
        return [], f"{mod_name}: {e}"
    new = [o for o in d.Objects if o.Name not in before]
    if not new:
        return [], f"{mod_name} read nothing"
    return new, None
EXPORTS = ("step", "iges", "brep", "stl", "obj", "3mf", "ply", "off", "wrl", "x3d", "glb", "gltf", "dae", "dxf", "svg")
# Written by FreeCAD's Mesh module as one mesh; by meshformats a mesh (and
# colour) per object; by flat2d a 2D projection.
FC_MESH_OUT = {"stl": ".stl", "obj": ".obj", "3mf": ".3mf", "ply": ".ply", "off": ".off", "wrl": ".wrl", "x3d": ".x3d"}
SCENE_OUT = {"glb": ".glb", "gltf": ".gltf", "dae": ".dae"}
FLAT_OUT = {"dxf": ".dxf", "svg": ".svg"}
# The 2D views: the shape turned so the view looks down -Z; X right, Y up.
VIEWS = {
    "top": ((1, 0, 0), (0, 1, 0)), "bottom": ((1, 0, 0), (0, -1, 0)),
    "front": ((1, 0, 0), (0, 0, 1)), "back": ((-1, 0, 0), (0, 0, 1)),
    "right": ((0, 1, 0), (0, 0, 1)), "left": ((0, -1, 0), (0, 0, 1)),
    "iso": ((0.7071068, 0.7071068, 0), (-0.4082483, 0.4082483, 0.8164966)),
}
SKIP_PROPS = {"Proxy", "ExpressionEngine", "_GroupTouched"}


def colour(v):
    """"#rrggbb", "#rrggbbaa" or [r, g, b(, a)] in 0…1 → (r, g, b, a); None when not given."""
    if v is None:
        return None
    if isinstance(v, str) and v.startswith("#") and len(v) in (7, 9):
        try:
            c = [int(v[i:i + 2], 16) / 255 for i in range(1, len(v), 2)]
        except ValueError:
            c = None
        if c:
            return tuple(c + [1.0] * (4 - len(c)))
    if isinstance(v, (list, tuple)) and len(v) in (3, 4) and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in v):
        return tuple(list(map(float, v)) + [1.0] * (4 - len(v)))
    raise ToolError("invalid_input", f"colors: \"#rrggbb\" or [r, g, b] in 0…1, not {v!r}.")


def view_matrix(view):
    if view not in VIEWS:
        raise ToolError("invalid_input", f"view: one of {', '.join(VIEWS)}.")
    xa, ya = (FreeCAD.Vector(*v) for v in VIEWS[view])
    za = xa.cross(ya)
    m = FreeCAD.Matrix(xa.x, xa.y, xa.z, 0, ya.x, ya.y, ya.z, 0, za.x, za.y, za.z, 0, 0, 0, 0, 1)
    return m


def edge_items(edges, layer, defl):
    """Projected edges (in the XY plane) as flat2d items: circles and arcs kept, the rest as polylines."""
    import math

    out = []
    for e in edges:
        c = e.Curve
        if isinstance(c, Part.Circle) and abs(abs(c.Axis.z) - 1) < 1e-6:
            cx, cy, r = c.Location.x, c.Location.y, c.Radius
            if e.isClosed():
                out.append({"kind": "circle", "c": [cx, cy], "r": r, "layer": layer})
                continue
            p0, p1 = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
            a0, a1 = (math.degrees(math.atan2(q.y - cy, q.x - cx)) for q in (p0, p1))
            if c.Axis.z < 0:
                a0, a1 = a1, a0
            out.append({"kind": "arc", "c": [cx, cy], "r": r, "a0": a0, "a1": a1, "layer": layer})
            continue
        pts = [[v.x, v.y] for v in e.discretize(Deflection=defl)]
        if len(pts) >= 2:
            out.append({"kind": "line", "points": pts, "layer": layer})
    return out


def flat_write(objs, fmt, path, a):
    """A 2D view of the objects (hidden lines on their own layer when hidden: true), or a section at z."""
    from .. import flat2d

    defl = float(a.get("tolerance", 0.01))
    shape = objs[0].Shape if len(objs) == 1 else Part.Compound([o.Shape for o in objs])
    items = []
    if a.get("section") is not None:
        z = picks.num(a["section"], "section")
        wires = shape.slice(FreeCAD.Vector(0, 0, 1), z)
        if not wires:
            raise ToolError("invalid_input", f"section: nothing at z = {z} mm (the shape runs {shape.BoundBox.ZMin:.2f} … {shape.BoundBox.ZMax:.2f}).")
        for w in wires:
            items += edge_items(w.Edges, "cut", defl)
        what = {"section": z, "wires": len(wires)}
    else:
        import TechDraw

        view = a.get("view", "top")
        sh = shape.transformGeometry(view_matrix(view)) if view != "top" else shape.copy()
        res = TechDraw.projectEx(sh, FreeCAD.Vector(0, 0, 1))
        # hard, smooth and outline edges (seams and isolines left out), visible then hidden
        vis = [e for i in (0, 1, 3) if not res[i].isNull() for e in res[i].Edges]
        hid = [e for i in (5, 6, 8) if not res[i].isNull() for e in res[i].Edges] if a.get("hidden") else []
        items = edge_items(vis, "visible", defl) + edge_items(hid, "hidden", defl)
        what = {"view": view, "visibleEdges": len(vis), **({"hiddenEdges": len(hid)} if a.get("hidden") else {})}
    if not items:
        raise ToolError("failed", "The view came out empty — nothing to draw.")
    writer = None
    if fmt == "dxf":
        text, writer = flat2d.write_dxf(items, path)
    else:
        text = flat2d.svg(items)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    x0, y0, x1, y1 = flat2d.bounds(items)
    out = {**what, "size": [round(x1 - x0, 3), round(y1 - y0, 3)], "units": "mm"}
    if fmt == "dxf":
        out["entities"] = flat2d.read_dxf_counts(text)
        out["writer"] = writer
    return out


def image_size(path):
    """(width, height) in pixels from a PNG, JPEG or BMP header; None if unknown."""
    import struct

    with open(path, "rb") as f:
        head = f.read(64 * 1024)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:2] == b"BM":
        w, h = struct.unpack("<ii", head[18:26])
        return w, abs(h)
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            mk = head[i + 1]
            n = struct.unpack(">H", head[i + 2:i + 4])[0]
            if mk in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return w, h
            i += 2 + n
    return None


def image_plane(d, path, label, a):
    """A picture as an image plane (a reference to trace over): width mm, its height from the picture's shape, on XY."""
    try:
        o = d.addObject("Image::ImagePlane", "ImagePlane")
    except Exception as e:
        raise ToolError("unavailable", f"Image planes are not available here ({e}).")
    px = image_size(path)
    w = picks.number(a, "width", 100, gt=0, msg="width: the picture's width in mm, above 0.")
    o.Label = label
    o.ImageFile = path
    o.XSize = w
    o.YSize = w * px[1] / px[0] if px and px[0] else w
    return o


def fmt_of(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    for k, exts in {**SOLID_FORMATS, **MESH_FORMATS}.items():
        if ext in exts:
            return k
    return ext


def readonly(o, p):
    try:
        if "ReadOnly" in (o.getEditorMode(p) or []):
            return True
    except Exception:
        pass
    try:
        st = o.getPropertyStatus(p)
        return "ReadOnly" in st or "Output" in st or "Immutable" in st
    except Exception:
        return False


def hidden(o, p):
    """Hidden in FreeCAD's property editor (the property is still there)."""
    try:
        if "Hidden" in (o.getEditorMode(p) or []):
            return True
    except Exception:
        pass
    try:
        return "Hidden" in o.getPropertyStatus(p)
    except Exception:
        return False


def doc_names(docs):
    """Open documents for a refusal: "Label", or "Label (Name)" where the
    internal name differs from the label or a label repeats, so two
    documents with one label can be told apart."""
    docs = list(docs)
    labels = [d.Label for d in docs]
    return ", ".join(d.Label if d.Name == d.Label and labels.count(d.Label) == 1 else f"{d.Label} ({d.Name})" for d in docs) or "none"


def open_labels(docs):
    """Open documents as a list of labels; a label two of them share is
    given as "Label (Name)" for each, the name being what doc_switch and
    doc_close tell them apart by."""
    docs = list(docs)
    labels = [d.Label for d in docs]
    return [d.Label if labels.count(d.Label) == 1 else f"{d.Label} ({d.Name})" for d in docs]


def errors(doc):
    out = []
    for o in doc.Objects:
        st = list(getattr(o, "State", []) or [])
        if "Invalid" in st or "Error" in st or (hasattr(o, "isValid") and not o.isValid()):
            try:
                why = o.getStatusString()
            except Exception:
                why = ", ".join(st)
            out.append({"object": o.Label, "type": o.TypeId, "error": why})
    return out


# A placement's keys, in Agent Link's spelling and FreeCAD's own (Base,
# Rotation), any case.
PLACEMENT_KEYS = {"at": "at", "base": "at", "position": "at", "axis": "axis", "angle": "angle", "rotation": "rotation"}
PLACEMENT_HELP = "{ at | Base: [x,y,z], axis | Axis: [x,y,z], angle | Angle: degrees } or Rotation: { axis, angle } | [x,y,z,w] (a quaternion)"


def to_placement(cur, v, p="Placement"):
    """A JSON placement over the current one: what is left out stays as it
    was (a move keeps the turn). Unknown keys are refused, with the keys
    there are."""
    if not isinstance(v, dict):
        raise ValueError(PLACEMENT_HELP)
    keys = {}
    for k, x in v.items():
        kk = PLACEMENT_KEYS.get(str(k).lower())
        if kk is None:
            raise ToolError("invalid_input", f"values.{p}.{k}: not a placement key — it takes {PLACEMENT_HELP}.")
        if kk in keys:
            raise ToolError("invalid_input", f"values.{p}: {k} given twice (at and Base are one key, as are the others).")
        keys[kk] = x
    if "rotation" in keys and ("axis" in keys or "angle" in keys):
        raise ToolError("invalid_input", f"values.{p}: Rotation, or axis and angle — not both.")
    cur = cur if isinstance(cur, FreeCAD.Placement) else FreeCAD.Placement()
    base = picks.vec3(keys["at"], f"{p}.at") if "at" in keys else FreeCAD.Vector(cur.Base)
    rot = FreeCAD.Rotation(cur.Rotation)
    if "rotation" in keys:
        r = keys["rotation"]
        if isinstance(r, dict):
            rk = {str(k).lower(): x for k, x in r.items()}
            bad = [k for k in r if str(k).lower() not in ("axis", "angle")]
            if bad:
                raise ToolError("invalid_input", f"values.{p}.Rotation.{bad[0]}: a rotation takes axis and angle (degrees), or [x,y,z,w].")
            rot = FreeCAD.Rotation(picks.direction(rk.get("axis"), f"{p}.Rotation.axis", (0, 0, 1)), picks.num(rk.get("angle", 0), f"{p}.Rotation.angle"))
        elif isinstance(r, (list, tuple)) and len(r) == 4:
            q = [picks.num(x, f"{p}.Rotation") for x in r]
            if sum(x * x for x in q) < 1e-12:
                raise ToolError("invalid_input", f"values.{p}.Rotation: [0,0,0,0] is no rotation.")
            rot = FreeCAD.Rotation(*q)
        else:
            raise ToolError("invalid_input", f"values.{p}.Rotation: {{ axis, angle }} or a quaternion [x,y,z,w].")
    elif "axis" in keys or "angle" in keys:
        axis = picks.direction(keys["axis"], f"{p}.axis") if "axis" in keys else FreeCAD.Vector(rot.Axis)
        angle = picks.num(keys["angle"], f"{p}.angle") if "angle" in keys else math.degrees(rot.Angle)
        rot = FreeCAD.Rotation(axis, angle)
    return FreeCAD.Placement(base, rot)


def to_value(o, p, v):
    """A JSON value into what the property takes, by its type."""
    t = o.getTypeIdOfProperty(p)
    try:
        if t in ("App::PropertyBool",):
            if not isinstance(v, bool):
                raise ValueError("true or false")
            return v
        if t.startswith("App::PropertyInteger") or t == "App::PropertyPercent":
            # PropertyPercent is an integer (0 … 100): FreeCAD refuses a float.
            if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
                raise ValueError("a whole number")
            return int(v)
        if t in ("App::PropertyFloat", "App::PropertyLength", "App::PropertyDistance", "App::PropertyAngle", "App::PropertyFloatConstraint", "App::PropertyArea", "App::PropertyVolume", "App::PropertyQuantity", "App::PropertyQuantityConstraint", "App::PropertyPrecision") or t.startswith("App::PropertyFloat"):
            if isinstance(v, str):
                return v  # "10 mm", "2 in": FreeCAD parses the unit
            return float(picks.num(v, p))
        if t in ("App::PropertyString", "App::PropertyFont", "App::PropertyFile", "App::PropertyPath"):
            if not isinstance(v, str):
                raise ValueError("a string")
            return v
        if t == "App::PropertyEnumeration":
            choices = o.getEnumerationsOfProperty(p) or []
            if v not in choices:
                raise ValueError(f"one of {', '.join(map(str, choices))}")
            return v
        if t in ("App::PropertyVector", "App::PropertyVectorDistance", "App::PropertyPosition", "App::PropertyDirection"):
            return picks.vec3(v, p)
        if t == "App::PropertyPlacement":
            return to_placement(getattr(o, p), v, p)
        if t in ("App::PropertyLink", "App::PropertyLinkGlobal", "App::PropertyLinkChild", "App::PropertyLinkHidden", "App::PropertyXLink"):
            return None if v is None else picks.find(o.Document, v)
        if t in ("App::PropertyLinkList", "App::PropertyLinkListGlobal", "App::PropertyLinkListChild"):
            if not isinstance(v, list):
                raise ValueError("a list of object names or labels")
            return [picks.find(o.Document, x) for x in v]
        if t in ("App::PropertyColor", "App::PropertyMaterialColor"):
            if isinstance(v, str) and v.startswith("#") and len(v) == 7:
                return tuple(int(v[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
            return tuple(float(x) for x in v)
        if t == "App::PropertyStringList":
            return [str(x) for x in v]
        if t == "App::PropertyFloatList":
            return [float(x) for x in v]
        if t == "App::PropertyIntegerList":
            return [int(x) for x in v]
    except ToolError:
        raise
    except (ValueError, TypeError) as e:
        raise ToolError("invalid_input", f"values.{p} ({t}): {e}.")
    if "LinkSub" in t:
        raise ToolError("invalid_input", f"values.{p}: a {t} (an object with its faces or edges) is not set by object_set — the tool that made the object sets it again (sketch_attach for a sketch's support, link_make / link_edit for a link, measure_keep for a measurement).")
    raise ToolError("invalid_input", f"values.{p}: a {t} is not set by object_set — it takes numbers, text, true/false, enumerations, vectors, placements, object links and lists of them (object_get gives each property's type); the tool that made the object changes the rest.")


def modified_state(d):
    """Whether the document has changes since its save: FreeCAD's own flags
    (App touched, the window's "*"), and the objects still marked touched."""
    out = {}
    try:
        out["touched"] = bool(d.isTouched())
        # by each object's State: an object has no isTouched() (only the
        # document has), so this list was never filled before
        from ..store import touched_names

        objs = touched_names(d)
        if objs:
            out["touchedObjects"] = objs[:10]
    except Exception:
        pass
    if getattr(FreeCAD, "GuiUp", False):
        try:
            import FreeCADGui

            g = FreeCADGui.getDocument(d.Name)
            if g is not None:
                out["modified"] = bool(g.Modified)
        except Exception:
            pass
    return out


def saved(d):
    """After d was written to its file: the window's mark cleared
    (_gui_saved), and what is still touched kept as the saved state for
    where there is no window (store.note_saved)."""
    _gui_saved(d)
    from ..store import note_saved

    note_saved(d)


def _gui_saved(d):
    """A save through App's document leaves the window's own modified mark
    (the "*" on its tab) set: FreeCAD clears it only for a save made through
    the GUI. Cleared here so a saved document reads as saved."""
    if not getattr(FreeCAD, "GuiUp", False):
        return
    try:
        import FreeCADGui

        # The file now holds what is in memory. FreeCAD 1.1 leaves the
        # document touched after a save from App with no object touched
        # (seen on the Mac), so the save itself decides here.
        try:
            d.purgeTouched()
        except Exception:
            pass
        g = FreeCADGui.getDocument(d.Name)
        if g is not None:
            g.Modified = False
    except Exception:
        pass



LIST_ALL = 12  # an import of more objects than this is summarised


def is_holder(o):
    """A group or a Draft layer: it holds imported objects, it is not one."""
    if o.TypeId in ("App::DocumentObjectGroup", "App::DocumentObjectGroupPython"):
        return True
    proxy = getattr(o, "Proxy", None)
    return type(proxy).__name__ in ("Layer", "LayerContainer") or o.Name.startswith(("LayerContainer",))


def summarised(out, holders=()):
    """The objects an import made: all of them when few, else counts by
    type and the first few (an import of a drawing of a thousand lines is
    not a thousand-line answer)."""
    res = {}
    if holders:
        res["layers"] = sorted({h.Label for h in holders})[:LIST_ALL]
        res["layerCount"] = len(holders)
    if len(out) <= LIST_ALL:
        res["objects"] = out
        return res
    by = {}
    for e in out:
        k = e.get("dxf") or e["type"]
        by[k] = by.get(k, 0) + 1
    res["byType"] = by
    res["objects"] = out[:5]
    res["more"] = f"{len(out) - 5} more ({', '.join(f'{n} {k}' for k, n in sorted(by.items()))}): doc_list or session_state lists them all."
    return res


def import_dxf(d, p, base, before, a):
    """A DXF: its LINE, ARC, CIRCLE, ELLIPSE, POINT, (LW)POLYLINE and SPLINE
    read by Agent Link's own reader (dxfread.py) — FreeCAD's dropped the
    closing edge of a closed 3D polyline and refused a SPLINE by fit points;
    a drawing with blocks, text, dimensions or hatches goes through
    FreeCAD's importer, its closed polylines closed after, and what it
    could not read said. (objects made, what was read)."""
    from .. import dxfread

    try:
        parsed = dxfread.read(p)
    except Exception as e:  # noqa: BLE001 - FreeCAD's reader may still read it
        parsed, why = None, str(e)
    else:
        why = None if parsed is not None else "a binary DXF"
    own_only = parsed is not None and parsed["entities"] and not parsed["other"]
    if own_only:
        made, took = dxf_own(d, parsed, base)
        took["reader"] = "Agent Link's own DXF reader (dxfread)"
        return made, took
    try:
        import Import

        Import.readDXF(p, d.Name)
    except Exception as e:  # noqa: BLE001
        for o in [o for o in d.Objects if o.Name not in before]:
            try:
                d.removeObject(o.Name)
            except Exception:  # noqa: BLE001
                pass
        if parsed is None or not parsed["entities"]:
            raise ToolError("unavailable", f"DXF import failed here ({e}){f'; {why}' if why else ''}: open it in the FreeCAD window (Draft's importer).") from None
        made, took = dxf_own(d, parsed, base)
        took.update(reader="Agent Link's own DXF reader (dxfread): FreeCAD's importer failed", freecadFailed=str(e),
                    notRead={k: v for k, v in parsed["other"].items()},
                    note="Blocks, text, dimensions and hatches are FreeCAD's importer's to read: open the file in the FreeCAD window for them.")
        return made, took
    made = [o for o in d.Objects if o.Name not in before]
    took = {"reader": "FreeCAD's DXF importer" + (f" (the drawing has {', '.join(f'{n} {k}' for k, n in sorted(parsed['other'].items()))})" if parsed and parsed["other"] else "")}
    if parsed is not None:
        fixed = dxf_close(made, parsed)
        if fixed:
            took["closed"] = f"{fixed} closed polyline(s) came in open (their closing edge dropped): closed here."
    return made, took


def dxf_own(d, parsed, base):
    """The parsed entities as Part::Feature objects, one group per layer."""
    from .. import dxfread

    made, failed, groups, counts = [], [], {}, {}
    for i, e in enumerate(parsed["entities"]):
        try:
            sh = dxfread.shape(e)
        except Exception as ex:  # noqa: BLE001 - said, the rest still come in
            failed.append({"entity": i, "type": e["type"], "layer": e.get("layer"), "why": str(ex) or type(ex).__name__})
            continue
        o = d.addObject("Part::Feature", e["type"].capitalize())
        o.Shape = sh
        o.Label = f"{e['type'].capitalize()} {e.get('layer', '0')}"
        o.addProperty("App::PropertyString", "DxfType", "DXF", "The DXF entity this came from").DxfType = e["type"]
        g = groups.get(e.get("layer", "0"))
        if g is None:
            g = d.addObject("App::DocumentObjectGroup", "Layer")
            g.Label = str(e.get("layer", "0"))
            groups[e.get("layer", "0")] = g
            made.append(g)
        g.addObject(o)
        made.append(o)
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    took = {"entities": counts}
    if failed:
        took["failed"] = failed[:10]
        took["failedCount"] = len(failed)
    if parsed.get("units") is not None:
        took["dxfUnits"] = {0: "none", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}.get(parsed["units"], parsed["units"])
    return made, took


def dxf_close(made, parsed):
    """Closed polylines FreeCAD's importer brought in open, closed: an open
    wire whose ends are the polyline's first and last points gets its
    closing edge. The count closed."""
    from .. import dxfread

    want = [e for e in parsed["entities"] if e["type"] in ("POLYLINE", "LWPOLYLINE") and e.get("closed") and len(e["points"]) > 2]
    fixed = 0
    for o in made:
        sh = getattr(o, "Shape", None)
        if sh is None or sh.isNull() or len(sh.Wires) != 1 or sh.Wires[0].isClosed():
            continue
        w = sh.Wires[0]
        ends = [w.OrderedVertexes[0].Point, w.OrderedVertexes[-1].Point]
        for e in want:
            pts = [FreeCAD.Vector(*dxfread.to_world(q, e.get("ocs"))) for q in e["points"]]
            if len(w.Edges) != len(dxfread.segments(e)) - 1:
                continue
            if {(round(v.x, 6), round(v.y, 6), round(v.z, 6)) for v in ends} == {(round(v.x, 6), round(v.y, 6), round(v.z, 6)) for v in (pts[0], pts[-1])}:
                try:
                    o.Shape = Part.Wire(w.OrderedEdges + [Part.makeLine(ends[1], ends[0])])
                    fixed += 1
                    want.remove(e)
                except Exception:  # noqa: BLE001
                    pass
                break
    return fixed

def went_from(session, doc):
    """Note the document the session is leaving: when the one it moves to is
    closed, the session goes back there (doc_new's "previous"), not to
    whichever open document FreeCAD lists last."""
    try:
        name = doc.Name
    except Exception:  # noqa: BLE001 - no document, or one already gone
        return
    trail = session.__dict__.setdefault("doc_trail", [])
    if name in trail:
        trail.remove(name)
    trail.append(name)
    del trail[:-20]


def tools(session):
    s = session

    def switch(doc):
        """The session moved to doc: its undo on, the families' notes
        cleared, the window's active document set, one snapshot. Where it
        came from is noted (went_from)."""
        from ..store import undo_on

        if getattr(s, "doc", None) is not None and doc is not s.doc:
            went_from(s, s.doc)
        undo_on(doc)
        s.doc = doc
        s.meta = {}
        if FreeCAD.GuiUp:
            try:
                import FreeCADGui

                FreeCAD.setActiveDocument(doc.Name)
                FreeCADGui.getDocument(doc.Name)
            except Exception:
                pass
        s.snapshot("doc")

    def where(path, ext=None):
        """A file path in the session's folder when relative, ext added
        when it does not end so."""
        if not isinstance(path, str) or not path:
            raise ToolError("invalid_input", "path: a file path (relative ones go in the session's folder).")
        p = paths.local(s, path)
        if ext and not p.lower().endswith(ext.lower()):
            p = paths.made(s, p + ext)
        return p

    # ---- documents ---------------------------------------------------------------------------

    def doc_hits(r, listed):
        """(the open document r names by the name FreeCAD lists it under or
        its Name, []) or (None, the documents r could mean: by label, then by
        name or label in any case, then by file). A Name is unique; labels
        are not."""
        docs = list(listed.values())
        rp = os.path.abspath(where(r)) if r.lower().endswith(".fcstd") else None
        d = listed.get(r) or next((x for x in docs if x.Name == r), None)
        if d is not None:
            return d, []
        return None, ([x for x in docs if x.Label == r] or [x for x in docs if r.lower() in (x.Name.lower(), x.Label.lower())]
                      or [x for x in docs if rp and os.path.abspath(x.FileName or "") == rp])

    def own_doc(r):
        """The session's own document when r is its name or label (the name
        session_state gave), else None."""
        try:
            if r in (s.doc.Name, s.doc.Label):
                return s.doc
        except Exception:  # noqa: BLE001 - the session's document is gone
            pass
        return None

    def unsaved(d):
        """Changed since its save; never saved and not empty counts too
        (headless has no * on a tab)."""
        from ..store import is_changed

        return is_changed(d) or (not d.FileName and len(d.Objects) > 0)

    def touched_marks(picked, unsaved_labels):
        """Which objects say a document changed, where FreeCAD's touched
        marks are all there is to go by: "Label: a, b; …"."""
        from ..store import touched_since_save

        return "; ".join(f"{d.Label}: {', '.join(t[:5])}" for d in picked for t in [touched_since_save(d)] if t and d.Label in unsaved_labels)

    def current_name():
        """The session's document's name, or None when it is gone."""
        try:
            return s.doc.Name
        except Exception:  # already gone
            return None

    def back_to(still):
        """Where the session goes when its document was closed: the latest
        document it came from that is still open (as doc_new's "previous"
        promised), else the last one FreeCAD lists, else a new one."""
        left = list(still.values())
        back = next((still[n] for n in reversed(s.__dict__.get("doc_trail", [])) if n in still), None)
        return back or (left[-1] if left else FreeCAD.newDocument("Unnamed"))

    def recent_files():
        """The window's File › Recent files, from settings (headless too)."""
        g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/RecentFiles")
        files = []
        for i in range(int(g.GetInt("RecentFiles", 4) or 4) + 20):
            f = g.GetString(f"MRU{i}", "")
            if f:
                files.append({"path": f, "exists": os.path.isfile(f)})
        return files

    def open_at(p):
        """The open document whose file is p, or None."""
        return next((x for x in FreeCAD.listDocuments().values() if os.path.abspath(x.FileName or "") == os.path.abspath(p)), None)

    def is_changed(d):
        """Whether d has changes since its save (store.is_changed)."""
        from ..store import is_changed as changed

        return changed(d)

    def unchanged(d):
        """d marked as its file has it (store._unchanged): FreeCAD 1.1 marks
        a document modified by its first recompute."""
        from ..store import _unchanged

        _unchanged(d)

    def free_name(p, overwrite):
        """p, or "<name> 2.FCStd" … when a file is there already and it may
        not be written over."""
        if os.path.exists(p) and not overwrite:
            base = p[:-6]
            k = 2
            while os.path.exists(f"{base} {k}.FCStd"):
                k += 1
            p = f"{base} {k}.FCStd"
        return p

    # ---- objects -----------------------------------------------------------------------------

    def is_shape(sh):
        """A Part shape that is not empty."""
        return isinstance(sh, Part.Shape) and not sh.isNull()

    def shape_row(sh):
        """A shape in a listing: a solid's stats, else its faces, edges and size."""
        return geo.stats(sh) if sh.Solids else {"faces": len(sh.Faces), "edges": len(sh.Edges), "box": geo.box_of(sh)["size"]}

    def prop_entry(o, p):
        """One property as object_get answers it: value (JSON), type,
        readOnly, hidden, an enumeration's choices."""
        try:
            v = picks.json_safe(getattr(o, p))
        except Exception as e:
            v = f"<unreadable: {e}>"
        entry = {"value": v, "type": o.getTypeIdOfProperty(p).replace("App::Property", "")}
        if readonly(o, p):
            entry["readOnly"] = True
        if hidden(o, p):
            entry["hidden"] = True
        if entry["type"] == "Enumeration":
            try:
                entry["choices"] = [str(c) for c in (o.getEnumerationsOfProperty(p) or [])][:40]
            except Exception:  # noqa: BLE001
                pass
        return entry

    def built_from(o):
        """The labels of o and of everything built from it."""
        try:
            return {o.Label} | {x.Label for x in o.InListRecursive}
        except Exception:
            return {o.Label}

    def along(objs):
        """What goes with objs: a PartDesign Body's own features and Origin,
        and the helpers a result was made with (picks.remember_made: a
        boolean's base shape and its FeatureBase) — each only when nothing
        staying uses it. (extra objects, inputs to show again, labels to
        give back)."""
        doc_ = s.doc
        going = {o.Name for o in objs}
        cand, show, labels = [], [], {}
        for o in objs:
            made, hid, lab = picks.made_record(o)
            cand += [doc_.getObject(n) for n in made]
            show += [n for n in hid]
            labels.update(lab)
            if getattr(o, "TypeId", "") == "PartDesign::Body":
                cand += list(getattr(o, "Group", None) or [])
                cand += [getattr(o, "Origin", None), getattr(o, "BaseFeature", None)]
        cand = [c for c in cand if c is not None and c.Name not in going]
        # Origins' axes and planes go with their Origin.
        for c in list(cand):
            if getattr(c, "TypeId", "") == "App::Origin":
                cand += [x for x in (getattr(c, "OriginFeatures", None) or []) if x.Name not in going]
        extra = []
        changed = True
        while changed:  # a helper goes once all that use it go
            changed = False
            for c in cand:
                if c.Name in going:
                    continue
                if getattr(c, "TypeId", "") != "PartDesign::Body" and all(p.Name in going for p in c.InList):
                    going.add(c.Name)
                    extra.append(c)
                    changed = True
        show = [n for n in show if n not in going]
        return extra, show, labels

    def removed(names):
        """Each of the named objects still in the document removed (one may
        have gone with another)."""
        for n in names:
            if s.doc.getObject(n) is not None:
                try:
                    s.doc.removeObject(n)
                except Exception:
                    pass

    def shown_again(show, labels):
        """The inputs a deleted result had hidden, shown again and given the
        label they had before it where that is free. (labels shown, {label
        now: label given back})."""
        shown, renamed = [], {}
        for n in show:
            x = s.doc.getObject(n)
            if x is None:
                continue
            old = labels.get(n)
            if old and x.Label != old and not any(y.Label == old for y in s.doc.Objects if y is not x):
                renamed[x.Label] = old
                x.Label = old
            if hasattr(x, "Visibility") and not x.Visibility:
                x.Visibility = True
                shown.append(x.Label)
        return shown, renamed

    def meta_moved(old, label):
        """What the families keep by an object's label (session.meta) kept
        under its new one."""
        if old in s.meta:
            s.meta[label] = s.meta.pop(old)

    def is_group(g):
        """A group, an App::Part or a link (not an Origin)."""
        return g.TypeId != "App::Origin" and (g.isDerivedFrom("App::DocumentObjectGroup") or g.TypeId in ("App::Part", "App::Link"))

    def group_row(g):
        """A group in object_group's list: what it holds, and a link's original."""
        row = {"group": g.Label, "type": g.TypeId}
        if hasattr(g, "Group"):
            row["holds"] = [x.Label for x in g.Group]
        if g.TypeId == "App::Link":
            lo = g.getLinkedObject(False) if hasattr(g, "getLinkedObject") else getattr(g, "LinkedObject", None)
            row["links"] = lo.Label if lo is not None else None
        return row

    # ---- import ------------------------------------------------------------------------------

    def read_shape(p):
        """The file's whole shape, as Part reads it (STEP, IGES, BREP)."""
        sh = Part.Shape()
        sh.read(p)
        return sh

    def mesh_module():
        """FreeCAD's Mesh module (loaded when a mesh file comes in)."""
        import Mesh

        return Mesh

    def mesh_read(p, fmt, units, up, core_why):
        """(the file's mesh, what was taken from it): glTF, Collada, VRML
        and 3DS through Agent Link's own reader (meshformats: every node
        flattened into one, units and up as given), the rest by FreeCAD's
        Mesh module (then nothing to say: None)."""
        import Mesh

        if fmt not in MORE_MESH:
            return Mesh.Mesh(p), None
        from .. import meshformats

        V, F, took = meshformats.read(p, units, up)
        took = {**(took or {}), "reader": "Agent Link's own reader (meshformats)", **({"coreNotUsed": core_why} if core_why else {})}
        m = Mesh.Mesh()
        m.addFacets([[tuple(V[i]) for i in t] for t in F.tolist()])
        return m, took

    def mesh_solid(m):
        """A shape of the mesh's triangles, made a solid (turned outside
        out when inside out, cleaned) where they close."""
        sh = Part.Shape()
        sh.makeShapeFromMesh(m.Topology, 0.05)
        try:
            sh = Part.Solid(Part.Shell(sh.Faces))
            if sh.Volume < 0:
                sh.reverse()
            sh = geo.clean(sh)
        except Exception:
            pass
        return sh

    def svg_insert(p, d):
        """An SVG read into d by Draft's importer (importSVG)."""
        import importSVG

        importSVG.insert(p, d.Name)

    def jt_reader():
        """FreeCAD's JtReader module (an ImportError where the build leaves it out)."""
        import JtReader

        return JtReader

    def import_row(o, fmt):
        """An imported object in the answer: name, label, type, its DXF
        entity, a shape's stats or a mesh's triangles, and what kind of
        thing a mesh file became."""
        e = {"name": o.Name, "label": o.Label, "type": o.TypeId}
        if getattr(o, "DxfType", None):
            e["dxf"] = o.DxfType
        sh = getattr(o, "Shape", None)
        if isinstance(sh, Part.Shape) and not sh.isNull():
            e.update(geo.stats(sh) if sh.Solids else {"faces": len(sh.Faces), "edges": len(sh.Edges)})
            if fmt in MESH_FORMATS:
                e["closed"] = bool(sh.Solids)
                e["note"] = "Made of the mesh's triangles: measure and boolean work; fillets and face queries do not see round faces."
        elif hasattr(o, "Mesh"):
            e["mesh"] = {"triangles": o.Mesh.CountFacets, "closed": o.Mesh.isSolid()}
            e["note"] = "A mesh (Mesh::Feature), not a body: mesh files come in as meshes unless solid: true is asked. import_file { solid: true } makes a body of it (up to 200000 triangles); meshobj_* tools work on it as it is."
        return e

    # ---- export ------------------------------------------------------------------------------

    def export_pick(ref):
        """The object to export: a mesh (Mesh::Feature) as it is, never
        refused for having no shape; else an object with a shape."""
        o = picks.find(s.doc, ref, "object")
        if is_mesh(o):
            return o
        return picks.shaped(s.doc, ref)

    def out_path(given, label, fmt):
        """Where an export is written: the path given, else the first
        object's label; the format's extension added unless it ends in one
        of the format's own; its folder made."""
        ext = {"step": ".step", "iges": ".iges", "brep": ".brep", **FC_MESH_OUT, **SCENE_OUT, **FLAT_OUT}[fmt]
        p = where(given or (label.replace(" ", "_") + ext))
        known = {*(SOLID_FORMATS.get(fmt) or ()), *(MESH_FORMATS.get(fmt) or ()), ext.lstrip(".")}
        if os.path.splitext(p)[1].lower().lstrip(".") not in known:
            p += ext
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def mesh_modules():
        """FreeCAD's Mesh and MeshPart modules (loaded when a mesh is written)."""
        import Mesh
        import MeshPart

        return Mesh, MeshPart

    def tessellated(sh, tol):
        """A shape as a mesh at a chord error of tol mm (MeshPart)."""
        import MeshPart

        return MeshPart.meshFromShape(Shape=sh, LinearDeflection=tol, AngularDeflection=0.0873, Relative=False)

    def placed_mesh(o, tol):
        """An object's mesh for writing: a mesh object's own, where it
        stands (Topology gives the points placed, so a moved mesh is written
        in place, also when merged with others); a shape tessellated."""
        import Mesh

        if is_mesh(o):
            m = o.Mesh
            pl = getattr(o, "Placement", None)
            return m.copy() if pl is None or pl.isIdentity() else Mesh.Mesh(m.Topology)
        return tessellated(o.Shape, tol)

    def read_back(p, fmt):
        """The mesh file read again to check it (VRML by Agent Link's own
        reader, as FreeCAD wrote it: mm, Z up)."""
        import Mesh

        if fmt == "wrl":
            from .. import meshformats

            V, F, _info = meshformats.read(p, "mm", "z")  # FreeCAD writes it as the document has it
            back = Mesh.Mesh()
            back.addFacets([[tuple(V[i]) for i in tr] for tr in F.tolist()])
            return back
        return Mesh.Mesh(p)

    def solid_written(shape, fmt, p, vol):
        """STEP, IGES or BREP written and read back: the volume against
        the bodies', solids and faces."""
        {"step": shape.exportStep, "iges": shape.exportIges, "brep": shape.exportBrep}[fmt](p)
        back = Part.Shape()
        back.read(p)
        verify = {"volume": round(back.Volume, 2), "volumeDiff": round(abs(back.Volume - vol), 3), "solids": len(back.Solids), "faces": len(back.Faces)}
        if fmt == "iges" and not back.Solids:
            verify["note"] = "IGES carries faces, not solids, as most readers take it."
        return verify

    def scene_written(objs, shape, p, tol, cols):
        """glTF or Collada of bodies, a mesh and colour per object, read
        back: triangles, objects and the size against the bodies'."""
        from .. import meshformats

        parts, tris = [], 0
        for o in objs:
            m = tessellated(o.Shape, tol)
            pts, fs = m.Topology
            rgba = colour(cols.get(o.Label) or cols.get(o.Name))
            parts.append({"name": o.Label, "V": [tuple(v) for v in pts], "F": fs, **({"rgba": rgba} if rgba else {})})
            tris += len(fs)
        for q in parts:
            q["V"] = np.array(q["V"], float).reshape(-1, 3)
            q["F"] = np.array(q["F"], int).reshape(-1, 3)
        meshformats.write(p, parts)
        V, F, info = meshformats.read(p)
        span = V.max(axis=0) - V.min(axis=0)
        want = shape.BoundBox
        return {"triangles": int(len(F)), "trianglesWritten": tris, "objects": info["nodes"],
                "size": [round(float(x), 2) for x in span], "sizeOfBodies": [round(want.XLength, 2), round(want.YLength, 2), round(want.ZLength, 2)],
                "note": "Metres, Y up, as glTF and Collada keep them; a mesh and colour per object (colors {label: \"#rrggbb\"})."}

    def mesh_written(shape, p, tol, fmt, vol):
        """The bodies as one mesh, written by FreeCAD's Mesh module and
        read back: triangles, volume against the bodies', closed."""
        m = tessellated(shape, tol)
        m.write(p)
        try:
            back = read_back(p, fmt)
            return {"triangles": back.CountFacets, "volume": round(back.Volume, 2), "volumeDiff": round(abs(back.Volume - vol), 2), "closed": back.isSolid()}
        except Exception:
            return {"triangles": m.CountFacets, "readBack": f"written; FreeCAD does not read {fmt.upper()} back to check it"}

    def scene_of_meshes(objs, p, tol, cols):
        """glTF or Collada of meshes as they are (no re-meshing), shaped
        objects tessellated beside them, read back."""
        from .. import meshformats

        parts, tris = [], 0
        for o in objs:
            pts, fs = placed_mesh(o, tol).Topology
            rgba = colour(cols.get(o.Label) or cols.get(o.Name))
            parts.append({"name": o.Label, "V": np.array([tuple(v) for v in pts], float).reshape(-1, 3), "F": np.array(fs, int).reshape(-1, 3), **({"rgba": rgba} if rgba else {})})
            tris += len(fs)
        meshformats.write(p, parts)
        V, F, info = meshformats.read(p)
        return {"triangles": int(len(F)), "trianglesWritten": tris, "objects": info["nodes"], "note": "Metres, Y up, as glTF and Collada keep them."}

    def merged_meshes(objs, p, tol, fmt):
        """Meshes as they are merged into one file, read back: triangles,
        closed, and the volume when closed."""
        import Mesh

        m = Mesh.Mesh()
        for o in objs:
            m.addMesh(placed_mesh(o, tol))
        m.write(p)
        try:
            back = read_back(p, fmt)
            verify = {"triangles": back.CountFacets, "trianglesWritten": m.CountFacets, "closed": back.isSolid()}
            if back.isSolid():
                verify["volume"] = round(back.Volume, 2)
        except Exception:
            verify = {"triangles": m.CountFacets, "readBack": f"written; FreeCAD does not read {fmt.upper()} back to check it"}
        return verify

    def close_doc(name):
        """FreeCAD.closeDocument, an edit in that document left first
        (gui_input.leave_edit, live 59)."""
        if getattr(FreeCAD, "GuiUp", False):
            from .. import gui_input
            import FreeCADGui

            gui_input.leave_edit(FreeCADGui, name)
        FreeCAD.closeDocument(name)

    helpers = {
        # the session and the document
        "doc": lambda: s.doc, "current": lambda: s.doc, "switch": switch, "where": where, "snapshot": lambda tool: s.snapshot(tool), "steps": lambda: s.steps,
        "unique": lambda label, own=None: s.unique(label, own) if own is not None else s.unique(label), "bodies": lambda: s.bodies(), "body": lambda ref: s.body(ref),
        "finish": lambda tool, read: picks.finish(s, tool, read), "errors": errors, "find": lambda ref, what="object": picks.find(s.doc, ref, what),
        "ref_list": picks.ref_list, "num": picks.num, "vec3": picks.vec3, "json_safe": lambda v: picks.json_safe(v),
        "recompute_scoped": lambda objs: picks.recompute_scoped(s.doc, objs),
        # documents
        "new_doc": lambda name: FreeCAD.newDocument(name), "open_doc": lambda p: FreeCAD.openDocument(p), "close_doc": close_doc,
        "listed_docs": lambda: FreeCAD.listDocuments(), "doc_hits": doc_hits, "own_doc": own_doc, "doc_names": doc_names, "open_labels": open_labels,
        "unsaved": unsaved, "touched_marks": touched_marks, "current_name": current_name, "back_to": back_to, "recent_files": recent_files, "open_at": open_at,
        "is_changed": is_changed, "unchanged": unchanged, "free_name": free_name, "saved": saved, "modified_state": modified_state,
        # files
        "isfile": os.path.isfile, "exists": os.path.exists, "abspath": os.path.abspath, "basename": os.path.basename, "dirname": os.path.dirname,
        "makedirs": lambda p: os.makedirs(p, exist_ok=True), "filesize": os.path.getsize, "stem": lambda p: os.path.splitext(os.path.basename(p))[0],
        # objects
        "is_shape": is_shape, "shape_row": shape_row, "once": lambda xs: list(dict.fromkeys(xs)), "SKIP_PROPS": SKIP_PROPS, "prop_entry": prop_entry,
        "readonly": readonly, "near": lambda p, names: difflib.get_close_matches(p, names, 3), "read": lambda o, p: getattr(o, p),
        "set_value": lambda o, p, v: setattr(o, p, to_value(o, p, v)), "built_from": built_from, "along": along, "removed": removed, "shown_again": shown_again,
        "meta_moved": meta_moved, "is_group": is_group, "group_row": group_row,
        "placement": lambda base, rot: FreeCAD.Placement(base, rot), "rotation": lambda: FreeCAD.Rotation(),
        # import
        "fmt_of": fmt_of, "CORE_READERS": CORE_READERS, "SOLID_FORMATS": SOLID_FORMATS, "MESH_FORMATS": MESH_FORMATS, "core_scene": core_scene,
        "read_shape": read_shape, "mesh_module": mesh_module, "mesh_read": mesh_read, "mesh_solid": mesh_solid, "import_dxf": import_dxf,
        "svg_insert": svg_insert, "jt_reader": jt_reader, "image_plane": image_plane, "is_holder": is_holder, "import_row": import_row, "summarised": summarised,
        # export
        "is_mesh": is_mesh, "export_pick": export_pick, "EXPORTS": EXPORTS, "FC_MESH_OUT": FC_MESH_OUT, "SCENE_OUT": SCENE_OUT, "FLAT_OUT": FLAT_OUT,
        "out_path": out_path, "compound": lambda shapes: Part.Compound(shapes), "mesh_modules": mesh_modules, "solid_written": solid_written, "flat_write": flat_write,
        "scene_written": scene_written, "mesh_written": mesh_written, "scene_of_meshes": scene_of_meshes, "merged_meshes": merged_meshes,
    }
    return runners.tools(GROUP, s, helpers)
