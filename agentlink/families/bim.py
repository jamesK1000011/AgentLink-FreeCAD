# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's BIM (Arch) workbench headless: walls along points or a sketch,
# windows and doors set into a wall (an opening cut through it), columns,
# beams and slabs, roofs, stairs, spaces with their floor area, levels in a
# building on a site, a schedule of quantities (into a sheet when asked), and
# IFC out and in where IfcOpenShell is installed.

import os

import FreeCAD
import Part

import Arch  # FreeCAD's BIM workbench; the family is left out without it

from .. import geometry as geo
from .. import runners
from .. import paths
from ..protocol import ToolError, bad
from . import picks

GROUP = "bim"
INFO = "BIM (Arch): walls, windows and doors in walls, columns, beams, slabs, roofs, stairs, spaces, levels, building and site, quantities, IFC in and out."

# The tools themselves are data (agentlink/data/tools.json, run by
# agentlink/runners.py's steps runner): each entry has the tool's words, its
# checks with their refusals, the order of its steps and its answer. What is
# here is what those entries call by name: the family's finishing code and
# the small functions that are geometry or FreeCAD's API (docs/data-tools.md).

V = FreeCAD.Vector
UP = V(0, 0, 1)


def vec(p, what):
    if not (isinstance(p, (list, tuple)) and len(p) in (2, 3) and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p)):
        raise bad(f"{what}: [x, y] or [x, y, z] in mm (got {p!r}).")
    return V(float(p[0]), float(p[1]), float(p[2]) if len(p) == 3 else 0.0)


def pos(a, k, default):
    return picks.number(a, k, default, gt=0, msg=f"{k}: above 0 mm.")


def frame(x, y):
    """A rotation taking local X, Y to x, y (Z their cross product)."""
    x, y = V(x).normalize(), V(y).normalize()
    z = x.cross(y)
    m = FreeCAD.Matrix(x.x, y.x, z.x, 0, x.y, y.y, z.y, 0, x.z, y.z, z.z, 0, 0, 0, 0, 1)
    return FreeCAD.Rotation(m)


def headless_call(fn, *args, **kw):
    """An Arch call that reaches for its dialogs when FreeCAD says a window is up
    (Agent Link's headless renderer loads FreeCADGui): called again as console
    mode would; a failure says where it came from."""
    import traceback

    try:
        return fn(*args, **kw)
    except Exception as e:
        if "Gui" not in str(e):
            where = traceback.extract_tb(e.__traceback__)[-1]
            raise ToolError("failed", f"{e} ({os.path.basename(where.filename)}:{where.lineno})") from None
        first = e
    up = FreeCAD.GuiUp
    try:
        FreeCAD.GuiUp = False
        return fn(*args, **kw)
    except Exception as e:
        where = traceback.extract_tb(e.__traceback__)[-1]
        w0 = traceback.extract_tb(first.__traceback__)[-1]
        raise ToolError("failed", f"{e} ({os.path.basename(where.filename)}:{where.lineno}); first {first} ({os.path.basename(w0.filename)}:{w0.lineno})") from None
    finally:
        FreeCAD.GuiUp = up


def is_bim(o):
    return hasattr(o, "IfcType") and not o.isDerivedFrom("Spreadsheet::Sheet")


def contained(o):
    """Whether a BIM container (level, building, site) holds o — not a window's host or a wall's subtraction."""
    return any(is_bim(p) and o in (getattr(p, "Group", None) or []) for p in o.InList)


def ifc_type(o):
    return str(getattr(o, "IfcType", "") or getattr(o, "IfcRole", "") or o.TypeId)


