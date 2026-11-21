# SPDX-License-Identifier: LGPL-2.1-or-later
# PartDesign features, one call each: pad, pocket, revolution, groove,
# hole, fillet, chamfer, draft, thickness, mirror and patterns, loft, pipe,
# datum planes; and the body's history — list, edit, remove, suppress.
# Faces and edges are named by where they are, not by index. A feature
# that fails is refused with FreeCAD's own error and nothing is kept.

import json
import re

import FreeCAD

from .. import runners
from . import pd_common as pc
from . import picks
from ..protocol import ToolError

GROUP = "feature"
INFO = "PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, datum planes) and the body's feature history."

# The tools themselves are data (agentlink/data/tools.json, run by
# agentlink/runners.py's steps runner): each entry has the tool's words, its
# checks with their refusals, the order of its steps and its answer. What is
# here is what those entries call by name: the family's finishing code and
# the small functions that are FreeCAD's API (docs/data-tools.md).

V = FreeCAD.Vector
KEYS = ("SideType", "Type", "Type2", "Length", "Length2", "Offset", "TaperAngle", "Midplane", "Reversed", "Angle", "Angle2", "Radius", "ChamferType", "Size", "Size2", "Value", "Join",
        "Occurrences", "TransformMode", "Factor", "Diameter", "Depth", "DepthType", "Threaded", "ModelThread", "ThreadType", "ThreadSize", "HoleCutType", "HoleCutDiameter", "HoleCutDepth",
        "Ruled", "Closed", "Mode", "Pitch", "Height", "Turns", "Suppressed", "Refine")


def has(o, p):
    return p in o.PropertiesList


def set_sides(f, side, length2=None):
    """A pad's or pocket's one | two | symmetric, after its Type is set.
    FreeCAD 1.1: SideType ("One side", "Two sides", "Symmetric") with a
    Type2 / Length2 for the second side; before it, Midplane and Type
    TwoLengths (1.1 warns when Midplane is set, and keeps "?TwoLengths" only
    to read old files). False where this FreeCAD has no two sides for the
    feature's Type (the entry refuses), True otherwise."""
    if side in (None, "one"):
        return True
    if has(f, "SideType"):
        f.SideType = {"two": "Two sides", "symmetric": "Symmetric"}[side]
        if side == "two" and length2 is None and has(f, "Type2") and f.Type == "ThroughAll":
            f.Type2 = "ThroughAll"  # through all, both ways: the second side is a 5 mm length otherwise
    elif side == "symmetric":
        f.Midplane = True
    elif f.Type != "Length":
        return False
    else:
        f.Type = "TwoLengths"
    if side == "two" and length2 is not None:
        f.Length2 = float(length2)
    return True


def thread_key(name):
    """(8.0, 1.0) of "M8x1", "M8x1.0" or "m8 x 1"; (5.0, None) of "M5";
    None of what is not a metric designation."""
    m = re.match(r"^\s*[Mm]\s*(\d+(?:\.\d+)?)(?:\s*[xX×]\s*(\d+(?:\.\d+)?))?\s*$", str(name))
    return (float(m.group(1)), float(m.group(2)) if m.group(2) else None) if m else None


def thread_pick(sizes, thread, coarse):
    """The designation in sizes that thread names: the same text, else the
    same diameter and pitch (FreeCAD 1.1 writes "M5x0.8", "M8x1.0"); a
    diameter alone picks the coarse one."""
    if thread in sizes:
        return thread
    want = thread_key(thread)
    if want is None:
        return None
    for z in sizes:
        k = thread_key(z)
        if k is None or abs(k[0] - want[0]) > 1e-9:
            continue
        if want[1] is None:
            if coarse:
                return z
        elif k[1] is not None and abs(k[1] - want[1]) <= 1e-9:
            return z
    return None


