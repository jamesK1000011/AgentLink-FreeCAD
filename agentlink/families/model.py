# SPDX-License-Identifier: LGPL-2.1-or-later
# Part workbench modelling: primitives (FreeCAD's own parametric ones, so
# object_set can change a size later), booleans, moves and copies, fillets
# and chamfers on edges picked by reference or by query, offsets and shells,
# and solids from profiles (extrude, revolve, loft, sweep). A result that
# consumes bodies is kept as a plain shape under the first body's label, so
# setups, specs and history follow it.

import FreeCAD
import Part

from .. import geometry as geo
from .. import loftmath as lm
from .. import paths, pointfiles
from ..protocol import Tool, ToolError
from ..tools import obj
from . import measure as ms
from . import picks

GROUP = "model"
INFO = "Part modelling: primitives, booleans, move/rotate/mirror/scale/arrays, fillets and chamfers, offset and shell, extrude, revolve, loft, sweep."

V = FreeCAD.Vector

PRIMS = {
    "box": "Part::Box", "cylinder": "Part::Cylinder", "sphere": "Part::Sphere", "cone": "Part::Cone",
    "torus": "Part::Torus", "wedge": "Part::Wedge", "prism": "Part::Prism", "tube": None,
}
# Primitives with an axis (their +z) that direction can turn.
AXIAL = ("cylinder", "cone", "prism", "tube")
WEDGE = {"xmin": 0, "ymin": 0, "zmin": 0, "x2min": 2, "z2min": 2, "xmax": 10, "ymax": 10, "zmax": 10, "x2max": 8, "z2max": 8}


def positive(a, key, default):
    return picks.number(a, key, default, gt=0, msg=f"{key}: above 0, mm.")


def changed(before, after):
    """Whether a boolean did anything: the volume or the face count moved."""
    tol = max(1e-6, 1e-7 * max(before.Volume, 1.0))
    return abs(after.Volume - before.Volume) > tol or len(after.Faces) != len(before.Faces)


def unsound_tool(sh):
    """Why a boolean's tool is no sound solid, or None: OCC silently leaves
    out a tool that is invalid, open or inside out."""
    if sh.isNull() or not sh.Solids:
        return "no solid in it"
    if not sh.isValid():
        return "not valid"
    if not all(x.isClosed() for x in sh.Shells):
        return "not closed: it has open edges"
    if sh.Volume <= 1e-9:
        return f"volume {sh.Volume:.3g} mm³, not above 0: inside out"
    return None


def _outside(inner, outer, tol):
    """How far box inner reaches outside box outer (0 when inside)."""
    return max(outer.XMin - inner.XMin, inner.XMax - outer.XMax, outer.YMin - inner.YMin, inner.YMax - outer.YMax,
               outer.ZMin - inner.ZMin, inner.ZMax - outer.ZMax, 0.0) if inner.isValid() and outer.isValid() else 0.0


def fuse_dropped(base_shape, tools, res):
    """The tools a fuse left out: each that reaches clearly outside the
    base's box (so it must add something) but whose box the result does not
    hold, or whose volume the result does not reach."""
    bb = base_shape.BoundBox
    tol = max(1e-3, 1e-4 * (bb.DiagonalLength if bb.isValid() else 1.0))
    lost = []
    for t in tools:
        tb = t.Shape.BoundBox
        if _outside(tb, bb, tol) <= tol:
            continue  # inside the base's box: it may add nothing and be right
        if _outside(tb, res.BoundBox, tol) > tol or res.Volume < max(base_shape.Volume, t.Shape.Volume) * (1 - 1e-6) - 1e-6:
            lost.append(t.Label)
    return lost


def report(session, o, tool, extra=None, check=True):
    """A made body's answer: its stats and whether it is sound. check
    False (a loft out of time) leaves the soundness check to body_check
    and says so."""
    if not check:
        out = picks.finish(session, tool, lambda: {"body": o.Label, **geo.stats(o.Shape), "sound": None}, recompute=False, extra=extra)
        out["unchecked"] = f"Not checked for soundness: the call was out of time ({len(o.Shape.Faces):,} faces). body_check {o.Label} checks it (it is timed and given its own deadline)."
        return out
    s = geo.soundness(o.Shape)
    out = picks.finish(session, tool, lambda: {"body": o.Label, **geo.stats(o.Shape), "sound": s["ok"]}, recompute=False, extra=extra)
    if not s["ok"]:
        out["problems"] = s["problems"]
    return out


# ---- profiles: what extrude, revolve, loft and sweep take ----------------------------------

def spec_points(session, spec, what="profile"):
    """The points a profile spec gives: { points: [[x,y,z] …] } or
    { points_file: "<file>.json"|".csv", key } (read on this side, a
    relative path in the session's folder); None for other specs."""
    if not isinstance(spec, dict):
        return None
    if spec.get("points_file") is not None:
        if spec.get("points") is not None:
            raise ToolError("invalid_input", f"{what}: points or points_file, not both.")
        f = spec["points_file"]
        if not isinstance(f, str) or not f.strip():
            raise ToolError("invalid_input", f"{what}.points_file: a file's path (.json or .csv).")
        p = paths.in_file(session, "part_loft", f, "points_file")
        return pointfiles.one_outline(p, spec.get("key"), f"{what}.points_file")
    if "points" in spec:
        if not isinstance(spec["points"], list):
            raise ToolError("invalid_input", f"{what}.points: a list of [x, y, z].")
        return spec["points"]
    return None


def bspline_through(pts, closed):
    """A B-spline wire through the points: periodic (smooth through the
    seam) when closed."""
    if closed and len(pts) > 3 and (pts[0] - pts[-1]).Length < 1e-9:
        pts = pts[:-1]
    c = Part.BSplineCurve()
    c.interpolate(pts, PeriodicFlag=bool(closed))
    return Part.Wire([c.toShape()])


def profile(session, spec, body=None, what="profile", closed_default=True):
    """A profile as a shape (a face or a wire) and the object it came from:
    a reference ("Sketch", "Box.Face6", "Box.Edge3"), { points: [[x,y,z] …]
    or points_file, key, closed, smooth }, or { circle: { center, radius,
    normal } }."""
    raw = spec_points(session, spec, what)
    if raw is not None:
        pts = [picks.vec3(p, f"{what}.points") for p in raw]
        if len(pts) < 2:
            raise ToolError("invalid_input", f"{what}.points: two or more [x, y, z].")
        closed = spec.get("closed", closed_default)
        if closed and len(pts) < 3:
            raise ToolError("invalid_input", f"{what}.points: three or more for a closed outline.")
        if spec.get("smooth"):
            try:
                return bspline_through(pts, closed), None
            except Exception as e:
                raise ToolError("invalid_input", f"{what}.points: no smooth curve through them ({e}) — points apart, in order, none doubled.")
        if closed and (pts[0] - pts[-1]).Length > 1e-9:
            pts.append(pts[0])
        return Part.makePolygon(pts), None
    if isinstance(spec, dict) and "circle" in spec:
        c = spec["circle"] or {}
        rad = picks.number(c, "radius", what=f"{what}.circle.radius", gt=0, msg=f"{what}.circle.radius: above 0.")
        return Part.Wire([Part.makeCircle(rad, picks.vec3(c.get("center"), f"{what}.circle.center", (0, 0, 0)), picks.direction(c.get("normal"), f"{what}.circle.normal", (0, 0, 1)))]), None
    if not isinstance(spec, str):
        raise ToolError("invalid_input", f"{what}: a sketch or wire's name, a face or edge (\"Box.Face6\"), {{ points: [[x,y,z] …], closed }} or {{ circle: {{ center, radius, normal }} }}.")
    label, sub, sh = picks.resolve(session, spec, body)
    if sub:
        if sub.startswith("Edge"):
            return Part.Wire([sh]), None
        if sub.startswith("Face"):
            return sh, None
        raise ToolError("invalid_input", f"{what}: a vertex is not a profile.")
    o = picks.find(session.doc, label)
    if sh.Solids:
        raise ToolError("invalid_input", f"{what}: {o.Label} is a solid — name one of its faces (\"{o.Label}.Face6\"; shape_query finds it).")
    if sh.Faces and len(sh.Faces) == 1:
        return sh.Faces[0], o
    wires = sh.Wires or ([Part.Wire(Part.__sortEdges__(sh.Edges))] if sh.Edges else [])
    if not wires:
        raise ToolError("invalid_input", f"{what}: {o.Label} has no wire.")
    if len(wires) == 1:
        return wires[0], o
    return Part.Compound(wires), o


