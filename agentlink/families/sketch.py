# SPDX-License-Identifier: LGPL-2.1-or-later
# Sketch tools: a PartDesign body, sketches on its planes or on a face found
# by where it is, geometry added by kind, constraints in FreeCAD's own
# terms (geometry id + vertex 1 start / 2 end / 3 centre), the solver's
# reading, and edits. Coordinates are the sketch's own, in mm; angles in
# degrees.

import math
import re
import os

import FreeCAD
import Part
import Sketcher

from .. import geometry as geo
from .. import runners
from ..once import DOF_NOTE
from ..protocol import ToolError
from . import pd_common as pc
from . import picks

GROUP = "sketch"
INFO = "PartDesign bodies and sketches: geometry, constraints, the solver's reading (DoF, conflicts, closed wires) and edits."

# The tools themselves are data (agentlink/data/tools.json, run by
# agentlink/runners.py's steps runner): each entry has the tool's words, its
# checks with their refusals, the order of its steps and its answer. What is
# here is what those entries call by name: the solver's reading, the
# geometry builders (one shape each, with its own input checks), the
# constraints by name, and the small functions that are geometry or
# FreeCAD's API (docs/data-tools.md).

V = FreeCAD.Vector
SOLVE = {0: "solved", -1: "the solver failed", -2: "redundant constraints", -3: "conflicting constraints", -4: "over-constrained", -5: "malformed constraints"}


def frame(pl):
    r = pl.Rotation
    return {"origin": geo.vec(pl.Base), "xAxis": geo.vec(r.multVec(V(1, 0, 0))), "yAxis": geo.vec(r.multVec(V(0, 1, 0))), "normal": geo.vec(r.multVec(V(0, 0, 1)))}


def _geo_kind(g):
    return type(g).__name__.replace("ArcOfCircle", "Arc").replace("LineSegment", "Line")


def _pt(v):
    return [geo.r3(v.x), geo.r3(v.y)]


def describe_geo(sk, i):
    g = sk.Geometry[i]
    k = _geo_kind(g)
    out = {"id": i, "kind": k.lower()}
    if sk.getConstruction(i):
        out["construction"] = True
    if k == "Line":
        out["from"], out["to"] = _pt(g.StartPoint), _pt(g.EndPoint)
    elif k == "Circle":
        out["center"], out["radius"] = _pt(g.Center), geo.r3(g.Radius)
    elif k == "Arc":
        out["center"], out["radius"] = _pt(g.Center), geo.r3(g.Radius)
        out["start"], out["end"] = _pt(g.StartPoint), _pt(g.EndPoint)
    elif k == "Point":
        out["at"] = [geo.r3(g.X), geo.r3(g.Y)]
    return out


def describe_con(sk, i):
    c = sk.Constraints[i]
    out = {"id": i, "type": c.Type}
    if c.Name:
        out["name"] = c.Name
    if c.Type in ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter"):
        out["value"] = round(c.Value, 4)
    elif c.Type == "Angle":
        out["value"] = round(math.degrees(c.Value), 4)
    refs = [[c.First, c.FirstPos]]
    if c.Second != -2000:
        refs.append([c.Second, c.SecondPos])
    if getattr(c, "Third", -2000) != -2000:
        refs.append([c.Third, c.ThirdPos])
    out["refs"] = refs
    if not c.Driving:
        out["driving"] = False
    return out


POS = {1: "the start of", 2: "the end of", 3: "the centre of"}


def ext_count(sk):
    """How many outside (external) geometries a sketch has: their ids run
    -3, -4 … -(2 + this). FreeCAD 1.1 keeps them in ExternalGeo behind the
    two axes (ids -1, -2); one linked edge can give more than one. Before
    1.1: one per linked sub-element (ExternalGeometry groups them by
    object, so its length is not the count)."""
    eg = getattr(sk, "ExternalGeo", None)
    if eg is not None:
        try:
            return max(0, len(eg) - 2)
        except Exception:
            pass
    n = 0
    for link in getattr(sk, "ExternalGeometry", None) or []:
        subs = link[1] if isinstance(link, (tuple, list)) and len(link) > 1 else ()
        n += len(subs) if isinstance(subs, (tuple, list)) else 1
    return n


def _snake(t):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", t).lower()


def ref_words(sk, g, pos=0):
    """A constraint's reference in words: "the start of line 3", "the x axis"."""
    if g == -1:
        return "the x axis"
    if g == -2:
        return "the y axis"
    if g <= -3:
        what = f"outside edge {g}"
    elif 0 <= g < len(sk.Geometry):
        what = f"{_geo_kind(sk.Geometry[g]).lower()} {g}"
    else:
        what = f"geometry {g}"
    return f"{POS[pos]} {what}" if pos in POS else what