def hole_spots(sk, f):
    """How many holes the sketch gives: FreeCAD drills at every circle and
    arc that is not construction geometry, and (1.1, by the Hole's
    BaseProfileType: 1 points, 2 circles, 4 arcs) at every sketch point."""
    mask = int(getattr(f, "BaseProfileType", 6))
    n = 0
    for i, g in enumerate(sk.Geometry):
        try:
            if sk.getConstruction(i):
                continue
        except Exception:
            pass
        t = type(g).__name__
        if (t == "Circle" and mask & 2) or (t == "ArcOfCircle" and mask & 4) or (t == "Point" and mask & 1):
            n += 1
    return n, bool(mask & 1)


def key_values(f):
    """A feature's key values as feature_list shows them: each of KEYS it
    has, left out where it says nothing (a false flag, a second length of a
    one-sided pad, a pattern's step outside Spacing mode), its profile, its
    originals, a dress-up's edges or faces, and what is bound to what."""
    out = {}
    for k in KEYS:
        if has(f, k):
            try:
                v = getattr(f, k)
            except Exception:
                continue
            v = picks.num_json(v)
            if k in ("Suppressed", "Refine", "Midplane", "Reversed", "Threaded", "ModelThread", "Ruled", "Closed", "TaperAngle") and not v:
                continue
            if k in ("Length2", "Type2") and not (has(f, "SideType") and f.SideType == "Two sides"):
                continue
            if k == "Angle2" and not (has(f, "Type") and f.Type == "TwoAngles"):
                continue
            if k == "Size2" and not (has(f, "ChamferType") and f.ChamferType == "Two distances"):
                continue
            if k == "Offset" and (not v if not has(f, "Occurrences") else getattr(f, "Mode", None) != "Spacing"):
                # a pad's offset from its up-to face (0: none); a pattern's step, used in Spacing mode only
                continue
            if k == "TransformMode" and v == "Features":
                continue
            out[k[0].lower() + k[1:]] = v
    for k in ("Profile",):
        if has(f, k) and getattr(f, k):
            p = getattr(f, k)
            out["profile"] = (p[0] if isinstance(p, tuple) else p).Label
    if has(f, "Originals") and f.Originals:
        out["originals"] = [o.Label for o in f.Originals]
    if has(f, "Base") and f.isDerivedFrom("PartDesign::DressUp") and f.Base:
        out["on"] = list(f.Base[1])
    bound = {p.lstrip("."): e for p, e in getattr(f, "ExpressionEngine", [])}
    if bound:
        out["bound"] = bound
    return out


def own_keys(f):
    """The key properties f has, as a refusal lists them."""
    return ", ".join(k for k in KEYS if has(f, k))


def version():
    """This FreeCAD's version, "1.1.3"."""
    return ".".join(FreeCAD.Version()[:3])


def solid_tip(b):
    """The body's tip when it has a solid (None for an empty body, or one
    whose tip has no shape yet)."""
    tip = b.Tip
    return tip if (tip is not None and not tip.Shape.isNull() and tip.Shape.Solids) else None


def profile_sketch(f):
    """The sketch a feature is built on: its Profile, which FreeCAD keeps as
    the sketch or as (sketch, [sub-elements]). None when it has none."""
    prof = getattr(f, "Profile", None)
    return (prof[0] if isinstance(prof, tuple) else prof) if prof else None


def users_of(f, b):
    """The labels of what refers to f by a property of its own: a sketch on
    its face, a fillet of its edges, a pattern of it. The feature after it
    (whose BaseFeature it is) does not: the body re-links that itself. Each
    once: InList repeats an object per link."""
    return list(dict.fromkeys(o.Label for o in f.InList if o != b and o.TypeId != "PartDesign::Body" and pc.uses(o, f)))


def multi_steps(b):
    """{ step's name: its MultiTransform's label }: a MultiTransform's steps
    sit in the body after it, as FreeCAD keeps them."""
    out = {}
    for o in b.Group:
        if o.TypeId == "PartDesign::MultiTransform":
            out.update({t.Name: o.Label for t in o.Transformations})
    return out