def ifc_set(o, t):
    """o's IFC type set to t (FreeCAD's spaced names: "Building Element Proxy"), any case; a refusal naming near ones when FreeCAD has no such type."""
    if not t:
        return None
    try:
        known = list(o.getEnumerationsOfProperty("IfcType") or [])
    except Exception:
        known = []
    want = str(t)
    if want.lower().startswith("ifc") and len(want) > 3:  # "IfcWallStandardCase" as IFC writes it
        want = "".join(c if c.islower() else " " + c for c in want[3:]).strip()
    pick = next((k for k in known if k.lower() == want.lower() or k.replace(" ", "").lower() == want.replace(" ", "").lower()), None)
    if pick is None:
        if not known:
            raise bad(f"{o.Label} has no IFC type to set (not a BIM object): bim_component {{ from }} makes it one.")
        w = want.lower()
        near = [k for k in known if w[:4] in k.lower()][:8] or ["Wall", "Slab", "Beam", "Column", "Covering", "Railing", "Furniture", "Building Element Proxy"]
        raise bad(f"type {t!r}: not an IFC type this FreeCAD knows. Near: {', '.join(near)} (FreeCAD's names have spaces: \"Sanitary Terminal\", \"Pipe Segment\").")
    o.IfcType = pick
    return pick


def rgb(c):
    """A colour as (r, g, b), each 0 … 1: "#rrggbb", or three numbers 0 … 1 or 0 … 255 ("0.8, 0.2, 0.1", [204, 51, 26])."""
    try:
        if isinstance(c, str) and c.strip().startswith("#") and len(c.strip()) == 7:
            h = c.strip()[1:]
            return tuple(round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4))
        v = [float(x) for x in (c.strip("()[] ").split(",") if isinstance(c, str) else c)]
        if len(v) == 3 and all(0 <= x <= 255 for x in v):
            return tuple(round(x / 255.0 if max(v) > 1 else x, 4) for x in v)
    except (TypeError, ValueError):
        pass
    raise bad(f"color {c!r}: \"#rrggbb\", or red, green, blue as \"0.8, 0.2, 0.1\" (each 0 to 1).")


def edges(o):
    """o's edges: none when it has no shape, or an empty one."""
    sh = getattr(o, "Shape", None)
    return list(sh.Edges) if isinstance(sh, Part.Shape) and not sh.isNull() else []


def ccw(points):
    """Whether a closed outline's points run counter-clockwise seen from above (+Z)."""
    area = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        area += p.x * q.y - q.x * p.y
    return area >= 0


def shape(o):
    """o's shape, or None when it has none or an empty one."""
    sh = getattr(o, "Shape", None)
    return sh if isinstance(sh, Part.Shape) and not sh.isNull() else None


def proxy_name(o):
    return type(getattr(o, "Proxy", None)).__name__


def settype(o, t):
    """o's IFC type set to t where this FreeCAD knows it; left as it is otherwise."""
    try:
        o.IfcType = t
    except Exception:
        pass


def have(module):
    """Whether this FreeCAD's Python has the module."""
    try:
        __import__(module)
    except ImportError:
        return False
    return True


def wall_run(edges, at):
    """The straight stretch of a wall's line that holds distance at from its
    start, and how far along that stretch at is: (None, …) past the end."""
    left = at
    for e in edges:
        if left <= e.Length + 1e-6:
            return e, left
        left -= e.Length
    return None, left


def wall_side(wall, width):
    """How far the wall's middle sits off its line, to the left of the line's
    direction: FreeCAD (ArchWall.getExtrusionData) offsets a Left wall by
    direction × normal, the right-hand side of the line going from its start,
    and its Offset pushes the same way."""
    align = str(getattr(wall, "Align", "Center"))
    off = {"Left": -width / 2, "Right": width / 2}.get(align, 0.0)
    return off + {"Left": -1.0, "Right": 1.0}.get(align, 0.0) * float(getattr(wall, "Offset", 0) or 0)


def window_shape(width, height, depth, fw, door):
    """A frame fw wide round a pane (a door: round a panel, open at the foot), standing on its local X."""
    outer = Part.makeBox(width, depth, height, V(0, -depth / 2, 0))
    inner = Part.makeBox(width - 2 * fw, depth + 2, height - (fw if door else 2 * fw), V(fw, -depth / 2 - 1, 0 if door else fw))
    pane_t = 40.0 if door else 10.0
    pane = Part.makeBox(width - 2 * fw, pane_t, height - (fw if door else 2 * fw), V(fw, -pane_t / 2, 0 if door else fw))
    return Part.makeCompound([outer.cut(inner), pane])


