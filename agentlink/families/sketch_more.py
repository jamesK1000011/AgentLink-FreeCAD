# SPDX-License-Identifier: LGPL-2.1-or-later
# More Sketcher, beside sketch.py: copy, move, rotate and scale geometry,
# rectangular and polar arrays, extend a curve, join two, a carbon copy of
# another sketch, edges projected from binders and other sketches, B-spline
# conversion, and validate — the Sketcher's own repair: missing
# coincidences, degenerate geometry, redundant and invalid constraints,
# and its auto-constrainer.

import math

import FreeCAD
import Part

from .. import runners
from . import pd_common as pc
from . import picks
from .sketch import SOLVE, ext_count

GROUP = "sketch"
INFO = ("Sketches: bodies, sketches on planes and faces, geometry and constraints, offset, external edges, fillet/trim/split/mirror, "
        "copy/move/rotate/scale, arrays, extend, join, carbon copy, projection from binders, B-spline conversion, validate and repair, the solver's state.")

# The tools themselves are data (agentlink/data/tools.json, "family":
# "sketch_more", run by agentlink/runners.py's steps runner): each entry has
# the tool's words, its checks with their refusals, the order of its steps
# and its answer. What is here is what those entries call by name
# (docs/data-tools.md).

V = FreeCAD.Vector


def solver_lists(sk):
    """The solver's lists after the last solve, as constraint ids from 0
    (FreeCAD counts them from 1): { conflicting, redundant, malformed }."""
    out = {}
    for k, p in (("conflicting", "ConflictingConstraints"), ("redundant", "RedundantConstraints"), ("malformed", "MalformedConstraints")):
        try:
            v = [int(i) - 1 for i in (getattr(sk, p, None) or [])]
        except Exception:
            v = []
        if v:
            out[k] = v
    return out


def state(sk):
    """The sketch after a solve, as every tool here answers it: counts, the
    solver's verdict and its lists, degrees of freedom, wires and how many
    are closed."""
    try:
        code = sk.solve()
    except Exception:
        code = -1
    out = {"sketch": sk.Label, "geometry": len(sk.Geometry), "constraints": len(sk.Constraints), "solver": SOLVE.get(code, f"code {code}")}
    dof = getattr(sk, "DoF", None)
    if dof is not None:
        out["dof"] = dof
    out.update(solver_lists(sk))
    try:
        w = sk.Shape.Wires
        out["wires"] = len(w)
        out["closedWires"] = sum(1 for x in w if x.isClosed())
    except Exception:
        pass
    return out


def kind_of(g):
    """A curve's kind as Part names it (LineSegment, ArcOfCircle, BSplineCurve …)."""
    return type(g).__name__


def kept(sk):
    """The sketch as it is, to put back if a change fails: some Sketcher
    calls change it outside the document's undo."""
    return ([g.copy() for g in sk.Geometry], [sk.getConstruction(i) for i in range(len(sk.Geometry))], [c.clone() if hasattr(c, "clone") else c for c in sk.Constraints])


def restore(doc, sk, snap):
    """Put a sketch back as kept() read it (geometry, construction flags,
    constraints), quietly: what could not be put back is left."""
    geo, cons_flags, cons = snap
    try:
        sk.deleteAllConstraints()
        sk.deleteAllGeometry()
        if geo:
            sk.addGeometry(geo, False)
            for i, f in enumerate(cons_flags):
                if f:
                    sk.setConstruction(i, True)
        if cons:
            sk.addConstraint(cons)
        doc.recompute()
    except Exception:
        pass


def copies(sk, geos, m):
    """Copies of the sketch's geometry of those ids, each moved by the matrix m."""
    out = []
    for g in geos:
        gg = sk.Geometry[g].copy()
        gg.transform(m)
        out.append(gg)
    return out


def turn(c, ang):
    """The matrix of a turn of ang degrees (counter-clockwise) about the point c of the sketch."""
    return FreeCAD.Placement(V(), FreeCAD.Rotation(V(0, 0, 1), ang), V(c[0], c[1], 0)).toMatrix()


def scaling(c, f):
    """The matrix of a scale by f about the point c of the sketch. Uniform in
    all three: OCCT reads a matrix's scale as the cube root of its
    determinant, so (f, f, 1) scaled by f**(2/3)."""
    m = FreeCAD.Matrix()
    m.move(V(-c[0], -c[1], 0))
    m2 = FreeCAD.Matrix()
    m2.scale(f, f, f)
    m = m2.multiply(m)
    m3 = FreeCAD.Matrix()
    m3.move(V(c[0], c[1], 0))
    return m3.multiply(m)


def reach(sk, g, end, t):
    """How far line g, going on from that end (1 | 2), is from curve t, and
    how far along the line it meets it: (gap, mm). A gap over 0: they do not
    meet that way."""
    tgt = sk.Geometry[t].toShape()
    p = sk.getPoint(g, end)
    other = sk.getPoint(g, 1 if end == 2 else 2)
    dvec = p - other
    dvec.normalize()
    far = Part.LineSegment(p, p + dvec * 10000).toShape()
    dist, pts, _ = far.distToShape(tgt)
    return dist, (pts[0][0] - p).Length