def whole_mode(f):
    """FreeCAD 1.1's own whole-body mode of a Transformed feature
    (TransformMode: "Features" | "Whole shape"; "body" for a release that
    words it so), or None where it has none."""
    if "TransformMode" not in f.PropertiesList:
        return None
    try:
        modes = list(f.getEnumerationsOfProperty("TransformMode") or [])
    except Exception:
        modes = []
    return next((m for m in modes if "whole" in m.lower()), None) or next((m for m in modes if "body" in m.lower()), None)


def whole_body(f, b, prior):
    """The whole body transformed by the new feature f: FreeCAD's own mode
    where it has it, else every additive and subtractive feature up to
    prior (the tip before f, which the body is read up to: the tip is put
    back on f whatever happens) as the originals. What was used, in words;
    None when the body has no such feature."""
    b.Tip = prior
    try:
        pick = whole_mode(f)
        if pick:
            f.TransformMode = pick
            return f"the whole body (FreeCAD's TransformMode \"{pick}\")"
        feats = [o for o in pc.solid_features(b, upto=None) if o is not f and o.isDerivedFrom("PartDesign::FeatureAddSub")]
        if not feats:
            return None
        f.Originals = feats
        return f"every additive and subtractive feature ({', '.join(o.Label for o in feats)}); fillets and chamfers are not repeated this way"
    finally:
        b.Tip = f


# ---- pd_pipe: the path as edges of any object, and a tube profile made for it -------------------

PIPE_MODES = ("Standard", "Fixed", "Frenet", "Auxiliary", "Binormal")
PIPE_TRANSITIONS = ("Transformed", "Right corner", "Round corner")
EDGE_RE = re.compile(r"^Edge([1-9][0-9]*)$")


def pipe_path(doc, b, ref, edges, sk=None):
    """The path of a pd_pipe: (object, [edge names] in the order they join,
    the start point and the direction there, in the object's own shape).
    ref: a sketch of the body first (its refusals as before), else any
    object with edges (a SubShapeBinder of a skeleton, a Draft wire).
    edges: None for all its edges, else names ("Edge3") joined end to end."""
    try:
        o = pc.sketch_of(doc, ref, b)
    except ToolError as e:
        o = picks.named(doc, ref) if isinstance(ref, str) else None
        if o is None or not getattr(getattr(o, "Shape", None), "Edges", None):
            if o is not None:
                raise ToolError("invalid_input", f"path: {o.Label} has no edges: give a sketch, a pd_binder of a skeleton, or a wire.") from None
            raise e
    if sk is not None and o is sk:
        raise ToolError("invalid_input", "path: another sketch than the profile — the profile is swept along the path's edges.")
    all_edges = list(o.Shape.Edges)
    if not all_edges:
        raise ToolError("invalid_input", f"path: {o.Label} has no edges (construction geometry does not count): sketch_add a line, arc or polyline.")
    if edges is None:
        names = [f"Edge{i + 1}" for i in range(len(all_edges))]
    else:
        names = [edges] if isinstance(edges, str) else edges
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            raise ToolError("invalid_input", f"edges: [\"Edge3\"] — names of edges of {o.Label}, joined end to end; shape_query {{ body: \"{o.Label}\", kind: \"edge\" }} lists them.")
        for n in names:
            m = EDGE_RE.match(n)
            if not m or int(m.group(1)) > len(all_edges):
                raise ToolError("not_found", f"edges: {n!r} is not an edge of {o.Label} (Edge1 … Edge{len(all_edges)}): shape_query {{ body: \"{o.Label}\", kind: \"edge\" }} lists them.")
        if len(set(names)) != len(names):
            raise ToolError("invalid_input", "edges: each edge once.")
    if edges is not None:
        names, start, tangent, flip = chain_edges(o.Shape, names, o.Label)
        return o, names, start, tangent, flip
    # All its edges, as FreeCAD's Pipe takes them (it joins them itself): the
    # start read from the chain they make, else from the first edge.
    try:
        _, start, tangent, flip = chain_edges(o.Shape, names, o.Label)
    except ToolError:
        e = all_edges[0]
        start, tangent, flip = e.Vertexes[0].Point, edge_tangent(e, False), False
    return o, names, start, tangent, flip