def as_face(sh, what="profile"):
    """A closed profile as a face (holes kept), for a solid."""
    if sh.ShapeType == "Face":
        return sh
    wires = sh.Wires
    if not wires or not all(w.isClosed() for w in wires):
        raise ToolError("invalid_input", f"{what}: not closed, so it makes no solid — close the outline, or solid: false for a surface.")
    try:
        return Part.makeFace(wires, "Part::FaceMakerBullseye")
    except Exception:
        try:
            return Part.Face(wires[0])
        except Exception as e:
            raise ToolError("failed", f"{what}: no face from it ({e}) — is it flat?")


def profile_normal(sh):
    if sh.ShapeType == "Face":
        return ms.face_normal(sh)
    try:
        pl = sh.findPlane()
        if pl is not None:
            return pl.Axis
    except Exception:
        pass
    return V(0, 0, 1)


# ---- loft profiles lined up, and the loft checked -------------------------------------------

def _pts(w, n=64):
    try:
        return list(w.discretize(Number=n))
    except Exception:
        return [v.Point for v in w.OrderedVertexes]


def winding_normal(w):
    """The way a closed wire runs round (right-hand rule), by Newell's sum
    over points along it, in the order the wire runs; None when it has no
    area to speak of."""
    p = _pts(w)
    if len(p) < 3:
        return None
    n = V(0, 0, 0)
    for a, b in zip(p, p[1:] + p[:1]):
        n = n + V((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y))
    return n if n.Length > 1e-12 else None


def centre(w):
    p = _pts(w, 48)
    c = V(0, 0, 0)
    for x in p:
        c = c + x
    return c * (1.0 / len(p)) if p else V(0, 0, 0)


def start_of(w):
    return w.OrderedVertexes[0].Point


def _one_curve(w):
    """The curve of a wire of one closed edge (a periodic B-spline, a
    circle), else None."""
    es = w.Edges
    if len(es) != 1:
        return None
    try:
        return es[0].Curve
    except Exception:
        return None


def reversed_wire(w):
    """The same outline running the other way round, rebuilt (not a flag
    a loft may read past)."""
    c = _one_curve(w)
    if c is not None and hasattr(c, "reverse"):
        e = w.Edges[0]
        try:
            c2 = c.copy()
            c2.reverse()
            return Part.Wire([c2.toShape()])
        except Exception:
            try:
                return Part.Wire([e.reversed()])
            except Exception:
                pass
    vs = [v.Point for v in w.OrderedVertexes]
    if all(isinstance(getattr(e, "Curve", None), Part.Line) for e in w.Edges) and len(vs) >= 2:
        pts = list(reversed(vs))
        if w.isClosed():
            pts.append(pts[0])
        return Part.makePolygon(pts)
    return w.reversed()


def started_at(w, target):
    """A closed wire whose seam (start) is at its point nearest target: a
    periodic B-spline re-parameterized there (a knot put in and made the
    origin), a wire of several edges started at its nearest corner."""
    c = _one_curve(w)
    if c is not None and isinstance(c, Part.BSplineCurve) and c.isPeriodic():
        try:
            u = c.parameter(target)
            c2 = c.copy()
            knots = c2.getKnots()
            near = min(range(len(knots)), key=lambda i: abs(knots[i] - u))
            if abs(knots[near] - u) > 1e-9:
                c2.insertKnot(u, 1, 1e-9)
                knots = c2.getKnots()
                near = min(range(len(knots)), key=lambda i: abs(knots[i] - u))
            c2.setOrigin(near + 1)
            nw = Part.Wire([c2.toShape()])
            if (start_of(nw) - c.value(u)).Length < 1e-4 * max(1.0, w.BoundBox.DiagonalLength):
                return nw
        except Exception:
            pass
        try:
            # Else the same curve sampled from that point round and drawn
            # through again (a hair off the original, never a twist).
            u = c.parameter(target)
            f, per = c.FirstParameter, c.LastParameter - c.FirstParameter
            n = max(48, 2 * c.NbPoles)
            pts = [c.value(f + ((u - f) + per * k / n) % per) for k in range(n)]
            c3 = Part.BSplineCurve()
            c3.interpolate(pts, PeriodicFlag=True)
            return Part.Wire([c3.toShape()])
        except Exception:
            return w
    es = w.OrderedEdges
    if len(es) < 2:
        return w
    vs = [v.Point for v in w.OrderedVertexes]
    k = min(range(len(vs)), key=lambda i: (vs[i] - target).Length)
    if k == 0:
        return w
    if all(isinstance(getattr(e, "Curve", None), Part.Line) for e in es):
        pts = vs[k:] + vs[:k]
        return Part.makePolygon(pts + [pts[0]])
    try:
        return Part.Wire(es[k:] + es[:k])
    except Exception:
        return w


def align_profiles(wires):
    """Profiles lined up for a loft: each closed one running round the same
    way along the loft (reversed where its winding disagrees with the way
    from the profile before to the next), and each seam at the point
    nearest the previous profile's start. Open profiles are turned so each
    starts at the end nearest the previous start. (wires, what was done)."""
    done = []
    if len(wires) < 2:
        return wires, done
    out = list(wires)
    if all(w.isClosed() for w in out):
        cs = [centre(w) for w in out]
        for i, w in enumerate(out):
            d = (cs[min(i + 1, len(cs) - 1)] - cs[max(i - 1, 0)])
            n = winding_normal(w)
            if n is None or d.Length < 1e-9:
                continue
            if n.dot(d) < 0:
                out[i] = reversed_wire(w)
                done.append(f"profiles.{i} reversed to run the same way round as the others")
        for i in range(1, len(out)):
            before = start_of(out[i])
            out[i] = started_at(out[i], start_of(out[i - 1]))
            if (start_of(out[i]) - before).Length > 1e-6:
                done.append(f"profiles.{i} started at the point nearest profiles.{i - 1}'s start")
    else:
        for i in range(1, len(out)):
            w, prev = out[i], start_of(out[i - 1])
            vs = w.OrderedVertexes
            if len(vs) >= 2 and (vs[-1].Point - prev).Length < (vs[0].Point - prev).Length:
                out[i] = reversed_wire(w)
                done.append(f"profiles.{i} reversed to start at the end nearest profiles.{i - 1}'s start")
    return out, done


# How far a loft may reach beyond the profiles' joint box, as a share of
# that box (each way, never under a quarter of its longest side's share).
LOFT_REACH = 0.15
# Seconds part_loft spends on tries (rebuilt profiles, lower degrees, span
# by span) before it answers with what it has: past the watchdog's change
# deadline a busy window is taken for a hung one.
LOFT_BUDGET = 60.0


def tight_box(sh):
    """The shape's box from its geometry itself. Shape.BoundBox of a
    B-spline face or edge not yet drawn is the box of its control points,
    which stand off a smooth loft through many sections by far more than
    the surface does: read that way, a sound loft looked like a 16–73%
    bulge."""
    try:
        bb = sh.optimalBoundingBox(False, False)
        if bb.isValid():
            return bb
    except Exception:
        pass
    try:
        pts = sh.tessellate(max(1e-3, sh.BoundBox.DiagonalLength / 400.0))[0] if sh.Faces else sh.discretize(Number=256)
        if pts:
            bb = FreeCAD.BoundBox()
            for p in pts:
                bb.add(p)
            return bb
    except Exception:
        pass
    return sh.BoundBox


def _box6(bb):
    return (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)


def loft_overshoot(res, wires):
    """How far the loft reaches beyond the profiles' joint box, as a share
    of the box (0 when inside the allowance), and the axis. Both boxes are
    read from the geometry, not from control points."""
    bb = FreeCAD.BoundBox()
    for w in wires:
        bb.add(tight_box(w))
    return lm.reach_beyond(_box6(tight_box(res)), _box6(bb), LOFT_REACH)