def detect(sk, prec):
    """What the Sketcher's own detectors find, each one tried (a release
    without it is left out): { degenerate, missingCoincidences,
    invalidConstraints }."""
    found = {}
    try:
        found["degenerate"] = int(sk.detectDegeneratedGeometries(prec))
    except Exception:
        pass
    try:
        found["missingCoincidences"] = int(sk.detectMissingPointOnPointConstraints(prec, False) or 0)
    except Exception:
        try:
            sk.detectMissingPointOnPointConstraints(prec)
            found["missingCoincidences"] = len(sk.MissingPointOnPointConstraints) if hasattr(sk, "MissingPointOnPointConstraints") else None
        except Exception:
            pass
    try:
        # True when they are all valid, whatever its doc string says
        found["invalidConstraints"] = not bool(sk.evaluateConstraints())
    except Exception:
        pass
    return found


def lower_degree(sk, g, by):
    """Lower a B-spline's degree by so many. Sketcher answers False, with no
    error, when it could not: here that is an error."""
    if sk.decreaseBSplineDegree(g, by) is False:
        raise ValueError(f"the degree of {g} could not be lowered by {by}")


def copy_frame(src, sk):
    """Put sketch sk where src is: the same support, map mode and offset,
    or the same placement where src is not attached."""
    sup = pc.support_prop(src)
    if getattr(src, sup, None):
        setattr(sk, pc.support_prop(sk), getattr(src, sup))
        sk.MapMode = src.MapMode
        sk.MapReversed = src.MapReversed
        sk.AttachmentOffset = src.AttachmentOffset
    else:
        sk.Placement = src.Placement


def new_beside(doc, src):
    """A new sketch in src's body, or in the document when src is in none."""
    body = next((p for p in src.InList if p.TypeId == "PartDesign::Body"), None)
    return body.newObject("Sketcher::SketchObject", "Sketch") if body else doc.addObject("Sketcher::SketchObject", "Sketch")


def bring_in(sk, src, inv):
    """src's geometry (in sk's frame: inv is the inverse of the first
    sketch's placement) and constraints added to sk, the constraints' ids
    moved up by what sk already has. Answers how many constraints were left
    out: those to outside geometry, which is not brought over."""
    lost = 0
    base = len(sk.Geometry)
    m = inv.multiply(src.Placement).toMatrix()
    gs = []
    for gg in src.Geometry:
        c = gg.copy()
        c.transform(m)
        gs.append(c)
    if gs:
        sk.addGeometry(gs, False)
        for i in range(len(gs)):
            if src.getConstruction(i):
                sk.setConstruction(base + i, True)
    for c in src.Constraints:
        try:
            cc = c.clone() if hasattr(c, "clone") else c
            if cc.First >= 0:
                cc.First += base
            if getattr(cc, "Second", -2000) >= 0:
                cc.Second += base
            if getattr(cc, "Third", -2000) >= 0:
                cc.Third += base
            sk.addConstraint(cc)
        except Exception:
            lost += 1
    return lost


def mirrored(src, about):
    """src's geometry mirrored about "y" (left-right), "x" (up-down) or
    "origin". A mirror turns an arc's sense round, and Sketcher keeps arcs
    counter-clockwise: the mirrored arc runs from the image of the end to
    the image of the start."""
    M = FreeCAD.Matrix()
    if about == "y":
        M.A11 = -1
    elif about == "x":
        M.A22 = -1
    else:
        M.A11 = M.A22 = -1
    gs = []
    for gg in src.Geometry:
        if about != "origin" and type(gg).__name__ == "ArcOfCircle":
            c0, p0, p1 = (V(M.A11 * q.x, M.A22 * q.y, 0) for q in (gg.Center, gg.EndPoint, gg.StartPoint))
            a0, a1 = math.atan2(p0.y - c0.y, p0.x - c0.x), math.atan2(p1.y - c0.y, p1.x - c0.x)
            if a1 <= a0:
                a1 += 2 * math.pi
            gs.append(Part.ArcOfCircle(Part.Circle(c0, V(0, 0, 1), gg.Radius), a0, a1))
            continue
        c = gg.copy()
        c.transform(M)
        gs.append(c)
    return gs


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "finish": lambda tool, read: picks.finish(s, tool, read, recompute=False), "unique": lambda label, *own: s.unique(label, *own),
               "sketch_of": lambda ref: pc.sketch_of(doc(), ref, None), "broken": pc.newly_broken, "plane_ref": lambda *x: pc.plane_ref(*x),
               "find_edges": lambda *x: pc.find_edges(*x), "support_prop": pc.support_prop, "version": lambda: ".".join(FreeCAD.Version()[:3]),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "setprop": setattr, "vec2": pc.vec2,
               # the family's: the solver's reading, a sketch kept and put back, the geometry
               "state": state, "solver_lists": solver_lists, "ext_count": ext_count, "kind_of": kind_of, "kept": kept,
               "restore": lambda sk, snap: restore(doc(), sk, snap), "copies": copies, "turn": turn, "scaling": scaling, "reach": reach, "detect": detect,
               "lower_degree": lower_degree, "copy_frame": copy_frame, "new_beside": lambda src: new_beside(doc(), src), "bring_in": bring_in, "mirrored": mirrored}
    return runners.tools(GROUP, s, helpers, family="sketch_more")