def chain_edges(shape, names, label, tol=1e-4):
    """The edges in the order they join end to end: (names, the start point,
    the direction there, whether the first edge runs backwards). Refused
    when they do not make one chain."""
    def ends(n):
        e = shape.getElement(n)
        vs = e.Vertexes
        return vs[0].Point, vs[-1].Point, e

    pts = {n: ends(n) for n in names}
    if len(names) == 1:
        a, z, e = pts[names[0]]
        return names, a, edge_tangent(e, False), False

    def near(p, q):
        return (p - q).Length < tol

    def links(n):
        return sum(1 for m in names if m != n for p in pts[n][:2] for q in pts[m][:2] if near(p, q))

    # The chain starts at an edge with a free end (or anywhere for a closed loop).
    first = next((n for n in names if links(n) < 2), names[0])
    left = [n for n in names if n != first]
    a, z, e = pts[first]
    # The free end is the start: when the first edge's own start joins the next edge, it runs backwards.
    free_a = not any(near(a, q) for m in left for q in pts[m][:2])
    free_z = not any(near(z, q) for m in left for q in pts[m][:2])
    flip = not free_a and free_z
    order, end = [first], (a if flip else z)
    while left:
        nxt = next((m for m in left if near(pts[m][0], end) or near(pts[m][1], end)), None)
        if nxt is None:
            raise ToolError("invalid_input", f"edges: {', '.join(names)} of {label} do not join end to end ({', '.join(left)} not reached from {order[-1]}): give edges that make one chain, in any order.")
        end = pts[nxt][1] if near(pts[nxt][0], end) else pts[nxt][0]
        order.append(nxt)
        left.remove(nxt)
    start = z if flip else a
    return order, start, edge_tangent(e, flip), flip


def edge_tangent(e, backwards):
    """The unit direction an edge leaves its start with (its end, backwards)."""
    try:
        t = e.tangentAt(e.LastParameter if backwards else e.FirstParameter)
    except Exception:
        vs = e.Vertexes
        t = vs[-1].Point - vs[0].Point
    if backwards:
        t = t * -1.0
    return t.normalize() if t.Length > 1e-12 else t


def tube_spec(spec):
    """profile { circle: { d, wall } }: (d, wall) as numbers or expression
    text; wall None for a solid rod."""
    c = spec.get("circle") if isinstance(spec, dict) else None
    if not isinstance(c, dict) or set(spec) - {"circle"} or set(c) - {"d", "wall"} or "d" not in c:
        raise ToolError("invalid_input", "profile: a sketch's name, or { circle: { d: 28.6, wall: 0.9 } } (mm or an expression such as \"Geo.tt_od\") — a tube square to the path at its start; leave wall out for a rod.")
    d, wall = c["d"], c.get("wall")
    for k, v in (("d", d), ("wall", wall)):
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float, str)) or (isinstance(v, str) and not v.strip()):
            raise ToolError("invalid_input", f"profile.circle.{k}: mm, or an expression (\"Geo.tt_od\").")
        if isinstance(v, (int, float)) and v <= 0:
            raise ToolError("invalid_input", f"profile.circle.{k}: more than 0 mm.")
    if isinstance(d, (int, float)) and isinstance(wall, (int, float)) and 2 * wall >= d:
        raise ToolError("invalid_input", f"profile.circle.wall: less than half of d ({d / 2:g} mm) — a wall of {wall:g} mm leaves no bore.")
    return d, wall


