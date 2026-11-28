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
from .. import runners
from ..protocol import ToolError
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


def open_edges(sh):
    """How many of a surface's edges bound one face only (its free border):
    OCC's ShapeAnalysis_Shell over its faces, which counts a cylinder's seam
    as joined. None when it cannot be read."""
    try:
        faces = sh.Faces
        if not faces:
            return None
        return len(Part.Shell(faces).getFreeEdges().Edges)
    except Exception:
        return None


def report_surface(session, o, tool, extra=None):
    """An asked-for surface's answer (solid: false): what a surface is —
    faces, area, box, its open edges — and never a solid's failings (it was
    answered "The shape is not closed … 0 solids where one is meant" with
    sound: false, as if the call had failed)."""
    def read():
        sh = o.Shape
        st = geo.stats(sh)
        out = {"body": o.Label, "surface": True, "faces": st["faces"], "area": st["area"], "box": st["box"], "valid": bool(sh.isValid())}
        free = open_edges(sh)
        if free is not None:
            out["openEdges"] = free
            out["closed"] = free == 0
        if not out["valid"]:
            out["problems"] = ["The surface is not valid (FreeCAD's isValid): history_undo, and make it another way — a profile that does not cross itself, a path with no turn tighter than the profile is wide."]
        out["note"] = ("A surface, as asked (solid: false): it has no volume and no inside, so it is not among session_state's bodies and body_check does not apply; "
                       "open edges are its border. surface_thicken gives it thickness; view_render { objects: [its name] } draws it."
                       + (" No open edges: it is closed all round — the same call with solid left out makes the solid." if free == 0 else ""))
        return out

    return picks.finish(session, tool, read, recompute=False, extra=extra)


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
        raise ToolError("invalid_input", f"{what}: not closed, so it makes no solid (solid: false makes a surface).")
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
    """The Part modelling tools are data (agentlink/data/tools.json, run by
    agentlink/runners.py's steps runner): each entry has the tool's words,
    its checks with their refusals, the order of its steps and its answer.
    What is here is what those entries call by name: the family's finishing
    code and the small functions that are geometry or FreeCAD's API
    (docs/data-tools.md)."""
    s = session
    doc = lambda: s.doc  # noqa: E731 — doc_open may change the session's document

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
            if a.get("solid", True) is False and not o.Shape.Solids:
                return report_surface(s, o, tool)
            return report(s, o, tool, check=not (late and late()))
        if not a.get("into"):
            raise ToolError("invalid_input", f"op {op}: into names the body it acts on.")
        tgt = picks.solid_body(s, a["into"])
        before = tgt.Shape
        after = {"fuse": lambda: before.fuse(result), "cut": lambda: before.cut(result), "common": lambda: before.common(result)}[op]()
        if not changed(before, after):
            raise ToolError("failed", f"op {op} into {tgt.Label} changed nothing: the made solid does not reach it (least distance {before.distToShape(result)[0]:.3f} mm).")
        o = picks.bake(s, tgt, after, a.get("name"))
        for c in consumed:
            if c is not None and hasattr(c, "Visibility"):
                c.Visibility = False
        return report(s, o, tool, {"op": op, "volumeChange": round(o.Shape.Volume - before.Volume, 2)})

    # ---- primitives ----

    def tube(ro, ri, h):
        """A tube as FreeCAD's own parametric one (BasicShapes); on an older
        or trimmed build, whatever that left is removed and it is a plain
        shape: a cylinder less its bore."""
        d = doc()
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
        return o

    def status_said(o):
        """FreeCAD's own word on an object that is not valid, for a refusal (" (FreeCAD: …)"), else nothing."""
        why = ""
        try:
            why = f" (FreeCAD: {o.getStatusString()})" if not o.isValid() else ""
        except Exception:
            pass
        return why

    # ---- booleans ----

    def boolean(shape, op, tools_):
        """shape fused with, cut by or common with the tools' shapes: one of them as itself, several as a list (OCC takes both)."""
        return {"fuse": shape.fuse, "cut": shape.cut, "common": shape.common}[op](tools_ if len(tools_) > 1 else tools_[0])

    def fuzzy_retry(shape, op, tools_, res):
        """Finding 66: OCC made an invalid result (two smooth lofts that
        overlap about 2 mm). Tried again once with a fuzzy value, 1e-4 and
        then 1e-3 of the base's box diagonal (TopoShape fuse/cut/common
        with a tolerance: OCC's SetFuzzyValue). (result, fuzzy or None,
        tried [mm]): the first valid result, else the first one as it was."""
        tried = []
        if res.isNull() or not res.Solids or res.isValid():
            return res, None, tried
        try:
            diag = float(shape.BoundBox.DiagonalLength)
        except Exception:
            return res, None, tried
        for k in (1e-4, 1e-3):
            fz = diag * k
            tried.append(round(fz, 6))
            try:
                fn = {"fuse": shape.fuse, "cut": shape.cut, "common": shape.common}[op]
                got = geo.clean(fn(list(tools_), fz))
            except Exception:
                continue
            if not got.isNull() and got.Solids and got.isValid():
                return got, round(fz, 6), tried
        return res, None, tried

    def baked(base, shape, name=None, consumed=(), keep=False):
        """picks.bake, and the labels of the inputs it hid (never silent: a hidden body is not drawn by view_render)."""
        s.last_hidden = []
        o = picks.bake(s, base, shape, name, consumed=consumed, keep=keep)
        return o, list(getattr(s, "last_hidden", []) or [])

    def inputs_left(objs, result):
        """[{object, type, visible}] for each input of a boolean that is in
        the document after it, other than the result (s1127e QA, H4: with a
        name, the base Part::Box stayed in the document, visible and uncut,
        and the answer did not say so)."""
        out = []
        names = {x.Name for x in doc().Objects}
        for o in objs:
            try:
                if o is None or o is result or o.Name not in names:
                    continue
                out.append({"object": o.Label, "type": o.TypeId, "visible": bool(getattr(o, "Visibility", True))})
            except Exception:  # noqa: BLE001 - removed meanwhile: not listed
                continue
        return out

    # ---- transforms ----

    def scaled_each(sh, c, fx, fy, fz):
        """sh scaled by a factor along each axis about c: moved to the origin, scaled, moved back (one matrix; the geometry is rebuilt)."""
        m = FreeCAD.Matrix()
        m.move(c * -1)
        m2 = FreeCAD.Matrix()
        m2.scale(fx, fy, fz)
        m = m2.multiply(m)
        m3 = FreeCAD.Matrix()
        m3.move(c)
        return sh.transformGeometry(m3.multiply(m))

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
                raise ToolError("invalid_input", f"edges: {ref!r} is not \"Edge3\" or \"Face6\" (a face takes all its edges), numbered from 1 — or edges: \"all\". shape_query {{ kind: \"edge\" }} lists them.")
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

    def queried(o, q, kind):
        """The faces or edges of o that a query picks (shape_query's own filter)."""
        q = dict(q)
        q.update(body=o.Name, kind=kind)
        _, _, hits = ms.query(s, q, kind)
        return [x for _, x, _ in hits]

    # ---- lofts ----

    class Clock:
        """The time a loft has: LOFT_BUDGET, or more where the heavy gate
        let a loft it estimated long run with a longer deadline."""

        def __init__(self):
            import time

            self.now = time.monotonic
            self.t0 = self.now()
            self.budget = max(LOFT_BUDGET, float(getattr(s, "call_budget", 0) or 0))

        def spent(self):
            return self.now() - self.t0

        def late(self):
            return self.spent() > self.budget

        def out_of_time(self, what):
            return f"out of time: {what} took {self.spent():.0f} s of the {self.budget:.0f} s a loft has (a window that stops answering is taken for hung)"

    def loft_route(clock, wires, solid, loop, ruled, deg, samples, segments):
        """The loft and how it was got, one algorithm against the clock:
        ruled between polygons; or smooth as given, then with the profiles
        rebuilt as matching B-splines, at maxDegree deg then 3 then 2, the
        least bulging kept; then span by span with the bulging spans ruled;
        two profiles OCC refuses smooth are ruled. Answers (the shape or
        None, why it is not fit to keep or None, the bulging spans, what was
        done in words, the degree used, the points a profile was rebuilt
        with)."""
        route, route_tries = [], []
        late, out_of_time = clock.late, clock.out_of_time

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
                if segments is not False and not loop and len(wires) >= 3 and clock.spent() < LOFT_BUDGET:
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
        return res, why, spans, route, used_deg, n

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

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"carry_material": lambda src, copies: picks.carry_material(s, src, copies), "doc": doc, "finish": finish, "report": lambda o, tool, extra=None, check=True: report(s, o, tool, extra, check),
               "unique": lambda label, *own: s.unique(label, *own), "solid_body": lambda ref: picks.solid_body(s, ref),
               "bake": lambda base, shape, name=None: picks.bake(s, base, shape, name), "baked": baked, "inputs_left": inputs_left, "clean": geo.clean,
               "find": lambda ref, *what: picks.find(doc(), ref, *what), "positive": positive, "num": picks.num, "vec3": picks.vec3,
               "direction": picks.direction, "placed": picks.placement, "placement_json": picks.placement_json, "ref_list": picks.ref_list,
               "split_ref": picks.split_ref, "element": picks.element,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "compound": Part.Compound, "as_shell": Part.Shell,
               "as_solid": Part.Solid, "as_wire": Part.Wire, "sorted_edges": lambda e: Part.__sortEdges__(e),
               # the family's
               "PRIMS": PRIMS, "AXIAL": AXIAL, "WEDGE": WEDGE, "tube": tube, "status_said": status_said, "boolean": boolean, "fuzzy_retry": fuzzy_retry, "changed": changed,
               "unsound_tool": unsound_tool, "fuse_dropped": fuse_dropped, "scaled_each": scaled_each, "pick_edges": pick_edges, "queried": queried,
               "profile": lambda spec, body=None, what="profile", closed_default=True: profile(s, spec, body, what, closed_default),
               "spec_points": lambda spec, what="profile": spec_points(s, spec, what), "as_face": as_face, "profile_normal": profile_normal,
               "outline_file": lambda f, key: pointfiles.outlines(paths.in_file(s, "part_loft", f, "profiles_file"), key, "profiles_file"),
               "points_along": _pts, "align_profiles": align_profiles, "loft_clock": Clock, "loft_route": loft_route, "strays": strays,
               "spans_said": spans_said}
    return runners.tools(GROUP, s, helpers)
