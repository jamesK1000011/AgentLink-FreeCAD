# SPDX-License-Identifier: LGPL-2.1-or-later
# Sketch tools: a PartDesign body, sketches on its planes or on a face found
# by where it is, geometry added by kind, constraints in FreeCAD's own
# terms (geometry id + vertex 1 start / 2 end / 3 centre), the solver's
# reading, and edits. Coordinates are the sketch's own, in mm; angles in
# degrees.

import json
import math
import re
import os

import FreeCAD
import Part
import Sketcher

from .. import geometry as geo
from .. import orient
from .. import resultline as rl
from .. import runners
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


def frame_of(sk):
    """The sketch's frame in the world as four tuples (origin, x axis, y
    axis, normal), from its global placement (resultline.frame_ranges)."""
    pl = sk.getGlobalPlacement() if hasattr(sk, "getGlobalPlacement") else sk.Placement
    r = pl.Rotation

    def t(v):
        return (float(v.x), float(v.y), float(v.z))

    return (t(pl.Base), t(r.multVec(V(1, 0, 0))), t(r.multVec(V(0, 1, 0))), t(r.multVec(V(0, 0, 1))))


def _box6(bb):
    return (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)


def body_ranges(b, sk):
    """Where body b's solid is in sketch sk's own frame: ((xmin, xmax),
    (ymin, ymax), (nmin, nmax)), n along the sketch's normal from its plane
    (mm, not rounded), from the corners of the solid's box. None when the
    body has no solid yet or the frame is not read."""
    try:
        shape = b.Shape
        if shape is None or shape.isNull() or not shape.Solids:
            return None
        return rl.frame_ranges(frame_of(sk), _box6(geo.bound_box(shape)))
    except Exception:  # noqa: BLE001 - no reading: nothing said
        return None


def body_extent(b, sk):
    """Where body b's solid is in sketch sk's own frame: {"x": [min, max],
    "y": [min, max], "normal": [min, max]} (mm, to 0.1). normal is along the
    sketch's normal, 0 at the sketch plane: it says which side of the sketch
    the body lies on. None when the body has no solid yet."""
    got = body_ranges(b, sk)
    if got is None:
        return None
    r = lambda v: round(float(v), 1) + 0.0  # noqa: E731
    return {k: [r(lo), r(hi)] for k, (lo, hi) in zip(("x", "y", "normal"), got)}


def face_ranges(link, sk):
    """The face a sketch sits on, in the sketch's own frame (as
    body_ranges): from the face's box. None when the sketch is not on a
    face or the face is not read."""
    try:
        obj, subs = link
        sub = subs[0] if subs else ""
        if not isinstance(sub, str) or not sub.startswith("Face"):
            return None
        return rl.frame_ranges(frame_of(sk), _box6(geo.bound_box(obj.Shape.getElement(sub))))
    except Exception:  # noqa: BLE001 - no reading: nothing said
        return None


def new_result(sk, b, what, link):
    """sketch_new's result line: the sketch and its support, the axes in
    words, the body's range in the sketch's x, y and normal, and for a face
    sketch the face's own x and y range."""
    try:
        return rl.sketch_new_result(sk.Label, what, axes(sk.Placement), body_ranges(b, sk), face_ranges(link, sk))
    except Exception:  # noqa: BLE001 - a reading only
        return f"Sketch {getattr(sk, 'Label', '')} is on {what}."


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


def con_brief(sk, ids):
    """Each constraint of ids in one short text: its id, FreeCAD's type and
    its refs [geometry, vertex], and its value when it has one:
    "4 Coincident [0, 2] [1, 1]", "9 Radius [4, 0] = 5". A constraint that
    cannot be read is passed over."""
    out = []
    for i in ids:
        try:
            d = describe_con(sk, i)
        except Exception:  # noqa: BLE001 - not read: not said
            continue
        refs = " ".join(f"[{g}, {p}]" for g, p in d["refs"])
        out.append(f"{d['id']} {d['type']} {refs}" + (f" = {d['value']:g}" if "value" in d else ""))
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


# Two points this near are one point (mm): OpenCASCADE's Precision::Confusion,
# the tolerance FreeCAD itself uses to tell whether two points coincide (a
# sketch's edges join into one wire at it; pd_common.TOUCH is the same
# number). It only decides float equality: whether an end is on another
# curve. No other number decides anything in the todo words (27 Nov, owner:
# NEAR_GAP, ROUND_NEAR, ROUND_NEAR_MM, TINY_GAP_MM and TINY_GAP went; the
# words give each open end and the measured distance to the nearest other
# one, and say nothing of what was meant).
SAME_POINT = pc.TOUCH


def _at(p):
    return f"({geo.r3(p[0]):g}, {geo.r3(p[1]):g})"


def _end_words(gid, kind, pos, p):
    """An open end in words, with its ref for sketch_constrain: "the end of
    line 3 [3, 2] (10, 0)"."""
    return f"{POS[pos]} {kind} {gid} [{gid}, {pos}] {_at(p)}"


def _mm(d):
    """A measured distance in mm: 3 places, and 3 significant digits under
    0.001 (a distance that is not zero is never said as 0)."""
    return f"{geo.r3(d):g}" if d >= 0.0005 or d == 0 else f"{d:.3g}"


OPEN_ENDS_SHOWN = 4  # phrases of open ends one todo says