def path_closed(path, names, tol=1e-4):
    """Whether a pd_pipe's path closes on itself (a ring, a circle for a
    rim): one closed edge, or edges whose every end meets another's."""
    try:
        es = [path.Shape.getElement(n) for n in names]
    except Exception:  # noqa: BLE001
        return False
    if len(es) == 1:
        e = es[0]
        try:
            if e.isClosed():
                return True
        except Exception:  # noqa: BLE001
            pass
        vs = e.Vertexes
        return len(vs) == 1 or (len(vs) > 1 and (vs[0].Point - vs[-1].Point).Length < tol)
    ends = []
    for e in es:
        vs = e.Vertexes
        if not vs:
            return False
        ends += [vs[0].Point, vs[-1].Point]
    return all(sum(1 for j, q in enumerate(ends) if j != i and (p - q).Length < tol) >= 1 for i, p in enumerate(ends))


CLOSED_TUBE = ("profile: a tube (circle with wall) on a closed path ({path}: {edges}) — FreeCAD's Pipe makes a solid ring there and leaves the bore out "
               "(bicycle runs, a rim on a circle path). Nothing was made. Make the ring in two calls on the same path: pd_pipe {{ profile: {{ circle: {{ d: {d} }} }} }}, "
               "then pd_pipe {{ profile: {{ circle: {{ d: {bore} }} }}, subtractive: true }}. Or pd_revolve a sketch of the ring's section.")


def closed_tube_words(path, names, spec):
    d, wall = spec
    bore = (f"{d - 2 * wall:g}" if isinstance(d, (int, float)) and isinstance(wall, (int, float)) else f"\"({d if isinstance(d, str) else f'{d:g} mm'}) - 2 * ({wall if isinstance(wall, str) else f'{wall:g} mm'})\"")
    return CLOSED_TUBE.format(path=path.Label, edges=", ".join(names), d=d if isinstance(d, (int, float)) else json.dumps(d), bore=bore)


def to_body(b, o, p, direction=False):
    """A point (or direction) of o's shape in the body's coordinates."""
    if b.hasObject(o):
        return p
    try:
        outer = o.getGlobalPlacement().multiply(o.Placement.inverse())
        inner = b.getGlobalPlacement().inverse()
    except Exception:
        outer, inner = FreeCAD.Placement(), b.Placement.inverse()
    if direction:
        return inner.Rotation.multVec(outer.Rotation.multVec(p))
    return inner.multVec(outer.multVec(p))


def tube_profile(s, b, spec, path, names, start, tangent, flip):
    """A sketch in the body square to the path at its start, with the tube's
    two circles (one for a rod): attached to the path's first edge
    (NormalToEdge) when the path is in the body, so it follows the
    skeleton; else placed there. The circles' diameters are named
    constraints (od, id) bound to the expressions given. (sketch, how it
    is held)."""
    import Part
    import Sketcher

    d, wall = spec
    sk = b.newObject("Sketcher::SketchObject", "TubeProfile")
    sk.Label = s.unique(f"{path.Label} tube")
    p0, t0 = to_body(b, path, start), to_body(b, path, tangent, True)
    held = "placed square to the path's start"
    if b.hasObject(path):
        try:
            setattr(sk, pc.support_prop(sk), [(path, names[0])])
            sk.MapMode = "NormalToEdge"
            sk.MapPathParameter = 1.0 if flip else 0.0
            held = f"attached to {path.Label}.{names[0]} (NormalToEdge): it follows the skeleton"
        except Exception:
            setattr(sk, pc.support_prop(sk), None)
            sk.MapMode = "Deactivated"
    if sk.MapMode == "Deactivated":
        sk.Placement = FreeCAD.Placement(p0, FreeCAD.Rotation(V(0, 0, 1), t0))
    num = lambda v, dflt: float(v) if isinstance(v, (int, float)) else dflt  # noqa: E731
    od = num(d, 10.0)
    idia = od - 2 * wall if isinstance(wall, (int, float)) and isinstance(d, (int, float)) else (od * 0.8 if wall is not None else None)
    rows = [("od", od)] + ([("id", idia)] if wall is not None else [])
    # A number beside an expression keeps its unit: FreeCAD refuses mm minus a plain number.
    mm = lambda v: v if isinstance(v, str) else f"{v:g} mm"  # noqa: E731
    for cname, dia in rows:
        g = sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), dia / 2.0), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", g, 3, -1, 1))
        c = sk.addConstraint(Sketcher.Constraint("Diameter", g, dia))
        sk.renameConstraint(c, cname)
        if cname == "od" and isinstance(d, str):
            sk.setExpression(f"Constraints.{cname}", d)
        if cname == "id" and (isinstance(d, str) or isinstance(wall, str)):
            sk.setExpression(f"Constraints.{cname}", f"({mm(d)}) - 2 * ({mm(wall)})")
    return sk, held


