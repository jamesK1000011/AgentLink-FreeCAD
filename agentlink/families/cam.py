# SPDX-License-Identifier: LGPL-2.1-or-later
# Toolpaths with FreeCAD's CAM workbench: a job round a body with its stock
# and an end mill, operations — profile, pocket, adaptive clearing, facing,
# drilling — each computed and read back (cut length, time, depth), and
# G-code written by one of FreeCAD's post-processors and checked against
# the stock. The mill family checks whether a part can be milled at all;
# this one makes the paths.

import importlib
import math
import os
import time

import FreeCAD

import Path  # noqa: F401  — FreeCAD's CAM workbench
import Path.Main.Job  # noqa: F401  — as before the tools were data: no family on a FreeCAD whose CAM has no such job
import Path.Tool.Controller  # noqa: F401

from .. import paths, runners
from ..protocol import ToolError
from . import measure as M
from . import picks

GROUP = "cam"
INFO = "Toolpaths (FreeCAD's CAM workbench): a job with stock and end mill, profile, pocket, adaptive, facing and drilling operations, G-code posted and checked."

OPS = {
    "profile": "Path.Op.Profile",
    "pocket": "Path.Op.PocketShape",
    "adaptive": "Path.Op.Adaptive",
    "face": "Path.Op.MillFace",
    "drill": "Path.Op.Drilling",
    "engrave": "Path.Op.Engrave",
    "helix": "Path.Op.Helix",
    "slot": "Path.Op.Slot",
    "deburr": "Path.Op.Deburr",
    "vcarve": "Path.Op.Vcarve",
    "thread": "Path.Op.ThreadMilling",
    "surface": "Path.Op.Surface",
    "waterline": "Path.Op.Waterline",
    "pocket3d": "Path.Op.Pocket",
    "tapping": "Path.Op.Tapping",
    "mill_facing": "Path.Op.MillFacing",
    "probe": "Path.Op.Probe",
    "custom": "Path.Op.Custom",
    "flute": "Path.Op.Flute",
}
POSTS = ["grbl", "linuxcnc", "mach3_mach4", "marlin", "smoothie", "centroid", "generic"]
RAPID = 3000.0  # mm/min, for the time estimate where the machine's is not known


def _jobs(doc):
    return [o for o in doc.Objects if o.TypeId == "Path::FeaturePython" and hasattr(o, "Operations") and hasattr(o, "Stock")]


def _job(doc, ref):
    return picks.one_of(_jobs(doc), ref, "job: say which — {labels}.", "job {ref}: the jobs are {labels}.", none="No CAM job: cam_job { body, tool } makes one.")


def _q(v, unit):
    try:
        return round(float(FreeCAD.Units.Quantity(v).getValueAs(unit)), 3)
    except Exception:
        try:
            return round(float(v), 3)
        except Exception:
            return None


CYCLES = ("G73", "G81", "G82", "G83", "G85", "G86", "G89")