def con_words(sk, i):
    """A constraint in words with its id: "#6 symmetric: the start of line 3
    and the end of line 3 about the x axis"."""
    d = describe_con(sk, i)
    refs = [ref_words(sk, g, p) for g, p in d["refs"]]
    t = _snake(d["type"])
    if t == "symmetric" and len(refs) == 3:
        on = f"{refs[0]} and {refs[1]} about {refs[2]}"
    else:
        on = " and ".join(refs)
    val = f" = {d['value']:g}" if "value" in d else ""
    return f"#{i} {t}{val}: {on}"


def clashing(sk, cap=150):
    """The constraints that take part in a conflict or redundancy: those
    whose switching off (one at a time) leaves the sketch solving cleanly —
    the solver's own lists name only one of each clash, often the last one
    added rather than the pair that disagree. [] when none clears it alone."""
    def clean():
        code = sk.solve()
        return code == 0 and not (getattr(sk, "ConflictingConstraints", None) or getattr(sk, "RedundantConstraints", None))

    n = len(sk.Constraints)
    if n > cap or not hasattr(sk, "setActive"):
        return []
    out = []
    for i in range(n):
        try:
            if not sk.getActive(i):
                continue
            sk.setActive(i, False)
        except Exception:
            continue
        try:
            if clean():
                out.append(i)
        finally:
            try:
                sk.setActive(i, True)
            except Exception:
                pass
    sk.solve()
    return out


def state_of(sk):
    code = sk.solve()
    conflicting = [i - 1 for i in (getattr(sk, "ConflictingConstraints", None) or [])]
    redundant = [i - 1 for i in (getattr(sk, "RedundantConstraints", None) or [])]
    partial = [i - 1 for i in (getattr(sk, "PartiallyRedundantConstraints", None) or [])]
    malformed = [i - 1 for i in (getattr(sk, "MalformedConstraints", None) or [])]
    dof = getattr(sk, "DoF", None)
    wires = sk.Shape.Wires if not sk.Shape.isNull() else []
    closed = sum(1 for w in wires if w.isClosed())
    openv = []
    if wires and closed < len(wires):
        # The ends of the open wires, in the sketch's own x/y. (Not the
        # sketch's OpenVertices: it lists every vertex that does not join
        # exactly two edges, a lone circle's too.)
        inv = sk.Placement.inverse()
        for w in wires:
            if not w.isClosed():
                vs = [v for v in w.Vertexes if sum(1 for e in w.Edges for ev in e.Vertexes if ev.isSame(v)) == 1]
                openv += [_pt(inv.multVec(v.Point)) for v in vs]
    out = {
        "sketch": sk.Label,
        "solver": SOLVE.get(code, f"code {code}"),
        "dof": dof,
        "fullyConstrained": dof == 0 if dof is not None else None,
        "wires": len(wires),
        "closedWires": closed,
    }
    if openv:
        out["openVertices"] = openv[:12]
    for k, v in (("conflicting", conflicting), ("redundant", redundant), ("partiallyRedundant", partial), ("malformed", malformed)):
        if v:
            out[k] = v
    ready = code == 0 and not conflicting and not redundant and not malformed and closed > 0 and not openv
    out["readyForFeature"] = ready
    if not ready:
        why = []
        if conflicting or redundant or malformed or code != 0:
            why.append("fix the constraints named (sketch_edit deleteConstraints)")
        if openv or (wires and closed < len(wires)):
            why.append("close the open wires: coincident constraints at the open vertices")
        if not wires:
            why.append("no profile yet: sketch_add")
        out["todo"] = "; ".join(why) or "the sketch has no closed wire"
    elif dof:
        # Its words after the count are said once a conversation (agentlink/once.py).
        out["note"] = f"{dof} degrees of freedom: {DOF_NOTE}"
    return out


# ---- geometry builders: (geometry, construction) lists and their constraints -----------------

def _line(a, b):
    return Part.LineSegment(a, b)


