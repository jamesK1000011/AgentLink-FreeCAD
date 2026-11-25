# SPDX-License-Identifier: LGPL-2.1-or-later
# More Sketcher, beside sketch.py: copy, move, rotate and scale geometry,
# rectangular and polar arrays, extend a curve, join two, a carbon copy of
# another sketch, edges projected from binders and other sketches, B-spline
# conversion, and validate — the Sketcher's own repair: missing
# coincidences, degenerate geometry, redundant and invalid constraints,
# and its auto-constrainer.

import math
import re

import FreeCAD
import Part

from .. import runners
from . import pd_common as pc
from . import picks
from ..protocol import ToolError
from .sketch import SOLVE, axes, ext_count

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


# Bicycle L5 build (21 Nov, finding 3): a tube profile sketch hung square to
# a binder's edge (NormalToEdge) lost its edge after a VarSet change
# ("missing element reference Binder010 ;Edge1;:H10f,..."). sketch_attach
# { edge } hangs it on an edge again in place, with a feature built from it;
# repair: true points each element of its support at the element of the same
# number on the same object.
EDGE_MODES = ("NormalToEdge", "FrenetNB", "FrenetTN", "FrenetTB", "Concentric", "RevolutionSection")
_ELEMENT = re.compile(r"(Edge|Face|Vertex)(\d+)")


def _plain(sub):
    """The element of a sub-name as its type and number ("Edge1"), out of
    a mapped one (";Edge1;:H10f,E…" or "Binder.;g3;SKT.Edge1"); None for none."""
    hits = _ELEMENT.findall(str(sub or ""))
    return (hits[-1][0] + hits[-1][1]) if hits else None


def _has_element(o, el):
    try:
        return o.Shape.getElement(el) is not None
    except Exception:
        return False


def _support_list(sk):
    """The sketch's support as [(object, [subs])]."""
    out = []
    for item in getattr(sk, pc.support_prop(sk), None) or []:
        try:
            o, subs = item[0], item[1]
        except Exception:
            continue
        out.append((o, list(subs) if isinstance(subs, (list, tuple)) else [subs]))
    return out