def window_props(win, width, height, wall):
    """The window's Width, Height and Hosts (the wall it is set into), added where the component has none."""
    for k, v in (("Width", width), ("Height", height)):
        if not hasattr(win, k):
            win.addProperty("App::PropertyLength", k, "Window", "")
        setattr(win, k, v)
    if not hasattr(win, "Hosts"):
        win.addProperty("App::PropertyLinkList", "Hosts", "Window", "The wall it is set into")
    win.Hosts = [wall]


def roof_runs(edges, verts):
    """Each slope's run: half the outline's depth away from its edge — the ridge midway."""
    runs = []
    for e in edges:
        p0, p1 = e.Vertexes[0].Point, e.Vertexes[-1].Point
        d = V(p1 - p0)
        d.z = 0
        d.normalize()
        far = max(abs((q - p0).x * d.y - (q - p0).y * d.x) for q in verts)
        runs.append(round(far / 2, 3))
    return runs


def roof_ridge(o, eaves):
    """The built roof's ridge above the eaves' height (None when FreeCAD
    gives no Heights). Heights are each pane's own run × tan(angle): on a
    hipped roof the panes over the shorter span meet lower and cut the
    others off, so the ridge is read from the roof as built — the highest
    point of its underside above the eaves' line."""
    try:
        hs = [float(h) for h in (getattr(o, "Heights", None) or [])]
    except (TypeError, ValueError):
        hs = []
    if not hs:
        return None
    under = []
    for f in getattr(o.Shape, "Faces", []):
        try:
            u0, u1, v0, v1 = f.ParameterRange
            if f.normalAt((u0 + u1) / 2, (v0 + v1) / 2).z < -1e-6:
                under.append(max(v.Point.z for v in f.Vertexes))
        except Exception:
            continue
    built = max(under) - eaves if under else 0
    return round(built, 1) if 1e-6 < built < max(hs) - 0.05 else round(max(hs), 1)


def kind_totals(rows):
    """The schedule's totals by kind: a count, and each quantity its rows carry added up."""
    totals = {}
    for r in rows:
        t = totals.setdefault(r["kind"], {"count": 0})
        t["count"] += 1
        for k in ("length_m", "area_m2", "volume_m3", "mass_kg"):
            if k in r:
                t[k] = round(t.get(k, 0) + r[k], 4)
    return totals


def cell(v):
    """A value as a spreadsheet cell's content: a number as it is, words as text."""
    return str(v) if isinstance(v, (int, float)) else f"'{v}"


