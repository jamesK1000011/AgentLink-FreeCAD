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
from .. import paths
from ..protocol import Tool, ToolError
from ..tools import obj
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
        if not isinstance(path, str) or not path:
            raise ToolError("invalid_input", "path: a file path (relative ones go in the session's folder).")
        p = paths.local(s, path)
        if ext and not p.lower().endswith(ext.lower()):
            p = paths.made(s, p + ext)
        return p

    def doc_new(a):
        name = a.get("name") or "Unnamed"
        d = FreeCAD.newDocument(name.replace(" ", "_"))
        d.Label = name
        old = s.doc.Name
        switch(d)
        return {"document": d.Name, "label": d.Label, "previous": old, "note": "The previous document stays open: doc_switch { document } returns to it (doc_open { path } when it was saved and closed)."}

    def doc_close(a):
        refs = a.get("documents") or [s.doc.Name]
        refs = picks.ref_list(refs)
        if not isinstance(refs, list) or not all(isinstance(r, str) and r for r in refs):
            raise ToolError("invalid_input", "documents: a list of open documents by name, label or .FCStd path (the current one when left out).")
        # By the name FreeCAD lists it under, its Name, its Label, then the
        # same in any case, then its file. A Name is unique; labels are not
        # (two documents can both be labelled "Part"), so a label that
        # names several is refused with their names.
        listed = FreeCAD.listDocuments()
        docs = list(listed.values())
        picked = []
        for r in refs:
            rp = os.path.abspath(where(r)) if r.lower().endswith(".fcstd") else None
            d = listed.get(r) or next((x for x in docs if x.Name == r), None)
            if d is None:
                hits = [x for x in docs if x.Label == r] or [x for x in docs if r.lower() in (x.Name.lower(), x.Label.lower())] \
                    or [x for x in docs if rp and os.path.abspath(x.FileName or "") == rp]
                if len(hits) > 1:
                    raise ToolError("invalid_input", f"{r!r}: {len(hits)} open documents have that label — give the name in brackets: {doc_names(hits)}.")
                d = hits[0] if hits else None
            if d is None:
                # The session's own document under the name session_state gave.
                try:
                    if r in (s.doc.Name, s.doc.Label):
                        d = s.doc
                except Exception:  # noqa: BLE001 - the session's document is gone
                    d = None
            if d is None:
                raise ToolError("not_found", f"{r!r}: no open document by that name, label or path — open, as label (name): {doc_names(docs)}. doc_switch with no arguments lists them with their files.")
            if not any(d.Name == x.Name for x in picked):
                picked.append(d)

        def changed(d):
            # Never saved and not empty counts too: headless has no * on a tab.
            from ..store import is_changed

            return is_changed(d) or (not d.FileName and len(d.Objects) > 0)

        unsaved = [d.Label for d in picked if changed(d)]
        if unsaved and not a.get("discard"):
            # which objects say so, where FreeCAD's touched marks are all there is to go by
            from ..store import touched_since_save

            marks = "; ".join(f"{d.Label}: {', '.join(t[:5])}" for d in picked for t in [touched_since_save(d)] if t and d.Label in unsaved)
            raise ToolError("invalid_state", "Changed since saved: " + ", ".join(unsaved) + (f" (objects marked changed — {marks})" if marks else "") + " — nothing was closed. doc_save first (doc_switch { document } to each, then doc_save), or doc_close { documents, discard: true } closes without saving and the changes are lost.")
        closed = []
        try:
            current = s.doc.Name
        except Exception:  # already gone
            current = None
        for d in picked:
            closed.append(d.Label)
            FreeCAD.closeDocument(d.Name)
        still = FreeCAD.listDocuments()
        left = list(still.values())
        if current not in still:
            # Back to the document the session came from (the latest one still
            # open), as doc_new's "previous" promised: FreeCAD's list is by name,
            # and its last entry was a document this work never touched.
            back = next((still[n] for n in reversed(s.__dict__.get("doc_trail", [])) if n in still), None)
            switch(back or (left[-1] if left else FreeCAD.newDocument("Unnamed")))
        # Two open documents may share a label (two files of one name): each
        # is then listed as "Label (Name)", so one document does not read as
        # listed twice.
        out = {"closed": closed, "document": s.doc.Name, "label": s.doc.Label, "open": open_labels(FreeCAD.listDocuments().values())}
        if unsaved:
            out["discarded"] = unsaved
            out["note"] = "Closed without saving (discard: true): the changes since each one's last save are gone."
        return out

    def doc_open(a):
        if a.get("recent") and not a.get("path"):
            # The window's File › Recent files, headless (O): from settings.
            g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/RecentFiles")
            files = []
            for i in range(int(g.GetInt("RecentFiles", 4) or 4) + 20):
                f = g.GetString(f"MRU{i}", "")
                if f:
                    files.append({"path": f, "exists": os.path.isfile(f)})
            return {"recent": files, "note": "doc_open { path } opens one." if files else "No recent files."}
        if not a.get("path"):
            raise ToolError("invalid_input", "path: the .FCStd file to open (relative: in the session's folder), or recent: true to list the recent files.")
        p = where(a.get("path"))
        if not os.path.isfile(p):
            raise ToolError("not_found", f"{p}: no such file — doc_open {{ recent: true }} lists the recent files; a relative path is looked for in the session's folder.")
        if not p.lower().endswith(".fcstd"):
            raise ToolError("invalid_input", f"{os.path.basename(p)}: doc_open opens FreeCAD documents (.FCStd) — import_file brings STEP, STL and the rest into this one.")
        d = next((x for x in FreeCAD.listDocuments().values() if os.path.abspath(x.FileName or "") == os.path.abspath(p)), None)
        fresh = d is None
        if d is None:
            try:
                d = FreeCAD.openDocument(p)
            except Exception as e:
                raise ToolError("failed", f"FreeCAD could not open {p}: {e}")
        # A document just opened, or one open with no changes, is as its file
        # after the recompute too: left unchanged (FreeCAD 1.1 marked it
        # modified, so a restart brought a saved file back as a recovered copy).
        from ..store import _unchanged, is_changed

        was = False if fresh else is_changed(d)
        d.recompute()
        if not was:
            _unchanged(d)
        switch(d)
        return {"document": d.Name, "label": d.Label, "path": p, "objects": len(d.Objects), "bodies": [o.Label for o in s.bodies()], "errors": errors(d),
                **({} if fresh else {"note": "It was open already: the open document is used as it stands (its unsaved changes kept), not read again from the file — doc_revert goes back to the file."})}

    def doc_save(a):
        d = s.doc
        label_was = d.Label
        if a.get("path"):
            p = where(a["path"], ".FCStd")
            # Another model's file is not this document's to write over.
            mine = os.path.abspath(d.FileName) if d.FileName else None
            if os.path.exists(p) and os.path.abspath(p) != mine and not a.get("overwrite"):
                raise ToolError("invalid_input", f"{p} is another FreeCAD document already there: another name, or overwrite: true once the person says to replace it.")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            d.saveAs(p)
        elif d.FileName:
            d.save()
            p = d.FileName
        else:
            p = where(f"{d.Label or d.Name}.FCStd")
            if os.path.exists(p) and not a.get("overwrite"):
                base = p[:-6]
                k = 2
                while os.path.exists(f"{base} {k}.FCStd"):
                    k += 1
                p = f"{base} {k}.FCStd"
            d.saveAs(p)
        saved(d)
        out = {"document": d.Name, "label": d.Label, "path": p, "bytes": os.path.getsize(p), **modified_state(d)}
        if d.Label != label_was:
            # FreeCAD's saveAs relabels the document after the file.
            out["labelWas"] = label_was
            out["note"] = f"Saved under a new file name, so FreeCAD relabelled the document {d.Label!r} (it was {label_was!r}); its name {d.Name!r} stays."
        return out

    def object_list(a):
        kind = (a.get("type") or "").lower()
        out = []
        for o in s.doc.Objects:
            if o.Name == "AgentLinkRecords":
                continue  # Agent Link's own records (setups, specs): bookkeeping, not a part
            if kind and kind not in o.TypeId.lower():
                continue
            e = {"name": o.Name, "label": o.Label, "type": o.TypeId}
            if hasattr(o, "Visibility"):
                e["visible"] = bool(o.Visibility)
            # an object linked twice (a group that also binds to it) once
            parents = list(dict.fromkeys(p.Label for p in o.InList))
            if parents:
                e["parents"] = parents
            sh = getattr(o, "Shape", None)
            if isinstance(sh, Part.Shape) and not sh.isNull():
                e["shape"] = geo.stats(sh) if sh.Solids else {"faces": len(sh.Faces), "edges": len(sh.Edges), "box": geo.box_of(sh)["size"]}
            elif hasattr(o, "Mesh"):
                e["mesh"] = {"triangles": o.Mesh.CountFacets, "closed": o.Mesh.isSolid()}
            st = list(getattr(o, "State", []) or [])
            if "Invalid" in st or "Error" in st:
                e["error"] = True
            out.append(e)
        return {"document": s.doc.Name, "count": len(out), "objects": out}

    def object_get(a):
        o = picks.find(s.doc, a.get("object"))
        flt = a.get("filter")
        names = [p for p in o.PropertiesList if p not in SKIP_PROPS]
        if isinstance(flt, list):
            names = [p for p in names if p in flt]
        elif isinstance(flt, str) and flt:
            names = [p for p in names if flt.lower() in p.lower() or flt.lower() in (o.getGroupOfProperty(p) or "").lower()]
        props = {}
        for p in names:
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
            props[p] = entry
        if not props and flt:
            raise ToolError("not_found", f"filter {flt!r}: no property of {o.Label} matches — object_get {{ object }} without filter lists them all.")
        return {"name": o.Name, "label": o.Label, "type": o.TypeId, "properties": props}

    def object_set(a):
        o = picks.find(s.doc, a.get("object"))
        vals = a.get("values")
        if not isinstance(vals, dict) or not vals:
            raise ToolError("invalid_input", "values: { Property: value, … } — object_get gives the names and types.")
        props = set(o.PropertiesList)
        for p, v in vals.items():
            if p not in props:
                near = difflib.get_close_matches(p, list(props), 3)
                raise ToolError("not_found", f"values.{p}: {o.Label} has no such property{' — did you mean ' + ', '.join(near) if near else ''}. object_get lists them.")
            if readonly(o, p):
                raise ToolError("invalid_input", f"values.{p}: read-only on {o.Label} (FreeCAD computes it)." + (" show { objects, visible } shows or hides it." if p == "Visibility" else ""))
        before = {p: picks.json_safe(getattr(o, p)) for p in vals}
        # Refused only for what this change broke (M4): the object and what
        # is built from it, not already broken before. Other objects failing
        # in the same recompute are said as a note.
        was_broken = {e["object"] for e in errors(s.doc)}
        for p, v in vals.items():
            try:
                setattr(o, p, to_value(o, p, v))
            except ToolError:
                raise
            except Exception as e:
                raise ToolError("invalid_input", f"values.{p}: FreeCAD refused {v!r} — {e}")
        # Only this object and what is built from it: an unrelated object
        # (a heavy mesh left touched) is not re-run by this call.
        picks.recompute_scoped(s.doc, [o])
        errs = errors(s.doc)
        try:
            mine = {o.Label} | {x.Label for x in o.InListRecursive}
        except Exception:
            mine = {o.Label}
        own = [e for e in errs if e["object"] in mine and e["object"] not in was_broken]
        if own:
            raise ToolError("failed", f"The recompute failed after setting it: {own[0]['object']}: {own[0]['error']} — nothing was kept.")
        s.snapshot("object_set")
        sets = {}
        same = []
        for p in vals:
            after = picks.json_safe(getattr(o, p))
            sets[p] = {"from": before[p], "to": after}
            if after == before[p]:
                sets[p]["unchanged"] = True
                same.append(p)
        out = {"object": o.Label, "set": sets, "step": len(s.steps)}
        if same:
            out["unchanged"] = same
            out["warning"] = f"{', '.join(same)}: unchanged — the value is what it was (the same value given, or FreeCAD kept its own)."
        if errs:
            out["note"] = "Set. Other objects failed in the same recompute, not from this change: " + "; ".join(f"{e['object']}: {e['error']}" for e in errs[:4])
        return out

    def _along(objs):
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

    def object_delete(a):
        names = a.get("objects")
        names = picks.ref_list(names, "objects: the names or labels to delete.")
        objs = [picks.find(s.doc, n) for n in names]
        extra, show, labels = _along(objs)
        going = {o.Name for o in objs} | {o.Name for o in extra}
        for o in objs:
            users = [p.Label for p in o.InList if p.Name not in going]
            if users and not a.get("force"):
                raise ToolError("invalid_state", f"{o.Label} is used by {', '.join(users)}: name those in objects too, or force: true deletes it and leaves them broken (FreeCAD removes it without asking; they fail at the next recompute). Nothing was deleted.")
        deleted = [o.Label for o in objs]
        along = [o.Label for o in extra]
        names_out = [o.Name for o in objs] + [o.Name for o in extra]
        for n in names_out:
            if s.doc.getObject(n) is not None:
                try:
                    s.doc.removeObject(n)
                except Exception:
                    pass
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

        def answer():
            out = {"deleted": deleted, "errors": errors(s.doc)}
            if along:
                out["alongWith"] = along
                out["alongNote"] = "Made for what was deleted and used by nothing else: deleted with it."
            if shown:
                out["shownAgain"] = shown
            if renamed:
                out["renamed"] = renamed
            return out

        return picks.finish(s, "object_delete", answer)

    def object_rename(a):
        o = picks.find(s.doc, a.get("object"))
        label = a.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ToolError("invalid_input", "label: the new name.")
        other = next((x for x in s.doc.Objects if x is not o and x.Label == label), None)
        if other is not None:
            raise ToolError("invalid_input", f"label {label!r}: taken by {other.Name} ({other.TypeId}) — give another label (FreeCAD would otherwise change it itself to keep labels apart).")
        old = o.Label
        o.Label = label
        if old in s.meta:
            s.meta[label] = s.meta.pop(old)
        s.snapshot("object_rename")
        return {"name": o.Name, "from": old, "to": o.Label, **({"note": "Setups, specs and waivers kept by the old label are not renamed with it."} if old != o.Label else {"unchanged": True}),
                **({"warning": f"FreeCAD changed the label to {o.Label!r} (not {label!r}) to keep it apart from another."} if o.Label != label else {})}

    def object_group(a):
        d = s.doc
        action = a.get("action", "add")
        if action == "list":
            out = []
            for g in d.Objects:
                if g.TypeId != "App::Origin" and (g.isDerivedFrom("App::DocumentObjectGroup") or g.TypeId in ("App::Part", "App::Link")):
                    row = {"group": g.Label, "type": g.TypeId}
                    if hasattr(g, "Group"):
                        row["holds"] = [x.Label for x in g.Group]
                    if g.TypeId == "App::Link":
                        lo = g.getLinkedObject(False) if hasattr(g, "getLinkedObject") else getattr(g, "LinkedObject", None)
                        row["links"] = lo.Label if lo is not None else None
                    out.append(row)
            return {"groups": out}
        if action == "link":
            src = picks.find(d, a.get("object"), "object")
            n = a.get("count", 1)
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 500:
                raise ToolError("invalid_input", "count: how many links, 1 … 500.")
            step_, at_ = picks.vec3(a.get("step"), "step", (0, 0, 0)), picks.vec3(a.get("at"), "at", (0, 0, 0))
            made = []
            for i in range(n):
                ln = d.addObject("App::Link", "Link")
                ln.setLink(src)
                ln.Label = s.unique(a.get("name") or f"{src.Label} link")
                ln.LinkPlacement = FreeCAD.Placement(at_ + step_ * i, FreeCAD.Rotation())
                made.append(ln.Label)
            d.recompute()
            s.snapshot("object_group")
            return {"links": made, "of": src.Label, "note": "Links show the original where placed and follow its edits; they weigh nothing in the file. A link's placement stands in for the original's own (LinkTransform is false): at is where the link is, not an offset from the original."}
        name = a.get("group")
        if action not in ("add", "remove", "dissolve"):
            raise ToolError("invalid_input", "action: add | remove (objects to or from group) | dissolve (group) | link (object, count, at, step) | list.")
        if not name:
            raise ToolError("invalid_input", "group: the group's label (made if new for add) — object_group { action: \"list\" } names the ones there are.")
        g = next((x for x in d.Objects if x.Label == name and hasattr(x, "Group")), None)
        kind = a.get("kind", "folder")
        if kind not in ("folder", "part"):
            raise ToolError("invalid_input", "kind: folder (a plain group) | part (an App::Part that moves as one).")
        objs = [picks.find(d, r, "objects") for r in (picks.ref_list(a.get("objects")) or [])]
        if g is None:
            if action != "add":
                have = ", ".join(x.Label for x in d.Objects if hasattr(x, "Group") and x.TypeId != "App::Origin") or "none"
                raise ToolError("not_found", f"group {name!r}: no such group to {action} — the groups: {have}.")
            g = d.addObject("App::Part" if kind == "part" else "App::DocumentObjectGroup", "Group")
            g.Label = s.unique(name, g)
        if action == "remove" and not objs and a.get("visible") is None:
            raise ToolError("invalid_input", "objects: the names or labels to take out of the group.")
        if action == "add":
            for o in objs:
                if o is g:
                    continue
                for p in o.InList:
                    if hasattr(p, "Group") and p is not g and o in p.Group and (p.isDerivedFrom("App::DocumentObjectGroup") or p.TypeId == "App::Part"):
                        p.removeObject(o)
                g.addObject(o)
        elif action == "remove":
            for o in objs:
                if o not in g.Group:
                    raise ToolError("invalid_input", f"{o.Label} is not in {g.Label} (it holds {', '.join(x.Label for x in g.Group) or 'nothing'}).")
                g.removeObject(o)
        elif action == "dissolve":
            objs_kept = [o for o in g.Group if o.TypeId != "App::Origin"]
            for o in objs_kept:
                g.removeObject(o)
            d.removeObject(g.Name)
            d.recompute()
            s.snapshot("object_group")
            return {"dissolved": name, "kept": [o.Label for o in objs_kept]}
        if a.get("visible") is not None:
            for o in g.Group:
                try:
                    o.Visibility = bool(a["visible"])
                except Exception:
                    pass
        d.recompute()
        s.snapshot("object_group")
        return {"group": g.Label, "type": g.TypeId, "holds": [x.Label for x in g.Group]}

    def recompute(a):
        frozen = bool(getattr(s.doc, "RecomputesFrozen", False))
        if a.get("force"):
            for o in s.doc.Objects:
                o.touch()
            try:
                # force also gets past the document's skip-recompute switch.
                n = s.doc.recompute(None, True)
            except TypeError:
                n = s.doc.recompute()
        else:
            n = s.doc.recompute()
        errs = errors(s.doc)
        s.snapshot("recompute")
        out = {"recomputed": n, "ok": not errs, "errors": errs}
        still = [o.Label for o in s.doc.Objects if "Touched" in (getattr(o, "State", None) or [])][:10]
        if still:
            out["stillTouched"] = still
        if n == 0 and frozen and not a.get("force"):
            out["note"] = "Nothing was recomputed: the document's skip-recompute switch is on (object_freeze { skipRecompute: false } turns it off; force: true recomputes anyway)."
        elif still:
            out["note"] = "Some objects stay marked touched after the recompute (a frozen object does; so does one whose input failed): see errors."
        return out

    def import_file(a):
        p = where(a.get("path"))
        if not os.path.isfile(p):
            raise ToolError("not_found", f"{p}: no such file — a relative path is looked for in the session's folder; give the whole path.")
        fmt = fmt_of(p)
        d = s.doc
        before = {o.Name for o in d.Objects}
        base = a.get("name") or os.path.splitext(os.path.basename(p))[0]
        made = []
        took = None
        core_made, core_why = [], None
        if fmt in CORE_READERS and a.get("units") is None and a.get("up") is None and not a.get("solid"):
            core_made, core_why = core_scene(d, p, fmt, before)
        if core_made:
            made = core_made
            took = {"reader": CORE_READERS[fmt][1]}
        elif fmt in SOLID_FORMATS:
            sh = Part.Shape()
            try:
                sh.read(p)
            except Exception as e:
                raise ToolError("failed", f"{os.path.basename(p)} could not be read as {fmt.upper()}: {e}")
            pieces = sh.Solids if (a.get("split") and len(sh.Solids) > 1) else [sh]
            for i, piece in enumerate(pieces):
                o = d.addObject("Part::Feature", "Import")
                o.Label = s.unique(base if len(pieces) == 1 else f"{base} {i + 1}")
                o.Shape = piece
                made.append(o)
        elif fmt in MESH_FORMATS:
            import Mesh

            try:
                if fmt in MORE_MESH:
                    from .. import meshformats

                    V, F, took = meshformats.read(p, a.get("units"), a.get("up"))
                    took = {**(took or {}), "reader": "Agent Link's own reader (meshformats)", **({"coreNotUsed": core_why} if core_why else {})}
                    m = Mesh.Mesh()
                    m.addFacets([[tuple(V[i]) for i in t] for t in F.tolist()])
                else:
                    m = Mesh.Mesh(p)
            except Exception as e:
                raise ToolError("failed", f"{os.path.basename(p)} could not be read as a mesh: {e}")
            if m.CountFacets == 0:
                raise ToolError("failed", f"{os.path.basename(p)}: no triangles read.")
            # Predictable: a mesh file comes in as a mesh (Mesh::Feature)
            # whatever its size; a body made of its triangles only when the
            # caller asks (solid: true). It used to turn closed meshes of up
            # to 20000 triangles into bodies on its own, so the same kind of
            # file came in as one type or the other by its triangle count.
            want_solid = a.get("solid") is True
            if want_solid:
                if m.CountFacets > 200000:
                    raise ToolError("invalid_input", f"solid: {m.CountFacets} triangles is too many to turn into a solid here — import it as a mesh (solid: false), or decimate it first.")
                sh = Part.Shape()
                sh.makeShapeFromMesh(m.Topology, 0.05)
                try:
                    sh = Part.Solid(Part.Shell(sh.Faces))
                    if sh.Volume < 0:
                        sh.reverse()
                    sh = geo.clean(sh)
                except Exception:
                    pass
                o = d.addObject("Part::Feature", "Import")
                o.Shape = sh
            else:
                o = d.addObject("Mesh::Feature", "Import")
                o.Mesh = m
            o.Label = s.unique(base)
            made.append(o)
        elif fmt == "dxf":
            made, took = import_dxf(d, p, base, before, a)
        elif fmt == "fcstd":
            raise ToolError("invalid_input", "A FreeCAD document: doc_open { path } opens it.")
        elif fmt == "svg":
            try:
                import importSVG

                importSVG.insert(p, d.Name)
            except Exception as e:
                raise ToolError("unavailable", f"SVG import failed here ({e}): open it in the FreeCAD window (Draft's importer).")
            made = [o for o in d.Objects if o.Name not in before]
            if not made:
                raise ToolError("failed", f"{os.path.basename(p)}: no paths, shapes or text read.")
        elif fmt == "jt":
            try:
                import JtReader
            except ImportError:
                raise ToolError("unavailable", "JT needs FreeCAD's JtReader, which this build leaves out: export STEP from the program that made it.") from None
            try:
                JtReader.insert(p, d.Name)
            except Exception as e:
                raise ToolError("failed", f"{os.path.basename(p)} could not be read as JT: {e}") from None
            made = [o for o in d.Objects if o.Name not in before]
        elif fmt in ("png", "jpg", "jpeg", "bmp"):
            made = [image_plane(d, p, s.unique(base), a)]
        elif fmt in ("pdf", "dwg", "ifc"):
            raise ToolError("unavailable", f"{fmt.upper()} comes in through the FreeCAD window's importers (Draft, BIM, image planes), not headless here: open it there.")
        else:
            raise ToolError("invalid_input", f"{fmt or 'no extension'}: import_file reads STEP, IGES, BREP, STL, OBJ, 3MF, PLY, OFF, AMF, glTF/GLB, Collada, VRML, 3DS, DXF, SVG and PNG/JPG/BMP pictures; FBX: export it as glTF from the program that made it.")
        picks.recompute_scoped(d, made)
        s.snapshot("import_file")
        out = []
        # Groups and layers hold the drawing, they are not drawing: counted,
        # not listed one by one.
        holders = [o for o in made if is_holder(o)]
        made = [o for o in made if not is_holder(o)]
        for o in made:
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
            out.append(e)
        res = {"path": p, "format": fmt, **({"read": took} if took else {}), "count": len(out), "step": len(s.steps)}
        res.update(summarised(out, holders))
        return res

    def export_pick(ref):
        # A mesh (Mesh::Feature) is exported as it is, never refused for
        # having no shape.
        o = picks.find(s.doc, ref, "object")
        if is_mesh(o):
            return o
        return picks.shaped(s.doc, ref)

    def export(a):
        names = a.get("objects")
        names = picks.ref_list(names)
        objs = [export_pick(n) for n in names] if names else [s.body(None)]
        fmt = (a.get("format") or "").lower()
        if not fmt and a.get("path"):
            fmt = fmt_of(a["path"])
        meshes = [o for o in objs if is_mesh(o)]
        fmt = fmt or ("stl" if meshes and len(meshes) == len(objs) else "step")
        if fmt not in EXPORTS:
            raise ToolError("invalid_input", f"format: one of {', '.join(EXPORTS)}.")
        if meshes and fmt not in FC_MESH_OUT and fmt not in SCENE_OUT:
            raise ToolError("invalid_input", f"{', '.join(o.Label for o in meshes)}: a mesh, written as {', '.join(list(FC_MESH_OUT) + list(SCENE_OUT))} — not {fmt.upper()}. For {fmt.upper()}, import_file the mesh again with solid: true (a body of its triangles) first.")
        if meshes:
            return export_meshes(objs, fmt, a)
        ext = {"step": ".step", "iges": ".iges", "brep": ".brep", **FC_MESH_OUT, **SCENE_OUT, **FLAT_OUT}[fmt]
        p = where(a.get("path") or (objs[0].Label.replace(" ", "_") + ext))
        known = {*(SOLID_FORMATS.get(fmt) or ()), *(MESH_FORMATS.get(fmt) or ()), ext.lstrip(".")}
        if os.path.splitext(p)[1].lower().lstrip(".") not in known:
            p += ext
        os.makedirs(os.path.dirname(p), exist_ok=True)
        shape = objs[0].Shape if len(objs) == 1 else Part.Compound([o.Shape for o in objs])
        vol = sum(o.Shape.Volume for o in objs if o.Shape.Solids)
        if fmt in SOLID_FORMATS:
            {"step": shape.exportStep, "iges": shape.exportIges, "brep": shape.exportBrep}[fmt](p)
            back = Part.Shape()
            back.read(p)
            verify = {"volume": round(back.Volume, 2), "volumeDiff": round(abs(back.Volume - vol), 3), "solids": len(back.Solids), "faces": len(back.Faces)}
            if fmt == "iges" and not back.Solids:
                verify["note"] = "IGES carries faces, not solids, as most readers take it."
        elif fmt in FLAT_OUT:
            verify = flat_write(objs, fmt, p, a)
        else:
            import Mesh
            import MeshPart

            tol = picks.number(a, "tolerance", 0.01, gt=0, msg="tolerance: the chord error, above 0 mm.")

            def mesh_of(sh):
                return MeshPart.meshFromShape(Shape=sh, LinearDeflection=tol, AngularDeflection=0.0873, Relative=False)

            if fmt in SCENE_OUT:
                from .. import meshformats

                parts, tris = [], 0
                cols = a.get("colors") or {}
                for o in objs:
                    m = mesh_of(o.Shape)
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
                verify = {"triangles": int(len(F)), "trianglesWritten": tris, "objects": info["nodes"],
                          "size": [round(float(x), 2) for x in span], "sizeOfBodies": [round(want.XLength, 2), round(want.YLength, 2), round(want.ZLength, 2)],
                          "note": "Metres, Y up, as glTF and Collada keep them; a mesh and colour per object (colors {label: \"#rrggbb\"})."}
            else:
                m = mesh_of(shape)
                m.write(p)
                try:
                    if fmt == "wrl":
                        from .. import meshformats

                        V, F, _info = meshformats.read(p, "mm", "z")  # FreeCAD writes it as the document has it
                        back = Mesh.Mesh()
                        back.addFacets([[tuple(V[i]) for i in tr] for tr in F.tolist()])
                    else:
                        back = Mesh.Mesh(p)
                    verify = {"triangles": back.CountFacets, "volume": round(back.Volume, 2), "volumeDiff": round(abs(back.Volume - vol), 2), "closed": back.isSolid()}
                except Exception:
                    verify = {"triangles": m.CountFacets, "readBack": f"written; FreeCAD does not read {fmt.upper()} back to check it"}
        return {"objects": [o.Label for o in objs], "format": fmt, "path": p, "bytes": os.path.getsize(p), "verify": verify}

    def export_meshes(objs, fmt, a):
        # Meshes as they are (no re-meshing), with any shaped objects
        # tessellated beside them; one file.
        import Mesh
        import MeshPart

        tol = picks.number(a, "tolerance", 0.01, gt=0, msg="tolerance: the chord error, above 0 mm.")
        ext = {**FC_MESH_OUT, **SCENE_OUT}[fmt]
        p = where(a.get("path") or (objs[0].Label.replace(" ", "_") + ext))
        known = {*(MESH_FORMATS.get(fmt) or ()), ext.lstrip(".")}
        if os.path.splitext(p)[1].lower().lstrip(".") not in known:
            p += ext
        os.makedirs(os.path.dirname(p), exist_ok=True)

        def mesh_of(o):
            if is_mesh(o):
                m = o.Mesh
                pl = getattr(o, "Placement", None)
                # Topology gives the points placed, so a moved mesh is written
                # where it stands, also when merged with others.
                return m.copy() if pl is None or pl.isIdentity() else Mesh.Mesh(m.Topology)
            return MeshPart.meshFromShape(Shape=o.Shape, LinearDeflection=tol, AngularDeflection=0.0873, Relative=False)

        if fmt in SCENE_OUT:
            from .. import meshformats

            parts, tris = [], 0
            cols = a.get("colors") or {}
            for o in objs:
                pts, fs = mesh_of(o).Topology
                rgba = colour(cols.get(o.Label) or cols.get(o.Name))
                parts.append({"name": o.Label, "V": np.array([tuple(v) for v in pts], float).reshape(-1, 3), "F": np.array(fs, int).reshape(-1, 3), **({"rgba": rgba} if rgba else {})})
                tris += len(fs)
            meshformats.write(p, parts)
            V, F, info = meshformats.read(p)
            verify = {"triangles": int(len(F)), "trianglesWritten": tris, "objects": info["nodes"], "note": "Metres, Y up, as glTF and Collada keep them."}
        else:
            m = Mesh.Mesh()
            for o in objs:
                m.addMesh(mesh_of(o))
            m.write(p)
            try:
                if fmt == "wrl":
                    from .. import meshformats

                    V, F, _info = meshformats.read(p, "mm", "z")
                    back = Mesh.Mesh()
                    back.addFacets([[tuple(V[i]) for i in tr] for tr in F.tolist()])
                else:
                    back = Mesh.Mesh(p)
                verify = {"triangles": back.CountFacets, "trianglesWritten": m.CountFacets, "closed": back.isSolid()}
                if back.isSolid():
                    verify["volume"] = round(back.Volume, 2)
            except Exception:
                verify = {"triangles": m.CountFacets, "readBack": f"written; FreeCAD does not read {fmt.upper()} back to check it"}
        return {"objects": [o.Label for o in objs], "meshes": [o.Label for o in objs if is_mesh(o)], "format": fmt, "path": p, "bytes": os.path.getsize(p), "verify": verify}

    objref = {"type": "string", "description": "An object's name or label."}
    return [
        Tool("doc_new", "Start a new, empty FreeCAD document and work in it from now on. name becomes its label; FreeCAD makes the internal name from it (spaces and odd characters become _, a number is added when taken): the reply's document is that name, label the label. The document before stays open, unsaved changes and all (doc_switch returns to it). Not undoable, and not in a batch's rollback.", obj({"name": {"type": "string"}}), doc_new),
        Tool("doc_close", "Close open documents. documents: each by internal name, label or .FCStd path (the current one when left out); a label two documents share is refused with their names. A document changed since its save (or never saved and not empty) is refused and nothing is closed: doc_save first, or discard: true closes WITHOUT saving and the changes are lost (there is no save input here). Work moves to another open document (reply: document, label, open — the labels of the documents still open, each as \"Label (Name)\" where two share a label; discarded lists what lost changes). Not undoable.",
             obj({"documents": {"type": "array", "items": {"type": "string"}}, "discard": {"type": "boolean"}}), doc_close),
        Tool("doc_open", "Open a FreeCAD document (path, .FCStd; relative: the session's folder) and work in it from now on. It is recomputed and each object's error listed (errors); a file just opened is left unmodified by that. A file already open is not read again: the open document is used with its unsaved changes (doc_revert goes back to the file). Other formats: import_file. recent: true lists the recent files instead. Reply: document (internal name), label, objects, bodies, errors. Not undoable.", obj({"path": {"type": "string"}, "recent": {"type": "boolean"}}), doc_open),
        Tool("doc_save", "Save the current document as .FCStd: path (relative goes in the session's folder; .FCStd added), else where it was saved, else <label>.FCStd there (\"<label> 2.FCStd\" … when taken). Saving under a new file name makes FreeCAD relabel the document after the file (reply: label, labelWas); its internal name stays. Never over another document's file unless overwrite: true — ask the person first. Materials, setups and notes the tools recorded are saved with it. Reply: path, bytes, touched / modified.", obj({"path": {"type": "string"}, "overwrite": {"type": "boolean"}}), doc_save),
        Tool("object_list", "Every object in the document: name (internal, fixed for life, unique), label (what the person sees and may rename), type, visible, parents (what uses it) and its shape (volume mm³, area, faces, solids, size for a solid; faces and edges else) or mesh; error: true marks a failed one (recompute gives the reason). type: part of the type to keep (\"Part::\", \"Sketch\"). Tools take either name or label; the name wins when both match. Changes nothing.", obj({"type": {"type": "string"}}), object_list),
        Tool("object_get", "One object's properties: value (mm, degrees; placements as { at, axis, angle }; links by label; a shape as its stats; lists cut at 50), type, readOnly (FreeCAD computes it: object_set refuses it), hidden (not shown in FreeCAD's property editor), choices for an enumeration. filter: a word in the property's name or group (\"Placement\", \"Base\"), or a list of exact names — use it, a feature has dozens. Changes nothing.", obj({"object": objref, "filter": {}}, ["object"]), object_get),
        Tool("object_set", "Set properties of an object: values { Length: 20, Placement: { at, axis, angle } (or FreeCAD's Base, Axis, Angle, Rotation; what is left out is kept), Refine: true, Base: \"Box\" (a link, by name or label; null clears), Mode: \"…\" } — each converted to its type: numbers are mm and degrees, or a string with a unit (\"1 in\", \"30 deg\") for lengths, angles and other quantities (not plain floats); whole numbers for integers and percents; enumerations checked against their choices; vectors [x,y,z]. Read-only properties, links to faces or edges and property names it does not have are refused (object_get lists names, types, choices). Recomputes the object and what is built from it; refused with nothing kept when that fails. Reply: set { from, to }, unchanged, health. Trap: a plain shape (Part::Feature from a boolean or import) has no sizes, only Placement; Label is set with object_rename.", obj({"object": objref, "values": {"type": "object"}}, ["object", "values"]), object_set, changes=True),
        Tool("object_delete", "Delete objects (objects: names or labels). Refused, nothing deleted, while another object uses one — FreeCAD itself deletes without asking and leaves the users broken, which force: true allows. Recomputes and lists any error. A PartDesign Body goes with its own features and Origin, and a boolean's result with the helpers made for it alone (alongWith names them); the inputs it hid are shown again and given their names back (shownAgain, renamed). Reply: deleted, errors, health.", obj({"objects": {}, "force": {"type": "boolean"}}, ["objects"]), object_delete, changes=True),
        Tool("object_rename", "Give an object a new label; its internal name never changes (FreeCAD fixes it at creation), and both keep working as references. A label another object has is refused (FreeCAD would alter it to stay unique unless its duplicate-labels preference is on). Expressions that use the label follow it. Trap: setups, specs and waivers keep the old label. Reply: name, from, to.", obj({"object": objref, "label": {"type": "string"}}, ["object", "label"]), object_rename, changes=True),
        Tool("object_group", "Organise the document: action add | remove (objects into or out of group — made if new for add; kind folder (App::DocumentObjectGroup, placement-less) | part (App::Part: its Placement moves everything in it)) — an object sits in one group, so add takes it out of the one before; dissolve (the group goes, its objects stay); link (count App::Link copies of object, the first at, each step [dx,dy,dz] further — light copies that follow the original; at is the link's whole placement, not an offset from the original's); list (groups, parts and links with what they hold). visible: false hides a group's objects. Reply: group, type, holds.",
             obj({"action": {"type": "string", "enum": ["add", "remove", "dissolve", "link", "list"]}, "group": {"type": "string"}, "kind": {"type": "string", "enum": ["folder", "part"]}, "objects": {"type": "array", "items": {"type": "string"}},
                  "object": {"type": "string"}, "count": {"type": "integer"}, "at": {"type": "array", "items": {}}, "step": {"type": "array", "items": {}}, "visible": {"type": "boolean"}, "name": {"type": "string"}}), object_group, changes=True),
        Tool("recompute", "Recompute the document and list each object that failed, with FreeCAD's reason (errors). Only touched objects and what is built from them are redone; force: true marks everything touched and recomputes it all, also past the document's skip-recompute switch (slow on a big model). Reply: recomputed (how many objects FreeCAD ran; 0 with nothing touched or with skip-recompute on, said in note), ok, errors, stillTouched. Tools that change the model recompute by themselves: this is for after object_freeze, an import or a doubt.", obj({"force": {"type": "boolean"}}), recompute, changes=True),
        Tool("import_file", "Bring a file into the current document (path; relative: the session's folder), by its extension. STEP, IGES, BREP: one body with the file's whole shape (split: true a body per solid); colours, part names and assembly structure are not read. STL, OBJ, 3MF, PLY, OFF, AMF and glTF/GLB, Collada, VRML 2, 3DS (every mesh node flattened into one, mm, Z up; units and up override what the format says; read says what was taken): a mesh (Mesh::Feature) unless solid: true asks for a body of its triangles (up to 200000; slow past a few tens of thousands). DXF: wires, arcs, circles, splines by layer (Agent Link's reader; a drawing with blocks, text or dimensions through FreeCAD's) and SVG as Draft geometry — many objects come back counted, the first few listed. JT where this FreeCAD has its reader. PNG, JPG, BMP: an image plane width mm wide on XY, to trace over. PDF, DWG, IFC need the FreeCAD window; FBX: export it as glTF; .FCStd: doc_open (doc_merge to bring its objects in). name: the label. Reply: format, count, objects (name, label, type, volume or mesh), health.", obj({"path": {"type": "string"}, "name": {"type": "string"}, "split": {"type": "boolean"}, "solid": {"type": "boolean"}, "units": {"type": "string", "enum": ["mm", "cm", "m", "in"]}, "up": {"type": "string", "enum": ["x", "y", "z"]}, "width": {"type": "number"}}, ["path"]), import_file, changes=True),
        Tool("export", "Write objects (the one body when left out; several go as one compound) and read it back (verify). Meshes (Mesh::Feature) go as they are to the mesh and scene formats (STL by default). Solids: STEP, IGES, BREP. One mesh: STL, OBJ, 3MF, PLY, OFF, VRML (wrl), X3D. A scene, a mesh per object with colors {label: \"#rrggbb\"}: glTF (glb, gltf), Collada (dae) — metres, Y up. 2D: DXF (R12) or SVG of a view (top | bottom | front | back | right | left | iso; hidden: true adds hidden lines on their own layer) or of a section at z mm (section) — circles and arcs kept as such, for laser and plasma cutting. format, or from path's extension; tolerance: the chord error, 0.01 mm.", obj({"objects": {}, "format": {"type": "string", "enum": list(EXPORTS)}, "path": {"type": "string"}, "tolerance": {"type": "number"}, "colors": {"type": "object"}, "view": {"type": "string", "enum": list(VIEWS)}, "hidden": {"type": "boolean"}, "section": {"type": "number"}}), export),
    ]