def attach_edge(doc, sk, b, a):
    """sketch_attach { edge, mode, at } or { repair: true }: the sketch hung
    on the edge (or its support re-pointed) where it is in the body, its
    offset and reversed kept unless given. Refused, with the sketch as it was,
    when FreeCAD cannot attach it. The answer's extra."""
    prop = pc.support_prop(sk)
    off0 = sk.AttachmentOffset
    was = (getattr(sk, prop, None), str(sk.MapMode), bool(getattr(sk, "MapReversed", False)), FreeCAD.Placement(off0.Base, off0.Rotation),
           float(getattr(sk, "MapPathParameter", 0.0) or 0.0))
    if a.get("repair"):
        if a.get("edge") is not None:
            raise ToolError("invalid_input", "edge or repair, not both: repair points the sketch's own support at the element of the same number; edge gives a new one.")
        sup = _support_list(sk)
        if not sup:
            raise ToolError("invalid_state", f"{sk.Label} has no support to repair (MapMode {sk.MapMode}): sketch_attach {{ plane | face | edge }} attaches it.")
        new, changed = [], []
        for o, subs in sup:
            keep = []
            for sub in subs:
                el = _plain(sub) if sub else sub
                if sub and el is None:
                    raise ToolError("invalid_state", f"{sk.Label}: the support element {sub!r} of {o.Label} names no edge, face or vertex — sketch_attach {{ edge | face | plane }} gives a new one.")
                if el and not _has_element(o, el):
                    raise ToolError("invalid_state", f"{sk.Label}: {o.Label} has no {el} now — sketch_attach {{ edge: \"{o.Label}.EdgeN\" }} with an edge it has (shape_query {{ body: \"{o.Label}\", kind: \"edge\" }} names them).")
                if el != sub:
                    changed.append(f"{o.Label}.{el}")
                keep.append(el or "")
            if keep:
                new.extend((o, x) for x in keep)
            else:
                new.append((o, ""))
        mode, what = str(sk.MapMode), ", ".join(f"{o.Label}.{x}" if x else o.Label for o, x in new)
    else:
        ref = str(a.get("edge") or "").strip()
        obj_ref, _, el = ref.rpartition(".")
        if not obj_ref or not _ELEMENT.fullmatch(el or "") or not el.startswith("Edge"):
            raise ToolError("invalid_input", f"edge {ref!r}: an object and one of its edges, \"Binder.Edge1\" (shape_query {{ body, kind: \"edge\" }} names them).")
        o = picks.find(doc, obj_ref, "edge")
        try:
            later = o in list(getattr(sk, "InListRecursive", None) or [])
        except Exception:
            later = False
        if later:
            raise ToolError("invalid_state", f"{o.Label} is built from {sk.Label}: hanging the sketch on its edge makes a cycle. Use an edge of an object made before the sketch (a binder of the skeleton).")
        if not _has_element(o, el):
            raise ToolError("invalid_input", f"edge {ref!r}: {o.Label} has no {el} (shape_query {{ body: \"{o.Label}\", kind: \"edge\" }} names its edges).")
        mode = str(a.get("mode") or "NormalToEdge")
        if mode not in EDGE_MODES:
            raise ToolError("invalid_input", f"mode {mode!r}: on an edge, one of {', '.join(EDGE_MODES)} (NormalToEdge: square to the edge, at its start or where at says).")
        new, what, changed = [(o, el)], f"{o.Label}.{el}", []
    try:
        setattr(sk, prop, new)
        sk.MapMode = mode
        if a.get("reversed") is not None:
            sk.MapReversed = bool(a.get("reversed"))
        if a.get("at") is not None:
            t = float(a.get("at"))
            if not 0.0 <= t <= 1.0:
                raise ToolError("invalid_input", f"at {t:g}: where on the edge, 0 (its start) to 1 (its end).")
            sk.MapPathParameter = t
        if a.get("offset") is not None or a.get("rotate") is not None:
            off = sk.AttachmentOffset
            z = float(a["offset"]) if a.get("offset") is not None else float(off.Base.z)
            rot = FreeCAD.Rotation(V(0, 0, 1), float(a["rotate"])) if a.get("rotate") is not None else off.Rotation
            sk.AttachmentOffset = FreeCAD.Placement(V(off.Base.x, off.Base.y, z), rot)
        doc.recompute()
        bad = None if sk.isValid() else sk.getStatusString()
    except ToolError:
        _put_support(sk, prop, was)
        raise
    except Exception as e:  # noqa: BLE001 - said, with the sketch put back
        bad = str(e)
    if bad:
        _put_support(sk, prop, was)
        doc.recompute()
        raise ToolError("failed", f"{sk.Label} would not attach to {what} ({mode}): {bad} — it stays as it was.")
    out = {"sketch": sk.Label, "on": what, "mode": mode, "support": what}
    if changed:
        out["repaired"] = changed
        out["note"] = f"{sk.Label} now names {', '.join(changed)} by number: the same element as before if the object's edges kept their order. sketch_state and the body's health show the result."
    try:
        out["at"] = round(float(sk.MapPathParameter), 4)
    except Exception:
        pass
    return out


def _put_support(sk, prop, was):
    sup, mode, rev, off, t = was
    try:
        setattr(sk, prop, sup)
        sk.MapMode = mode
        sk.MapReversed = rev
        sk.AttachmentOffset = off
        if "MapPathParameter" in sk.PropertiesList:
            sk.MapPathParameter = t
    except Exception:  # noqa: BLE001
        pass


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "finish": lambda tool, read: picks.finish(s, tool, read, recompute=False), "unique": lambda label, *own: s.unique(label, *own),
               "sketch_of": lambda ref: pc.sketch_of(doc(), ref, None, s), "broken": pc.newly_broken, "plane_ref": lambda *x: pc.plane_ref(*x),
               "find_edges": lambda *x: pc.find_edges(*x), "support_prop": pc.support_prop, "version": lambda: ".".join(FreeCAD.Version()[:3]),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "setprop": setattr, "vec2": pc.vec2,
               # the family's: the solver's reading, a sketch kept and put back, the geometry
               "attach_edge": lambda sk, b, a: attach_edge(doc(), sk, b, a), "state": state, "solver_lists": solver_lists, "ext_count": ext_count, "kind_of": kind_of, "kept": kept,
               "restore": lambda sk, snap: restore(doc(), sk, snap), "copies": copies, "turn": turn, "scaling": scaling, "reach": reach, "detect": detect,
               "lower_degree": lower_degree, "copy_frame": copy_frame, "new_beside": lambda src: new_beside(doc(), src), "bring_in": bring_in, "mirrored": mirrored, "axes": axes}
    return runners.tools(GROUP, s, helpers, family="sketch_more")