def stopped(e):
    """Where FreeCAD's code stopped with e: its file, line, function and the line itself, in brackets ("" when unknown)."""
    import traceback

    fr = traceback.extract_tb(e.__traceback__)
    return f" (FreeCAD's {os.path.basename(fr[-1].filename)}:{fr[-1].lineno}, in {fr[-1].name}: {(fr[-1].line or '').strip()[:120]})" if fr else ""


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def finish(o, tool, extra=None):
        return picks.finish(s, tool, lambda: reading(o), extra=extra)

    def reading(o):
        sh = getattr(o, "Shape", None)
        out = {"object": o.Label, "ifc": ifc_type(o)}
        if isinstance(sh, Part.Shape) and not sh.isNull():
            b = geo.box_json(sh)
            out["box"], out["min"] = b["size"], b["min"]
            if sh.Solids:
                out["volume_m3"] = round(sh.Volume / 1e9, 4)
        elif not getattr(o, "Group", None):
            out["warning"] = "no shape came out — check its base and sizes."
        st = o.getStatusString() if hasattr(o, "getStatusString") else ""
        if st and st not in ("Valid", "Touched"):
            out["status"] = st
        return out

    def named(o, label):
        o.Label = s.unique(label, o)
        return o

    def baseline(points, label, closed=False):
        if not (isinstance(points, list) and len(points) >= 2):
            raise bad("points: two or more [x, y(, z)] in mm, a list of them." if not closed else "points: the outline's corners, three or more [x, y(, z)] in mm (it is closed for you).")
        P = [vec(p, "points") for p in points]
        if any((P[i + 1] - P[i]).Length < 1e-6 for i in range(len(P) - 1)):
            raise bad("points: two in a row are the same point; leave the repeat out (closed: true, or an outline, joins the last to the first for you).")
        if closed and (P[0] - P[-1]).Length > 1e-6:
            P.append(P[0])
        if closed and len(P) < 4:
            raise bad("points: an outline needs three or more corners.")
        w = Part.makePolygon(P)
        o = doc().addObject("Part::Feature", "Baseline")
        o.Shape = w
        o.Label = s.unique(label)
        return o

    def walls():
        return [o for o in doc().Objects if ifc_type(o) == "Wall" or (hasattr(o, "Proxy") and type(getattr(o, "Proxy", None)).__name__ == "_Wall")]

    # ---- structure -------------------------------------------------------------

    def prism(x, y, z, label):
        """A structure x by y across (centred on its local origin), z along its local Z.
        FreeCAD's own box structure (no base) is that only while z is the longest:
        a Beam or Column with Length above Height is laid along X instead
        (ArchStructure.getExtrusionData), so a squat one is built on a section face."""
        if z > x:
            return Arch.makeStructure(None, length=x, width=y, height=z)
        sec = doc().addObject("Part::Feature", "Section")
        sec.Shape = Part.Face(Part.makePolygon([V(-x / 2, -y / 2, 0), V(x / 2, -y / 2, 0), V(x / 2, y / 2, 0), V(-x / 2, y / 2, 0), V(-x / 2, -y / 2, 0)]))
        sec.Label = s.unique(f"{label} section")
        sec.Visibility = False
        o = Arch.makeStructure(sec, height=z)
        if hasattr(o, "Normal"):
            o.Normal = V(0, 0, 1)
        return o

    # ---- quantities ----------------------------------------------------------------

    def quantities():
        rows = []
        for o in doc().Objects:
            t = ifc_type(o)
            sh = getattr(o, "Shape", None)
            if not isinstance(sh, Part.Shape) or sh.isNull():
                continue
            vol = sh.Volume / 1e9 if sh.Solids else 0.0
            row = None
            if o in walls():
                base = getattr(o, "Base", None)
                length = sum(e.Length for e in base.Shape.Edges) / 1000 if base is not None and getattr(base, "Shape", None) else 0
                h = float(getattr(o, "Height", 0)) / 1000
                w = float(getattr(o, "Width", 0)) / 1000
                row = {"kind": "wall", "length_m": round(length, 3), "height_m": round(h, 3), "width_m": round(w, 3),
                       "area_m2": round(vol / w, 3) if w else 0, "volume_m3": round(vol, 4)}
            elif t in ("Window", "Door") or type(getattr(o, "Proxy", None)).__name__ == "_Window":
                w, h = float(getattr(o, "Width", 0)), float(getattr(o, "Height", 0))
                row = {"kind": "door" if t == "Door" else "window", "width_m": round(w / 1000, 3), "height_m": round(h / 1000, 3), "area_m2": round(w * h / 1e6, 3)}
            elif t in ("Column", "Beam", "Slab", "Footing"):
                row = {"kind": t.lower(), "volume_m3": round(vol, 4)}
                if t in ("Slab", "Footing"):
                    th = float(getattr(o, "Height", 0) or 0)
                    row["area_m2"] = round(vol * 1000 / th, 3) if th else 0
            elif t == "Space" or type(getattr(o, "Proxy", None)).__name__ == "_Space":
                ar = getattr(o, "Area", 0)
                row = {"kind": "space", "area_m2": round(float(getattr(ar, "Value", ar) or 0) / 1e6, 3), "use": str(getattr(o, "SpaceType", ""))}
            elif t in ("Reinforcing Bar", "Rebar") or type(getattr(o, "Proxy", None)).__name__ == "_Rebar":
                row = {"kind": "rebar", "volume_m3": round(vol, 5), "mass_kg": round(vol * 7850, 1)}
            elif t in ("Roof", "Stair"):
                row = {"kind": t.lower(), "volume_m3": round(vol, 4)}
            if row:
                rows.append({"object": o.Label, **row})
        return rows

    # ---- IFC -------------------------------------------------------------------------

    def ifc_module(name):
        for m in (f"importers.{name}", name):
            try:
                return __import__(m, fromlist=["x"])
            except ImportError:
                continue
        raise ToolError("unavailable", f"FreeCAD's {name} is not found in this build.")

    def where(p, default):
        return paths.local(s, p or default, expand=False)

    def ifc_bodies(p):
        import ifcopenshell
        import ifcopenshell.geom

        f = ifcopenshell.open(p)
        st = ifcopenshell.geom.settings()
        for key in ("use-world-coords", getattr(st, "USE_WORLD_COORDS", None)):
            try:
                st.set(key, True)
                break
            except Exception:
                continue
        unit = 1000.0  # IfcOpenShell gives metres
        n, first = 0, None
        for el in f.by_type("IfcProduct"):
            if not getattr(el, "Representation", None) or el.is_a("IfcOpeningElement") or el.is_a("IfcSpatialStructureElement") and not el.is_a("IfcSpace"):
                continue
            try:
                sh_ = ifcopenshell.geom.create_shape(st, el)
                g = getattr(sh_, "geometry", sh_)
                vs, fs = list(g.verts), list(g.faces)
            except Exception as e:
                first = first or f"{el.is_a()}: {e}"
                continue
            if not fs:
                continue
            P = [V(vs[i] * unit, vs[i + 1] * unit, vs[i + 2] * unit) for i in range(0, len(vs), 3)]
            faces = []
            for i in range(0, len(fs), 3):
                a_, b_, c_ = P[fs[i]], P[fs[i + 1]], P[fs[i + 2]]
                if (b_ - a_).cross(c_ - a_).Length > 1e-9:
                    faces.append(Part.Face(Part.makePolygon([a_, b_, c_, a_])))
            if not faces:
                continue
            sh = Part.makeShell(faces)
            try:
                sol = Part.makeSolid(sh)
                sh = sol.removeSplitter() if sol.isValid() else sh
            except Exception:
                pass
            o = doc().addObject("Part::Feature", "Ifc")
            o.Shape = sh
            o.Label = s.unique(el.Name or el.is_a()[3:])
            o.addProperty("App::PropertyString", "IfcType", "IFC", "IFC class")
            o.IfcType = el.is_a()[3:]
            n += 1
        if not n:
            raise ToolError("failed", f"IFC import: no product geometry could be read (IfcOpenShell {getattr(ifcopenshell, 'version', '?')}; {first or 'no products with geometry'}).")

    # ---- shared by the entries -----------------------------------------------------

    def setprops(o, vals):
        """Set those of vals the object has; answer what was set."""
        done = {}
        for k, v in vals.items():
            if v is not None and hasattr(o, k):
                try:
                    setattr(o, k, v)
                    done[k] = v
                except Exception:
                    pass
        return done

    def component(base):
        """base as an Arch component; where this FreeCAD makes none, base itself given an IFC type."""
        mk = getattr(Arch, "makeComponent", None)
        o = headless_call(mk, base) if mk else None
        if o is None:
            o = base
            o.addProperty("App::PropertyString", "IfcType", "IFC", "IFC type")
        return o

    def rebar_line(p0, p1, bar):
        """The base line for FreeCAD's rebar: a Draft wire from p0 to p1,
        labelled as bar and hidden; bar itself where Draft cannot make one.
        FreeCAD's rebar reads its length from its base's Length (a Draft
        wire), a sketch's geometry or a helix (Mod/BIM/ArchRebar.py
        getLengthOfRebar); a plain Part::Feature line has none, and FreeCAD
        printed "Cannot calculate rebar length from its base object" at each
        recompute."""
        try:
            import Draft
        except ImportError:
            return bar
        try:
            w = headless_call(Draft.make_wire, [p0, p1], closed=False, face=False)
        except ToolError:
            return bar
        if w is None:
            return bar
        w.Label = bar.Label
        if getattr(w, "ViewObject", None) is not None:
            w.ViewObject.Visibility = False
        return w

    def lies_over(made, before):
        """Whether what an import made lies where the document's own shapes
        already were (their boxes cross): an IFC is read in its own
        coordinates, so a file exported from this document lands on it."""
        def box(objs):
            bb = None
            for o in objs:
                sh = getattr(o, "Shape", None)
                if not isinstance(sh, Part.Shape) or sh.isNull():
                    continue
                b = sh.BoundBox
                if not b.isValid():
                    continue
                bb = FreeCAD.BoundBox(b) if bb is None else (bb.add(b) or bb)
            return bb

        new = box(made)
        old = box([o for o in doc().Objects if o.Name in before])
        return bool(new is not None and old is not None and new.intersect(old))

    def plain_bars(bar, p0, p1, spread, first, span, n, dia):
        """FreeCAD's rebar loads its GUI here: the same n bars made as solids
        on bar, an Arch component typed Reinforcing Bar."""
        d = p1 - p0
        step = span / (n - 1) if n > 1 else 0
        bars = [Part.makeCylinder(dia / 2, d.Length, p0 + spread * (first + i * step), d) for i in range(n)]
        bar.Shape = Part.makeCompound(bars)
        mkc = getattr(Arch, "makeComponent", None)
        o = headless_call(mkc, bar) if mkc else bar
        if not hasattr(o, "IfcType"):
            o.addProperty("App::PropertyString", "IfcType", "IFC", "IFC type")
        settype(o, "Reinforcing Bar")
        return o

    def drop(*objs):
        """Remove what a refused call had already made (None: nothing)."""
        for o in objs:
            if o is not None:
                doc().removeObject(o.Name)

    def ifc_open(p):
        import ifcopenshell

        return ifcopenshell.open(p)

    def folder_for(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "finish": finish, "named": named, "baseline": baseline, "setprops": setprops, "headless_call": headless_call,
               "pos": pos, "num": picks.num, "is_bim": is_bim, "ifc_type": ifc_type, "ifc_set": ifc_set,
               "find": lambda ref, *what: picks.find(doc(), ref, *what), "finds": lambda refs, *what: [picks.find(doc(), r, *what) for r in (refs or [])],
               "vec": vec, "edges": edges, "loose": lambda: [o for o in doc().Objects if is_bim(o) and not contained(o)],
               "facing": lambda at, n: FreeCAD.Placement(at, FreeCAD.Rotation(V(0, 0, 1), n)), "done": lambda tool, out: picks.finish(s, tool, out),
               "recorded": lambda tool, out: picks.finish(s, tool, out, recompute=False),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "frame": frame, "face": Part.Face, "box": Part.makeBox,
               "polygon": Part.makePolygon, "sorted_edges": lambda e: Part.__sortEdges__(e), "unique": lambda label, *own: s.unique(label, *own),
               "ref_list": picks.ref_list, "isfile": os.path.isfile, "filesize": os.path.getsize,
               # the family's
               "shape": shape, "proxy_name": proxy_name, "settype": settype, "have": have, "walls": walls, "wall_run": wall_run, "wall_side": wall_side,
               "window_shape": window_shape, "window_props": window_props, "component": component, "prism": prism, "drop": drop,
               "ccw": ccw, "roof_runs": roof_runs, "roof_ridge": roof_ridge, "rgb": rgb, "plain_bars": plain_bars, "rebar_line": rebar_line, "lies_over": lies_over,
               "quantities": quantities, "kind_totals": kind_totals, "cell": cell,
               "where": where, "folder_for": folder_for, "ifc_module": ifc_module, "ifc_open": ifc_open, "ifc_bodies": ifc_bodies, "stopped": stopped}
    return runners.tools(GROUP, s, helpers)