def open_end_words(ends, curves, size, dist, rounds=(), joined=None):
    """The todo words for the open ends of a sketch's outline: each open end
    with its ref and the measured distance (mm) to the nearest other open
    end. Two ends that are each the other's nearest are one phrase. An
    end that lies on another curve (within SAME_POINT) is a branch:
    branch_words says it, and here it is only a nearest end of others.
    ends: [(gid, kind, pos, (x, y))], pos 1 start / 2 end; curves: the ids
    of the outline's curves; dist(gid, (x, y)): mm from that curve to the
    point. size, rounds and joined are not used (27 Nov): no share of the
    outline's size and no kind of curve decides the words, no words are
    held back for other words, and no constraint is named for two ends."""
    by_key = {(gid, pos): (gid, kind, pos, p) for gid, kind, pos, p in ends}
    nearest = {}
    for gid, _kind, pos, p in ends:
        others = [(math.dist(p, q), g2, s2) for g2, _k2, s2, q in ends if (g2, s2) != (gid, pos)]
        if others:
            d, g2, s2 = min(others)
            nearest[(gid, pos)] = (d, (g2, s2))
    branch = {(gid, pos) for gid, _k, pos, p in ends if any(dist(g, p) <= SAME_POINT for g in curves if g != gid)}
    words, said = [], set()
    for gid, kind, pos, p in ends:
        key = (gid, pos)
        if key in said or key in branch:
            continue
        said.add(key)
        me = _end_words(gid, kind, pos, p)
        if key not in nearest:
            words.append(f"{me} is an open end, the only one")
            continue
        d, other = nearest[key]
        g2, k2, s2, q = by_key[other]
        if nearest[other][1] == key and other not in said and other not in branch:
            # each is the other's nearest: one phrase for the two
            said.add(other)
            words.append(f"{me} and {_end_words(g2, k2, s2, q)} are open ends, {_mm(d)} mm apart")
        else:
            words.append(f"{me} is an open end; the nearest other open end is {_end_words(g2, k2, s2, q)}, {_mm(d)} mm away")
    if len(words) > OPEN_ENDS_SHOWN:
        words = words[:OPEN_ENDS_SHOWN] + [f"and {len(words) - OPEN_ENDS_SHOWN} more open ends (openVertices)"]
    return words


def _names(items):
    """(kind, gid) pairs in words, by kind: "lines 2 and 4, circle 0"."""
    groups = {}
    for k, g in items:
        if g not in groups.setdefault(k, []):
            groups[k].append(g)
    out = []
    for k, gs in groups.items():
        ids = [str(g) for g in gs]
        out.append(f"{k} {ids[0]}" if len(ids) == 1 else f"{k}s {', '.join(ids[:-1])} and {ids[-1]}")
    return ", ".join(out)


def branch_words(ends, curves, size, dist, rounds=(), joins=()):
    """The todo words for each point where a wire branches: three or more
    edges meet there (an outline has two at each joint), as the ends of
    curves and the curves that pass through it. ends: [(gid, kind, pos,
    (x, y))], every end of the open curves; curves: {gid: kind}; size and
    dist as open_end_words; rounds: the ids of the full circles. size is
    not used: two points are one point within SAME_POINT, whatever the
    size. joins: pairs of ends whose own words say the joint (none are
    given since 27 Nov: each fact is said where it is measured)."""
    tol = SAME_POINT

    def joined(g, p, other):
        # An end at p that a caller's own words pair with an end of curve
        # other (joins): not said here too. state_of gives no pairs since
        # 27 Nov: a branch and an open end are two measured facts, each said.
        for (a, pa), (b, pb) in joins:
            if (a in g and b == other and math.dist(pa, p) <= tol) or (b in g and a == other and math.dist(pb, p) <= tol):
                return True
        return False

    spots = []
    for gid, kind, _pos, p in ends:
        for q, at_ in spots:
            if math.dist(q, p) <= tol:
                at_.append((kind, gid))
                break
        else:
            spots.append((p, [(kind, gid)]))
    words = []
    for p, at_ in spots:
        mine = {g for _k, g in at_}
        through = [(curves[g], g) for g in curves if g not in mine and dist(g, p) <= tol and not joined(mine, p, g)]
        if len(at_) + 2 * len(through) < 3:
            continue
        who = _names(at_)
        if through:
            words.append(f"{who} {'meets' if len(at_) == 1 else 'meet'} {_names(through)} at {_at(p)}")
        else:
            words.append(f"{who} meet at {_at(p)}")
    if not words:
        return []
    if len(words) > 4:
        words = words[:4] + [f"and {len(words) - 4} more points where a wire branches"]
    # The measured fact, once: on the first point.
    words[0] += ": a wire branches there"
    return words


def cross_words(loops, meet):
    """The todo words for closed loops that cross or touch each other (a
    loop inside another, apart from it, is a hole: no words). loops: their
    names; meet(i, j): (x, y) where loops i and j meet, or None."""
    words = []
    for i in range(len(loops)):
        for j in range(i + 1, len(loops)):
            p = meet(i, j)
            if p is not None:
                words.append(f"{loops[i]} meets {loops[j]} at {_at(p)}")
    if not words:
        return []
    if len(words) > 4:
        words = words[:4] + [f"and {len(words) - 4} more loops that meet"]
    return words


def _outline(sk):
    """The outline curves of sketch sk (not construction, not points):
    {gid: kind}, the ends of the open ones [(gid, kind, pos, (x, y))], the
    ids of its full circles, its size (mm) and dist(gid, (x, y))."""
    curves, ends, rounds = {}, [], []
    for i, g in enumerate(sk.Geometry):
        k = _geo_kind(g)
        if k == "Point" or sk.getConstruction(i):
            continue
        curves[i] = k.lower()
        if k in ("Circle", "Ellipse"):
            if k == "Circle":
                rounds.append(i)
            continue
        for pos, q in ((1, getattr(g, "StartPoint", None)), (2, getattr(g, "EndPoint", None))):
            if q is not None:
                ends.append((i, k.lower(), pos, (q.x, q.y)))
    try:
        size = sk.Shape.BoundBox.DiagonalLength
    except Exception:  # noqa: BLE001
        size = 0.0

    def dist(i, p):
        return sk.Geometry[i].toShape().distToShape(Part.Vertex(V(p[0], p[1], 0)))[0]

    return curves, ends, rounds, size, dist


def _branch_words(sk, joins=()):
    """branch_words for sketch sk; [] when it cannot be read."""
    try:
        curves, ends, rounds, size, dist = _outline(sk)
        return branch_words(ends, curves, size, dist, rounds, joins)
    except Exception:  # noqa: BLE001 - no reading: the general todo stays
        return []