def pipe_options(f, a):
    """mode and transition passed to FreeCAD's Pipe (its own words)."""
    for key, prop, allowed in (("mode", "Mode", PIPE_MODES), ("transition", "Transition", PIPE_TRANSITIONS)):
        v = a.get(key)
        if v is None:
            continue
        if v not in allowed:
            raise ToolError("invalid_input", f"{key} {v!r}: one of {', '.join(allowed)}.")
        setattr(f, prop, v)
    # Bicycle L5 build (21 Nov, finding 4): Refine on every pipe of a large
    # weldment made the body unorientable after small changes; off by default.
    if "Refine" in (getattr(f, "PropertiesList", None) or ()):
        f.Refine = bool(a.get("refine", False))


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def new(b, kind, label):
        """A new feature of the body, labelled (uniquely) and made the tip:
        some releases leave the tip where it was for a pattern, and the body
        is the new feature's shape from here on. A datum plane is no tip."""
        label = s.unique(label)
        f = b.newObject(kind, kind.split("::")[-1])
        f.Label = label
        if kind != "PartDesign::Plane" and b.Tip != f:
            b.Tip = f
        return f

    def settle(b, f, tool, before=None, must_change=None, hint=""):
        """Recompute, refuse a feature (or a later one) that failed or changed
        nothing where it must, else the body's reading (pd_common.settle)."""
        return pc.settle(s, b, f, tool, before, must_change, hint=hint)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "settle": settle, "new": new, "snapshot": lambda tool: s.snapshot(tool), "steps": lambda: len(s.steps),
               "body": lambda ref: pc.pd_body(doc(), ref), "sketch_of": lambda ref, b=None: pc.sketch_of(doc(), ref, b), "in_body": pc.in_body,
               "volume": pc.volume, "tip_shape": pc.tip_shape, "solid_tip": solid_tip, "body_reading": pc.body_reading, "short": pc.short, "version": version,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "setprop": setattr, "xyz": pc.geo.vec, "vec3": pc.vec3, "num_json": picks.num_json,
               # faces, edges, planes and axes by where they are (pd_common)
               "find_faces": lambda *x: pc.find_faces(*x), "find_edges": lambda *x: pc.find_edges(*x), "ref_shape": pc.ref_shape, "ref_names": pc.ref_names,
               "plane_ref": lambda *x: pc.plane_ref(*x), "axis_ref": lambda *x: pc.axis_ref(*x), "support_prop": pc.support_prop,
               "ref_snapshot": pc.ref_snapshot, "repair_refs": pc.repair_refs, "broken": pc.newly_broken,
               # the family's
               "has_prop": has, "own_keys": own_keys, "set_sides": set_sides, "thread_key": thread_key, "thread_pick": thread_pick, "hole_spots": hole_spots,
               "key_values": key_values, "profile_sketch": profile_sketch, "users_of": users_of, "multi_steps": multi_steps, "whole_body": whole_body,
               "pipe_path": lambda b, ref, edges, sk=None: pipe_path(doc(), b, ref, edges, sk), "tube_spec": tube_spec, "path_closed": path_closed, "closed_tube_words": closed_tube_words,
               "tube_profile": lambda *x: tube_profile(s, *x), "pipe_options": pipe_options}
    return runners.tools(GROUP, s, helpers)