def loft_spans(res, wires):
    """The spans (profiles i to i + 1) whose part of the loft reaches
    beyond those two profiles' own box by more than LOFT_REACH, worst
    first: [{span, share, axis}]."""
    try:
        pts = [lm.tup(p) for p in res.tessellate(max(1e-3, res.BoundBox.DiagonalLength / 300.0))[0]]
    except Exception:
        return []
    return lm.span_bulges(pts, [_box6(tight_box(w)) for w in wires], [lm.tup(centre(w)) for w in wires], LOFT_REACH)


def spans_said(spans, k=4):
    return "; ".join(f"profiles {x['span'][0]}–{x['span'][1]} by {x['share'] * 100:.0f}% along {x['axis']}" for x in spans[:k]) + (f" (and {len(spans) - k} more)" if len(spans) > k else "")


def outline_points(w, n):
    """n points spread by arc length round (or along) a wire, from its start."""
    dense = _pts(w, max(8 * n, 256))
    closed = w.isClosed()
    if closed and len(dense) > 2 and (dense[0] - dense[-1]).Length < 1e-9:
        dense = dense[:-1]
    return lm.resample(dense, n, closed)


def is_polygon(w):
    return all(isinstance(getattr(e, "Curve", None), Part.Line) for e in w.Edges)


def sample_count(wires, asked=None):
    """How many points each profile is rebuilt with: asked, else enough for
    the finest profile (its corners or its B-spline's poles, twice), 48 or
    more, 256 at most."""
    if asked:
        return asked
    need = 24
    for w in wires:
        c = _one_curve(w)
        if c is not None and hasattr(c, "NbPoles"):
            need = max(need, 2 * c.NbPoles)
        else:
            need = max(need, len(w.OrderedVertexes) if is_polygon(w) else 2 * len(w.Edges) * 12)
    return int(min(256, max(48, need)))


def as_polygons(wires, n):
    """Each profile a polygon of the same n points (arc length, seams lined
    up), so a ruled loft pairs point with point. Profiles that are polygons
    of one corner count already keep their corners."""
    closed = wires[0].isClosed()
    if all(is_polygon(w) for w in wires) and len({len(w.OrderedVertexes) for w in wires}) == 1:
        outs = [[lm.tup(v.Point) for v in w.OrderedVertexes] for w in wires]
        kept = True
    else:
        outs = [outline_points(w, n) for w in wires]
        kept = False
    if closed:
        outs, _ = lm.line_up(outs)
    ws = [Part.makePolygon([V(*p) for p in o] + ([V(*o[0])] if closed else [])) for o in outs]
    return ws, kept, len(outs[0])


def as_matching_bsplines(wires, n):
    """Each profile rebuilt as a B-spline through the same n points (arc
    length, seams lined up) with one and the same parameters, so every
    section has the same knots and OCC has nothing to make compatible."""
    closed = wires[0].isClosed()
    outs = [outline_points(w, n) for w in wires]
    if closed:
        outs, _ = lm.line_up(outs)
    m = len(outs[0]) + (1 if closed else 0)
    params = [i / float(m - 1) for i in range(m)]
    ws = []
    for o in outs:
        c = Part.BSplineCurve()
        c.interpolate([V(*p) for p in o], PeriodicFlag=closed, Parameters=params)
        ws.append(Part.Wire([c.toShape()]))
    return ws