MAX_LOOPS = 40   # closed wires past which the crossing test is not run


def cross_test(sk, wires):
    """The crossing test of the closed wires of sketch sk, as facts (27 Nov,
    facts only): (words, why). words: cross_words' list ([] when no two
    closed wires meet), or None when the test did not run; why: the reason
    then ("" when it ran). The test compares each closed wire with each
    other closed wire. It does not compare a wire with itself."""
    try:
        loops = [w for w in wires if w.isClosed()]
    except Exception:  # noqa: BLE001
        return None, "the wires were not read"
    if len(loops) > MAX_LOOPS:
        return None, f"{len(loops)} closed wires, and the test runs for {MAX_LOOPS} at most"
    if len(loops) < 2:
        return [], ""
    got = _cross_words(sk, wires)
    return (None, "the wires were not read") if got is None else (got, "")


def _cross_words(sk, wires):
    """cross_words for the closed wires of sketch sk (its Shape's, in the
    world: read back into the sketch's own x/y); [] when none meet or the
    test did not run, None when it cannot be read."""
    try:
        loops = [w for w in wires if w.isClosed()]
        if len(loops) < 2 or len(loops) > MAX_LOOPS:
            return []
        curves, _ends, _rounds, size, dist = _outline(sk)
        tol = 1e-6 * max(size, 1.0)
        inv = sk.Placement.inverse()

        def name(w):
            ids = []
            for e in w.Edges:
                m = inv.multVec(e.valueAt((e.FirstParameter + e.LastParameter) / 2))
                d, g = min(((dist(g, (m.x, m.y)), g) for g in curves), default=(math.inf, None))
                if g is not None and d <= max(tol, 1e-4) and g not in ids:
                    ids.append(g)
            if len(ids) == 1:
                return f"{curves[ids[0]]} {ids[0]}"
            return f"the loop of {_names([(curves[g], g) for g in ids])}" if ids else "a loop"

        def meet(i, j):
            a, b = loops[i], loops[j]
            try:
                if not a.BoundBox.intersect(b.BoundBox):
                    return None
            except Exception:  # noqa: BLE001
                pass
            d, pts, _info = a.distToShape(b)
            if d > tol:
                return None
            q = inv.multVec(pts[0][0])
            return (q.x, q.y)

        return cross_words([name(w) for w in loops], meet)
    except Exception:  # noqa: BLE001 - no reading: said as not tested
        return None


def _open_end_words(sk, openv, joined=None):
    """open_end_words for sketch sk: its open ends (openv, the sketch's own
    x/y) matched to the curves they end, by id. [] when one is not matched."""
    ends = []
    curves = [i for i, g in enumerate(sk.Geometry) if not sk.getConstruction(i) and _geo_kind(g) != "Point"]
    for p in openv:
        hit = None
        for i in curves:
            g = sk.Geometry[i]
            for pos, q in ((1, getattr(g, "StartPoint", None)), (2, getattr(g, "EndPoint", None))):
                if q is not None and math.dist((q.x, q.y), p) <= 1e-3:
                    hit = (i, _geo_kind(g).lower(), pos, (q.x, q.y))
                    break
            if hit:
                break
        if hit is None:
            return []
        ends.append(hit)
    try:
        size = sk.Shape.BoundBox.DiagonalLength
    except Exception:  # noqa: BLE001
        size = 0.0

    def dist(i, p):
        return sk.Geometry[i].toShape().distToShape(Part.Vertex(V(p[0], p[1], 0)))[0]

    rounds = [i for i in curves if _geo_kind(sk.Geometry[i]) == "Circle"]
    return open_end_words(ends, curves, size, dist, rounds, joined)


def fresh(sk):
    """Sketch sk's Shape (its wires) built again from its geometry and
    constraints now. FreeCAD builds a sketch's Shape only when the sketch
    recomputes; solve() moves the geometry and keeps the old Shape (blind
    QA, 26 Nov: sketch_constrain gave the open ends of the call before).
    A stand-in without recompute is left as it is. Not while a batch holds
    the document's recompute (agentlink/hold.py: the held answer leaves the
    wires out, and the build comes at the end). Never raises."""
    try:
        if getattr(getattr(sk, "Document", None), "RecomputesFrozen", False) is True:
            return
    except Exception:  # noqa: BLE001
        pass
    if callable(getattr(sk, "recompute", None)):
        try:
            sk.recompute()
        except Exception:  # noqa: BLE001 - the solver's reading below says what is wrong
            pass


def open_ends_of(sk, wires):
    """The ends of the open wires, in the sketch's own x/y. (Not the
    sketch's OpenVertices: it lists every vertex that does not join
    exactly two edges, a lone circle's too.)"""
    openv = []
    inv = sk.Placement.inverse()
    for w in wires:
        if not w.isClosed():
            vs = [v for v in w.Vertexes if sum(1 for e in w.Edges for ev in e.Vertexes if ev.isSame(v)) == 1]
            openv += [_pt(inv.multVec(v.Point)) for v in vs]
    return openv