def path_stats(commands, tc):
    """Lengths, depth and an estimated time of a path's moves: cutting at
    the tool controller's feeds, rapids at RAPID."""
    hf = _q(tc.HorizFeed, "mm/min") if tc is not None else None
    vf = _q(tc.VertFeed, "mm/min") if tc is not None else None
    x = y = z = None
    cut = rapid = minutes = 0.0
    zmin, zmax = math.inf, -math.inf
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    retract_initial = True
    for c in commands:
        name = c.Name.upper()
        p = c.Parameters
        if name in CYCLES and None not in (x, y, z) and "Z" in p:
            # A drilling cycle: rapid over the hole, down to R, feed to Z, back up.
            nx, ny, bottom = p.get("X", x), p.get("Y", y), p["Z"]
            r = p.get("R", z)
            top = max(z, r)
            over = math.hypot(nx - x, ny - y) + (top - z) + (top - r)
            depth = max(0.0, r - bottom)
            rapid += over + depth
            minutes += (over + depth) / RAPID + (depth / (vf or hf) if (vf or hf) else 0.0)
            cut += depth
            zmin, zmax = min(zmin, bottom), max(zmax, r)
            for k, v in enumerate((nx, ny, bottom)):
                lo[k], hi[k] = min(lo[k], v), max(hi[k], v)
            for k, v in enumerate((nx, ny, r)):
                lo[k], hi[k] = min(lo[k], v), max(hi[k], v)
            x, y, z = nx, ny, (top if retract_initial else r)
            continue
        if name in ("G98", "G99"):
            retract_initial = name == "G98"
            continue
        if name not in ("G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03"):
            continue
        nx, ny, nz = p.get("X", x), p.get("Y", y), p.get("Z", z)
        if None in (x, y, z):
            x, y, z = nx, ny, nz
            continue
        if None in (nx, ny, nz):
            continue
        d = math.dist((x, y, z), (nx, ny, nz))
        if name in ("G2", "G02", "G3", "G03") and ("I" in p or "J" in p):
            cx, cy = x + p.get("I", 0.0), y + p.get("J", 0.0)
            r = math.hypot(x - cx, y - cy)
            a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
            sweep = (a0 - a1) if name in ("G2", "G02") else (a1 - a0)
            sweep = sweep % (2 * math.pi) or 2 * math.pi
            d = math.hypot(r * sweep, nz - z)
        if name in ("G0", "G00"):
            rapid += d
            minutes += d / RAPID
        else:
            cut += d
            plunge = abs(nz - z) > 1e-9 and math.hypot(nx - x, ny - y) < 1e-9
            feed = (vf if plunge else hf) or hf or vf
            if feed:
                minutes += d / feed
            zmin, zmax = min(zmin, z, nz), max(zmax, z, nz)
            for k, v in enumerate((nx, ny, nz)):
                lo[k], hi[k] = min(lo[k], v), max(hi[k], v)
        x, y, z = nx, ny, nz
    out = {"cutMm": round(cut, 1), "rapidMm": round(rapid, 1), "minutes": round(minutes, 2)}
    if zmin < math.inf:
        out["cutZ"] = [round(zmin, 3), round(zmax, 3)]
        out["cutBox"] = {"min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi]}
    return out


def path_seen(x):
    """What a person could see of an operation's or dressup's path, told
    without a picture (round 6, cam 008-032 showed no toolpath): path {
    moves: the motion commands (G0-G3 and cycles), length: mm of them },
    shown: FreeCAD draws it (the object's Visibility, and every group it is
    in shown), and why not when it is not."""
    why = None
    try:
        cmds = list(x.Path.Commands) if getattr(x, "Path", None) is not None else []
        moves = [c for c in cmds if c.Name.upper() in ("G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03") + CYCLES]
        st = path_stats(cmds, None)
        out = {"path": {"moves": len(moves), "length": round(st["cutMm"] + st["rapidMm"], 1)}}
    except Exception as e:  # noqa: BLE001
        moves = []
        out = {"path": {"moves": 0, "length": 0.0}}
        why = f"its path could not be read ({type(e).__name__})"
    try:
        if why:
            pass
        elif not bool(getattr(x, "Visibility", True)):
            why = f"{x.Label} is hidden"
        elif not bool(getattr(x, "Active", True)):
            why = f"{x.Label} is not Active"
        elif not moves:
            why = f"{x.Label} has no moves (recompute, or nothing to cut)"
        else:
            for p in getattr(x, "InListRecursive", None) or ():
                if "Operations" in (getattr(p, "PropertiesList", None) or ()) and not bool(getattr(p, "Visibility", True)):
                    why = f"its job {p.Label} is hidden (CAM hides the job's operations with it)"
                    break
    except Exception:  # noqa: BLE001
        pass
    out["shown"] = why is None
    if why:
        out["shownWhy"] = why
    view = path_view(x)
    if view is not None:
        out["view"] = view
        nothing = view_why(view)
        if nothing and out["shown"]:
            out["shown"] = False
            out["shownWhy"] = nothing
    return out


def view_why(view):
    """Why the window draws nothing of a path, from path_view's facts; None
    when they show nothing against it (or were not read)."""
    try:
        if "vp" in view and view["vp"] is None:
            return view.get("vpWhy") or "no view provider"
        if view.get("Visibility") is False:
            return "its view is hidden (ViewObject.Visibility false)"
        sw = (view.get("modeSwitch") or {}).get("whichChild")
        if isinstance(sw, int) and sw < 0:
            return "FreeCAD's drawing of it is switched off (its display mode switch is -1)"
        pts = [n for n in view.get("coordPoints") or () if isinstance(n, int)]
        if pts and max(pts) == 0:
            return "its drawing holds 0 points (the view provider was not filled from the path)"
        idx = [n for n in view.get("lineIndices") or () if isinstance(n, int)]
        if idx and max(idx) == 0:
            return "its drawing has no line to draw (0 line indices: ShowCount or StartIndex past the path)"
        if view.get("inScene") is False:
            return "its drawing is not in the 3D view's scene"
        for u in view.get("sceneSwitches") or ():
            w = u.get("whichChild") if isinstance(u, dict) else None
            on = u.get("childOnPath") if isinstance(u, dict) else None
            # -1 none, -2 inherit, -3 all (SO_SWITCH_NONE / INHERIT / ALL)
            if isinstance(w, int) and (w == -1 or (w >= 0 and isinstance(on, int) and w != on)):
                return f"a switch above it in the 3D view's scene is off for it (depth {u.get('depth')}, whichChild {w})"
        if "box" in view and view["box"] is None:
            return "nothing of its drawing has a size in the scene (an empty bounding box)"
    except Exception:  # noqa: BLE001
        return None
    return None


VIEW_BUDGET = 0.3  # s: the view facts stop being gathered past this


def _gui():
    """FreeCADGui when a window is up, else None."""
    try:
        if not bool(getattr(FreeCAD, "GuiUp", False)):
            return None
        import FreeCADGui

        return FreeCADGui
    except Exception:  # noqa: BLE001
        return None


def _vis(o):
    """An object's view Visibility (None when it has no view)."""
    try:
        vo = getattr(o, "ViewObject", None)
        return None if vo is None else bool(vo.Visibility)
    except Exception:  # noqa: BLE001
        return None


def _num(v):
    try:
        if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
            return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return round(float(v), 3) if isinstance(v, float) else v
        if isinstance(v, tuple):
            return [_num(c) for c in v]
        return str(v)
    except Exception:  # noqa: BLE001
        return None


def _field(coin, node, name):
    """A Coin field's value as text-safe Python (a node typed or not)."""
    for get in (lambda: getattr(node, name),
                lambda: getattr(coin.cast(node, node.getTypeId().getName().getString()), name)):
        try:
            f = get()
            if name in ("point", "coordIndex"):
                return int(f.getNum())
            return int(f.getValue())
        except Exception:  # noqa: BLE001
            continue
    try:
        return str(node.getField(name).get())
    except Exception:  # noqa: BLE001
        return None


def _find(coin, root, type_name, limit=8):
    """The nodes of a Coin type under root, every switch child searched."""
    try:
        t = coin.SoType.fromName(type_name)
        if t.isBad():
            return []
        sa = coin.SoSearchAction()
        sa.setType(t)
        sa.setInterest(coin.SoSearchAction.ALL)
        sa.setSearchingAll(True)
        sa.apply(root)
        pl = sa.getPaths()
        return [pl[i].getTail() for i in range(min(pl.getLength(), limit))]
    except Exception:  # noqa: BLE001
        return []


def _box(coin, what):
    """SoGetBoundingBoxAction on a node or a path: [min, max], or None when
    nothing in it is drawn (a switch off counts as nothing)."""
    try:
        ba = coin.SoGetBoundingBoxAction(coin.SbViewportRegion())
        ba.apply(what)
        bb = ba.getBoundingBox()
        if bb.isEmpty():
            return None
        return [[round(float(c), 3) for c in bb.getMin().getValue()], [round(float(c), 3) for c in bb.getMax().getValue()]]
    except Exception:  # noqa: BLE001
        return "?"


def path_view(x, budget=VIEW_BUDGET):
    """A probe (round 7, cam 008-032: shown true, no path seen): what
    FreeCAD's window holds of an operation's or dressup's path — its view
    provider's properties, its Coin nodes (the mode switch, every switch
    under the root, the points in each coordinate node, the line indices),
    the box of what it draws, whether its root is in the 3D view's scene
    graph (and the switches on the way down), and the view Visibility of
    its job, the job's Operations and Model groups, the model clones and
    the stock. None with no window. Never raises; stops past budget
    seconds ("cut": the part not read)."""
    G = _gui()
    if G is None:
        return None
    t0 = time.monotonic()
    out = {}

    def late(part):
        if time.monotonic() - t0 > budget:
            out["cut"] = part
            return True
        return False

    try:
        vo = getattr(x, "ViewObject", None)
        if vo is None:
            out["vp"] = None
            out["vpWhy"] = "no view provider: the window has nothing to draw it with"
        else:
            out["vp"] = str(getattr(vo, "TypeId", "?"))
            try:
                px = getattr(vo, "Proxy", None)
                out["vpProxy"] = type(px).__name__ if px is not None else None
            except Exception:  # noqa: BLE001
                pass
            props = list(getattr(vo, "PropertiesList", None) or ())
            for p in ("Visibility", "DisplayMode", "LineWidth", "ShowCount", "StartIndex", "StartPosition", "ShowNodes", "SelectionStyle"):
                if p in props:
                    try:
                        out[p] = _num(getattr(vo, p))
                    except Exception:  # noqa: BLE001
                        out[p] = "?"
            try:
                out["isVisible"] = bool(vo.isVisible())
            except Exception:  # noqa: BLE001
                pass
            try:
                out["objVisibility"] = bool(x.Visibility)
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    try:
        out["job"] = _job_view(x)
    except Exception as e:  # noqa: BLE001
        out["job"] = f"{type(e).__name__}: {e}"
    if out.get("vp") is None or late("nodes"):
        return out
    try:
        from pivy import coin
    except Exception as e:  # noqa: BLE001
        out["coin"] = f"{type(e).__name__}: {e}"
        return out
    try:
        root = vo.RootNode
        out["rootChildren"] = int(root.getNumChildren())
        try:
            sw = vo.SwitchNode
            out["modeSwitch"] = {"whichChild": _field(coin, sw, "whichChild"), "children": int(sw.getNumChildren())}
        except Exception:  # noqa: BLE001
            pass
        out["switches"] = [{"whichChild": _field(coin, n, "whichChild"), "children": int(n.getNumChildren())} for n in _find(coin, root, "SoSwitch")]
        if late("coords"):
            return out
        out["coordPoints"] = [_field(coin, n, "point") for n in _find(coin, root, "SoCoordinate3")]
        out["lineIndices"] = [_field(coin, n, "coordIndex") for n in _find(coin, root, "SoBrepEdgeSet")]
        if late("box"):
            return out
        out["box"] = _box(coin, root)
    except Exception as e:  # noqa: BLE001
        out["nodesError"] = f"{type(e).__name__}: {e}"
    if late("scene"):
        return out
    try:
        gd = G.getDocument(x.Document.Name)
        v = getattr(gd, "ActiveView", None) if gd is not None else None
        sg = v.getSceneGraph() if v is not None and hasattr(v, "getSceneGraph") else None
        if sg is None:
            out["inScene"] = None
            out["inSceneWhy"] = "no 3D view for its document"
        else:
            sa = coin.SoSearchAction()
            sa.setNode(vo.RootNode)
            sa.setInterest(coin.SoSearchAction.FIRST)
            sa.setSearchingAll(True)
            sa.apply(sg)
            path = sa.getPath()
            out["inScene"] = path is not None
            if path is not None:
                ups = []
                for i in range(path.getLength()):
                    n = path.getNode(i)
                    if n.isOfType(coin.SoSwitch.getClassTypeId()):
                        u = {"depth": i, "whichChild": _field(coin, n, "whichChild"), "children": int(n.getNumChildren())}
                        if i + 1 < path.getLength():
                            u["childOnPath"] = int(path.getIndex(i + 1))
                        ups.append(u)
                out["sceneSwitches"] = ups
                out["sceneDepth"] = int(path.getLength())
                if not late("sceneBox"):
                    out["sceneBox"] = _box(coin, path)
    except Exception as e:  # noqa: BLE001
        out["sceneError"] = f"{type(e).__name__}: {e}"
    return out


def _job_view(x):
    """The view Visibility of the job x is in, its Operations and Model
    groups, the model clones (with Transparency) and the stock; None when
    x is in no job."""
    job = None
    for p in getattr(x, "InListRecursive", None) or ():
        if "Operations" in (getattr(p, "PropertiesList", None) or ()) and "Stock" in p.PropertiesList:
            job = p
            break
    if job is None:
        return None
    ops = getattr(job, "Operations", None)
    model = getattr(job, "Model", None)
    stock = getattr(job, "Stock", None)
    clones = []
    for b in list(getattr(model, "Group", None) or ())[:4]:
        c = {"name": b.Label, "Visibility": _vis(b)}
        try:
            c["Transparency"] = int(b.ViewObject.Transparency)
        except Exception:  # noqa: BLE001
            pass
        clones.append(c)
    out = {"name": job.Label, "Visibility": _vis(job),
           "Operations": _vis(ops) if ops is not None else None,
           "inOperations": bool(ops is not None and x in (getattr(ops, "Group", None) or ())),
           "Model": _vis(model) if model is not None else None,
           "clones": clones,
           "Stock": _vis(stock) if stock is not None else None}
    try:
        out["StockTransparency"] = int(stock.ViewObject.Transparency)
    except Exception:  # noqa: BLE001
        pass
    return out


def tools(session):
    s = session

    def doc():
        """The session's document, made FreeCAD's active one."""
        if s.doc is None:
            raise ToolError("invalid_state", "No document: doc_new first.")
        FreeCAD.setActiveDocument(s.doc.Name)
        return s.doc

    def tc_of(job):
        """The job's first tool controller, or None."""
        group = job.Tools.Group if hasattr(job, "Tools") else []
        return group[0] if group else None

    def set_tool(tc, t):
        """A tool controller's sizes, feeds, speed and number from an input
        record; shared by cam_job, cam_tool and cam_tool_add, so each of its
        inputs is checked here, in its own words."""
        if t.get("diameter") is not None:
            d = picks.number(t, "diameter", what="tool.diameter", gt=0, msg="tool.diameter: the end mill's, mm, over 0.")
            tc.Tool.Diameter = d
        if t.get("feed") is not None:
            v = picks.number(t, "feed", gt=0, msg="feed: mm/min across, over 0.")
            tc.HorizFeed = f"{v} mm/min"
        if t.get("plunge") is not None:
            v = picks.number(t, "plunge", gt=0, msg="plunge: mm/min down, over 0.")
            tc.VertFeed = f"{v} mm/min"
        if t.get("rpm") is not None:
            tc.SpindleSpeed = picks.number(t, "rpm", ge=0, msg="rpm: the spindle's speed, 0 or more.")
        if t.get("number") is not None:
            tc.ToolNumber = int(t["number"])

    def tool_out(tc):
        """A tool controller as the answers give it, or None."""
        if tc is None:
            return None
        return {"name": tc.Label, "number": tc.ToolNumber, "diameter": _q(tc.Tool.Diameter, "mm"), "feed": _q(tc.HorizFeed, "mm/min"), "plunge": _q(tc.VertFeed, "mm/min"), "rpm": tc.SpindleSpeed}

    def stock_out(job):
        """The job's stock as its box: min, max, size."""
        bb = job.Stock.Shape.BoundBox
        return {"min": [round(bb.XMin, 3), round(bb.YMin, 3), round(bb.ZMin, 3)], "max": [round(bb.XMax, 3), round(bb.YMax, 3), round(bb.ZMax, 3)], "size": [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]}

    def commands(x):
        """An operation's or dressup's path commands; none when it has no path."""
        return list(x.Path.Commands) if getattr(x, "Path", None) is not None else []

    def op_type(op):
        """What kind of operation or dressup it is: its FreeCAD class."""
        return op.Proxy.__class__.__name__ if hasattr(op, "Proxy") else op.TypeId

    def path_module(name):
        """One of the CAM workbench's own modules by its dotted name (an
        operation's, a dressup's, the stock's): ImportError where this
        FreeCAD has none."""
        if not name.startswith("Path."):
            raise ImportError(f"{name} is not one of CAM's modules")
        return importlib.import_module(name)

    def with_tool(tc, make):
        """make() with tc as the tool controller FreeCAD finds. With more than
        one tool FreeCAD asks which in a dialog (and headless fails), or takes
        the one selected in the window: for this one call its finder answers
        tc, and is put back after."""
        import PathScripts.PathUtils as PathUtils

        orig_find = PathUtils.findToolController
        PathUtils.findToolController = lambda *args, **kw: tc
        try:
            return make()
        finally:
            PathUtils.findToolController = orig_find

    def face_names(o, q):
        """The faces of o one entry of faces names: a name as it is, or what
        shape_query finds for a filter (with near, the one closest to the
        point, not every match). None found: an empty list."""
        if isinstance(q, str):
            return [q]
        query = {**q, "body": o.Label}
        query.setdefault("kind", "face")
        _, _, hits = M.query(s, query)
        if q.get("near") is not None and len(hits) > 1:
            import Part

            pt = picks.vec3(q["near"] if isinstance(q["near"], list) else q["near"].get("point"), "near")
            hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(pt))[0])[:1]
        return [d["ref"] for _, _, d in hits]

    HINTS = {"helix": "helix bores round holes: give the hole's wall (a cylinder face), with a tool smaller than the hole",
             "thread": "thread milling needs a round hole's wall and a thread-mill tool",
             "drill": "drilling needs round holes, upright",
             "deburr": "deburr follows edges: a chamfer or V tool (cam_tool_add)",
             "vcarve": "V-carving follows letters or a sketch (base) with a V-bit (cam_tool_add)",
             "engrave": "engraving follows letters, a sketch or a wire (base)"}

    def where(e):
        """An error with the file and line FreeCAD raised it at."""
        import traceback

        fr = traceback.extract_tb(e.__traceback__)[-1]
        return f"{e} ({os.path.basename(fr.filename)}:{fr.lineno})"

    def make_op(mod, kind, name, job):
        """A new operation of mod in the job. FreeCAD 1.0's hole operations
        look for holes in Create before the operation knows its model, and
        fail; those are built the way newer releases do."""
        d = doc()
        cls = {"drill": "ObjectDrilling", "helix": "ObjectHelix", "thread": "ObjectThreadMilling", "tapping": "ObjectTapping"}.get(kind)
        if cls and hasattr(mod, cls):
            nm = name or kind.capitalize()
            op = d.addObject("Path::FeaturePython", nm)
            op.Proxy = getattr(mod, cls)(op, nm, job)
            if getattr(op.Proxy, "model", None) is None:
                op.Proxy.job, op.Proxy.model = job, job.Model.Group
            return op
        return mod.Create(name or kind.capitalize(), None, job)

    def enum_of(o, prop):
        """The values an enumeration property takes; None when it is not one."""
        try:
            return o.getEnumerationsOfProperty(prop)
        except Exception:
            return None

    def stack_of(top, tuples):
        """One of the job's operations with what it is stacked on: a dressup
        on a dressup on an operation, outermost first (the job lists the
        outermost). tuples: a Base that is a tuple is faces, not a path, as a
        list always is."""
        y, stack = top, [top]
        while getattr(y, "Base", None) is not None and not isinstance(y.Base, (list, tuple) if tuples else list) and hasattr(y.Base, "Path"):
            y = y.Base
            stack.append(y)
        return stack

    # ---- the simulation (cam_sim) ----

    def sim_tool(op, job):
        """An operation with its cutter for the height map: (op, diameter mm,
        ball-ended)."""
        tc = tc_for(op) or tc_of(job)
        tool = tc.Tool
        d = float(_q(tool.Diameter, "mm"))
        shape = str(getattr(tool, "ShapeName", "") or getattr(tool, "ShapeType", "") or getattr(tool, "BitShape", "") or tool.Label).lower()
        return (op, d, "ball" in shape)

    def sim_run(job, cutters, res):
        """The job cut on a height map of res mm cells (Agent Link's millsim):
        the stock's top from above, each operation's moves run through it in
        order, then the cut stock against the part. Answers per (each op's
        removed volume and crashes), crashes, removed, part (gouge and left),
        low (the lowest cut) and the map, heights and difference for the
        picture."""
        import numpy as np

        from .. import millsim

        sb = job.Stock.Shape.BoundBox
        pad = max(d for _, d, _ in cutters)
        grid = millsim.Grid(sb.XMin - pad, sb.YMin - pad, sb.XMax + pad, sb.YMax + pad, res)
        sp, sf = job.Stock.Shape.tessellate(0.05)
        H = millsim.top_of_mesh(grid, [(v.x, v.y, v.z) for v in sp], sf, floor=sb.ZMin)
        H = np.maximum(H, sb.ZMin)
        part = None
        for m in job.Model.Group:
            pp, pf = m.Shape.tessellate(0.02)
            top = millsim.top_of_mesh(grid, [(v.x, v.y, v.z) for v in pp], pf)
            part = top if part is None else np.maximum(part, top)
        removed, crashes, per = 0.0, [], []
        here = None  # the tool's place at the end of the last op
        for op, d, ball in cutters:
            segs = millsim.moves([(c.Name, dict(c.Parameters)) for c in op.Path.Commands], here)
            if segs:
                here = segs[-1][2]
            rem, cr = millsim.run(grid, H, segs, d / 2.0, ball)
            removed += rem
            per.append({"op": op.Label, "tool": d, **({"ballEnd": True} if ball else {}), "removedMm3": round(rem, 1), **({"crashes": len(cr)} if cr else {})})
            crashes += [{"op": op.Label, "at": [round(x, 2) for x in c[0]], "intoStockMm": round(c[1], 2)} for c in cr]
        cmp_, diff = millsim.compare(grid, H, part if part is not None else np.full_like(H, -np.inf), sb.ZMin, tol=max(0.02, res / 10))
        return {"per": per, "crashes": crashes, "removed": removed, "part": cmp_, "low": float(np.min(H)), "grid": grid, "H": H, "diff": diff}

    def sim_picture(run, sb):
        """The simulation's picture as PNG bytes: from above, each spot of
        the part coloured by what is left on it (blue gouged, green right,
        red left over); off the part the cut stock in grey, lighter higher."""
        import numpy as np

        from .. import render

        cmp_, diff, H, grid = run["part"], run["diff"], run["H"], run["grid"]
        span = max(0.1, abs(cmp_.get("gouge", {}).get("deepest", 0.0)), cmp_.get("left", {}).get("most", 0.0))
        t = (diff + span) / (2 * span)
        img = render.jet(np.nan_to_num(t, nan=0.5))
        hz = (H - sb.ZMin) / max(1e-6, sb.ZLength)
        grey = 0.25 + 0.6 * np.clip(hz, 0, 1)
        off = ~np.isfinite(diff)
        img[off] = np.stack([grey[off]] * 3, axis=-1)
        img = img[::-1]
        k = max(1, int(round(760 / max(grid.nx, grid.ny))))
        img = np.repeat(np.repeat(img, k, axis=0), k, axis=1)
        h, w = img.shape[:2]
        canvas = np.full((h + 70, max(w, 420), 3), 0.12)
        canvas[:h, :w] = img
        render.legend(canvas, -span, span, "mm", "jet", "LEFT ON THE PART", h + 40)
        return render.png(canvas)

    def write_bytes(path, data):
        """data written as the file path."""
        with open(path, "wb") as f:
            f.write(data)

    def write_text(path, text):
        """text written as the file path (UTF-8)."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # ---- posting (cam_post) ----

    def post_factory():
        """FreeCAD 1.x's post-processor factory; None on a FreeCAD without it."""
        try:
            from Path.Post.Processor import PostProcessorFactory
        except ImportError:
            return None
        return PostProcessorFactory

    def by_job(job, name, factory):
        """FreeCAD 1.x: the job's post-processor object builds the list to post — the
        work offsets (Fixtures), each tool change, the active operations in the job's
        order — and runs the controller's script or class on it, as the Post command
        does. With a window up a post-processor opens its editor dialog unless told
        not to: --no-show-editor is added to the job's own arguments for this run."""
        old = str(job.PostProcessorArgs or "")
        touched = "Touched" in job.State
        args = " ".join(x for x in old.split() if x != "--show-editor")
        if "--no-show-editor" not in args.split():
            args = (args + " --no-show-editor").strip()
        job.PostProcessorArgs = args
        try:
            pp = factory.get_post_processor(job, name)
            sections = pp.export() if pp is not None else None
        finally:
            job.PostProcessorArgs = old
            if not touched:
                job.purgeTouched()
        return "\n".join(g for _, g in (sections or []) if isinstance(g, str))

    def post_script(name):
        """The controller's post script, loaded afresh (FreeCAD 1.0's way,
        and the fallback); None where this FreeCAD has none of that name."""
        try:
            post = importlib.import_module(f"Path.Post.scripts.{name}_post")
            importlib.reload(post)
        except ImportError:
            return None
        return post

    def postables(ops):
        """What a post script is given: the operations in order, each new
        tool controller before the first operation that uses it (no work
        offsets)."""
        out = []
        seen_tc = None
        for op in ops:
            tc = tc_for(op)
            if tc is not None and tc is not seen_tc:
                out.append(tc)
                seen_tc = tc
            out.append(op)
        return out

    # ---- more tools, dressups, setup ----

    SHAPES = ("endmill", "ballend", "bullnose", "v-bit", "chamfer", "drill", "thread-mill", "radius", "dovetail", "reamer", "tap", "slittingsaw", "taperedballnose")
    # An input's property on the bit, by the names FreeCAD has used for it, and its unit.
    BIT_PROPS = {"angle": (("CuttingEdgeAngle", "TipAngle"), "°"), "length": (("Length",), "mm"), "cuttingLength": (("CuttingEdgeHeight",), "mm"),
                 "tipDiameter": (("TipDiameter",), "mm"), "cornerRadius": (("CornerRadius", "CuttingRadius", "TorusRadius"), "mm")}

    def shape_file(shape):
        """A tool shape's file in CAM's shape library (FreeCAD 1.0's tool
        bits are made from one), or None."""
        import Path as _P

        mod_dir = os.path.dirname(os.path.dirname(os.path.abspath(_P.__file__)))  # …/Mod/CAM
        roots = [os.path.join(mod_dir, "Tools", "Shape")]
        for base in (FreeCAD.getResourceDir(), FreeCAD.getHomePath(), os.path.join(FreeCAD.getHomePath(), "share")):
            roots += [os.path.join(base, "Mod", m, "Tools", "Shape") for m in ("CAM", "Path")]
        for root in roots:
            f = os.path.join(root, f"{shape}.fcstd")
            if os.path.isfile(f):
                return f
        return None

    def bit_factory():
        """FreeCAD 1.0's tool bit factory, or None. 1.1 still answers
        "import Path.Tool.Bit" (an alias of the new tool bit module) but it
        has no Factory: cam_tool_add failed there with "has no attribute
        'Factory'". Only the 1.0 module is used this way."""
        try:
            import Path.Tool.Bit as PathToolBit  # 1.0
        except ImportError:
            return None
        return PathToolBit.Factory if hasattr(PathToolBit, "Factory") else None

    def toolbit(shape, name):
        """A tool bit of a shape the way releases after 1.0 make one, put in
        the document and hidden as FreeCAD's own tool controller does with
        its bit."""
        from Path.Tool.toolbit import ToolBit  # later releases

        try:
            bit = ToolBit.from_shape_id(shape, name)
        except TypeError:
            bit = ToolBit.from_shape_id(shape)
        o = bit.attach_to_doc(FreeCAD.ActiveDocument)
        if getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = False
        return o

    def bit_of(tc):
        """A tool controller's tool as the plain record cam_tool_add takes."""
        b = tc.Tool
        shape = None
        for k in ("ShapeID", "ShapeName", "ShapeFile", "BitShape"):  # 1.1 keeps the shape's id; 1.0 its file
            v = getattr(b, k, None)
            if v:
                shape = os.path.splitext(os.path.basename(str(v)))[0]
                break
        shape = shape or "endmill"
        if shape not in SHAPES:
            alt = shape.replace("_", "-").lower()
            shape = alt if alt in SHAPES else shape.replace("-", "").replace("_", "").lower()
        rec = {"name": tc.Label, "shape": shape, "diameter": _q(b.Diameter, "mm"), "number": tc.ToolNumber,
               "feed": _q(tc.HorizFeed, "mm/min"), "plunge": _q(tc.VertFeed, "mm/min"), "rpm": tc.SpindleSpeed}
        for k, (props, unit) in BIT_PROPS.items():
            prop = next((pn for pn in props if hasattr(b, pn)), None)
            if prop is not None:
                try:
                    rec[k] = _q(getattr(b, prop), "deg" if unit == "°" else unit)
                except Exception:
                    pass
        if int(getattr(b, "Flutes", 0) or 0) > 0:
            rec["flutes"] = int(b.Flutes)
        return rec

    def write_tools(p, recs):
        """The tool records written as Agent Link's own tool file."""
        import json

        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"agentlink": "cam-tools", "version": 1, "tools": recs}, f, indent=1)

    def read_tools(p):
        """A tool file's content, as (content, None); (None, the error) when
        it cannot be read or is not JSON."""
        import json

        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f), None
        except (OSError, ValueError) as e:
            return None, e

    def one_tool(args):
        """cam_tool_add run for one record of a tool file: its entry's own
        steps, so an imported tool is made and checked as an added one."""
        return runners.run_steps("cam_tool_add", runners.entries()["cam_tool_add"], args, helpers)

    DRESSUPS = {"tags": "Path.Dressup.Tags", "dogbone": "Path.Dressup.DogboneII", "boundary": "Path.Dressup.Boundary", "array": "Path.Dressup.Array",
                "ramp": "Path.Dressup.Gui.RampEntry", "leadinout": "Path.Dressup.Gui.LeadInOut"}

    def base_op(x):
        """The operation under a stack of dressups."""
        seen = 0
        while getattr(x, "Base", None) is not None and not isinstance(x.Base, list) and hasattr(x.Base, "Path") and seen < 20:
            x, seen = x.Base, seen + 1
        return x

    def tc_for(x):
        """The tool controller an operation, or the one under a dressup, runs with."""
        return getattr(base_op(x), "ToolController", None) or getattr(x, "ToolController", None)

    def dress(mod, op, job, kind):
        """A dressup of mod on op, however this FreeCAD makes it: the
        module's Create, or its ObjectDressup on a new object (ramp entry and
        lead in/out keep their Create with their commands; made as those
        do). An error where the module has neither."""
        if hasattr(mod, "Create"):
            return mod.Create(op)
        if hasattr(mod, "ObjectDressup"):
            dr = doc().addObject("Path::FeaturePython", f"{kind.capitalize()}Dressup")
            proxy = mod.ObjectDressup(dr)
            dr.Base = op
            job.Proxy.addOperation(dr, op)
            if hasattr(proxy, "setup"):
                try:
                    proxy.setup(dr)
                except TypeError:
                    proxy.setup(dr, True)
            return dr
        raise AttributeError("no way to make it here")

    def undress(job, dr, op):
        """A dressup taken back off: out of the job and the document, its
        operation back in the job."""
        job.Operations.removeObject(dr)
        if op not in job.Operations.Group:
            job.Proxy.addOperation(op)
        doc().removeObject(dr.Name)
        doc().recompute()

    def place(job, new, after):
        """new moved to just after another of the job's operations (last
        when that one is not listed)."""
        g = [o for o in job.Operations.Group if o is not new]
        i = g.index(after) + 1 if after in g else len(g)
        job.Operations.Group = g[:i] + [new] + g[i:]

    def custom_module():
        """CAM's custom G-code operation module; None where this FreeCAD has none."""
        try:
            from Path.Op import Custom
        except ImportError:
            return None
        return Custom

    def custom_create(Custom, label, job):
        """A custom G-code operation in the job, across the releases' two
        ways of saying which job."""
        return Custom.Create(label, parentJob=job) if "parentJob" in Custom.Create.__code__.co_varnames else Custom.Create(label)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "job_of": lambda ref: _job(doc(), ref), "body": lambda ref: s.body(ref), "find": lambda ref, what: picks.find(doc(), ref, what),
               "unique": lambda label, own=None: s.unique(label, own), "snapshot": lambda tool: s.snapshot(tool), "num": picks.num, "ref_list": picks.ref_list,
               "merged": lambda *ds: {k: v for d in ds for k, v in d.items()}, "setprop": setattr, "qty": _q,
               "in_out": lambda name: os.path.join(s.out_dir, name), "isabs": os.path.isabs,
               "out_path": lambda p, kind=None: paths.made(s, p, kind), "post_path": lambda p: paths.out_file(s, "cam_post", p, expand=False),
               "write_bytes": write_bytes, "write_text": write_text,
               # FreeCAD's own
               "vector": lambda xs: FreeCAD.Vector(*xs), "path_module": path_module,
               # the family's
               "OPS": OPS, "POSTS": POSTS, "SHAPES": SHAPES, "BIT_PROPS": BIT_PROPS, "DRESSUPS": DRESSUPS, "HINTS": HINTS, "CUTS": ("G1", "G2", "G3", "G01", "G02", "G03") + CYCLES,
               "path_stats": path_stats, "path_seen": path_seen, "tc_of": tc_of, "tc_for": tc_for, "base_op": base_op, "set_tool": set_tool, "tool_out": tool_out, "stock_out": stock_out,
               "commands": commands, "op_type": op_type, "with_tool": with_tool, "face_names": face_names, "where": where, "make_op": make_op, "enum_of": enum_of, "stack_of": stack_of,
               "sim_tool": sim_tool, "sim_run": sim_run, "sim_picture": sim_picture, "post_factory": post_factory, "by_job": by_job, "post_script": post_script,
               "postables": postables, "shape_file": shape_file, "bit_factory": bit_factory, "toolbit": toolbit, "bit_of": bit_of, "write_tools": write_tools,
               "read_tools": read_tools, "one_tool": one_tool, "dress": dress, "undress": undress, "place": place, "custom_module": custom_module,
               "custom_create": custom_create}
    return runners.tools(GROUP, s, helpers)