def strays(res, sources, budget=2.0):
    """How far the result strays from the points it was made from: the
    largest and mean distance, and which profile; None if not measured."""
    import time as _t

    per = max(4, 480 // max(1, len(sources)))
    worst, which, tot, cnt = 0.0, None, 0.0, 0
    t0 = _t.time()
    try:
        shell = res.Faces[0] if len(res.Faces) == 1 else Part.Compound(res.Faces)
    except Exception:
        return None
    for i, pts in enumerate(sources):
        if not pts:
            continue
        step = max(1, len(pts) // per)
        for p in pts[::step]:
            try:
                d = shell.distToShape(Part.Vertex(p))[0]
            except Exception:
                continue
            tot, cnt = tot + d, cnt + 1
            if d > worst:
                worst, which = d, i
            if _t.time() - t0 > budget:
                break
        if _t.time() - t0 > budget:
            break
    if not cnt:
        return None
    return {"maxDistance": round(worst, 4), "meanDistance": round(tot / cnt, 4), "profile": which, "points": cnt}


def loft_problem(res, wires, solid):
    """Why a loft is not fit to keep, or None."""
    if res.isNull():
        return "it came out empty"
    over, axis = loft_overshoot(res, wires)
    if over:
        return f"profiles twist or the smooth loft overshoots: it bulges {over * 100:.0f}% of the profiles' size beyond them along {axis}"
    if not res.isValid():
        return "it came out invalid"
    if solid:
        if not res.Solids:
            return "it made no solid"
        if not all(x.isClosed() for x in res.Shells):
            return "not closed: it has open edges"
        if res.Volume <= 1e-9:
            return f"its volume is {res.Volume:.3g} mm³, not above 0"
    return None


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731 — doc_open may change the session's document
    body = {"type": "string", "description": "A body's name or label; may be left out when there is one."}
    prof = {"description": "A sketch or wire's name, a face or edge (\"Box.Face6\"), { points: [[x,y,z] …], closed: true, smooth }, { points_file: \"<file>.json\"|\".csv\", key } (points read from a file in the session's folder, not sent in the call) or { circle: { center, radius, normal } }."}
    common_in = {"into": body, "op": {"type": "string", "enum": ["new", "fuse", "cut", "common"]}, "name": {"type": "string"}}

    def finish(result, a, tool, consumed=(), late=None):
        """A made solid: a new body, or fused into / cut from / common with
        `into`. late(): whether the call is out of time (a loft): then the
        coplanar faces are left unmerged and the soundness check is left
        to body_check, said in the answer."""
        op = a.get("op") or ("fuse" if a.get("into") else "new")
        if op == "new":
            o = doc().addObject("Part::Feature", "Body")
            o.Label = s.unique(a.get("name") or tool.split("_")[1].capitalize())
            o.Shape = result if late and late() else geo.clean(result)
            for c in consumed:
                if c is not None and hasattr(c, "Visibility"):
                    c.Visibility = False
            doc().recompute()
            return report(s, o, tool, check=not (late and late()))
        if not a.get("into"):
            raise ToolError("invalid_input", f"op {op}: into names the body it acts on.")
        tgt = picks.solid_body(s, a["into"])
        before = tgt.Shape
        after = {"fuse": lambda: before.fuse(result), "cut": lambda: before.cut(result), "common": lambda: before.common(result)}[op]()
        if not changed(before, after):
            raise ToolError("failed", f"op {op} into {tgt.Label} changed nothing: the made solid does not reach it (least distance {before.distToShape(result)[0]:.3f} mm) — check the direction and length.")
        o = picks.bake(s, tgt, after, a.get("name"))
        for c in consumed:
            if c is not None and hasattr(c, "Visibility"):
                c.Visibility = False
        return report(s, o, tool, {"op": op, "volumeChange": round(o.Shape.Volume - before.Volume, 2)})

    # ---- primitives ----

    def part_primitive(a):
        kind = picks.choice(a, "kind", PRIMS, f"kind: one of {', '.join(PRIMS)}.")
        pl = picks.placement(a)
        if a.get("direction") is not None:
            # The axis (+z of the primitive) turned to point along direction,
            # then any rotate on top of that, about at.
            if kind not in AXIAL:
                raise ToolError("invalid_input", f"direction: for {', '.join(AXIAL)} (their axis); a {kind} turns with rotate.")
            aim = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), picks.direction(a.get("direction"), "direction"))
            pl = FreeCAD.Placement(pl.Base, pl.Rotation.multiply(aim))
        label = s.unique(a.get("name") or kind.capitalize())
        d = doc()
        if kind == "box":
            size = a.get("size", [10, 10, 10])
            if not (isinstance(size, list) and len(size) == 3 and all(isinstance(x, (int, float)) and x > 0 for x in size)):
                raise ToolError("invalid_input", "size: [x, y, z], each above 0 mm.")
            o = d.addObject("Part::Box", "Box")
            o.Length, o.Width, o.Height = [float(x) for x in size]
        elif kind == "cylinder":
            o = d.addObject("Part::Cylinder", "Cylinder")
            o.Radius, o.Height = positive(a, "radius", 5), positive(a, "height", 10)
        elif kind == "sphere":
            o = d.addObject("Part::Sphere", "Sphere")
            o.Radius = positive(a, "radius", 5)
        elif kind == "cone":
            r1, r2 = positive(a, "radius", 5), picks.num(a.get("radius2", 0), "radius2")
            if r2 < 0 or abs(r1 - r2) < 1e-9:
                raise ToolError("invalid_input", "radius2: the top radius, 0 or more and not equal to radius (that is a cylinder).")
            o = d.addObject("Part::Cone", "Cone")
            o.Radius1, o.Radius2, o.Height = r1, r2, positive(a, "height", 10)
        elif kind == "torus":
            r1, r2 = positive(a, "radius", 10), positive(a, "radius2", 2)
            if r2 >= r1:
                raise ToolError("invalid_input", "radius2: the tube's radius, under radius (the ring's).")
            o = d.addObject("Part::Torus", "Torus")
            o.Radius1, o.Radius2 = r1, r2
        elif kind == "wedge":
            w = dict(WEDGE)
            bad = [k for k in (a.get("wedge") or {}) if k not in WEDGE]
            if bad:
                raise ToolError("invalid_input", f"wedge.{bad[0]}: the keys are {', '.join(WEDGE)}.")
            w.update({k: picks.num(v, f"wedge.{k}") for k, v in (a.get("wedge") or {}).items()})
            if not (w["xmax"] > w["xmin"] and w["ymax"] > w["ymin"] and w["zmax"] > w["zmin"] and w["x2max"] >= w["x2min"] and w["z2max"] >= w["z2min"]):
                raise ToolError("invalid_input", "wedge: each max above its min (x2/z2 may be equal: a ridge).")
            o = d.addObject("Part::Wedge", "Wedge")
            for k, v in w.items():
                setattr(o, k[0].upper() + k[1:], v)
        elif kind == "prism":
            n = int(a.get("sides", 6))
            if n < 3:
                raise ToolError("invalid_input", "sides: 3 or more.")
            o = d.addObject("Part::Prism", "Prism")
            o.Polygon, o.Circumradius, o.Height = n, positive(a, "radius", 5), positive(a, "height", 10)
        else:  # tube
            ro, ri, h = positive(a, "radius", 5), picks.num(a.get("radius2", 2), "radius2"), positive(a, "height", 10)
            if not 0 < ri < ro:
                raise ToolError("invalid_input", "radius2: the bore's radius, above 0 and under radius.")
            before = {x.Name for x in d.Objects}
            try:
                from BasicShapes import Shapes

                o = Shapes.addTube(d, "Tube")
                o.OuterRadius, o.InnerRadius, o.Height = ro, ri, h
            except Exception:  # an older or trimmed build: a plain shape
                for x in [x for x in d.Objects if x.Name not in before]:
                    d.removeObject(x.Name)
                o = d.addObject("Part::Feature", "Tube")
                o.Shape = Part.makeCylinder(ro, h).cut(Part.makeCylinder(ri, h))
        o.Label = label
        o.Placement = pl
        d.recompute()
        if o.Shape.isNull() or not o.Shape.Solids:
            raise ToolError("failed", f"The {kind} came out empty — check its sizes.")
        return report(s, o, "part_primitive", {"kind": kind, "type": o.TypeId, "placement": picks.placement_json(o.Placement)})

    # ---- booleans ----

    def part_boolean(a):
        op = picks.choice(a, "op", ("fuse", "cut", "common"), "op: fuse, cut or common.")
        base = picks.solid_body(s, a.get("base"))
        names = a.get("tools")
        names = picks.ref_list(names, "tools: the bodies to fuse, cut away or keep in common with base.")
        tl = [picks.solid_body(s, n) for n in names]
        if any(t is base for t in tl):
            raise ToolError("invalid_input", "tools: base is among them — a body with itself changes nothing.")
        bs = base.Shape
        shapes = [t.Shape for t in tl]
        for t in tl:
            why = unsound_tool(t.Shape)
            if why:
                raise ToolError("failed", f"{op}: the tool {t.Label} is not a sound solid ({why}), so OCC would drop it and leave {base.Label} as it was. Nothing was changed; {t.Label} is kept. "
                                f"body_check {t.Label} says more; part_fix or part_refine {{ fix: true }} may repair it, else rebuild it.")
        res = {"fuse": bs.fuse, "cut": bs.cut, "common": bs.common}[op](shapes if len(shapes) > 1 else shapes[0])
        res = geo.clean(res)
        if not res.isNull() and res.Solids and not res.isValid():
            raise ToolError("failed", f"{op}: OCC made an invalid result from {base.Label} and {', '.join(t.Label for t in tl)}. Nothing was changed; the tools are kept. "
                            "Overlap the pieces clearly (not face on face), or fewer faces first (part_refine).")
        if op == "fuse":
            lost = fuse_dropped(bs, tl, res)
            if lost:
                raise ToolError("failed", f"fuse: nothing of {', '.join(lost)} was added to {base.Label} although it reaches outside {base.Label}'s box (volume change {res.Volume - bs.Volume:.2f} mm³): "
                                "OCC dropped the tool. Nothing was changed; the tools are kept. Check each with body_check, overlap the pieces clearly (not face on face), or fewer faces first (part_refine).")
        if op == "common" and res.Volume < 1e-6:
            raise ToolError("failed", f"common: {base.Label} and {', '.join(t.Label for t in tl)} do not overlap (least distance {bs.distToShape(shapes[0])[0]:.3f} mm) — nothing would be left.")
        if not changed(bs, res):
            dist = min(bs.distToShape(x)[0] for x in shapes)
            why = "they do not touch" if dist > 1e-6 else ("the tools lie inside it" if op == "fuse" else "they only touch it")
            raise ToolError("failed", f"{op} changed nothing in {base.Label}: {why} (least distance {dist:.3f} mm). Move a tool into the base (part_transform), then again.")
        o = picks.bake(s, base, res, a.get("name"), consumed=tl, keep=bool(a.get("keep")))
        extra = {"op": op, "volumeChange": round(o.Shape.Volume - bs.Volume, 2), ("kept" if a.get("keep") else "removed"): [t.Label for t in tl]}
        if len(o.Shape.Solids) > 1:
            extra["note"] = f"{len(o.Shape.Solids)} separate solids: pieces that do not touch."
        return report(s, o, "part_boolean", extra)

    # ---- transforms ----

    def part_transform(a):
        o = picks.solid_body(s, a.get("body"))
        op = a.get("op")
        sh = o.Shape
        about = picks.vec3(a.get("about"), "about", (0, 0, 0)) if a.get("about") is not None else None
        if op in ("move", "rotate"):
            if op == "move":
                pl = FreeCAD.Placement(picks.vec3(a.get("by"), "by"), FreeCAD.Rotation())
            else:
                c = about if about is not None else sh.BoundBox.Center
                pl = FreeCAD.Placement(V(), FreeCAD.Rotation(picks.direction(a.get("axis"), "axis", (0, 0, 1)), picks.num(a.get("angle"), "angle")), c)
            if a.get("copy"):
                new = sh.copy()
                new.Placement = pl.multiply(new.Placement)
                n = doc().addObject("Part::Feature", "Body")
                n.Label = s.unique(a.get("name") or o.Label)
                n.Shape = new
                doc().recompute()
                return report(s, n, "part_transform", {"op": op, "from": o.Label})
            o.Placement = pl.multiply(o.Placement)
            doc().recompute()
            return report(s, o, "part_transform", {"op": op, "placement": picks.placement_json(o.Placement)})
        if op == "mirror":
            c = about if about is not None else sh.BoundBox.Center
            new = sh.mirror(c, picks.direction(a.get("normal"), "normal", (1, 0, 0)))
            if a.get("fuse"):
                res = sh.fuse(new)
                return report(s, picks.bake(s, o, res, a.get("name")), "part_transform", {"op": "mirror", "fused": True})
        elif op == "scale":
            f = a.get("factor")
            c = about if about is not None else V(0, 0, 0)
            if isinstance(f, list):
                fx, fy, fz = [picks.num(x, "factor") for x in (f + [1, 1, 1])[:3]]
                if min(fx, fy, fz) <= 0:
                    raise ToolError("invalid_input", "factor: each above 0.")
                m = FreeCAD.Matrix()
                m.move(c * -1)
                m2 = FreeCAD.Matrix()
                m2.scale(fx, fy, fz)
                m = m2.multiply(m)
                m3 = FreeCAD.Matrix()
                m3.move(c)
                new = sh.transformGeometry(m3.multiply(m))
            else:
                fac = picks.num(f, "factor")
                if fac <= 0:
                    raise ToolError("invalid_input", "factor: above 0 — a number, or [fx, fy, fz] for each axis.")
                new = sh.copy()
                new.scale(fac, c)
        elif op in ("linear", "polar"):
            n = int(a.get("count", 2))
            if n < 2:
                raise ToolError("invalid_input", "count: 2 or more, the original counted.")
            copies = [sh]
            if op == "linear":
                step = picks.vec3(a.get("step"), "step")
                for i in range(1, n):
                    c2 = sh.copy()
                    c2.translate(step * i)
                    copies.append(c2)
            else:
                axis = picks.direction(a.get("axis"), "axis", (0, 0, 1))
                c = about if about is not None else V(0, 0, 0)
                total = picks.num(a.get("angle", 360), "angle")
                each = total / n if abs(abs(total) - 360) < 1e-9 else total / (n - 1)
                for i in range(1, n):
                    c2 = sh.copy()
                    c2.rotate(c, axis, each * i)
                    copies.append(c2)
            if a.get("fuse", True):
                res = copies[0].fuse(copies[1:])
            else:
                res = Part.Compound(copies)
            o2 = picks.bake(s, o, res, a.get("name"))
            extra = {"op": op, "count": n}
            if len(o2.Shape.Solids) > 1:
                extra["note"] = f"{len(o2.Shape.Solids)} separate solids: the copies do not touch — one body holding them."
            return report(s, o2, "part_transform", extra)
        else:
            raise ToolError("invalid_input", "op: move { by }, rotate { axis, angle, about }, mirror { normal, about, fuse }, scale { factor, about }, linear { count, step }, polar { count, axis, about, angle }.")
        n = doc().addObject("Part::Feature", "Body")
        n.Label = s.unique(a.get("name") or f"{o.Label} {op}")
        n.Shape = geo.clean(new)
        doc().recompute()
        return report(s, n, "part_transform", {"op": op, "from": o.Label})

    # ---- fillets and chamfers ----

    def pick_edges(o, a):
        sh = o.Shape
        out = []
        refs = a.get("edges")
        if refs == "all":
            return list(sh.Edges)
        for ref in refs or []:
            head, sub = picks.split_ref(ref) if isinstance(ref, str) else (None, None)
            if not sub:
                raise ToolError("invalid_input", f"edges: {ref!r} is not \"Edge3\" or \"Face6\" (a face takes all its edges).")
            if head and picks.find(doc(), head) is not o:
                raise ToolError("invalid_input", f"edges: {ref} is on another body than {o.Label}.")
            el = picks.element(sh, sub, o.Label)
            out.extend([sh.Edges[picks.index_of(sh, e, "Edges") - 1] for e in el.Edges] if sub.startswith("Face") else [sh.Edges[int(sub[4:]) - 1]])
        if a.get("query"):
            q = dict(a["query"])
            q.update(body=o.Name, kind="edge")
            _, _, hits = ms.query(s, q, "edge")
            out.extend(x for _, x, _ in hits)
        uniq = []
        for e in out:
            if not any(e.isSame(u) for u in uniq):
                uniq.append(e)
        if not uniq:
            raise ToolError("invalid_input", "No edge picked: edges [\"Edge3\", \"Face6\" …] or \"all\", or query { type, axis, radius, near, inside, of } as shape_query takes.")
        return uniq

    def round_edges(kind):
        def run(a):
            o = picks.solid_body(s, a.get("body"))
            size = positive(a, "radius" if kind == "fillet" else "size", 1)
            edges = pick_edges(o, a)
            sh = o.Shape
            try:
                res = sh.makeFillet(size, edges) if kind == "fillet" else sh.makeChamfer(size, edges)
            except Exception as e:
                raise ToolError("failed", f"The {kind} of {size} mm on {len(edges)} edges failed ({e}): try a smaller size, fewer edges at once, or the edges of one face.")
            if res.isNull() or not res.isValid() or not res.Solids:
                raise ToolError("failed", f"The {kind} left a broken shape: {size} mm is likely more than a face beside an edge can take — smaller, or fewer edges.")
            o2 = picks.bake(s, o, res, a.get("name"))
            return report(s, o2, f"part_{kind}", {"edges": len(edges), "volumeChange": round(o2.Shape.Volume - sh.Volume, 2)})

        return run

    # ---- offset and shell ----

    def part_offset(a):
        o = picks.solid_body(s, a.get("body"))
        d = picks.num(a.get("distance"), "distance")
        if abs(d) < 1e-6:
            raise ToolError("invalid_input", "distance: not 0 — out (+) or in (-), mm.")
        join = {"arc": 0, "intersection": 2}.get(a.get("join", "arc"))
        if join is None:
            raise ToolError("invalid_input", "join: arc (rounded corners) or intersection (sharp).")
        try:
            res = o.Shape.makeOffsetShape(d, 1e-6, join=join, fill=False)
        except Exception as e:
            raise ToolError("failed", f"The offset failed ({e}): a smaller distance, or join: arc.")
        if not res.Solids:
            try:
                res = Part.Solid(Part.Shell(res.Faces)) if res.Faces else res
            except Exception:
                pass
        if res.isNull() or not res.Solids:
            raise ToolError("failed", f"The offset of {d} mm left no solid: inward past half the thinnest wall, or a fillet smaller than it.")
        o2 = picks.bake(s, o, res, a.get("name"))
        return report(s, o2, "part_offset", {"distance": d})

    def part_thickness(a):
        o = picks.solid_body(s, a.get("body"))
        t = positive(a, "thickness", 1)
        sh = o.Shape
        faces = []
        for ref in a.get("open") or []:
            head, sub = picks.split_ref(ref)
            if not sub or not sub.startswith("Face"):
                raise ToolError("invalid_input", f"open: {ref!r} — faces to remove (\"Face6\").")
            faces.append(picks.element(sh, sub, o.Label))
        if a.get("query"):
            q = dict(a["query"])
            q.update(body=o.Name, kind="face")
            _, _, hits = ms.query(s, q, "face")
            faces.extend(x for _, x, _ in hits)
        if not faces:
            raise ToolError("invalid_input", "open: the faces to remove, at least one (\"Face6\"), or query { normal: \"+z\", sort: \"-z\", limit: 1 }.")
        inward = a.get("inward", True)
        try:
            res = sh.makeThickness(faces, -t if inward else t, 1e-3, False, False, 0, {"arc": 0, "intersection": 2}.get(a.get("join", "intersection"), 2))
        except Exception as e:
            raise ToolError("failed", f"The shell failed ({e}): a thinner wall, or join: arc, or remove fewer faces.")
        if res.isNull() or not res.Solids or res.Volume < 1e-6:
            raise ToolError("failed", f"The shell of {t} mm left no solid: thinner than half the part's smallest size.")
        if not res.isValid():
            raise ToolError("failed", f"The shell of {t} mm is not valid: a thinner wall, or fillets larger than {t} mm first.")
        o2 = picks.bake(s, o, res, a.get("name"))
        return report(s, o2, "part_thickness", {"thickness": t, "inward": bool(inward), "opened": len(faces), "volumeChange": round(o2.Shape.Volume - sh.Volume, 2)})

    # ---- solids from profiles ----

    def part_extrude(a):
        sh, src = profile(s, a.get("profile"), a.get("body"))
        solid = a.get("solid", True)
        base = as_face(sh) if solid else sh
        if a.get("direction") is not None:
            vec = picks.vec3(a["direction"], "direction")
            if a.get("length") is not None:
                vec = picks.direction(a["direction"], "direction") * picks.num(a["length"], "length")
        else:
            vec = profile_normal(sh) * picks.num(a.get("length", 10), "length")
        if vec.Length < 1e-9:
            raise ToolError("invalid_input", "length: not 0.")
        if a.get("symmetric"):
            base = base.copy()
            base.translate(vec * -0.5)
        res = base.extrude(vec)
        if solid and not res.Solids:
            raise ToolError("failed", "The extrusion made no solid: the profile must be a closed, flat outline.")
        return finish(res, a, "part_extrude", [src])

    def part_revolve(a):
        sh, src = profile(s, a.get("profile"), a.get("body"))
        solid = a.get("solid", True)
        base = as_face(sh) if solid else sh
        ang = picks.num(a.get("angle", 360), "angle")
        res = base.revolve(picks.vec3(a.get("at"), "at", (0, 0, 0)), picks.direction(a.get("axis"), "axis", (0, 0, 1)), ang)
        if solid and not res.Solids:
            try:
                res = Part.Solid(Part.Shell(res.Faces))
            except Exception:
                raise ToolError("failed", "The revolve made no solid: the profile must be closed and not cross the axis.")
        if solid and res.Volume < 0:
            res.reverse()
        return finish(res, a, "part_revolve", [src])

    def part_loft(a):
        specs = a.get("profiles") or []
        if a.get("profiles_file") is not None:
            if specs:
                raise ToolError("invalid_input", "profiles or profiles_file, not both.")
            f = a["profiles_file"]
            if not isinstance(f, str) or not f.strip():
                raise ToolError("invalid_input", "profiles_file: a file's path (.json or .csv) holding every profile's points.")
            found = pointfiles.outlines(paths.in_file(s, "part_loft", f, "profiles_file"), a.get("key"), "profiles_file")
            specs = [{"points": pts, "closed": True, "smooth": bool(a.get("smooth", False))} for _, pts in found]
        if not isinstance(specs, list) or len(specs) < 2:
            raise ToolError("invalid_input", "profiles: two or more, in order (or profiles_file with two or more outlines).")
        wires, srcs, given = [], [], []
        for i, p in enumerate(specs):
            sh, src = profile(s, p, a.get("body"), f"profiles.{i}")
            if sh.ShapeType == "Face":
                sh = sh.OuterWire
            elif sh.ShapeType != "Wire":
                if len(sh.Wires) != 1:
                    raise ToolError("invalid_input", f"profiles.{i}: one wire each — {len(sh.Wires)} here.")
                sh = sh.Wires[0]
            wires.append(sh)
            srcs.append(src)
            raw = spec_points(s, p, f"profiles.{i}") if isinstance(p, dict) else None
            given.append([picks.vec3(q, "points") for q in raw] if raw is not None else _pts(sh, 48))
        solid = bool(a.get("solid", True))
        open_ = [i for i, w in enumerate(wires) if not w.isClosed()]
        if solid and open_:
            raise ToolError("invalid_input", f"not closed: profiles.{open_[0]} is an open edge or wire, so the loft has no inside. Close it (part_wire {{ kind: \"bspline\", closed: true }}), or solid: false for a surface.")
        if open_ and len(open_) != len(wires):
            raise ToolError("invalid_input", f"profiles: each closed or each open — profiles.{open_[0]} is open, the others closed.")
        deg = a.get("maxDegree", 5)
        if isinstance(deg, bool) or not isinstance(deg, int) or not 1 <= deg <= 8:
            raise ToolError("invalid_input", "maxDegree: a whole number 1 to 8 (5 by default, FreeCAD's): the most the loft may bend along its way; lower is stiffer and overshoots less.")
        samples = a.get("samples")
        if samples is not None and (isinstance(samples, bool) or not isinstance(samples, int) or not 8 <= samples <= 512):
            raise ToolError("invalid_input", "samples: how many points each profile is rebuilt with when it must be, 8 to 512.")
        segments = a.get("segments")
        loop = bool(a.get("closed", False))
        if segments and loop:
            raise ToolError("invalid_input", "segments: not with closed: true (a loft back to its first profile).")
        wires, aligned = align_profiles(wires)
        ruled = bool(a.get("ruled", False))
        route, route_tries = [], []

        import time as _time

        t0 = _time.monotonic()
        # The time the call has: LOFT_BUDGET, or more where the heavy gate
        # let a loft it estimated long run with a longer deadline.
        budget = max(LOFT_BUDGET, float(getattr(s, "call_budget", 0) or 0))

        def late():
            return _time.monotonic() - t0 > budget

        def out_of_time(what):
            return f"out of time: {what} took {_time.monotonic() - t0:.0f} s of the {budget:.0f} s a loft has (a window that stops answering is taken for hung)"

        def make(ws, rl, d):
            """(result, why not kept) — why None when it is fit to keep."""
            if route_tries and late():
                return None, out_of_time("the tries so far")
            route_tries.append(d)
            try:
                r = Part.makeLoft(ws, solid, rl, loop, d)
            except Exception as e:
                return None, f"OCC could not build it ({e})"
            if late():
                # OCC's loft alone used the time: checking it (validity on
                # thousands of faces) would run past the deadline.
                return None, out_of_time(f"OCC's loft ({len(r.Faces):,} faces)")
            if solid and r.Solids and r.Volume < 0:
                r.reverse()
            why = loft_problem(r, ws, solid)
            if why is None and late():
                return r, None
            if why and late():
                return None, out_of_time("the loft and its check") + f"; it was not fit to keep: {why}"
            if why and not why.startswith("profiles twist"):
                try:
                    r2 = r.copy()
                    r2.fix(1e-7, 1e-7, 1e-3)
                    if solid and not r2.Solids and r2.Shells:
                        r2 = Part.Solid(r2.Shells[0])
                    if solid and r2.Solids and r2.Volume < 0:
                        r2.reverse()
                    if loft_problem(r2, ws, solid) is None:
                        route.append("OCC's shape fix repaired the loft")
                        return r2, None
                except Exception:
                    pass
            return r, why

        n = sample_count(wires, samples)
        res, why, spans, tried = None, None, [], []
        used_deg = deg
        if ruled:
            # A ruled loft pairs edge with edge: B-splines (one closed edge
            # each, knots apart) failed it outright, polygons of one point
            # count never do.
            pw, kept, cnt = as_polygons(wires, n)
            res, why = make(pw, True, deg)
            route.append(f"ruled: each profile as it was, a polygon of {cnt} corners, seams lined up" if kept
                         else f"ruled: each profile made a polygon of the same {cnt} points, spread by arc length, seams lined up")
        else:
            rebuilt = {}

            def profiles_for(which):
                if which == "given":
                    return wires
                if "ws" not in rebuilt:
                    try:
                        rebuilt["ws"] = as_matching_bsplines(wires, n)
                    except Exception as e:
                        rebuilt["ws"] = None
                        tried.append(f"rebuilt|err|the profiles could not be rebuilt ({e})")
                return rebuilt["ws"]

            refused, first = {}, {}
            best = None  # (share, result, wires, degree, why)
            for d in [deg] + [x for x in (3, 2) if x < deg]:
                for which in ("given", "rebuilt"):
                    ws = profiles_for(which)
                    if ws is None or which in refused:
                        continue
                    r, w = make(ws, False, d)
                    if w is None:
                        res, used_deg = r, d
                        if which == "rebuilt":
                            said = f"OCC refused them as given ({refused['given']})" if "given" in refused else f"as given it bulged {first['given'] * 100:.0f}%"
                            route.append(f"profiles rebuilt as B-splines through the same {n} points each (arc length, seams lined up, one set of knots): {said}")
                        if d != deg:
                            route.append(f"maxDegree lowered to {d}: at {deg} the loft bulged {min(first.values()) * 100:.0f}% beyond its profiles")
                        break
                    if r is None or not w.startswith("profiles twist"):
                        refused[which] = w
                        tried.append(f"{which}|err|{w}")
                        continue
                    share = loft_overshoot(r, ws)[0]
                    first.setdefault(which, share)
                    if best is None or share < best[0]:
                        best = (share, r, ws, d, w)
                if res is not None:
                    break
            if res is None and best is not None:
                spans = loft_spans(best[1], best[2])
                why = best[4]
                if segments is not False and not loop and len(wires) >= 3 and _time.monotonic() - t0 < LOFT_BUDGET:
                    seg = segmented(best[2], spans, best[3], solid)
                    if seg is not None:
                        res, why, used_deg = seg[0], None, best[3]
                        route.append(f"segments: lofted span by span and joined — {seg[1]} ruled (they bulged smooth: {spans_said(spans)}), the rest smooth at maxDegree {best[3]}")
            if res is None and best is None and len(wires) == 2:
                # Two profiles: a smooth loft is straight between them anyway.
                pw, kept, cnt = as_polygons(wires, n)
                r, w = make(pw, True, deg)
                if w is None:
                    res, why = r, None
                    route.append(f"OCC refused a smooth loft of the two profiles ({tried[0].split('|', 2)[-1] if tried else 'failed'}); between two profiles it is straight anyway, so it is ruled between polygons of {cnt} points each (arc length, seams lined up)")
            if res is None and why is None:
                why = tried[0].split("|", 2)[-1] if tried else "it failed"
        if res is None or why:
            if why and why.startswith("profiles twist"):
                hint = ""
                if spans:
                    hint += f" Where: {spans_said(spans)}."
                hint += (" Tried maxDegree " + ", ".join(str(d) for d in [deg] + [d for d in (3, 2) if d < deg]) + " and the profiles rebuilt alike." if not ruled else "")
                hint += (" Lofted span by span with those spans ruled, it was not sound either." if segments is not False and spans and not ruled and not loop and len(wires) >= 3 else "")
                hint += " ruled: true for straight runs; more profiles where the shape turns quickly; or loft the bulging span's neighbours apart and part_boolean fuse."
            elif why and why.startswith("out of time"):
                k = max(2, len(wires) // 2 + 1)
                pts = max(8, int(n * 0.7))
                hint = (f" Lighter: split it into lofts of about {k} profiles (each run starting on the profile the last ended on) and part_boolean fuse them; "
                        f"or fewer points a profile (samples: {pts}); or fewer profiles where the shape changes slowly.")
            else:
                hint = " Each profile closed (or each open), in order along the loft, none crossing another."
            raise ToolError("failed", f"The loft is not kept: {why}.{hint} Nothing was added.")
        extra = {}
        if aligned:
            # One line a profile ran to 51 lines: a count and the first few.
            extra["aligned"] = aligned if len(aligned) <= 4 else aligned[:3] + [f"… and {len(aligned) - 3} more profiles lined up alike ({len(aligned)} in all)"]
        if route:
            extra["route"] = route
        if not ruled:
            extra["maxDegree"] = used_deg
        st = None if late() else strays(res, given)
        if st:
            if st.get("profile") is None:
                st.pop("profile", None)
            else:
                st["profile"] = f"profiles.{st['profile']}"
            extra["strays"] = st
        out = finish(res, a, "part_loft", srcs, late=late)
        if extra and isinstance(out, dict):
            out.update(extra)
        return out

    def segmented(ws, spans, d, solid):
        """The loft span by span: the bulging spans ruled (each its own two
        profiles), the runs between them smooth, sewn into one; checked as
        a whole loft is. (shape, the ruled spans said) or None."""
        bad = set()
        for _ in range(3):
            bad |= {x["span"][0] for x in spans} or set()
            if not bad:
                return None
            faces = []
            try:
                for i, j, rl in lm.pieces(len(ws), bad):
                    part = ws[i:j + 1]
                    try:
                        r = Part.makeLoft(part, False, rl, False, d)
                    except Exception:
                        if not rl:
                            return None
                        r = Part.makeLoft(part, False, False, False, d)
                    faces.extend(r.Faces)
                if solid:
                    faces.append(Part.Face(ws[0]))
                    faces.append(Part.Face(ws[-1]))
                sewn = Part.Compound(faces)
                sewn.sewShape()
                if solid:
                    if len(sewn.Shells) != 1 or not sewn.Shells[0].isClosed():
                        return None
                    res = Part.Solid(sewn.Shells[0])
                    if res.Volume < 0:
                        res.reverse()
                else:
                    res = sewn.Shells[0] if len(sewn.Shells) == 1 else sewn
            except Exception:
                return None
            if loft_problem(res, ws, solid) is None and (not solid or geo.soundness(res)["ok"]):
                return res, ", ".join(f"{i}–{i + 1}" for i in sorted(bad))
            spans = loft_spans(res, ws)
            if not spans or {x["span"][0] for x in spans} <= bad:
                return None
        return None

    def part_sweep(a):
        sh, src = profile(s, a.get("profile"), a.get("body"))
        if sh.ShapeType == "Face":
            sh = sh.OuterWire
        path_spec = a.get("path")
        if isinstance(path_spec, dict) and "points" in path_spec:
            path_spec = {**path_spec, "closed": path_spec.get("closed", False)}
        path, psrc = profile(s, path_spec, a.get("body"), "path", closed_default=False)
        if path.ShapeType == "Face":
            path = path.OuterWire
        if path.ShapeType != "Wire":
            path = Part.Wire(Part.__sortEdges__(path.Edges))
        solid = bool(a.get("solid", True))
        try:
            res = path.makePipeShell([sh], solid, bool(a.get("frenet", False)), {"none": 0, "right": 1, "round": 2}.get(a.get("corners", "right"), 1))
        except Exception as e:
            raise ToolError("failed", f"The sweep failed ({e}): the profile at the path's start, across it; a path without sharp turns tighter than the profile.")
        if solid and not res.Solids:
            raise ToolError("failed", "The sweep made no solid: a closed profile.")
        return finish(res, a, "part_sweep", [src, psrc])

    placement_in = {"at": {"type": "array", "items": {"type": "number"}}, "rotate": {"type": "object", "description": "{ axis: [x,y,z], angle: degrees } about at"}}
    direction_in = {"direction": {"type": "array", "items": {"type": "number"}, "description": "[x,y,z]: where a cylinder's, cone's, prism's or tube's axis points from at (+z when left out); rotate turns it further."}}
    return [
        Tool(
            "part_primitive",
            "Add a FreeCAD primitive as a body: box { size [x,y,z] } (a corner at at), cylinder { radius, height }, cone { radius, radius2 (top), height }, prism { sides, radius (to a corner), height } and tube { radius, radius2 (bore), height } (base centred at at, up +z, or along direction [x,y,z]), sphere { radius } and torus { radius, radius2 } (centred), wedge { wedge: { xmin … z2max } as FreeCAD's Part Wedge }. at [x,y,z] and rotate { axis, angle } place it. Parametric: object_set changes a size later (Length, Radius …) until a boolean bakes it.",
            obj({"kind": {"type": "string", "enum": list(PRIMS)}, "size": {"type": "array", "items": {"type": "number"}}, "radius": {"type": "number"}, "radius2": {"type": "number"}, "height": {"type": "number"}, "sides": {"type": "integer"}, "wedge": {"type": "object"}, **placement_in, **direction_in, "name": {"type": "string"}}, ["kind"]),
            part_primitive,
            changes=True,
        ),
        Tool(
            "part_boolean",
            "fuse, cut or common base with tools (bodies). The result keeps base's name (name: a new one) as a plain shape, coplanar faces merged; the tools are removed (keep: true hides them — a hidden body is still a body to the other tools). Refused when nothing would change (not touching, or inside for fuse), for common with no overlap, when a tool is not a sound solid (invalid, open, inside out) and when a fuse drops a tool OCC could not join; the tools are kept then. A boolean of many faces (meshes made solids) is asked about first with its time: the window is frozen while OCC works. Answers whether the result is sound (valid, closed, volume above 0, no sliver faces).",
            obj({"op": {"type": "string", "enum": ["fuse", "cut", "common"]}, "base": body, "tools": {"description": "A body or a list of them."}, "keep": {"type": "boolean"}, "name": {"type": "string"}}, ["op", "tools"]),
            part_boolean,
            changes=True,
        ),
        Tool(
            "part_transform",
            "Move or copy a body: move { by [dx,dy,dz] }, rotate { axis, angle degrees, about [x,y,z] (its box centre by default) } — in place, copy: true for a new body; mirror { normal, about (box centre) } and scale { factor or [fx,fy,fz], about (origin) } make a new body (mirror fuse: true joins the mirror to the original); linear { count, step [dx,dy,dz] } and polar { count, axis, about, angle (360 shares out evenly) } array the body into itself, fused (fuse: false keeps the copies apart in one body). Trap: face numbers change after this; shape_query again.",
            obj({"op": {"type": "string", "enum": ["move", "rotate", "mirror", "scale", "linear", "polar"]}, "body": body, "by": {"type": "array", "items": {"type": "number"}}, "axis": {}, "angle": {"type": "number"}, "about": {"type": "array", "items": {"type": "number"}}, "normal": {}, "factor": {}, "count": {"type": "integer"}, "step": {"type": "array", "items": {"type": "number"}}, "copy": {"type": "boolean"}, "fuse": {"type": "boolean"}, "name": {"type": "string"}}, ["op"]),
            part_transform,
            changes=True,
        ),
        Tool(
            "part_fillet",
            "Round edges of a body: radius mm; edges [\"Edge3\", \"Face6\" (all its edges) …] or \"all\", and/or query { type, axis, radius, near, inside, of: \"Face6\" … } as shape_query takes for edges. Refused with a broken result: a radius larger than a face beside the edge allows. Trap: fillet last — a later boolean renumbers edges and may not keep the round tidy.",
            obj({"body": body, "radius": {"type": "number"}, "edges": {}, "query": {"type": "object"}, "name": {"type": "string"}}, ["radius"]),
            round_edges("fillet"),
            changes=True,
        ),
        Tool(
            "part_chamfer",
            "Bevel edges of a body by size mm, the edges picked as part_fillet picks them (edges refs, \"all\", or query).",
            obj({"body": body, "size": {"type": "number"}, "edges": {}, "query": {"type": "object"}, "name": {"type": "string"}}, ["size"]),
            round_edges("chamfer"),
            changes=True,
        ),
        Tool(
            "part_offset",
            "Grow (+) or shrink (-) a solid by distance mm all round; join arc (rounded corners, default) or intersection (sharp). Refused when it leaves no solid (shrunk past half the thinnest part).",
            obj({"body": body, "distance": {"type": "number"}, "join": {"type": "string", "enum": ["arc", "intersection"]}, "name": {"type": "string"}}, ["distance"]),
            part_offset,
            changes=True,
        ),
        Tool(
            "part_thickness",
            "Shell a solid: open the faces named (open [\"Face6\"] or query { normal: \"+z\", sort: \"-z\", limit: 1 }) and leave walls of thickness mm, inward by default (inward: false grows outward). join intersection (sharp, default) or arc. Trap: fillets smaller than the wall break it — shell first, or a thinner wall.",
            obj({"body": body, "thickness": {"type": "number"}, "open": {"type": "array", "items": {"type": "string"}}, "query": {"type": "object"}, "inward": {"type": "boolean"}, "join": {"type": "string", "enum": ["arc", "intersection"]}, "name": {"type": "string"}}, ["thickness"]),
            part_thickness,
            changes=True,
        ),
        Tool(
            "part_extrude",
            "Extrude a profile into a solid: length along its normal (a face's outward one; +z for a flat outline), or direction [x,y,z] (its length, or length given); symmetric splits it both ways. op new (default without into) | fuse (default with into) | cut | common with into: a boss or a pocket in one call. Refused when the cut or fuse misses into. solid: false gives a surface from an open profile. The source sketch is hidden.",
            obj({"profile": prof, "body": body, "length": {"type": "number"}, "direction": {"type": "array", "items": {"type": "number"}}, "symmetric": {"type": "boolean"}, "solid": {"type": "boolean"}, **common_in}, ["profile"]),
            part_extrude,
            changes=True,
        ),
        Tool(
            "part_revolve",
            "Revolve a profile about an axis: axis [x,y,z] (+z) through at [x,y,z] (origin), angle degrees (360). The profile must not cross the axis. op / into as part_extrude.",
            obj({"profile": prof, "body": body, "axis": {}, "at": {"type": "array", "items": {"type": "number"}}, "angle": {"type": "number"}, "solid": {"type": "boolean"}, **common_in}, ["profile"]),
            part_revolve,
            changes=True,
        ),
        Tool(
            "part_loft",
            "A solid through two or more profiles in order (each a sketch, face, wire, { points }, { points_file, key } or { circle }; { points, smooth: true } is a B-spline through the points), or all at once from profiles_file (a .json list of point lists, or a .csv; key picks a list inside; smooth: true for B-splines): many sections read from a file, not sent in the call. "
            "The profiles are lined up first (each run the same way round, each seam at the point nearest the one before: aligned says what changed). ruled: true is straight between them: each profile is made a polygon of the same number of points (spread by arc length, seams lined up; samples sets it; polygons of one corner count keep theirs), so it always pairs up, and route says so. "
            "Smooth (the default): if OCC refuses the profiles as given, they are rebuilt as B-splines through the same points with one set of knots; if the loft bulges more than 15% beyond its profiles (read from the surface, not its control points), it is tried again at maxDegree 3 then 2 (maxDegree: 1–8, 5 by default; lower is stiffer); if it still bulges, it is lofted span by span with the bulging spans ruled and sewn into one, kept only if sound (segments: false turns that off). route says what was done; a refusal names the spans that bulge (profiles i–i+1, by how much) so ruled or more profiles can go there. "
            "Two profiles that OCC will not loft smooth are ruled between matching polygons (straight between two anyway). closed: back to the first. The answer gives strays: how far the result lies from the points it was made from at most and on average, and the profile. Refused, with the reason, when invalid, open or inside out. A loft of many profiles and points is heavy (its time grows about as the cube of its faces: 91 profiles of 36 points ruled 10 s, of 80 points over 2 min): it is estimated first from profiles x points (ruled and smooth timed apart) and, past a minute, refused once with the estimate and how to split it (runs of profiles fused, or fewer points: samples) — the same call again runs it, the watchdog waiting its estimate times three. Past its time (60 s, or twice an estimate it was let run on) it stops — between tries, after OCC's loft, before the checks — and says so; a kept loft made late is not soundness-checked (unchecked says so: body_check it). aligned gives the first few changes and a count. op / into as part_extrude.",
            obj({"profiles": {"type": "array", "items": {}, "description": "Each a sketch or wire's name, a face (\"Box.Face6\"), { points: [[x,y,z] …], closed, smooth }, { points_file: \"<file>.json\"|\".csv\", key, closed, smooth } or { circle }."},
                 "profiles_file": {"type": "string", "description": "A .json (a list of [[x,y,z] …] lists, or an object of them) or .csv (x,y,z rows; outlines apart by blank lines or named in a first column) holding every profile, in order. A relative path is in the session's folder."},
                 "key": {"description": "With profiles_file: the name (or number from 0) of the list in the file that holds the profiles."},
                 "smooth": {"type": "boolean", "description": "With profiles_file: B-splines through the points (else polygons)."},
                 "body": body, "ruled": {"type": "boolean"}, "closed": {"type": "boolean"}, "solid": {"type": "boolean"},
                 "maxDegree": {"type": "integer", "minimum": 1, "maximum": 8}, "samples": {"type": "integer", "minimum": 8, "maximum": 512},
                 "segments": {"type": "boolean", "description": "false: no span-by-span loft when a smooth one bulges."}, **common_in}),
            part_loft,
            changes=True,
        ),
        Tool(
            "part_sweep",
            "Sweep a closed profile along a path (a wire or sketch, an edge \"Box.Edge3\", or { points } — open by default): frenet: true keeps a helix's profile upright; corners right (default), round or none at sharp turns. Trap: put the profile at the path's start, across it. op / into as part_extrude.",
            obj({"profile": prof, "path": prof, "body": body, "frenet": {"type": "boolean"}, "corners": {"type": "string", "enum": ["right", "round", "none"]}, "solid": {"type": "boolean"}, **common_in}, ["profile", "path"]),
            part_sweep,
            changes=True,
        ),
    ]