def state_of(sk):
    # Every sketch tool's state comes from here: the Shape is built again
    # first, so the wires and open ends are those of the sketch as it is now.
    # Solve first, then build: a solve after the build marks the sketch as
    # touched again ("1 object not recomputed yet", live 25 Nov).
    code = sk.solve()
    fresh(sk)
    conflicting = [i - 1 for i in (getattr(sk, "ConflictingConstraints", None) or [])]
    redundant = [i - 1 for i in (getattr(sk, "RedundantConstraints", None) or [])]
    partial = [i - 1 for i in (getattr(sk, "PartiallyRedundantConstraints", None) or [])]
    malformed = [i - 1 for i in (getattr(sk, "MalformedConstraints", None) or [])]
    dof = getattr(sk, "DoF", None)
    wires = sk.Shape.Wires if not sk.Shape.isNull() else []
    closed = sum(1 for w in wires if w.isClosed())
    openv = open_ends_of(sk, wires) if wires and closed < len(wires) else []
    out = {
        "sketch": sk.Label,
        "solver": SOLVE.get(code, f"code {code}"),
        "dof": dof,
        "fullyConstrained": dof == 0 if dof is not None else None,
        "wires": len(wires),
        "closedWires": closed,
    }
    if openv:
        out["openVertices"] = openv[:OPEN_LISTED]
        if len(openv) > OPEN_LISTED:
            out["openVerticesCount"] = len(openv)  # the list is cut: the count of all
    points = _free_points(sk)
    if points:
        out["points"] = points
    for k, v in (("conflicting", conflicting), ("redundant", redundant), ("partiallyRedundant", partial), ("malformed", malformed)):
        if v:
            out[k] = v
    # Facts only (27 Nov): no word says whether the sketch is ready for a
    # feature. FreeCAD's Hole takes a sketch of points only; a pipe's path is
    # an open wire. The measured state: the wires, the open ends, the points,
    # and the closed wires that meet another closed wire (where that test ran).
    cross = []
    if closed:
        cross, why_not = cross_test(sk, wires)
        if cross is None:
            out["wiresMeet"] = f"not tested: {why_not}"
            cross = []
        else:
            out["wiresMeet"] = len(cross)
        out["selfCrossing"] = "not tested"
    said = []
    if openv or (wires and closed < len(wires)):
        joins = []
        gaps = _open_end_words(sk, openv, joins)
        said += _branch_words(sk, joins) + gaps
    said += cross
    if said:
        out["todo"] = "; ".join(said)
    return out


OPEN_LISTED = 12  # open ends that openVertices lists; openVerticesCount says how many there are


def _free_points(sk):
    """How many points of sketch sk are not construction geometry (FreeCAD's
    Hole drills at each one, by its BaseProfileType)."""
    n = 0
    try:
        for i, g in enumerate(sk.Geometry):
            if _geo_kind(g) == "Point" and not sk.getConstruction(i):
                n += 1
    except Exception:  # noqa: BLE001 - not read: not said
        return 0
    return n


def item_error(e):
    """sketch_add's refusal for the shape that failed: the same refusal and
    its words. A tool's own refusal keeps its code; a ValueError is the
    input's; any other error is FreeCAD's failure."""
    if isinstance(e, ToolError):
        raise e
    code, msg = ("invalid_input" if isinstance(e, ValueError) else "failed"), (str(e) or type(e).__name__)
    raise ToolError(code, msg) from e


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


# The kinds whose place is one point that the builder puts at the sketch
# origin when the call does not give it: {kind: that input}. A rectangle's
# corner is its place too. by_default says it in the answer (27 Nov QA: a
# rectangle with no center went to [0, 0] and no answer said so).
ORIGIN_DEFAULT = {"circle": "center", "rectangle": "center", "rounded_rectangle": "center", "polygon": "center",
                  "arc_slot": "center", "ellipse": "center", "hyperbola": "center", "parabola": "vertex"}


# The other inputs a builder fills when the call does not give them:
# {kind: {input: the value build uses}} (27 Nov, facts only: every value
# that the tool stored and the call did not give is said). A parabola's
# from and to (-2 and 2 times its focal) and what a kind refuses when left
# out (a radius, a size) are not here.
VALUE_DEFAULT = {"arc": {"start": 0, "end": 90}, "arc_slot": {"start": 0, "end": 90}, "polygon": {"sides": 6, "rotation": 0},
                 "ellipse": {"rotation": 0}, "parabola": {"rotation": 0}, "hyperbola": {"rotation": 0, "from": -1, "to": 1},
                 "bspline": {"closed": False, "interpolate": True}, "polyline": {"closed": False}}


def by_default(item):
    """{input: value} for each input that the builder filled because the
    call did not give it: the place ([0, 0], the sketch origin) and the
    values of VALUE_DEFAULT; None when the call gave them all."""
    k = item.get("kind")
    out = {}
    f = ORIGIN_DEFAULT.get(k)
    if not (f is None or f in item or (k in ("rectangle", "rounded_rectangle") and "corner" in item)):
        out[f] = [0, 0]
    for name, v in VALUE_DEFAULT.get(k, {}).items():
        if item.get(name) is None:
            out[name] = v
    if k == "bspline" and item.get("interpolate") is False and item.get("degree") is None:
        out["degree"] = 3
    if item.get("construction") is None:
        out["construction"] = False
    return out or None


def _origin_or(item, field):
    """The point the call gave for field, or the sketch origin (by_default says so)."""
    return pc.vec2(item[field] if field in item else [0, 0], field)