def _font(path=None):
    """A TrueType font: the one given, the Draft preference's, TechDraw's own, or a system one."""
    import glob

    tries = [path] if path else []
    try:
        tries.append(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft").GetString("FontFile", ""))
    except Exception:
        pass
    res = FreeCAD.getResourceDir()
    tries += [os.path.join(res, "Mod", "TechDraw", "Resources", "fonts", "osifont-lgpl3fe.ttf"),
              *glob.glob(os.path.join(res, "**", "*.ttf"), recursive=True)[:5],
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", *glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)[:3],
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]
    for t in tries:
        if t and os.path.isfile(os.path.expanduser(t)):
            return os.path.expanduser(t)
    raise ToolError("unavailable", "No TrueType font found: give text.font, a .ttf file's path.")


def _arc(c, r, a0, a1):
    return Part.ArcOfCircle(Part.Circle(c, V(0, 0, 1), r), a0, a1)


def build(item):
    """One item -> (geometries, constraints (as tuples with local ids), dims (name, tuple), report)."""
    k = item.get("kind")
    C = []
    D = []
    if k == "line":
        return [_line(pc.vec2(item.get("from"), "from"), pc.vec2(item.get("to"), "to"))], C, D
    if k == "polyline":
        pts = [pc.vec2(p, "points[]") for p in item.get("points") or []]
        if len(pts) < 2:
            raise ToolError("invalid_input", "polyline.points: two or more [x, y].")
        closed = bool(item.get("closed"))
        if closed and (pts[0] - pts[-1]).Length < 1e-9:
            pts = pts[:-1]
        segs = list(zip(pts, pts[1:] + ([pts[0]] if closed else [])))
        G = [_line(a, b) for a, b in segs]
        for i in range(len(G) - 1):
            C.append(("Coincident", i, 2, i + 1, 1))
        if closed:
            C.append(("Coincident", len(G) - 1, 2, 0, 1))
        # Axis-aligned sides held so, as a rectangle's are (the guide's
        # promise: shapes come with their horizontal/vertical constraints).
        for i, (a, b) in enumerate(segs):
            if (b - a).Length < 1e-9:
                continue
            if abs(b.y - a.y) < 1e-9:
                C.append(("Horizontal", i))
            elif abs(b.x - a.x) < 1e-9:
                C.append(("Vertical", i))
        return G, C, D
    if k == "circle":
        r = float(item.get("radius") or item.get("diameter", 0) / 2.0)
        if r <= 0:
            raise ToolError("invalid_input", "circle: radius (or diameter), mm.")
        G = [Part.Circle(pc.vec2(item.get("center", [0, 0]), "center"), V(0, 0, 1), r)]
        D.append(("d", ("Diameter", 0, 2 * r)))
        return G, C, D
    if k == "arc":
        r = float(item.get("radius", 0))
        if r <= 0:
            raise ToolError("invalid_input", "arc: center, radius, start and end angles (degrees, counter-clockwise from +x).")
        a0, a1 = math.radians(float(item.get("start", 0))), math.radians(float(item.get("end", 90)))
        if a1 <= a0:
            a1 += 2 * math.pi
        D.append(("r", ("Radius", 0, r)))
        return [_arc(pc.vec2(item.get("center", [0, 0]), "center"), r, a0, a1)], C, D
    if k == "point":
        p = pc.vec2(item.get("at"), "at")
        return [Part.Point(p)], C, D
    if k in ("rectangle", "rounded_rectangle"):
        w, h = (item.get("size") or [None, None])[:2]
        if not (isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0):
            raise ToolError("invalid_input", f"{k}: size [w, h] (mm), and center [x, y] or corner [x, y] (its lower left).")
        if "corner" in item:
            c0 = pc.vec2(item["corner"], "corner")
            x0, y0 = c0.x, c0.y
        else:
            c = pc.vec2(item.get("center", [0, 0]), "center")
            x0, y0 = c.x - w / 2.0, c.y - h / 2.0
        x1, y1 = x0 + w, y0 + h
        if k == "rectangle":
            p = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
            G = [_line(p[i], p[(i + 1) % 4]) for i in range(4)]
            C += [("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)]
            C += [("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1), ("Vertical", 3)]
            D += [("width", ("DistanceX", 0, 1, 0, 2, w)), ("height", ("DistanceY", 1, 1, 1, 2, h))]
            return G, C, D
        r = float(item.get("radius", 0))
        if not (0 < r < min(w, h) / 2.0):
            raise ToolError("invalid_input", f"rounded_rectangle.radius: over 0 and under half the short side ({min(w, h) / 2.0} mm).")
        G = [
            _line(V(x0 + r, y0, 0), V(x1 - r, y0, 0)),  # 0 bottom
            _line(V(x1, y0 + r, 0), V(x1, y1 - r, 0)),  # 1 right
            _line(V(x1 - r, y1, 0), V(x0 + r, y1, 0)),  # 2 top
            _line(V(x0, y1 - r, 0), V(x0, y0 + r, 0)),  # 3 left
            _arc(V(x1 - r, y0 + r, 0), r, -math.pi / 2, 0),  # 4 lower right
            _arc(V(x1 - r, y1 - r, 0), r, 0, math.pi / 2),  # 5 upper right
            _arc(V(x0 + r, y1 - r, 0), r, math.pi / 2, math.pi),  # 6 upper left
            _arc(V(x0 + r, y0 + r, 0), r, math.pi, 1.5 * math.pi),  # 7 lower left
        ]
        for ln, arc in ((0, 4), (1, 5), (2, 6), (3, 7)):
            C.append(("Tangent", ln, 2, arc, 1))
            C.append(("Tangent", arc, 2, (ln + 1) % 4, 1))
        C += [("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1), ("Vertical", 3), ("Equal", 4, 5), ("Equal", 4, 6), ("Equal", 4, 7)]
        D += [("width", ("DistanceX", 3, 1, 1, 1, w)), ("height", ("DistanceY", 0, 1, 2, 1, h)), ("r", ("Radius", 4, r))]
        return G, C, D
    if k == "polygon":
        n = int(item.get("sides", 6))
        R = float(item.get("radius", 0))
        if n < 3 or R <= 0:
            raise ToolError("invalid_input", "polygon: sides (3 or more), radius (to the corners, mm), center, rotation (degrees).")
        c = pc.vec2(item.get("center", [0, 0]), "center")
        rot = math.radians(float(item.get("rotation", 0)))
        pts = [V(c.x + R * math.cos(rot + 2 * math.pi * i / n), c.y + R * math.sin(rot + 2 * math.pi * i / n), 0) for i in range(n)]
        G = [_line(pts[i], pts[(i + 1) % n]) for i in range(n)]
        G.append(("construction", Part.Circle(c, V(0, 0, 1), R)))
        C += [("Coincident", i, 2, (i + 1) % n, 1) for i in range(n)]
        C += [("PointOnObject", i, 1, n) for i in range(n)]
        C += [("Equal", 0, i) for i in range(1, n)]
        D += [("d", ("Diameter", n, 2 * R))]
        return G, C, D
    if k == "slot":
        p1, p2 = pc.vec2(item.get("from"), "from"), pc.vec2(item.get("to"), "to")
        r = float(item.get("radius", 0))
        d = p2 - p1
        if r <= 0 or d.Length < 1e-6:
            raise ToolError("invalid_input", "slot: from and to (its two end centres, apart), radius (half its width), mm.")
        t = math.atan2(d.y, d.x)
        n = V(-math.sin(t), math.cos(t), 0)
        G = [
            _arc(p1, r, t + math.pi / 2, t + 1.5 * math.pi),  # 0 arc at from: +n to -n
            _arc(p2, r, t - math.pi / 2, t + math.pi / 2),  # 1 arc at to: -n to +n
            _line(p1 - n * r, p2 - n * r),  # 2
            _line(p2 + n * r, p1 + n * r),  # 3
        ]
        C += [("Tangent", 0, 2, 2, 1), ("Tangent", 2, 2, 1, 1), ("Tangent", 1, 2, 3, 1), ("Tangent", 3, 2, 0, 1), ("Equal", 0, 1)]
        if abs(d.y) < 1e-9:
            C.append(("Horizontal", 2))
        elif abs(d.x) < 1e-9:
            C.append(("Vertical", 2))
        D += [("r", ("Radius", 0, r)), ("length", ("Distance", 0, 3, 1, 3, d.Length))]
        return G, C, D
    if k == "arc_slot":
        c = pc.vec2(item.get("center", [0, 0]), "center")
        R = float(item.get("radius", 0))
        r = float(item.get("width", 0)) / 2
        a0, a1 = math.radians(float(item.get("start", 0))), math.radians(float(item.get("end", 90)))
        if a1 <= a0:
            a1 += 2 * math.pi
        if R <= 0 or r <= 0 or r >= R:
            raise ToolError("invalid_input", "arc_slot: center, radius (of its middle line), width (under twice the radius), start and end (deg, ccw).")
        p0 = c + V(math.cos(a0), math.sin(a0), 0) * R
        p1 = c + V(math.cos(a1), math.sin(a1), 0) * R
        G = [
            _arc(c, R + r, a0, a1),  # 0 outer
            _arc(c, R - r, a0, a1),  # 1 inner
            _arc(p0, r, a0 + math.pi, a0 + 2 * math.pi),  # 2 cap at start: inner to outer, bulging back
            _arc(p1, r, a1, a1 + math.pi),  # 3 cap at end: outer to inner
        ]
        C += [("Coincident", 0, 3, 1, 3), ("Tangent", 2, 1, 1, 1), ("Tangent", 2, 2, 0, 1), ("Tangent", 3, 1, 0, 2), ("Tangent", 3, 2, 1, 2)]
        D += [("width", ("Radius", 2, r)), ("radius", ("Radius", 0, R + r))]
        return G, C, D
    if k == "bspline":
        pts = [pc.vec2(p, "points[]") for p in item.get("points") or []]
        closed = bool(item.get("closed"))
        if len(pts) < (3 if closed else 2):
            raise ToolError("invalid_input", "bspline.points: [x, y] it passes through (interpolate, the default) or its control poles (interpolate: false) — 2 or more, 3 closed.")
        bs = Part.BSplineCurve()
        if item.get("interpolate", True):
            if closed and (pts[0] - pts[-1]).Length < 1e-9:
                pts = pts[:-1]
            bs.interpolate(pts, PeriodicFlag=closed)
        else:
            deg = int(item.get("degree", 3))
            if not 1 <= deg <= min(len(pts) - 1, 9):
                raise ToolError("invalid_input", f"bspline.degree: 1 to {min(len(pts) - 1, 9)} for {len(pts)} poles.")
            bs.buildFromPoles(pts, closed, deg)
        return [bs], C, D
    if k == "ellipse":
        c = pc.vec2(item.get("center", [0, 0]), "center")
        a_, b_ = float(item.get("major", 0)) / 2, float(item.get("minor", 0)) / 2
        if a_ <= 0 or b_ <= 0 or b_ > a_:
            raise ToolError("invalid_input", "ellipse: center, major and minor (its full width and height, mm, major the larger), rotation (deg).")
        t = math.radians(float(item.get("rotation", 0)))
        e = Part.Ellipse(c + V(math.cos(t), math.sin(t), 0) * a_, c + V(-math.sin(t), math.cos(t), 0) * b_, c)
        return [e], C, D
    if k in ("arc3", "circle3"):
        pts = [pc.vec2(p, f"{k}.points") for p in item.get("points") or []]
        if len(pts) != 3:
            raise ToolError("invalid_input", f"{k}.points: three [x, y] — {'start, a point on it, end' if k == 'arc3' else 'on the circle'}.")
        try:
            c = Part.Circle(*pts)
        except Exception:
            raise ToolError("invalid_input", f"{k}.points: three points not on one line.") from None
        if k == "circle3":
            D.append(("d", ("Diameter", 0, 2 * c.Radius)))
            return [Part.Circle(c.Location, V(0, 0, 1), c.Radius)], C, D
        D.append(("r", ("Radius", 0, c.Radius)))
        lo, hi = _ccw(c, pts[0], pts[2], pts[1])
        return [_arc(c.Location, c.Radius, lo, hi)], C, D
    if k == "parabola":
        v = pc.vec2(item.get("vertex", [0, 0]), "vertex")
        f = float(item.get("focal", 0))
        if f <= 0:
            raise ToolError("invalid_input", "parabola: vertex, focal (distance from vertex to focus, mm), rotation (deg: the way it opens, 0 = +x), from and to (y along it, mm).")
        t = math.radians(float(item.get("rotation", 0)))
        pb = Part.Parabola()
        pb.Focal = f
        pb.Center = v
        if t:
            pb.rotate(FreeCAD.Placement(V(), FreeCAD.Rotation(V(0, 0, 1), math.degrees(t)), v))
        u0, u1 = float(item.get("from", -2 * f)), float(item.get("to", 2 * f))
        return [Part.ArcOfParabola(pb, min(u0, u1), max(u0, u1))], C, D
    if k == "hyperbola":
        c = pc.vec2(item.get("center", [0, 0]), "center")
        a_, b_ = float(item.get("major", 0)), float(item.get("minor", 0))
        if a_ <= 0 or b_ <= 0:
            raise ToolError("invalid_input", "hyperbola: center, major and minor (semi-axes, mm), rotation (deg), from and to (its parameter, -1 … 1 by default).")
        t = math.radians(float(item.get("rotation", 0)))
        h = Part.Hyperbola(c + V(math.cos(t), math.sin(t), 0) * a_, c + V(-math.sin(t), math.cos(t), 0) * b_, c)
        u0, u1 = float(item.get("from", -1)), float(item.get("to", 1))
        return [Part.ArcOfHyperbola(h, min(u0, u1), max(u0, u1))], C, D
    raise ToolError("invalid_input", "kind: line, polyline, arc, arc3, circle, circle3, ellipse, parabola, hyperbola, bspline, rectangle, rounded_rectangle, polygon, slot or point.")


def _ccw(cu, start, end, mid):
    """The parameters of a circle's arc from start to end through mid,
    counter-clockwise as Sketcher keeps arcs (start and end swapped if the
    three run clockwise)."""
    c = cu.Location

    def ang(p):
        return math.atan2(p.y - c.y, p.x - c.x)

    a0, a1, am = ang(start), ang(end), ang(mid)

    def norm(x):
        while x < 0:
            x += 2 * math.pi
        return x
    if norm(am - a0) <= norm(a1 - a0):
        lo, hi = a0, a0 + norm(a1 - a0)
    else:
        lo, hi = a1, a1 + norm(a0 - a1)
    return lo, hi


def _remap(t, ids):
    """A constraint tuple with local geometry ids -> the sketch's ids."""
    kind = t[0]
    a = list(t[1:])
    shape = {
        "Coincident": "gpgp", "Horizontal": "g", "Vertical": "g", "Equal": "gg", "PointOnObject": "gpg",
        "Diameter": "gv", "Radius": "gv", "DistanceX": "gpgpv", "DistanceY": "gpgpv", "Distance": "gpgpv",
    }.get(kind)
    if kind == "Tangent":
        shape = "gpgp"
    out = []
    for s, v in zip(shape, a):
        out.append(ids[v] if s == "g" else v)
    return (kind, *out)


# ---- constraints by name ---------------------------------------------------------------------

def _ref(r, what):
    """[geo] or [geo, pos]; 'origin' is the sketch's origin point."""
    if r == "origin":
        return (-1, 1)
    if isinstance(r, int) and not isinstance(r, bool):
        return (r, None)
    if isinstance(r, list) and r and all(isinstance(x, int) and not isinstance(x, bool) for x in r) and len(r) <= 2:
        v = r[1] if len(r) == 2 else 0
        if v not in (0, 1, 2, 3):
            raise ToolError("invalid_input", f"{what}: vertex {v} of geometry {r[0]} — 1 its start, 2 its end, 3 its centre (arcs, circles, ellipses); 0 or left out means the whole curve.")
        return (r[0], v or None)
    raise ToolError("invalid_input", f"{what}: a geometry id, [id, vertex] (vertex 1 start, 2 end, 3 centre) or \"origin\". The axes: -1 the horizontal, -2 the vertical; outside edges -3 down (sketch_external). sketch_state lists the ids.")


def make_constraint(sk, c):
    t = str(c.get("type", "")).lower().replace("_", "").replace("-", "")
    refs = [_ref(r, f"refs[{i}]") for i, r in enumerate(c.get("refs") or [])]
    val = c.get("value")
    pts = [r for r in refs if r[1] is not None]
    n = len(refs)

    def need(ok, form):
        if not ok:
            raise ToolError("invalid_input", f"{t}: refs {form}.")

    def mm():
        if not isinstance(val, (int, float)):
            raise ToolError("invalid_input", f"{t}: value, a number in mm.")
        return float(val)

    if t == "coincident":
        need(n == 2 and len(pts) == 2, "two points [[g, v], [g, v]]")
        return [("Coincident", refs[0][0], refs[0][1], refs[1][0], refs[1][1])]
    if t in ("horizontal", "vertical"):
        k = t.capitalize()
        if n == 1 and not pts:
            return [(k, refs[0][0])]
        need(n == 2 and len(pts) == 2, "one line [g], or two points [[g, v], [g, v]]")
        return [(k, refs[0][0], refs[0][1], refs[1][0], refs[1][1])]
    if t in ("parallel", "perpendicular", "equal"):
        need(n == 2 and not pts, "two geometries [g, g] (no vertices)")
        return [(t.capitalize(), refs[0][0], refs[1][0])]
    if t == "tangent":
        if n == 2 and not pts:
            return [("Tangent", refs[0][0], refs[1][0])]
        need(n == 2 and len(pts) == 2, "two curves [g, g] (tangent wherever they touch), or two end points joined smoothly [[g, v], [g, v]]")
        return [("Tangent", refs[0][0], refs[0][1], refs[1][0], refs[1][1])]
    if t == "symmetric":
        need(n == 3 and refs[0][1] and refs[1][1], "two points and a line [[g, v], [g, v], g] or a point [[g, v], [g, v], [g, v]]")
        if refs[2][1]:
            return [("Symmetric", refs[0][0], refs[0][1], refs[1][0], refs[1][1], refs[2][0], refs[2][1])]
        return [("Symmetric", refs[0][0], refs[0][1], refs[1][0], refs[1][1], refs[2][0])]
    if t == "pointonobject":
        need(n == 2 and refs[0][1] and not refs[1][1], "a point and a curve [[g, v], g]")
        return [("PointOnObject", refs[0][0], refs[0][1], refs[1][0])]
    if t in ("distance", "distancex", "distancey"):
        k = {"distance": "Distance", "distancex": "DistanceX", "distancey": "DistanceY"}[t]
        v = mm()
        if n == 1 and not pts:
            return [(k, refs[0][0], v)]
        if n == 1 and pts and k != "Distance":
            return [(k, refs[0][0], refs[0][1], v)]
        if n == 2 and len(pts) == 2:
            return [(k, refs[0][0], refs[0][1], refs[1][0], refs[1][1], v)]
        if n == 2 and refs[0][1] and not refs[1][1] and k == "Distance":
            return [(k, refs[0][0], refs[0][1], refs[1][0], v)]
        need(False, "a line [g] (its length), a point [[g, v]] (from the origin, X/Y only), two points, or a point and a line (distance)")
    if t in ("radius", "diameter"):
        need(n == 1 and not pts, "one circle or arc [g]")
        return [(t.capitalize(), refs[0][0], mm())]
    if t == "angle":
        if not isinstance(val, (int, float)):
            raise ToolError("invalid_input", "angle: value, a number in degrees.")
        a = math.radians(float(val))
        if n == 1 and not pts:
            return [("Angle", refs[0][0], a)]
        need(n == 2 and not pts, "one line [g] (its angle from +x) or two lines [g, g] (from the first's direction to the second's, each start to end, counter-clockwise)")
        return [("Angle", refs[0][0], refs[1][0], a)]
    if t in ("fix", "lock", "block"):
        need(n == 1, "one point [[g, v]] (held where it is) or one geometry [g] (blocked)")
        g, p = refs[0]
        if g < 0:
            raise ToolError("invalid_input", f"{t}: refs one point or geometry of the sketch's own (id 0 up) — the axes, the origin and outside edges are fixed already.")
        if p is None:
            return [("Block", g)]
        at = sk.getPoint(g, p)
        return [("DistanceX", g, p, at.x), ("DistanceY", g, p, at.y)]
    raise ToolError("invalid_input", f"type {c.get('type')!r}: one of coincident, horizontal, vertical, parallel, perpendicular, tangent, equal, symmetric, point_on_object, distance, distance_x, distance_y, radius, diameter, angle, fix (also lock, block).")


def con_index(sk, ref):
    if isinstance(ref, int):
        if 0 <= ref < len(sk.Constraints):
            return ref
    elif isinstance(ref, str):
        for i, c in enumerate(sk.Constraints):
            if c.Name == ref:
                return i
    raise ToolError("not_found", f"constraint {ref!r}: not in {sk.Label}, which has {len(sk.Constraints)} (ids 0 to {len(sk.Constraints) - 1}) — sketch_state lists them with their ids and names.")


# ---- what the entries call ----------------------------------------------------------------------

def gid(sk, g):
    """g, a geometry id of the sketch's own (0 up); refused otherwise."""
    if not isinstance(g, int) or not (0 <= g < len(sk.Geometry)):
        raise ToolError("invalid_input", f"geometry {g!r}: not in {sk.Label} (0 to {len(sk.Geometry) - 1}).")
    return g


def constraint(t):
    """Sketcher's constraint of a tuple (type, ids …, value)."""
    return Sketcher.Constraint(*t)


def face_frame(P):
    """The attachment offset that lines a sketch on a face (placed at P) up
    with the world: its origin the world origin's foot on the face's plane,
    its x along the world axis that lies most in the plane — so coordinates
    read as the part's own."""
    n = P.Rotation.multVec(V(0, 0, 1))
    o = n * P.Base.dot(n)
    best = max((V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)), key=lambda e: 1 - abs(e.dot(n)))
    x = best - n * best.dot(n)
    x.normalize()
    y = n.cross(x)
    D = FreeCAD.Placement(o, FreeCAD.Rotation(x, y, n, "ZXY"))
    return P.inverse().multiply(D)


def geo_of_edge(e):
    """An edge as sketch geometry: a segment, an arc or circle, else a
    B-spline through it."""
    c = e.Curve
    if isinstance(c, Part.Line):
        return Part.LineSegment(e.Vertexes[0].Point, e.Vertexes[-1].Point)
    if isinstance(c, Part.Circle):
        if e.isClosed():
            return Part.Circle(c.Location, V(0, 0, 1), c.Radius)
        # By three points on it: an offset's arc can come with its axis
        # down, which the sketch reads as the rest of the circle.
        f, l_ = e.FirstParameter, e.LastParameter
        return Part.ArcOfCircle(e.valueAt(f), e.valueAt((f + l_) / 2), e.valueAt(l_))
    return e.toNurbs().Edges[0].Curve


def offset_out(w, d, join):
    """Wire w offset by d in its plane. Out is out whichever way the profile
    runs: a closed offset meant to grow that came back smaller is done the
    other way."""
    off = w.makeOffset2D(d, join, False, not w.isClosed(), False)
    if w.isClosed() and off.Wires and off.Wires[0].isClosed():
        a0, a1 = Part.Face(w).Area, Part.Face(off.Wires[0]).Area
        if (a1 - a0) * d < 0:
            off = w.makeOffset2D(-d, join, False, False, False)
    return off


def fillet(sk, chamfer, *args):
    """Sketcher's fillet at a corner (geo, vertex, radius) or between two
    curves (geo, geo, point, point, radius), the curves trimmed to it and no
    constraints made; chamfer (FreeCAD 1.0+): a straight cut, not an arc."""
    sk.fillet(*args, True, False, *((True,) if chamfer else ()))


def bounds(sk, geos):
    """The box round those geometries of the sketch."""
    bb = None
    for g in geos:
        b2 = sk.Geometry[g].toShape().BoundBox
        bb = b2 if bb is None else bb.united(b2)
    return bb


def text_outlines(sk, words, font, hgt, at, construction):
    """Before FreeCAD 1.2 (no Text constraint): the letters' outlines added
    to the sketch as plain geometry, lines as segments and the rest as
    B-splines."""
    for ch in Part.makeWireString(words, font, hgt):
        for w in ch:
            for e in w.Edges:
                e = e.translated(V(at[0], at[1], 0))
                if isinstance(e.Curve, Part.Line):
                    g2 = Part.LineSegment(e.Vertexes[0].Point, e.Vertexes[-1].Point)
                else:
                    g2 = e.toNurbs().Edges[0].Curve
                sk.addGeometry(g2, construction)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def edge_refs(body, q):
        """The references ("Edge7") of the body's edges a shape_query filter
        names; with near, the one nearest that point. [] when none match."""
        from . import measure as M

        query = {**q, "body": body.Label, "kind": q.get("kind", "edge")}
        _, _, hits = M.query(s, query)
        if not hits:
            return []
        if q.get("near") is not None and len(hits) > 1:
            pt = pc.vec3(q["near"], "near")
            hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(pt))[0])[:1]
        return [d["ref"] for _, _, d in hits]

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "finish": lambda tool, read, recompute=True: picks.finish(s, tool, read, recompute=recompute),
               "snapshot": lambda tool: s.snapshot(tool), "steps": lambda: len(s.steps), "unique": lambda label, *own: s.unique(label, *own),
               "body": lambda ref: pc.pd_body(doc(), ref), "sketch_of": lambda ref, b=None: pc.sketch_of(doc(), ref, b), "body_of": pc.body_of,
               "body_reading": pc.body_reading, "broken": pc.newly_broken, "plane_ref": lambda *x: pc.plane_ref(*x), "support_prop": pc.support_prop,
               "version": lambda: ".".join(FreeCAD.Version()[:3]),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "setprop": setattr, "vec2": pc.vec2, "is_tuple": lambda x: isinstance(x, tuple),
               "line": lambda a, b: Part.LineSegment(a, b), "wire": lambda edges: Part.Wire(edges), "sort_edges": lambda edges: Part.sortEdges(edges),
               "quantity": lambda text: FreeCAD.Units.Quantity(text), "constraint": constraint,
               # the family's: the solver's reading, the builders, constraints by name
               "frame": frame, "state_of": state_of, "describe_geo": describe_geo, "describe_con": describe_con, "geo_kind": _geo_kind, "ext_count": ext_count,
               "con_words": con_words, "clashing": clashing, "build": build, "remap": _remap, "ref": _ref, "make_constraint": make_constraint, "con_index": con_index,
               "gid": gid, "face_frame": face_frame, "geo_of_edge": geo_of_edge, "offset_out": offset_out, "edge_refs": edge_refs, "fillet": fillet, "bounds": bounds,
               "font_file": _font, "text_outlines": text_outlines}
    return runners.tools(GROUP, s, helpers)
