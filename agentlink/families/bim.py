# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's BIM (Arch) workbench headless: walls along points or a sketch,
# windows and doors set into a wall (an opening cut through it), columns,
# beams and slabs, roofs, stairs, spaces with their floor area, levels in a
# building on a site, a schedule of quantities (into a sheet when asked), and
# IFC out and in where IfcOpenShell is installed.

import math
import os

import FreeCAD
import Part

import Arch  # FreeCAD's BIM workbench; the family is left out without it

from .. import geometry as geo
from .. import runners
from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "bim"
INFO = "BIM (Arch): walls, windows and doors in walls, columns, beams, slabs, roofs, stairs, spaces, levels, building and site, quantities, IFC in and out."

V = FreeCAD.Vector
UP = V(0, 0, 1)
WINDOWS = ("Fixed", "Open 1-pane", "Open 2-pane", "Sash 2-pane", "Sliding 2-pane", "Sliding 4-pane", "Awning")
DOORS = ("Simple door", "Glass door")
ROLES = {"column": "Column", "beam": "Beam", "slab": "Slab", "footing": "Footing"}


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


def ccw(points):
    """Whether a closed outline's points run counter-clockwise seen from above (+Z)."""
    area = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        area += p.x * q.y - q.x * p.y
    return area >= 0


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

    # ---- walls and openings ----------------------------------------------------

    def bim_wall(a):
        width, height = pos(a, "width", 200), pos(a, "height", 3000)
        align = {"center": "Center", "left": "Left", "right": "Right"}.get(a.get("align", "center"))
        if align is None:
            raise bad("align: center (the line runs down the middle), left (the line is the wall's left face going from the first point on: the wall lies to the right) or right (the wall lies to the left).")
        name = a.get("name") or "Wall"
        if a.get("base"):
            base = picks.find(doc(), a["base"], "base")
            if not isinstance(getattr(base, "Shape", None), Part.Shape) or base.Shape.isNull() or not base.Shape.Edges:
                raise bad(f"base: {base.Label} has no edges to run a wall along; give a sketch or wire, or points [[x, y] …].")
        elif not a.get("points"):
            raise bad("points [[x, y] …] (the wall's line, mm) or base (a sketch or wire's label): one of them.")
        else:
            base = baseline(a.get("points"), f"{name} line", bool(a.get("closed")))
        w = Arch.makeWall(base, width=width, height=height, align=align)
        named(w, name)
        length = sum(e.Length for e in base.Shape.Edges)
        return finish(w, "bim_wall", {"length": round(length, 1), "width": width, "height": height, "align": align.lower(), "base": base.Label})

    def bim_opening(a):
        wall = picks.find(doc(), a.get("wall"), "wall")
        kind = a.get("kind", "window")
        preset = a.get("preset") or ("Simple door" if kind == "door" else "Open 1-pane")
        if preset not in WINDOWS + DOORS:
            raise bad(f"preset: a window — {', '.join(WINDOWS)} — or a door — {', '.join(DOORS)}.")
        width = pos(a, "width", 900 if kind == "door" else 1000)
        height = pos(a, "height", 2100 if kind == "door" else 1200)
        if kind not in ("window", "door"):
            raise bad("kind: window | door.")
        sill = picks.num(a.get("sill", 0 if kind == "door" else 900), "sill")
        at = picks.num(a.get("at", 0), "at")
        if at < 0:
            raise bad("at: 0 or more, the opening's left edge in mm along the wall's line from its first point.")
        if wall not in walls():
            raise bad(f"wall: {wall.Label} is not a wall (bim_list shows them); bim_edit {{ op: \"subtract\" }} cuts other components.")
        base = getattr(wall, "Base", None)
        edges = base.Shape.Edges if base is not None and getattr(base, "Shape", None) else []
        if not edges:
            raise bad(f"wall: {wall.Label} has no baseline to place the opening along (a wall made by bim_wall has one).")
        if sill + height > float(getattr(wall, "Height", 0) or 0) + 1e-6 and float(getattr(wall, "Height", 0) or 0) > 0:
            raise bad(f"sill + height is {sill + height:g} mm, above the wall's {float(wall.Height):g} mm: a lower sill or height.")
        # Which straight run of the wall: the one holding distance at.
        run, left = None, at
        for e in edges:
            if left <= e.Length + 1e-6:
                run = e
                break
            left -= e.Length
        if run is None:
            total = sum(e.Length for e in edges)
            raise bad(f"at: {at:g} is past the end of {wall.Label} ({total:.0f} mm of line); the opening's left edge goes at 0 … {max(total - width, 0):.0f}.")
        p0, p1 = run.Vertexes[0].Point, run.Vertexes[-1].Point
        d = p1 - p0
        if d.Length < 1e-9:
            raise bad("The wall's run there has no length.")
        if left + width > run.Length + 1e-6:
            raise bad(f"The opening runs past the end of that straight stretch of wall ({run.Length:.0f} mm long, the opening {left:.0f} … {left + width:.0f} along it): a smaller at or width; an opening cannot cross a corner.")
        d.normalize()
        # Across the wall: where its middle sits off the line (align), and how thick it is.
        # FreeCAD (ArchWall.getExtrusionData) offsets a Left wall by direction × normal,
        # the right-hand side of the line going from its start; n here points left.
        n = UP.cross(d)
        n.normalize()
        W = float(getattr(wall, "Width", 200))
        off = {"Left": -W / 2, "Right": W / 2}.get(str(getattr(wall, "Align", "Center")), 0.0)
        off += {"Left": -1.0, "Right": 1.0}.get(str(getattr(wall, "Align", "Center")), 0.0) * float(getattr(wall, "Offset", 0) or 0)
        pl = FreeCAD.Placement(p0 + d * left + n * off + V(0, 0, sill), frame(d, n))
        fw, depth = float(a.get("frame", 50)), float(a.get("depth", 100))
        door = preset in DOORS
        if fw <= 0 or depth <= 0 or 2 * fw >= min(width, height):
            raise bad(f"frame: above 0 and under half the opening's smaller side ({min(width, height) / 2:g} mm); depth above 0.")
        # The opening, cut out of the wall (the wall's Subtractions), a little deeper than it.
        hole = doc().addObject("Part::Feature", "Opening")
        hole.Label = s.unique(f"{a.get('name') or ('Door' if door else 'Window')} opening")
        hole.Shape = Part.makeBox(width, W + 20, height, V(0, -(W + 20) / 2, 0))
        hole.Placement = pl
        wall.Subtractions = list(wall.Subtractions) + [hole]
        # The window itself: a frame round a pane (a door's panel), as an Arch component typed Window or Door.
        outer = Part.makeBox(width, depth, height, V(0, -depth / 2, 0))
        inner = Part.makeBox(width - 2 * fw, depth + 2, height - (fw if door else 2 * fw), V(fw, -depth / 2 - 1, 0 if door else fw))
        pane_t = 40.0 if door else 10.0
        pane = Part.makeBox(width - 2 * fw, pane_t, height - (fw if door else 2 * fw), V(fw, -pane_t / 2, 0 if door else fw))
        shape = Part.makeCompound([outer.cut(inner), pane])
        base = doc().addObject("Part::Feature", "WindowShape")
        base.Label = s.unique(f"{a.get('name') or ('Door' if door else 'Window')} shape")
        base.Shape = shape
        base.Placement = pl
        mk = getattr(Arch, "makeComponent", None)
        win = headless_call(mk, base) if mk else None
        if win is None:
            win = base
            win.addProperty("App::PropertyString", "IfcType", "IFC", "IFC type")
        named(win, a.get("name") or ("Door" if door else "Window"))
        try:
            win.IfcType = "Door" if door else "Window"
        except Exception:
            pass
        for k, v in (("Width", width), ("Height", height)):
            if not hasattr(win, k):
                win.addProperty("App::PropertyLength", k, "Window", "")
            setattr(win, k, v)
        if not hasattr(win, "Hosts"):
            win.addProperty("App::PropertyLinkList", "Hosts", "Window", "The wall it is set into")
        win.Hosts = [wall]
        built = f"{'door' if door else 'window'}: a {fw:g} mm frame round a {'panel' if door else 'pane'} (FreeCAD's window presets need its window)"
        before = wall.Shape.Volume if wall.Shape.Solids else 0
        doc().recompute()
        after = wall.Shape.Volume if wall.Shape.Solids else 0
        out = finish(win, "bim_opening", {"wall": wall.Label, "preset": built, "width": width, "height": height, "sill": sill, "at": at})
        out["wallCut_m3"] = round((before - after) / 1e9, 4)
        out["opening"] = hole.Label
        if before - after <= 0:
            out["warning"] = "The wall was not cut: the opening may be outside it (a wall moved after it was made, or a sill above its top). view_render shows where it landed; object_delete removes it and its opening."
        return out

    # ---- structure -------------------------------------------------------------

    def bim_structure(a):
        kind = picks.choice(a, "kind", ROLES, f"kind: {', '.join(ROLES)}.", "column")
        name = a.get("name") or kind.capitalize()
        if kind in ("slab", "footing"):
            t = pos(a, "thickness", 200 if kind == "slab" else 500)
            up = None
            if a.get("base"):
                base = picks.find(doc(), a["base"], "base")
                bs = getattr(base, "Shape", None)
                if not isinstance(bs, Part.Shape) or bs.isNull() or bs.Solids or not (bs.Faces or any(w.isClosed() for w in bs.Wires)):
                    raise bad(f"base: {base.Label} is not a closed flat outline (a closed sketch, a closed wire or a face); or give points [[x, y] …].")
            else:
                pts = a.get("points")
                if not pts:
                    raise bad(f"points: the {kind}'s outline, [x, y(, z)] each, closed for you; or base, a closed sketch or wire by label.")
                base = baseline(pts, f"{name} outline", closed=True)
                try:
                    base.Shape = Part.Face(base.Shape)
                except Exception:
                    doc().removeObject(base.Name)
                    raise bad("points: the outline is not flat or crosses itself; give its corners in order, all in one plane.") from None
                # FreeCAD extrudes along the face's normal, which follows the order the
                # corners were given in: told to go up whichever way round they run.
                up = base.Shape.Faces[0].normalAt(0, 0)
                if up.z < 0:
                    up = up.negative()
            o = Arch.makeStructure(base, height=t)
            if up is not None and abs(up.z) > 1e-6 and hasattr(o, "Normal"):
                o.Normal = up
            if kind == "footing":
                o.Placement.Base = o.Placement.Base - V(0, 0, t)
        elif kind == "column":
            w, dp, h = pos(a, "width", 300), pos(a, "depth", 300), pos(a, "height", 3000)
            o = prism(w, dp, h, name)
            o.Placement = FreeCAD.Placement(vec(a.get("at", [0, 0, 0]), "at"), FreeCAD.Rotation())
        else:
            if a.get("from") is None or a.get("to") is None:
                raise bad("from and to: the beam's two ends, [x, y, z] each in mm (its centre line).")
            p0, p1 = vec(a.get("from"), "from"), vec(a.get("to"), "to")
            d = p1 - p0
            if d.Length < 1e-6:
                raise bad("from and to: the beam's two ends, apart.")
            w, h = pos(a, "width", 200), pos(a, "depth", 400)
            dn = V(d).normalize()
            side = UP.cross(dn)
            if side.Length < 1e-9:
                raise bad("A beam runs across, not straight up: kind column { at, width, depth, height } for an upright.")
            side.normalize()
            o = prism(w, h, d.Length, name)
            # The section across (X sideways, Y up), extruded along its local Z: the beam's run.
            o.Placement = FreeCAD.Placement(p0, frame(side, dn.cross(side)))
        named(o, name)
        if hasattr(o, "IfcType"):
            try:
                o.IfcType = ROLES[kind]
            except Exception:
                pass
        return finish(o, "bim_structure", {"kind": kind})

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

    def presets():
        try:
            import ArchProfile
        except ImportError:
            raise ToolError("unavailable", "This FreeCAD's BIM has no profile library.") from None
        return headless_call(ArchProfile.readPresets)

    def bim_profiles(a):
        """FreeCAD's steel and timber section library: names to give bim_member."""
        q = str(a.get("search", "")).lower()
        cat = str(a.get("category", "")).lower()
        rows = [r for r in presets() if (not q or q in str(r[2]).lower()) and (not cat or cat == str(r[1]).lower())]
        cats = sorted({str(r[1]) for r in presets()})
        lim = int(a.get("limit", 40))
        return {"count": len(rows), "categories": cats,
                "profiles": [{"name": r[2], "category": r[1], "type": r[3], "dims": r[4:]} for r in rows[:lim]],
                **({"more": len(rows) - lim} if len(rows) > lim else {})}

    def bim_member(a):
        """A steel or timber member of a library section (HEB200, IPE300, RHS …) from one point to another."""
        name = str(a.get("profile", ""))
        rows = presets()
        row = next((r for r in rows if str(r[2]).lower() == name.lower()), None)
        if row is None:
            near = [r[2] for r in rows if name.lower()[:3] and str(r[2]).lower().startswith(name.lower()[:3])][:8]
            raise bad(f"profile: {name!r} is not in the library" + (f" — near: {', '.join(near)}" if near else "") + " (bim_profiles lists them).")
        p0, p1 = vec(a.get("from"), "from"), vec(a.get("to"), "to")
        d = p1 - p0
        if d.Length < 1e-6:
            raise bad("from and to: the member's two ends, apart.")
        prof = headless_call(Arch.makeProfile, row)
        if prof is None:
            raise ToolError("failed", f"FreeCAD could not make the {name} section.")
        prof.Label = s.unique(f"{name} section", prof)
        o = headless_call(Arch.makeStructure, prof, height=d.Length)
        dn = V(d).normalize()
        side = UP.cross(dn)
        if side.Length < 1e-9:
            side = V(1, 0, 0)  # upright: the section's X along world X
        side.normalize()
        rot = frame(side, dn.cross(side))
        if a.get("rotate"):
            rot = rot.multiply(FreeCAD.Rotation(V(0, 0, 1), float(a["rotate"])))
        o.Placement = FreeCAD.Placement(p0, rot)
        upright = abs(dn.z) > 0.99
        named(o, a.get("name") or f"{name} {'column' if upright else 'beam'}")
        if hasattr(o, "IfcType"):
            try:
                o.IfcType = "Column" if upright else "Beam"
            except Exception:
                pass
        out = finish(o, "bim_member", {"profile": name, "category": row[1], "length": round(d.Length, 1)})
        if o.Shape.Solids:
            dens = float(a.get("density", 7850 if str(row[1]).upper() not in ("TIMBER", "WOOD") else 500))
            out["mass_kg"] = round(o.Shape.Volume / 1e9 * dens, 1)
            out["kgPerM"] = round(out["mass_kg"] / (d.Length / 1000), 1)
        return out

    def bim_roof(a):
        name = a.get("name") or "Roof"
        made_base = not a.get("base")
        if a.get("base"):
            base = picks.find(doc(), a["base"], "base")
            bs = getattr(base, "Shape", None)
            if not isinstance(bs, Part.Shape) or bs.isNull() or bs.Solids or not bs.Wires or not bs.Wires[0].isClosed():
                raise bad(f"base: {base.Label} is not a closed outline (a closed sketch or wire); or give points [[x, y] …] at the eaves' height.")
        elif not a.get("points"):
            raise bad("points [[x, y] …] (the outline at the eaves' height, mm) or base (a closed sketch or wire's label): one of them.")
        else:
            base = baseline(a.get("points"), f"{name} outline", closed=True)

        def refuse(msg):
            if made_base:
                doc().removeObject(base.Name)
            return bad(msg)

        # FreeCAD's roof reads the outline's first wire, its edges in order (ArchRoof.execute).
        edges = Part.__sortEdges__(base.Shape.Wires[0].Edges)
        n = len(edges)
        if any(len(e.Vertexes) < 2 or abs(e.Length - (e.Vertexes[-1].Point - e.Vertexes[0].Point).Length) > 1e-6 for e in edges):
            raise refuse("A roof's outline is straight edges only: FreeCAD slopes one pane up from each edge.")
        ang = a.get("angle", 30)
        try:
            angles = [float(x) for x in ang] if isinstance(ang, list) else [float(ang)] * n
        except (TypeError, ValueError):
            raise refuse("angle: degrees, one number or a list of one per edge.") from None
        if len(angles) != n:
            raise refuse(f"angle: one number, or one per edge ({n} here, in the outline's order); 90 makes a gable end.")
        if any(not 0 < x <= 90 for x in angles):
            raise refuse("angle: above 0 up to 90 degrees each (90: a gable end, no pane on that edge).")
        if all(x == 90 for x in angles):
            raise refuse("angle: every edge is a gable (90), so there is no pane left to build: give the sloping edges an angle below 90.")
        t = pos(a, "thickness", 150)
        over = picks.num(a.get("overhang", 300), "overhang")
        # Each slope's run: half the outline's depth away from its edge — the ridge midway.
        verts = [e.Vertexes[0].Point for e in edges]
        runs = []
        for e in edges:
            p0, p1 = e.Vertexes[0].Point, e.Vertexes[-1].Point
            d = V(p1 - p0)
            d.z = 0
            d.normalize()
            far = max(abs((q - p0).x * d.y - (q - p0).y * d.x) for q in verts)
            runs.append(round(far / 2, 3))
        if a.get("run") is not None:
            r = a["run"]
            try:
                runs = [float(x) for x in r] if isinstance(r, list) else [float(r)] * n
            except (TypeError, ValueError):
                raise refuse("run: mm from an edge in to its ridge, one number or a list of one per edge.") from None
            if len(runs) != n:
                raise refuse(f"run: one number, or one per edge ({n} here).")
        # The outline must run counter-clockwise seen from above (wiki Arch_Roof): a
        # clockwise one slopes its panes outwards. Flip turns it round inside FreeCAD,
        # which then counts the edges backwards, so the per-edge lists are turned too.
        flip = not ccw(verts)
        la, lr = (list(reversed(angles)), list(reversed(runs))) if flip else (angles, runs)
        o = Arch.makeRoof(base, 0, la, lr, [-1] * n, [t] * n, [over] * n)
        if flip:
            if not hasattr(o, "Flip"):
                doc().removeObject(o.Name)
                raise refuse("The outline runs clockwise seen from above and this FreeCAD's roof cannot be flipped: give the points counter-clockwise.")
            o.Flip = True
        named(o, name)
        out = finish(o, "bim_roof", {"edges": n, "angles": angles, "runs": runs})
        try:
            hs = [float(h) for h in (getattr(o, "Heights", None) or [])]
        except (TypeError, ValueError):
            hs = []
        if hs:
            out["ridge"] = round(max(hs), 1)
        if flip:
            out["flipped"] = True
        return out

    def bim_stairs(a):
        length, width, height = pos(a, "length", 4500), pos(a, "width", 1000), pos(a, "height", 3000)
        steps = int(a.get("steps", max(3, round(height / 175))))
        if steps < 2:
            raise bad("steps: 2 or more (FreeCAD counts risers: steps - 1 treads share the length).")
        o = Arch.makeStairs(None, length=length, width=width, height=height, steps=steps)
        d = vec(a.get("direction", [1, 0]), "direction")
        d.z = 0
        if d.Length < 1e-9:
            raise bad("direction: which way the flight rises, [x, y].")
        d.normalize()
        # Steps along local X, its width along Y, rising up Z.
        o.Placement = FreeCAD.Placement(vec(a.get("at", [0, 0, 0]), "at"), frame(d, UP.cross(d)))
        named(o, a.get("name") or "Stairs")
        riser, going = height / steps, length / max(steps - 1, 1)
        out = finish(o, "bim_stairs", {"steps": steps, "riser": round(riser, 1), "going": round(going, 1), "blondel": round(2 * riser + going, 1)})
        if not 600 <= 2 * riser + going <= 650:
            out["note"] = "2 risers + 1 going is outside 600–650 mm (Blondel): the flight will feel steep or long."
        return out

    def bim_space(a):
        name = a.get("name") or "Space"
        if a.get("base"):
            base = picks.find(doc(), a["base"], "base")
            if not isinstance(getattr(base, "Shape", None), Part.Shape) or base.Shape.isNull() or not base.Shape.Solids:
                raise bad(f"base: {base.Label} is not a solid; a space takes a solid of the room's volume, or points (its floor outline) and height.")
        elif not a.get("points"):
            raise bad("points [[x, y] …] (the room's floor outline, mm) with height, or base (a solid's label): one of them.")
        else:
            h = pos(a, "height", 2600)
            base = baseline(a.get("points"), f"{name} outline", closed=True)
            try:
                face = Part.Face(base.Shape)
            except Exception:
                doc().removeObject(base.Name)
                raise bad("points: the outline is not flat or crosses itself; give the room's corners in order.") from None
            up = face.normalAt(0, 0)
            base.Shape = face.extrude((up.negative() if up.z < 0 else up) * h)
            base.Visibility = False
        o = Arch.makeSpace([base])
        named(o, name)
        if a.get("use") and hasattr(o, "SpaceType"):
            kinds = list(o.getEnumerationsOfProperty("SpaceType") or [])
            want = str(a["use"]).lower()
            pick = next((k for k in kinds if k.lower() == want), None)
            if pick is None:
                near = [k for k in kinds if want in k.lower()][:8] or ["Room", "Office", "Corridor / Transition", "Restrooms", "Dining Area", "Food Preparation", "Stairs", "Lobby"]
                doc().removeObject(o.Name)
                if not a.get("base"):
                    doc().removeObject(base.Name)
                raise bad(f"use {a['use']!r}: not one of FreeCAD's space types. Near: {', '.join(near)}. Leave use out for Undefined; put a free name in name.")
            o.SpaceType = pick
        doc().recompute()
        area = getattr(o, "Area", None)
        a_m2 = float(area.Value if hasattr(area, "Value") else area or 0) / 1e6
        return finish(o, "bim_space", {"area_m2": round(a_m2, 3), "use": str(getattr(o, "SpaceType", ""))})

    # ---- levels, building, site ---------------------------------------------------

    def bim_building(a):
        objs = [picks.find(doc(), r, "levels") for r in picks.ref_list(a.get("levels") or [], "levels: the levels' labels (bim_level makes them), a list.")] if a.get("levels") else []
        b = Arch.makeBuilding(objs)
        named(b, a.get("name") or "Building")
        out = finish(b, "bim_building", {"levels": [x.Label for x in objs]})
        if a.get("site", True):
            site = Arch.makeSite([b])
            named(site, a.get("siteName") or "Site")
            doc().recompute()
            out["site"] = site.Label
        return out

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

    def bim_schedule(a):
        rows = quantities()
        totals = {}
        for r in rows:
            t = totals.setdefault(r["kind"], {"count": 0})
            t["count"] += 1
            for k in ("length_m", "area_m2", "volume_m3", "mass_kg"):
                if k in r:
                    t[k] = round(t.get(k, 0) + r[k], 4)
        out = {"rows": rows, "totals": totals}
        if a.get("sheet"):
            sh = doc().addObject("Spreadsheet::Sheet", "Schedule")
            sh.Label = s.unique(a.get("sheet") if isinstance(a.get("sheet"), str) else "Schedule")
            cols = ["object", "kind", "length_m", "height_m", "width_m", "area_m2", "volume_m3", "mass_kg", "use"]
            for j, c in enumerate(cols):
                sh.set(f"{chr(65 + j)}1", c)
            for i, r in enumerate(rows, start=2):
                for j, c in enumerate(cols):
                    if c in r and r[c] != "":
                        v = r[c]
                        sh.set(f"{chr(65 + j)}{i}", str(v) if isinstance(v, (int, float)) else f"'{v}")
            sh.recompute()
            out["sheet"] = sh.Label
            picks.finish(s, "bim_schedule", out)
        return out

    # ---- IFC -------------------------------------------------------------------------

    def need_ifc():
        try:
            import ifcopenshell  # noqa: F401
        except ImportError:
            raise ToolError("unavailable", "IFC needs IfcOpenShell, which this FreeCAD does not have, so bim_export, bim_import and the ifc_ tools cannot run. Installing it is the person's step: in FreeCAD, the BIM workbench's Setup command (BIM_Setup) checks for it and offers the install, then FreeCAD is restarted. Until then export { format: \"step\" } carries the shapes without the BIM data.")

    def ifc_module(name):
        for m in (f"importers.{name}", name):
            try:
                return __import__(m, fromlist=["x"])
            except ImportError:
                continue
        raise ToolError("unavailable", f"FreeCAD's {name} is not found in this build.")

    def where(p, default):
        return paths.local(s, p or default, expand=False)

    def bim_export(a):
        need_ifc()
        names = a.get("objects")
        if names:
            objs = [picks.find(doc(), n) for n in names]
        else:
            tops = [o for o in doc().Objects if ifc_type(o) in ("Site", "Building") or type(getattr(o, "Proxy", None)).__name__ in ("_Site", "_Building")]
            objs = tops[:1] or [o for o in doc().Objects if is_bim(o) and not contained(o)]
            if not objs:
                raise bad("Nothing to write: no BIM objects here (bim_wall … make them; bim_list shows them), or give objects.")
        p = where(a.get("path"), (doc().Label or "model") + ".ifc")
        if not p.lower().endswith(".ifc"):
            p += ".ifc"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        ex = ifc_module("exportIFC")
        # A classification with no space in it stops FreeCAD's exporter cold
        # (it splits "<system> <code>"): named here, before it is tried.
        bare = [o.Label for o in doc().Objects if isinstance(getattr(o, "StandardCode", None), str) and o.StandardCode.strip() and " " not in o.StandardCode.strip()]
        if bare:
            raise ToolError("invalid_state", f"classification of {', '.join(bare[:6])}: FreeCAD's IFC export needs \"<system> <code>\" (\"Uniclass Ss_25_10_30\") — bim_ifc {{ objects, classification }} sets it so, \"\" clears it. Nothing was written.")
        try:
            ex.export(objs, p)
        except Exception as e:
            # Where FreeCAD's exporter stopped: its last line and the object it
            # was on when one can be told ("not enough values to unpack" alone
            # named neither, and the whole model was left to guess over).
            import traceback as _tb

            fr = _tb.extract_tb(e.__traceback__)
            where = f" (FreeCAD's {os.path.basename(fr[-1].filename)}:{fr[-1].lineno}, in {fr[-1].name}: {(fr[-1].line or '').strip()[:120]})" if fr else ""
            raise ToolError("failed", f"IFC export failed: {e}{where}. objects: [names] exports part of the model, which finds the object it trips on; bim_preflight lists objects with no shape and invalid solids.") from None
        import ifcopenshell

        f = ifcopenshell.open(p)
        counts = {k: len(f.by_type(k)) for k in ("IfcWall", "IfcWindow", "IfcDoor", "IfcSlab", "IfcColumn", "IfcBeam", "IfcSpace", "IfcBuildingStorey", "IfcRoof", "IfcStair")}
        return {"path": p, "bytes": os.path.getsize(p), "schema": f.schema, "objects": [o.Label for o in objs], "readBack": {k: v for k, v in counts.items() if v}}

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

    def bim_import(a):
        need_ifc()
        p = where(a.get("path"), "")
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {a.get('path')!r}: no such file (a relative path is looked for in the session's output folder; give the full path of an .ifc elsewhere).")
        before = {o.Name for o in doc().Objects}
        how = "FreeCAD's IFC importer"
        try:
            im = ifc_module("importIFC")
            im.insert(p, doc().Name)
        except Exception as e:
            # FreeCAD's importer and the IfcOpenShell installed can disagree on
            # settings: each product's geometry read here instead, as a body.
            for o in [o for o in doc().Objects if o.Name not in before]:
                doc().removeObject(o.Name)
            how = f"each product's geometry, read with IfcOpenShell (FreeCAD's importer: {e})"
            ifc_bodies(p)
        doc().recompute()
        made = [o for o in doc().Objects if o.Name not in before]
        kinds = {}
        for o in made:
            kinds[ifc_type(o)] = kinds.get(ifc_type(o), 0) + 1
        return picks.finish(s, "bim_import", lambda: {"path": p, "objects": len(made), "byType": kinds, "read": how}, recompute=False)

    # ---- more building elements ---------------------------------------------------

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

    def bim_curtain_wall(a):
        name = a.get("name") or "Curtain wall"
        pts = a.get("points")
        h = pos(a, "height", 3000)
        vs, hs = pos(a, "vertical", 1500), pos(a, "horizontal", 1500)
        mw, md = pos(a, "mullion", 50), pos(a, "depth", 100)
        mk = getattr(Arch, "makeCurtainWall", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no curtain wall; bim_wall with bim_opening is the nearest.")
        line = baseline(pts, f"{name} line")
        runs = [e.Length for e in line.Shape.Edges]
        length = sum(runs)
        face = line.Shape.extrude(V(0, 0, h))
        line.Shape = face
        o = headless_call(mk, line)
        named(o, name)
        # FreeCAD divides each face of the base (each straight stretch) into the
        # same number of panels: counted on the mean stretch.
        set_ = setprops(o, {"VerticalSections": max(1, round(length / len(runs) / vs)), "HorizontalSections": max(1, round(h / hs)),
                            "VerticalMullionWidth": mw, "VerticalMullionHeight": md, "HorizontalMullionWidth": mw, "HorizontalMullionHeight": md,
                            "PanelThickness": float(a.get("glass", 20))})
        return finish(o, "bim_curtain_wall", {"length": round(length, 1), "height": h, "stretches": len(runs), "set": set_})

    def bim_rebar(a):
        host = picks.find(doc(), a.get("structure"), "structure")
        sh = getattr(host, "Shape", None)
        if not isinstance(sh, Part.Shape) or sh.isNull() or not sh.Solids:
            raise bad(f"structure: {host.Label} has no solid to reinforce; give a slab, beam, column or footing (bim_structure).")
        mk = getattr(Arch, "makeRebar", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no rebar.")
        if a.get("layer", "bottom") not in ("bottom", "top"):
            raise bad("layer: bottom | top.")
        bb = sh.BoundBox
        cover = picks.num(a.get("cover", 30), "cover")
        dia = pos(a, "diameter", 12)
        along = a.get("along", "x")
        layer = a.get("layer", "bottom")
        z = bb.ZMin + cover + dia / 2 if layer == "bottom" else bb.ZMax - cover - dia / 2
        if along == "x":
            p0, p1, spread, width = V(bb.XMin + cover, bb.YMin, z), V(bb.XMax - cover, bb.YMin, z), V(0, 1, 0), bb.YLength
        elif along == "y":
            p0, p1, spread, width = V(bb.XMin, bb.YMin + cover, z), V(bb.XMin, bb.YMax - cover, z), V(1, 0, 0), bb.XLength
        elif along == "z":
            y = bb.YMin + cover + dia / 2
            p0, p1, spread, width = V(bb.XMin, y, bb.ZMin + cover), V(bb.XMin, y, bb.ZMax - cover), V(1, 0, 0), bb.XLength
        else:
            raise bad("along: x | y | z — the bars' own direction.")
        if cover < 0:
            raise bad("cover: 0 or more mm of concrete outside the bars.")
        if (p1 - p0).dot({"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}[along]) <= 0:
            raise bad(f"cover: 2 × {cover:g} mm leaves no bar length along {along} (the structure's box is {bb.XLength:g} × {bb.YLength:g} × {bb.ZLength:g} mm); a smaller cover.")
        span = width - 2 * cover - dia
        if span <= 0:
            raise bad(f"cover and diameter leave no room across the structure ({width:g} mm wide there); a smaller cover.")
        if a.get("spacing"):
            n = math.ceil(span / pos(a, "spacing", None) - 1e-9) + 1  # at most the spacing asked
        else:
            n = int(a.get("amount", 4))
        if n < 1:
            raise bad("amount: 1 or more bars (or spacing mm).")
        if n > 2000:
            raise bad(f"{n} bars: too many to build in one call; a wider spacing or a smaller amount.")
        bar = doc().addObject("Part::Feature", "RebarLine")
        bar.Label = s.unique(f"{a.get('name') or 'Rebar'} line")
        bar.Shape = Part.makePolygon([p0, p1])
        try:
            o = headless_call(mk, host, bar, diameter=dia, amount=n, offset=cover + dia / 2)
            setprops(o, {"Direction": spread})
            how = "FreeCAD's rebar"
        except ToolError:
            # FreeCAD's rebar loads its GUI here: the same bars made as solids,
            # an Arch component typed Reinforcing Bar.
            d = p1 - p0
            first = cover + dia / 2
            step = span / (n - 1) if n > 1 else 0
            bars = [Part.makeCylinder(dia / 2, d.Length, p0 + spread * (first + i * step), d) for i in range(n)]
            bar.Shape = Part.makeCompound(bars)
            mkc = getattr(Arch, "makeComponent", None)
            o = headless_call(mkc, bar) if mkc else bar
            if not hasattr(o, "IfcType"):
                o.addProperty("App::PropertyString", "IfcType", "IFC", "IFC type")
            try:
                o.IfcType = "Reinforcing Bar"
            except Exception:
                pass
            how = "bars made here (FreeCAD's rebar needs its window)"
        named(o, a.get("name") or "Rebar")
        out = finish(o, "bim_rebar", {"made": how, "structure": host.Label, "bars": n, "diameter": dia, "along": along, "layer": layer,
                                       "spacing": round(span / (n - 1), 1) if n > 1 else None})
        length = (p1 - p0).Length
        out["totalLength_m"] = round(n * length / 1000, 3)
        out["mass_kg"] = round(n * length * 3.14159 * (dia / 2) ** 2 * 7.85e-6, 2)
        return out

    def bim_panel(a):
        mk = getattr(Arch, "makePanel", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no panel.")
        t = pos(a, "thickness", 18)
        if a.get("points"):
            base = baseline(a["points"], f"{a.get('name') or 'Panel'} outline", closed=True)
            try:
                base.Shape = Part.Face(base.Shape)
            except Exception:
                raise bad("points: the outline is not flat or crosses itself; give the panel's corners in order.") from None
            o = headless_call(mk, base, thickness=t)
        else:
            o = headless_call(mk, None, length=pos(a, "length", 1000), width=pos(a, "width", 500), thickness=t)
            o.Placement.Base = vec(a.get("at", [0, 0, 0]), "at")
        named(o, a.get("name") or "Panel")
        return finish(o, "bim_panel", {"thickness": t})

    def bim_grid(a):
        mk = getattr(Arch, "makeAxis", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no axes.")
        made, lines = [], {}
        for dirn, k in (("x", "xSpacing"), ("y", "ySpacing")):
            sp = a.get(k) or a.get("spacing")
            if not sp:
                continue
            if not isinstance(sp, list) and int(a.get("count", 4)) < 2:
                raise bad("count: 2 or more grid lines (count - 1 spaces of spacing mm).")
            try:
                sp = [float(x) for x in sp] if isinstance(sp, list) else [float(sp)] * (int(a.get("count", 4)) - 1)
            except (TypeError, ValueError):
                raise bad(f"{k if a.get(k) else 'spacing'}: mm between grid lines, one number (with count) or a list of gaps.") from None
            if any(x <= 0 for x in sp):
                raise bad("spacing: every gap above 0 mm.")
            length = pos(a, "length", 10000)
            ax = headless_call(mk, len(sp) + 1, sp[0])
            ax.Distances = [0.0] + sp
            ax.Angles = [0.0] * (len(sp) + 1)
            ax.Length = length  # the lines' own length (makeAxis's second input is the gap, not this)
            if dirn == "y":
                # An axis set's lines stand at x = 0, gap, … and run along +Y. Turned a quarter
                # they run along -X, so the set is moved their length along X to cover 0 … length.
                ax.Placement = FreeCAD.Placement(V(length, 0, 0), FreeCAD.Rotation(V(0, 0, 1), 90))
            named(ax, f"{a.get('name') or 'Grid'} {dirn.upper()}")
            made.append(ax.Label)
            at, cur = [], 0.0
            for g in [0.0] + sp:
                cur += g
                at.append(round(cur, 3))
            lines[dirn] = at
        if not made:
            raise bad("spacing (or xSpacing / ySpacing): mm between grid lines, one number (with count) or a list of gaps.")
        return picks.finish(s, "bim_grid", lambda: {"axes": made, "lines": lines, "length": pos(a, "length", 10000)})

    def bim_section(a):
        mk = getattr(Arch, "makeSectionPlane", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no section plane.")
        objs = [picks.find(doc(), r, "objects") for r in (a.get("objects") or [])] or [o for o in doc().Objects if is_bim(o) and not contained(o)]
        n = vec(a.get("normal", [0, 0, 1]), "normal")
        if n.Length < 1e-9:
            raise bad("normal: a direction, not [0, 0, 0] ([0, 0, 1] for a plan cut, [0, 1, 0] for a section looking along Y).")
        if not objs:
            raise bad("Nothing to cut: no BIM objects here; give objects, or make some first (bim_wall …).")
        o = headless_call(mk, objs)
        o.Placement = FreeCAD.Placement(vec(a.get("at", [0, 0, 1200]), "at"), FreeCAD.Rotation(V(0, 0, 1), n))
        named(o, a.get("name") or "Section")
        return picks.finish(s, "bim_section", lambda: {"object": o.Label, "cuts": [x.Label for x in objs], "note": "A section plane for TechDraw (td_bim of it) and the FreeCAD window; export { section: z } writes a plan cut as DXF/SVG headless."})

    def bim_material(a):
        mk = getattr(Arch, "makeMaterial", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's BIM has no materials.")
        name = a.get("name") or "Material"
        mat = next((o for o in doc().Objects if o.Label == name and type(getattr(o, "Proxy", None)).__name__ == "_ArchMaterial"), None)
        if mat is None:
            mat = headless_call(mk, name)
            named(mat, name)
        data = dict(getattr(mat, "Material", {}) or {})
        if a.get("density") is not None:
            data["Density"] = f"{pos(a, 'density', None):g} kg/m^3"
        if a.get("description") is not None:
            data["Description"] = str(a["description"])
        if a.get("color") is not None:
            # FreeCAD's material reads its colour from DiffuseColor, "(r, g, b)" each 0 … 1
            # (ArchMaterial.onChanged); any other key is kept but colours nothing.
            data["DiffuseColor"] = str(rgb(a["color"]))
        objs = [picks.find(doc(), r, "objects") for r in (a.get("objects") or [])]
        without = [o.Label for o in objs if not hasattr(o, "Material")]
        if without:
            raise bad(f"objects: {', '.join(without)} cannot carry a BIM material (not BIM components); bim_component {{ from }} makes a shape one.")
        mat.Material = data
        for o in objs:
            o.Material = mat
        return picks.finish(s, "bim_material", lambda: {"material": mat.Label, "data": dict(mat.Material), "on": [o.Label for o in objs]})

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": doc, "finish": finish, "named": named, "baseline": baseline, "setprops": setprops, "headless_call": headless_call,
               "pos": pos, "num": picks.num, "is_bim": is_bim, "ifc_type": ifc_type, "ifc_set": ifc_set,
               "find": lambda ref, *what: picks.find(doc(), ref, *what), "finds": lambda refs: [picks.find(doc(), r) for r in (refs or [])]}

    pt = {"type": "array", "items": {"type": "number"}}
    pts = {"type": "array", "items": pt}
    return runners.tools(GROUP, s, helpers) + [
        Tool("bim_wall", "A wall along points [[x, y(, z)] …] mm (closed: true joins the last to the first) or a base sketch/wire: width (200), height (3000). align center | left (the line is the wall's left face going from the first point, so the wall lies to its right) | right. Answers length, box, min, volume_m3, base (the line bim_opening measures along).",
             obj({"points": pts, "closed": {"type": "boolean"}, "base": {"type": "string"}, "width": {"type": "number"}, "height": {"type": "number"},
                  "align": {"type": "string", "enum": ["center", "left", "right"]}, "name": {"type": "string"}}), bim_wall, changes=True),
        Tool("bim_opening", "A window or door in a wall, its opening cut through: kind window | door, width, height, at (the opening's left edge, mm along the wall's line from its first point; one straight stretch only), sill (900 window, 0 door), frame (50), depth (100). Whatever preset says, it is a plain frame round a pane or a door panel. Answers wallCut_m3 (0 with a warning: nothing was cut), opening (the cutting box), box, min.",
             obj({"wall": {"type": "string"}, "kind": {"type": "string", "enum": ["window", "door"]}, "preset": {"type": "string"}, "width": {"type": "number"}, "height": {"type": "number"},
                  "at": {"type": "number"}, "sill": {"type": "number"}, "frame": {"type": "number"}, "depth": {"type": "number"}, "name": {"type": "string"}}, ["wall"]), bim_opening, changes=True),
        Tool("bim_structure", "Structure, mm: column { at (centre of its foot), width (X), depth (Y), height } | beam { from, to (centre line), width, depth (vertical) } | slab or footing { points (outline) or base (closed sketch/wire), thickness }: a slab rises from its outline, a footing hangs below. Answers box, min, volume_m3.",
             obj({"kind": {"type": "string", "enum": list(ROLES)}, "at": pt, "from": pt, "to": pt, "points": pts, "base": {"type": "string"}, "width": {"type": "number"}, "depth": {"type": "number"},
                  "height": {"type": "number"}, "thickness": {"type": "number"}, "name": {"type": "string"}}), bim_structure, changes=True),
        Tool("bim_profiles", "FreeCAD's section library (steel HEA/HEB/IPE/UPN/RHS/CHS …, timber): search (part of a name), category, limit (40). Answers profiles [{ name, category, type, dims }]. Changes nothing.",
             obj({"search": {"type": "string"}, "category": {"type": "string"}, "limit": {"type": "integer"}}), bim_profiles),
        Tool("bim_member", "A library section between two points (its centre line): profile (\"HEB200\"; bim_profiles lists them), from, to, rotate degrees about its length, density kg/m³ (7850 steel, 500 timber). Answers length, mass_kg, kgPerM (root radii left out, so a little light).",
             obj({"profile": {"type": "string"}, "from": pt, "to": pt, "rotate": {"type": "number"}, "density": {"type": "number"}, "name": {"type": "string"}}, ["profile", "from", "to"]), bim_member, changes=True),
        Tool("bim_roof", "A pitched roof over a closed outline of straight edges at the eaves' height (points or base), a pane rising from each edge: angle degrees, one or a list per edge in the outline's order (90: a gable end); run mm from each edge to its ridge (half the outline's depth by default); thickness (150), overhang (300). Either way round works. Answers angles, runs, ridge (height above the eaves), box, volume_m3.",
             obj({"points": pts, "base": {"type": "string"}, "angle": {}, "run": {}, "thickness": {"type": "number"}, "overhang": {"type": "number"}, "name": {"type": "string"}}), bim_roof, changes=True),
        Tool("bim_stairs", "A straight flight, mm: at (the foot, on its left side going up), direction [x, y], length (run, 4500), width (1000), height (3000), steps (risers; height / 175 by default). Answers riser, going, blondel (2 risers + going; 600–650 is comfortable). FreeCAD 1.1 may add Railing objects.",
             obj({"at": pt, "direction": pt, "length": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "steps": {"type": "integer"}, "name": {"type": "string"}}), bim_stairs, changes=True),
        Tool("bim_space", "A room from its floor outline (points, height 2600) or a base solid. use: one of FreeCAD's space types (Room, Office, Restrooms, Corridor / Transition …; a wrong one is refused with near names); a free name goes in name. Answers area_m2, use, box.",
             obj({"points": pts, "base": {"type": "string"}, "height": {"type": "number"}, "use": {"type": "string"}, "name": {"type": "string"}}), bim_space, changes=True),
        Tool("bim_building", "A building holding levels (labels from bim_level; make them first), on a site too (site: false for none; siteName). Answers levels, site.",
             obj({"levels": {"type": "array", "items": {"type": "string"}}, "site": {"type": "boolean"}, "siteName": {"type": "string"}, "name": {"type": "string"}}), bim_building, changes=True),
        Tool("bim_curtain_wall", "A curtain wall along points, height mm (3000): a mullion about every vertical / horizontal mm (1500; each straight stretch gets the same count), mullion width (50) and depth (100), glass thickness (20). Answers length, stretches, set (what FreeCAD took).",
             obj({"points": pts, "height": {"type": "number"}, "vertical": {"type": "number"}, "horizontal": {"type": "number"}, "mullion": {"type": "number"},
                  "depth": {"type": "number"}, "glass": {"type": "number"}, "name": {"type": "string"}}, ["points"]), bim_curtain_wall, changes=True),
        Tool("bim_rebar", "Straight bars in a structure, laid out in its bounding box: along x | y | z (the bars' direction), layer bottom | top, diameter (12), cover (30), spacing mm (never wider than asked) or amount (4). Answers made (FreeCAD's rebar, or plain bars), bars, spacing, totalLength_m, mass_kg.",
             obj({"structure": {"type": "string"}, "along": {"type": "string", "enum": ["x", "y", "z"]}, "layer": {"type": "string", "enum": ["bottom", "top"]}, "diameter": {"type": "number"},
                  "cover": {"type": "number"}, "spacing": {"type": "number"}, "amount": {"type": "integer"}, "name": {"type": "string"}}, ["structure"]), bim_rebar, changes=True),
        Tool("bim_panel", "A panel (sheet material), mm: an outline (points, flat) or length (1000) × width (500) centred on at; thickness (18). Answers box, volume_m3. bim_panel_out lays panels out for cutting.",
             obj({"points": pts, "length": {"type": "number"}, "width": {"type": "number"}, "thickness": {"type": "number"}, "at": pt, "name": {"type": "string"}}), bim_panel, changes=True),
        Tool("bim_grid", "Grid lines from the origin: spacing mm (one number with count lines, or a list of gaps) for both ways, or xSpacing (lines at x = 0, gap …, running along Y) and ySpacing each; length of the lines (10000). Answers axes (\"Grid X\", \"Grid Y\") and lines (where each stands).",
             obj({"spacing": {}, "xSpacing": {}, "ySpacing": {}, "count": {"type": "integer"}, "length": {"type": "number"}, "name": {"type": "string"}}), bim_grid, changes=True),
        Tool("bim_section", "A section plane through objects (every BIM object not in a level when left out): at ([0, 0, 1200]), normal ([0, 0, 1]: a plan cut). It draws nothing itself: td_bim puts it on a page; export { section: z } writes a plan cut as DXF/SVG.",
             obj({"objects": {"type": "array", "items": {"type": "string"}}, "at": pt, "normal": pt, "name": {"type": "string"}}), bim_section, changes=True),
        Tool("bim_material", "A BIM material by name (made if new): density kg/m³ (what bim_quantities weighs with), description, color (\"#rrggbb\" or \"r, g, b\" 0 to 1); put on objects (BIM components). Answers material, data, on.",
             obj({"name": {"type": "string"}, "density": {"type": "number"}, "description": {"type": "string"}, "color": {"type": "string"}, "objects": {"type": "array", "items": {"type": "string"}}}, ["name"]), bim_material, changes=True),
        Tool("bim_schedule", "Quantities read off the model (Agent Link's own, not an Arch schedule object): walls (length, height, width, area, volume), windows and doors, columns, beams, slabs, footings, roofs, stairs, rebar, spaces, as rows with totals by kind. sheet: true (or a name) also writes a spreadsheet (a change).",
             obj({"sheet": {}}), bim_schedule, changes=True, reads={"sheet": [None, False, ""]}),
        Tool("bim_export", "Write IFC (path, .ifc added; the output folder when relative): the site or building with all it holds, or objects. IFC lengths are metres. Answers path, bytes, schema, readBack (count by IFC class, read from the file). Without IfcOpenShell: refused 'unavailable' with the install step.",
             obj({"objects": {"type": "array", "items": {"type": "string"}}, "path": {"type": "string"}}), bim_export),
        Tool("bim_import", "Read an IFC file (path) into the document as FreeCAD objects. Answers objects, byType, read (which reader). Thousands of elements can outlast the call; to edit a file in place, ifc_open instead. Needs IfcOpenShell.", obj({"path": {"type": "string"}}, ["path"]), bim_import, changes=True),
    ]