def build(item):
    """One item -> (geometries, constraints (as tuples with local ids), dims (name, tuple), report)."""
    k = item.get("kind")
    C = []
    D = []
    if k == "line":
        a, b = pc.vec2(item.get("from"), "from"), pc.vec2(item.get("to"), "to")
        if (b - a).Length > 1e-9:
            # dims: its length, <name>_length (bicycle drive of 20 Nov, finding 6: a named line had no dimension)
            D.append(("length", ("Distance", 0, (b - a).Length)))
        return [_line(a, b)], C, D
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
        G = [Part.Circle(_origin_or(item, "center"), V(0, 0, 1), r)]
        D.append(("d", ("Diameter", 0, 2 * r)))
        return G, C, D
    if k == "arc":
        r = float(item.get("radius", 0))
        if r <= 0:
            raise ToolError("invalid_input", "arc: center, radius, start and end angles (degrees, counter-clockwise from +x).")
        if "center" not in item:
            # No default centre for an arc (27 Nov QA: two arcs with no
            # center went to [0, 0] with no word). The hub adds what the
            # call gave and what an arc takes (protocol.arrived_words).
            raise ToolError("invalid_input", "center: an arc needs its centre [x, y].")
        a0, a1 = math.radians(float(item.get("start", 0))), math.radians(float(item.get("end", 90)))
        if a1 <= a0:
            a1 += 2 * math.pi
        D.append(("r", ("Radius", 0, r)))
        return [_arc(pc.vec2(item["center"], "center"), r, a0, a1)], C, D
    if k == "point":
        p = pc.vec2(item.get("at"), "at")
        return [Part.Point(p)], C, D
    if k in ("rectangle", "rounded_rectangle"):
        size = item.get("size")
        w, h = (list(size) + [None, None] if isinstance(size, (list, tuple)) else [None, None])[:2]
        if not (isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0):
            # The fields it was given, and the form (live, 22 Nov: x, y,
            # width, height three times in one run).
            other = [f for f in ("width", "height", "x", "y", "w", "h") if f in item]
            raise ToolError("invalid_input", f"{k}: size [w, h] (mm), and center [x, y] or corner [x, y] (its lower left)."
                                             + (f" {', '.join(other)}: not fields of a {k}." if other else "")
                                             + f" Example: {{ \"tool\": \"sketch_add\", \"kind\": \"{k}\", \"corner\": [0, 0], \"size\": [60, 30] }}.")
        if "corner" in item:
            c0 = pc.vec2(item["corner"], "corner")
            x0, y0 = c0.x, c0.y
        else:
            c = _origin_or(item, "center")
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
        c = _origin_or(item, "center")
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
        c = _origin_or(item, "center")
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
        c = _origin_or(item, "center")
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
        v = _origin_or(item, "vertex")
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
        c = _origin_or(item, "center")
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


# The vertices each kind of sketch geometry has (FreeCAD's PointPos: 1 start,
# 2 end, 3 centre). A kind not named here is not checked.
VERTICES = {"Line": (1, 2), "Circle": (3,), "Ellipse": (3,), "Point": (1,), "BSplineCurve": (1, 2),
            "Arc": (1, 2, 3), "ArcOfEllipse": (1, 2, 3), "ArcOfHyperbola": (1, 2, 3), "ArcOfParabola": (1, 2, 3)}
VERTEX_WORDS = {1: "start point", 2: "end point", 3: "centre"}


def vertex_words(sk, g, p):
    """Why point [g, p] is not a point of geometry g, or None. FreeCAD takes
    such a constraint, and then its solver reads it as malformed (blind QA,
    26 Nov: a coincident on "the start of circle 0" came back as
    over-constrained)."""
    if p is None or not (0 <= g < len(sk.Geometry)):
        return None
    k = _geo_kind(sk.Geometry[g])
    has = VERTICES.get(k)
    if has is None or p in has:
        return None
    kind = k.lower()
    name = f"{kind} {g}"
    if has == (3,):
        return (f"{name} has no start or end point; use its centre, [{g}, 3], or the {kind} itself, {g} "
                f"(point_on_object, refs [[g, v], {g}], puts point v of curve g on the {kind})")
    if has == (1,):
        return f"{name} has only one vertex: [{g}, 1]"
    pts = ", ".join("[%d, %d] its %s" % (g, v, VERTEX_WORDS[v]) for v in has)
    return f"{name} has no {VERTEX_WORDS[p]} (vertex {p}); its points are {pts}"


# A join (a coincident, or two end points made tangent) pulls two points
# together. The answer says how far each of its points moved: any distance
# over MOVE_TOL, the tolerance for two equal numbers (27 Nov: no other limit).
MOVE_TOL = rl.TOL
JOINS = ("Coincident", "Tangent")


def join_points(sk, ts):
    """[(kind, (g1, p1, g2, p2), (x1, y1), (x2, y2), gap mm)] for each join
    in constraint tuples ts, read before the constraints go in: where its
    two points are now. [] on any error."""
    out = []
    try:
        for t in ts:
            if t[0] not in JOINS or len(t) < 5:
                continue
            a, b = sk.getPoint(t[1], t[2]), sk.getPoint(t[3], t[4])
            out.append((t[0].lower(), (t[1], t[2], t[3], t[4]), (a.x, a.y), (b.x, b.y), math.dist((a.x, a.y), (b.x, b.y))))
    except Exception:  # noqa: BLE001 - a reading only
        return []
    return out


def join_moves(sk, joins):
    """The joins (join_points, read before) whose points moved in the solve:
    [(kind, ids, a, b, gap, [(words of a point, mm it moved)])], the points
    that moved over MOVE_TOL only. Never raises."""
    out = []
    for kind, ids, a, b, d in joins:
        try:
            g1, p1, g2, p2 = ids
            pts = []
            for g, p, was in ((g1, p1, a), (g2, p2, b)):
                now = sk.getPoint(g, p)
                m = math.dist(was, (now.x, now.y))
                if m > MOVE_TOL:
                    pts.append((ref_words(sk, g, p), m))
            if pts:
                out.append((kind, ids, a, b, d, pts))
        except Exception:  # noqa: BLE001 - not read: not said
            continue
    return out


def join_move_words(st, sk, joins):
    """st (state_of's) with the todo words first for each join that moved:
    "coincident joined the end of arc 0 (0.9, 20) and the start of line 3
    (170.7, -12.5), 172 mm apart: the shape moved". Never raises."""
    try:
        words = [f"{kind} joined {ref_words(sk, g1, p1)} {_at(a)} and {ref_words(sk, g2, p2)} {_at(b)}, {geo.r3(d):g} mm apart: the shape moved"
                 for kind, (g1, p1, g2, p2), a, b, d, _pts in join_moves(sk, joins)]
    except Exception:  # noqa: BLE001
        return st
    if words:
        st = dict(st)
        st["todo"] = "; ".join(words + ([st["todo"]] if st.get("todo") else []))
    return st


def dof_of(sk):
    """FreeCAD's degrees of freedom of a sketch as it stands, or None."""
    v = getattr(sk, "DoF", None)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


JOINS_SHOWN = 6  # joins one constraint answer says one by one


def _shapes_box(sk, ids):
    """(xmin, xmax, ymin, ymax) of the geometry ids in the sketch's own x/y;
    construction geometry is left out unless all of it is construction. None
    when not read."""
    try:
        use = [i for i in ids if 0 <= i < len(sk.Geometry)]
        solid = [i for i in use if not sk.getConstruction(i)]
        bbs = []
        for i in solid or use:
            sh = sk.Geometry[i].toShape()
            try:
                bb = sh.optimalBoundingBox(True, False)
            except Exception:  # noqa: BLE001 - the plain box then
                bb = sh.BoundBox
            bbs.append(bb)
        if not bbs:
            return None
        return (min(b.XMin for b in bbs), max(b.XMax for b in bbs), min(b.YMin for b in bbs), max(b.YMax for b in bbs))
    except Exception:  # noqa: BLE001 - not read: not said
        return None


def con_result(sk, added, dof_before, joins, st):
    """sketch_constrain's result line: the constraints added (in words), the
    degrees of freedom before and after, each join that moved geometry with
    the distance each point moved (no lower limit but MOVE_TOL), and the
    extent of the sketch's shapes after the solve. Never raises."""
    try:
        return _con_result(sk, added, dof_before, joins, st)
    except Exception:  # noqa: BLE001 - a reading only
        return f"Added constraint {', '.join(str(i) for i in added)}." if added else "Added no constraint."


def _con_result(sk, added, dof_before, joins, st):
    try:
        words = [con_words(sk, i) for i in added]
    except Exception:  # noqa: BLE001
        words = []
    moves = []
    more = 0
    try:
        got = join_moves(sk, joins)
        moves = [(f"{ref_words(sk, g1, p1)} and {ref_words(sk, g2, p2)}", [(w, m) for w, m in pts])
                 for _k, (g1, p1, g2, p2), _a, _b, _d, pts in got[:JOINS_SHOWN]]
        more = max(0, len(got) - JOINS_SHOWN)
    except Exception:  # noqa: BLE001
        pass
    box = _shapes_box(sk, range(len(sk.Geometry))) if hasattr(sk, "Geometry") else None
    spans = ((box[0], box[1]), (box[2], box[3])) if box else None
    return rl.constraint_result(words, dof_before, st.get("dof") if isinstance(st, dict) else None, moves, spans, more)


def _mid(g):
    return g.value((g.FirstParameter + g.LastParameter) / 2)


def support_face(sk):
    """The face that sketch sk is on, in the frame of its body's parent (the
    frame of the body's own Shape), or None: a sketch on a plane, or a face
    that is not read."""
    try:
        link = getattr(sk, pc.support_prop(sk), None)
        obj, subs = link[0] if isinstance(link, (list, tuple)) and link and isinstance(link[0], (list, tuple)) else link
        sub = subs[0] if isinstance(subs, (list, tuple)) else subs
        if not isinstance(sub, str) or not sub.startswith("Face"):
            return None
        f = obj.Shape.getElement(sub)
        b = pc.body_of(sk)
        pl = getattr(b, "Placement", None)
        if pl is not None and not pl.isIdentity():
            f = f.transformed(pl.toMatrix())
        return f
    except Exception:  # noqa: BLE001 - not read: not said
        return None


def lies_words(sk, world):
    """Where the world box of a call's new shapes lies against the face
    the sketch is on and against its body's solid, one sentence each
    (resultline.lies_text: the words of a feature's answer), from the
    boxes as they are measured now. A sentence whose box is not read is
    left out; a body with no solid has none. Nothing is said while a batch
    holds the document's recompute (agentlink/hold.py): the body is then
    the one from before the build. Nothing is said for a body inside a
    moved Part (_one_frame): the boxes are then in two frames. 27 Nov QA: the answers said where
    material went only after a feature was made."""
    out = []
    try:
        if getattr(getattr(sk, "Document", None), "RecomputesFrozen", False) is True:
            return []
    except Exception:  # noqa: BLE001
        pass
    if not _one_frame(sk):
        return []
    f = support_face(sk)
    if f is not None:
        try:
            out.append(rl.lies_text("the face", world, _box6(geo.bound_box(f)), flat=True))
        except Exception:  # noqa: BLE001
            pass
    try:
        b = pc.body_of(sk)
        shape = b.Shape if b is not None else None
        if shape is not None and not shape.isNull() and shape.Solids:
            out.append(rl.lies_text("the body", world, _box6(geo.bound_box(shape))))
    except Exception:  # noqa: BLE001
        pass
    return [t for t in out if t]


def _one_frame(sk):
    """Whether the world box of the sketch's shapes (frame_of: the sketch's
    global placement) and its body's Shape are in one frame: the body's own
    Placement is its global one (no moved Part holds the body). False: the
    boxes are not compared. A body that does not say (a stand-in): True."""
    try:
        b = pc.body_of(sk)
        if b is None or not hasattr(b, "getGlobalPlacement"):
            return True
        return bool(b.getGlobalPlacement().isSame(b.Placement, 1e-9))
    except Exception:  # noqa: BLE001 - not read: not compared
        return False


def add_result(sk, out, st):
    """sketch_add's result line: each shape of the call with its ids, its
    extent in the sketch's x/y and in the world, a circle's centre and
    radius, an arc's start, middle and end point; then the sketch's wires,
    closed wires and open ends. Never raises."""
    try:
        return _add_result(sk, out, st)
    except Exception:  # noqa: BLE001 - a reading only
        return "Added " + ", ".join(f"{i.get('kind', 'shape')} {rl.id_text(i.get('ids') or [])}" for i in out or []) + "."


def _add_result(sk, out, st):
    try:
        frame = frame_of(sk)
    except Exception:  # noqa: BLE001
        frame = None
    shapes, worlds = [], []
    for item in out or []:
        ids = list(item.get("ids") or [])
        kw = {}
        try:
            use = [i for i in ids if 0 <= i < len(sk.Geometry)]
            solid = [i for i in use if not sk.getConstruction(i)] or use
            if len(solid) == 1:
                g = sk.Geometry[solid[0]]
                k = _geo_kind(g)
                if k == "Circle":
                    kw["circle"] = ((g.Center.x, g.Center.y), g.Radius)
                elif k == "Arc":
                    m = _mid(g)
                    kw["arc"] = ((g.StartPoint.x, g.StartPoint.y), (m.x, m.y), (g.EndPoint.x, g.EndPoint.y))
                elif k == "Line":
                    kw["line"] = ((g.StartPoint.x, g.StartPoint.y), (g.EndPoint.x, g.EndPoint.y))
        except Exception:  # noqa: BLE001 - not read: not said
            kw = {}
        box = _shapes_box(sk, ids)
        if box:
            kw["xr"], kw["yr"] = (box[0], box[1]), (box[2], box[3])
            if frame is not None:
                kw["world"] = rl.world_box(frame, kw["xr"], kw["yr"])
                worlds.append(kw["world"])
        if isinstance(item.get("byDefault"), dict):
            kw["default"] = item["byDefault"]
        shapes.append(rl.shape_text(str(item.get("kind") or "shape"), ids, **kw))
    wires = closed = ends = None
    if isinstance(st, dict):
        wires, closed = st.get("wires"), st.get("closedWires")
        try:
            ws = sk.Shape.Wires if not sk.Shape.isNull() else []
            ends = len(open_ends_of(sk, ws)) if ws else 0
        except Exception:  # noqa: BLE001
            ends = None
    lies = []
    if worlds:
        union = tuple(f(w[i] for w in worlds) for i, f in enumerate((min, max, min, max, min, max)))
        lies = lies_words(sk, union)
    return rl.sketch_add_result(shapes, wires, closed, ends, lies)


def refs_read(sk, raw, refs):
    """What the refs of a call are as _ref read them, one clause each: "The
    call gave 2 refs: [2, 0] is arc 2 as a whole (vertex 0 is the whole
    curve; its points are [2, 1] start point, [2, 2] end point, [2, 3]
    centre); [0, 1] is the start of line 0." A ref written with vertex 0
    gets the points that its geometry has (VERTICES). 27 Nov QA: [2, 0] was
    read as the whole curve, and the refusal said only "refs two points"."""
    if not refs:
        return "The call gave no refs."
    said = []
    for r, (g, p) in zip(raw, refs):
        shown = json.dumps(r)
        if r == "origin":
            said.append(f"{shown} is the sketch origin")
        elif p is not None:
            said.append(f"{shown} is {ref_words(sk, g, p)}")
        else:
            words = f"{shown} is {ref_words(sk, g)} as a whole"
            if isinstance(r, list) and len(r) == 2:
                more = "vertex 0 is the whole curve"
                try:
                    has = VERTICES.get(_geo_kind(sk.Geometry[g])) if 0 <= g < len(sk.Geometry) else None
                except Exception:  # noqa: BLE001 - not read: not said
                    has = None
                if has:
                    more += "; its points are " + ", ".join(f"[{g}, {v}] {VERTEX_WORDS[v]}" for v in has)
                words += f" ({more})"
            said.append(words)
    return f"The call gave {rl.plural(len(refs), 'ref')}: " + "; ".join(said) + "."


def make_constraint(sk, c):
    t = str(c.get("type", "")).lower().replace("_", "").replace("-", "")
    refs = [_ref(r, f"refs[{i}]") for i, r in enumerate(c.get("refs") or [])]
    for g, p in refs:
        why = vertex_words(sk, g, p)
        if why:
            raise ToolError("invalid_input", f"({t}): {why}. Nothing was added.")
    val = c.get("value")
    pts = [r for r in refs if r[1] is not None]
    n = len(refs)

    def need(ok, form):
        if not ok:
            raise ToolError("invalid_input", f"{t}: refs {form}. {refs_read(sk, c.get('refs') or [], refs)}")

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


def face_frame(P, up=None):
    """The attachment offset that lines a sketch on a face (placed at P) up
    with the world: its origin the world origin's foot on the face's plane,
    its axes by orient.face_axes — y up world z on a standing face, else x
    along the world axis that lies most in the plane — so coordinates read
    as the part's own. up: the world axis sketch y runs along."""
    n = P.Rotation.multVec(V(0, 0, 1))
    o = n * P.Base.dot(n)
    x, y = (V(*c) for c in _axes_or_refuse(orient.face_axes, n, up))
    D = FreeCAD.Placement(o, FreeCAD.Rotation(x, y, n, "ZXY"))
    return P.inverse().multiply(D)


def attachment(sk, wrote=""):
    """What FreeCAD stores for the attachment of sketch sk, by FreeCAD's own
    property names: AttachmentSupport (as "Label: Face3"), MapMode,
    MapReversed and AttachmentOffset { at, axis, angle }. wrote: the reason
    Agent Link set AttachmentOffset itself (a face sketch lined up with the
    world, up, offset), said in setBy; "" when it did not."""
    out = {}
    try:
        sup = getattr(sk, pc.support_prop(sk), None) or []
        said = []
        for item in (sup if isinstance(sup, (list, tuple)) else [sup]):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                subs = [item[1]] if isinstance(item[1], str) else [str(x) for x in item[1] if x]
                said.append(str(item[0].Label) + (": " + ", ".join(subs) if subs else ""))
            elif hasattr(item, "Label"):
                said.append(str(item.Label))
        out[pc.support_prop(sk)] = said[0] if len(said) == 1 else said
        out["MapMode"] = str(sk.MapMode)
        out["MapReversed"] = bool(getattr(sk, "MapReversed", False))
        ao = sk.AttachmentOffset
        out["AttachmentOffset"] = picks.placement_json(ao)
        if wrote:
            out["setBy"] = f"Agent Link set AttachmentOffset ({wrote}). FreeCAD's own value is the identity."
    except Exception:  # noqa: BLE001 - a reading only
        pass
    return out


def up_frame(P, up):
    """The attachment offset that turns a sketch placed at P about its own
    normal so its y runs along the world axis up (orient.up_axes). The origin
    and the normal stay as the attachment put them."""
    n = P.Rotation.multVec(V(0, 0, 1))
    x, y = (V(*c) for c in _axes_or_refuse(orient.up_axes, n, up))
    D = FreeCAD.Placement(P.Base, FreeCAD.Rotation(x, y, n, "ZXY"))
    return P.inverse().multiply(D)


def _axes_or_refuse(fn, n, up):
    try:
        return fn((n.x, n.y, n.z), up)
    except ValueError as e:
        raise ToolError("invalid_input", f"{e} Nothing was made.")


def axes(pl):
    """A sketch's frame (placement pl) in one line of words (orient.axes_line)."""
    return orient.axes_line(frame(pl))


def on_words(what, pl):
    """sketch_new's on for a face: which face (face_said) and where the
    sketch origin is (the world origin's foot on the face)."""
    o = ", ".join(orient.num(c) for c in frame(pl)["origin"])
    return f"{what}; sketch origin at [{o}]"


def face_said(b, link, what):
    """Which face a sketch is on, by its side: "the face +z at z 5" (the
    words of a feature's answer, pd_common.side_word: the outward normal's
    axis and where the face is along it; a slanted face: its normal and a
    point on it), and whose it is when a feature before the tip made it.
    27 Nov QA: "face at [30.0, 15.0, 5.0]" gave the face's centre, and a
    model read it as the sketch origin. When the face is not read: what
    (plane_ref's words), marked as the face's centre."""
    try:
        obj, subs = link
        f = obj.Shape.getElement(subs[0])
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        c = f.CenterOfMass
        words = "the face " + pc.side_word((n.x, n.y, n.z), (c.x, c.y, c.z))
        return words + ("" if obj is getattr(b, "Tip", None) else f" ({obj.Label}'s)")
    except Exception:  # noqa: BLE001 - not read: the words that plane_ref gave, which name the face's centre
        return f"{what} (its centre)" if str(what).startswith("face at") else what


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


_FILLET_BEFORE = {}


def _named(sk):
    return [c.Name for c in sk.Constraints if getattr(c, "Name", "")]


def fillet(sk, chamfer, *args):
    """Sketcher's fillet at a corner (geo, vertex, radius) or between two
    curves (geo, geo, point, point, radius), the curves trimmed to it;
    chamfer (FreeCAD 1.0+): a straight cut, not an arc. The corner is kept
    as a point (Sketcher's "Preserve corner", createCorner): the corner's
    constraints, bound ones too, move to it and stay (live finding T3,
    21 Nov: without it they were deleted with no word)."""
    _FILLET_BEFORE[id(sk)] = _named(sk)
    sk.fillet(*args, True, True, *((True,) if chamfer else ()))


def fillet_made(sk, n0, chamfer=False):
    """What a fillet made and what it took away, for its answer: the new
    arc (or chamfer line) by id, the kept corner point, and the named
    constraints that are gone."""
    kind = "Part::GeomLineSegment" if chamfer else "Part::GeomArcOfCircle"
    made = [i for i in range(n0, len(sk.Geometry)) if sk.Geometry[i].TypeId == kind]
    points = [i for i in range(n0, len(sk.Geometry)) if sk.Geometry[i].TypeId == "Part::GeomPoint"]
    out = ("line " if chamfer else "arc ") + ", ".join(str(i) for i in made or [len(sk.Geometry) - 1])
    if points:
        out += f"; corner kept as point {points[0]}"
    lost = [n for n in _FILLET_BEFORE.pop(id(sk), []) if n not in set(_named(sk))]
    if lost:
        out += f"; named constraints gone: {', '.join(lost)} (bind them again)"
    return out


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
               "body": lambda ref: pc.pd_body(doc(), ref), "sketch_of": lambda ref, b=None: pc.sketch_of(doc(), ref, b, s), "note_sketch": lambda sk, asked=None: pc.note_made_sketch(s, sk, asked), "status_words": pc.status_words, "body_of": pc.body_of,
               "body_reading": pc.body_reading, "broken": pc.newly_broken, "plane_ref": lambda *x: pc.plane_ref(*x), "face_pick": lambda *x: pc.face_pick(*x), "face_pick_said": lambda *x: pc.face_pick_said(*x), "support_prop": pc.support_prop, "plane_mode": pc.plane_mode,
               "version": lambda: ".".join(FreeCAD.Version()[:3]),
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "setprop": setattr, "vec2": pc.vec2, "is_tuple": lambda x: isinstance(x, tuple),
               "line": lambda a, b: Part.LineSegment(a, b), "wire": lambda edges: Part.Wire(edges), "sort_edges": lambda edges: Part.sortEdges(edges),
               "quantity": lambda text: FreeCAD.Units.Quantity(text), "constraint": constraint,
               # the family's: the solver's reading, the builders, constraints by name
               "frame": frame, "state_of": state_of, "fresh": fresh, "join_points": join_points, "join_move_words": join_move_words, "dof_of": dof_of, "con_result": con_result, "add_result": add_result, "new_result": new_result, "describe_geo": describe_geo, "describe_con": describe_con, "geo_kind": _geo_kind, "ext_count": ext_count,
               "con_words": con_words, "clashing": clashing, "build": build, "remap": _remap, "ref": _ref, "make_constraint": make_constraint, "con_index": con_index,
               "gid": gid, "face_frame": face_frame, "up_frame": up_frame, "axes": axes, "on_words": on_words, "face_said": face_said, "geo_of_edge": geo_of_edge, "offset_out": offset_out, "edge_refs": edge_refs, "edges_form": pc.edges_form, "fillet": fillet, "fillet_made": fillet_made, "bounds": bounds,
               "font_file": _font, "text_outlines": text_outlines, "item_error": item_error, "body_extent": body_extent, "by_default": by_default,
               "attachment": attachment, "con_brief": con_brief, "placement_json": picks.placement_json, "placement_fact": geo.placement_fact}
    return runners.tools(GROUP, s, helpers)
