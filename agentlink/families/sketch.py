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


def body_extent(b, sk):
    """Where body b's solid is in sketch sk's own x/y: {"x": [min, max],
    "y": [min, max]} (mm, to 0.1), from the corners of the solid's box
    taken through the inverse of the sketch's place in the world. None
    when the body has no solid yet."""
    try:
        shape = b.Shape
        if shape is None or shape.isNull() or not shape.Solids:
            return None
        bb = geo.bound_box(shape)  # exact, not the box of the view's triangles
        pl = sk.getGlobalPlacement() if hasattr(sk, "getGlobalPlacement") else sk.Placement
        inv = pl.inverse()
    except Exception:  # noqa: BLE001 - no reading: nothing said
        return None
    pts = [inv.multVec(V(x, y, z)) for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax) for z in (bb.ZMin, bb.ZMax)]
    r = lambda v: round(float(v), 1) + 0.0  # noqa: E731
    return {"x": [r(min(p.x for p in pts)), r(max(p.x for p in pts))], "y": [r(min(p.y for p in pts)), r(max(p.y for p in pts))]}


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


# An open end within this part of the outline's size of another open end is
# a gap to close (a coincident constraint); farther from every other end,
# and on no other curve, it is a loose end (a stray line, or a side left out).
NEAR_GAP = 0.1
# Heuristic (blind QA, 26 Nov: round ends drawn as full circles plus lines):
# an open end this near a full circle's edge (a share of the outline's size,
# at least ROUND_NEAR_MM, never past the NEAR_GAP distance) is a line meant to
# meet a round end there. Such ends are not paired to each other: joining
# them collapses the outline. The words say to use an arc in its place.
ROUND_NEAR = 0.05
ROUND_NEAR_MM = 3.0
# Two open ends closer than this (mm, or this share of the outline's size)
# are one joint: said as a gap to close before any other words of them.
TINY_GAP_MM = 0.01
TINY_GAP = 1e-4


def _at(p):
    return f"({geo.r3(p[0]):g}, {geo.r3(p[1]):g})"


def open_end_words(ends, curves, size, dist, rounds=(), joined=None):
    """The todo words for the open ends of a sketch's outline, one phrase
    each (a curve with both ends loose: one phrase). ends: [(gid, kind,
    pos, (x, y))], pos 1 start / 2 end; curves: the ids of the outline's
    curves; size: the outline's size (its box's diagonal, mm); dist(gid,
    (x, y)): mm from that curve to the point; rounds: the ids of its full
    circles. [] when an end is on another curve (a branch: branch_words
    says it). joined: a list that gets ((gid, (x, y)), (gid2, (x2, y2)))
    for each two ends the words say to join (branch_words then says
    nothing more of that point)."""
    tol = 1e-6 * max(size, 1.0)
    gap = max(NEAR_GAP * size, tol)
    rgap = min(max(ROUND_NEAR * size, ROUND_NEAR_MM), gap)
    at = _at

    def round_of(gid, p):
        near_ = [(dist(c, p), c) for c in rounds if c != gid]
        return min(near_) if near_ else (math.inf, None)

    near, rnd, loose, pairs = [], [], {}, set()

    def pair(gid, kind, pos, p, d, g2, k2, s2, q):
        key = tuple(sorted(((gid, pos), (g2, s2))))
        if key not in pairs:
            pairs.add(key)
            if joined is not None:
                joined.append(((gid, p), (g2, q)))
            # A line end at an arc end: the card's join, tangent, joins and
            # smooths them; coincident leaves a corner (QA 1126h: the todo and
            # the card named different joins).
            if {kind, k2} == {"line", "arc"}:
                how = f"sketch_constrain tangent [[{gid}, {pos}], [{g2}, {s2}]] joins and smooths them"
            else:
                how = "sketch_constrain coincident joins them"
            near.append(f"{POS[pos]} {kind} {gid} {at(p)} is {geo.r3(d):g} mm from {POS[s2]} {k2} {g2} {at(q)}: " + how)

    # Two ends a hair apart are one joint left open: the coincident words
    # first, always (26 Nov QA: an end 0.001 mm from the next one got the
    # round-end words of a hole circle nearby, and the real fix was hidden).
    tiny = max(TINY_GAP_MM, TINY_GAP * size, tol)
    paired = set()
    for gid, kind, pos, p in ends:
        others = [(math.dist(p, q), g2, k2, s2, q) for g2, k2, s2, q in ends if (g2, s2) != (gid, pos) and g2 != gid]
        d, g2, k2, s2, q = min(others) if others else (math.inf, None, None, None, None)
        if tol < d <= tiny:
            pair(gid, kind, pos, p, d, g2, k2, s2, q)
            paired |= {(gid, pos), (g2, s2)}
    ends = [e for e in ends if (e[0], e[2]) not in paired]
    by_round = {(gid, pos): round_of(gid, p) for gid, _k, pos, p in ends}
    # Heuristic: a circle is a round end drawn as a full circle only when the
    # ends of two or more other curves come near it. One end near a circle
    # is near a hole (a pin hole inside a round end, 26 Nov QA), not a
    # round end: its own words below say what is open there.
    came = {}
    for gid, _k, pos, _p in ends:
        rd, rc = by_round[(gid, pos)]
        if rc is not None and rd <= rgap:
            came.setdefault(rc, set()).add(gid)
    for key, (rd, rc) in list(by_round.items()):
        if rc is not None and rd <= rgap and rd > tol and len(came.get(rc, ())) < 2:
            by_round[key] = (math.inf, None)
    for gid, kind, pos, p in ends:
        rd, rc = by_round[(gid, pos)]
        if rd <= rgap:
            if rd > tol:
                rnd.append(f"{kind} {gid} ends at {at(p)}, {geo.r3(rd):g} mm from circle {rc}: an outline uses an arc there, not a full circle")
            continue  # on the circle: a branch, which branch_words says
        others = [(math.dist(p, q), g2, k2, s2, q) for g2, k2, s2, q in ends if g2 != gid and by_round[(g2, s2)][0] > rgap]
        d, g2, k2, s2, q = min(others) if others else (math.inf, None, None, None, None)
        if d <= gap:
            pair(gid, kind, pos, p, d, g2, k2, s2, q)
            continue
        if any(dist(g, p) <= tol for g in curves if g != gid):
            continue  # on another curve: a branch, which branch_words says
        loose.setdefault((gid, kind), []).append(p)
    words = rnd
    for (gid, kind), ps in loose.items():
        if len(ps) > 1:
            words.append(f"{kind} {gid} touches nothing at {' or '.join(at(p) for p in ps)}: remove it (sketch_edit {{ delete: [{gid}] }}) or join its ends")
        else:
            words.append(f"{kind} {gid} ends at {at(ps[0])} on nothing: remove it (sketch_edit {{ delete: [{gid}] }}) or join that end to another end")
    words = near + words
    if len(words) > 4:
        words = words[:4] + [f"and {len(words) - 4} more open ends (openVertices)"]
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
    dist as open_end_words; rounds: the ids of the full circles; joins:
    open_end_words' joined, the ends it says to join."""
    tol = 1e-6 * max(size, 1.0)

    def joined(g, p, other):
        # An end at p that the gap words join to an end of curve other: that
        # curve passes through p only because its own end is a hair away
        # (blind QA, 26 Nov: "a wire branches there" and "0.003 mm from the
        # end of line 3: coincident joins them" for one joint). One point,
        # one message: the gap words, whose fix is right.
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
    words, round_ = [], False
    for p, at_ in spots:
        mine = {g for _k, g in at_}
        through = [(curves[g], g) for g in curves if g not in mine and dist(g, p) <= tol and not joined(mine, p, g)]
        if len(at_) + 2 * len(through) < 3:
            continue
        who = _names(at_)
        if through:
            words.append(f"{who} {'meets' if len(at_) == 1 else 'meet'} {_names(through)} at {_at(p)}")
            round_ = round_ or any(g in rounds for _k, g in through)
        else:
            words.append(f"{who} meet at {_at(p)}")
    if not words:
        return []
    if len(words) > 4:
        words = words[:4] + [f"and {len(words) - 4} more points where a wire branches"]
    # The why, once: on the first point.
    words[0] += ": a wire branches there; an outline has two edges at each joint" + (", so use an arc there, not a full circle (two round ends joined by straight sides are one slot item: slot { from, to, radius, radius2 })" if round_ else "")
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
    words[0] += ": a pad or pocket uses only loops that do not cross or touch; make one outline"
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


def _cross_words(sk, wires):
    """cross_words for the closed wires of sketch sk (its Shape's, in the
    world: read back into the sketch's own x/y); [] when it cannot be read."""
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
    except Exception:  # noqa: BLE001 - no reading: nothing said
        return []


MAX_OVERLAP_CURVES = 200


def overlap_words(sk):
    """Curves of sketch sk that lie on each other for a length (exact: the
    common part of their shapes), in words: "line 4 lies on line 0 from
    [35, 0] to [-30, 0]" (QA 1126i: a polyline back over its own first edge
    read closedWires 1, readyForFeature true, and padded only part of it).
    Construction geometry is left out; [] when none or not readable."""
    out = []
    try:
        ids = []
        for g, c in enumerate(sk.Geometry):
            try:
                if sk.getConstruction(g):
                    continue
            except Exception:  # noqa: BLE001
                pass
            if type(c).__name__ in ("LineSegment", "ArcOfCircle", "Circle"):
                ids.append(g)
        if len(ids) > MAX_OVERLAP_CURVES:
            return []
        shapes = {g: sk.Geometry[g].toShape() for g in ids}
        for n, a in enumerate(ids):
            for b in ids[n + 1:]:
                sa, sb = shapes[a], shapes[b]
                if not sa.BoundBox.intersect(sb.BoundBox):
                    continue
                com = sa.common(sb)
                if com.isNull() or com.Length <= 1e-6:
                    continue
                vs = com.Vertexes
                ends = f" from {_pt(vs[0].Point)} to {_pt(vs[-1].Point)}" if len(vs) >= 2 else ""
                out.append(f"{_geo_kind(sk.Geometry[b]).lower()} {b} lies on {_geo_kind(sk.Geometry[a]).lower()} {a}{ends} "
                           f"({_mm(com.Length)} mm): delete one or move it")
    except Exception:  # noqa: BLE001 - no reading: nothing said
        return []
    return out


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
    # Ready only when every wire is closed (open wires with T-junctions have
    # no one-edge end) and no two closed wires cross or touch: FreeCAD makes
    # a face of loops apart or one inside another (a hole), not of loops
    # that meet.
    cross = _cross_words(sk, wires) if wires and closed == len(wires) else []
    cross += overlap_words(sk) if wires else []
    ready = code == 0 and not conflicting and not redundant and not malformed and bool(wires) and closed == len(wires) and not cross
    out["readyForFeature"] = ready
    if not ready:
        why = []
        if conflicting or redundant or malformed or code != 0:
            why.append("fix the constraints named (sketch_edit deleteConstraints)")
        if openv or (wires and closed < len(wires)):
            joins = []
            gaps = _open_end_words(sk, openv, joins)
            said = _branch_words(sk, joins) + gaps
            why += said or ["close the open wires: coincident constraints at the open vertices"]
        why += cross
        if not wires:
            why.append("no profile yet: sketch_add")
        out["todo"] = "; ".join(why) or "the sketch has no closed wire"
    elif dof:
        # Its words after the count are said once a conversation (agentlink/once.py).
        out["note"] = f"{dof} degrees of freedom: {DOF_NOTE}"
    return out


def item_error(n, e):
    """sketch_add's refusal for item n that failed (blind QA, 24 Nov: FreeCAD's
    words did not say which item): the same refusal, its words after
    "items[n]: ". A tool's own refusal keeps its code; a ValueError is the
    input's; any other error is FreeCAD's failure."""
    if isinstance(e, ToolError):
        code, msg = e.code, e.message
    else:
        code, msg = ("invalid_input" if isinstance(e, ValueError) else "failed"), (str(e) or type(e).__name__)
    head = f"items[{n}]"
    err = ToolError(code, msg if str(msg).startswith(head) else f"{head}: {msg}", kind=getattr(e, "kind", None))
    raise err from e


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
        size = item.get("size")
        w, h = (list(size) + [None, None] if isinstance(size, (list, tuple)) else [None, None])[:2]
        if not (isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0):
            # The fields it was given, and the form (live, 22 Nov: x, y,
            # width, height three times in one run).
            other = [f for f in ("width", "height", "x", "y", "w", "h") if f in item]
            raise ToolError("invalid_input", f"{k}: size [w, h] (mm), and center [x, y] or corner [x, y] (its lower left)."
                                             + (f" {', '.join(other)}: not fields of a {k}." if other else "")
                                             + f" Example: {{ \"kind\": \"{k}\", \"corner\": [0, 0], \"size\": [60, 30] }}.")
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
        r2 = float(item.get("radius2", r) if item.get("radius2") is not None else r)
        d = p2 - p1
        if r <= 0 or r2 <= 0 or d.Length < 1e-6:
            raise ToolError("invalid_input", "slot: from and to (its two end centres, apart), radius (the round end at from), radius2 (the round end at to; the same as radius when left out), mm.")
        if d.Length <= abs(r - r2) + 1e-6:
            raise ToolError("invalid_input", f"slot: the ends are {pc._g(d.Length)} mm apart, but the radii differ by {pc._g(abs(r - r2))} mm: one round end is inside the other. Move the ends apart or make the radii closer.")
        t = math.atan2(d.y, d.x)
        # The outer tangent lines touch each round end where its outward
        # normal is at t +- beta, with cos(beta) = (r - r2) / length (exact;
        # beta is 90 deg when the radii are equal, the plain slot).
        b = math.acos(max(-1.0, min(1.0, (r - r2) / d.Length)))
        uu = V(math.cos(t + b), math.sin(t + b), 0)
        ul = V(math.cos(t - b), math.sin(t - b), 0)
        G = [
            _arc(p1, r, t + b, t - b + 2 * math.pi),  # 0 round end at from: upper to lower, round the back
            _arc(p2, r2, t - b, t + b),  # 1 round end at to: lower to upper
            _line(p1 + ul * r, p2 + ul * r2),  # 2
            _line(p2 + uu * r2, p1 + uu * r),  # 3
        ]
        C += [("Tangent", 0, 2, 2, 1), ("Tangent", 2, 2, 1, 1), ("Tangent", 1, 2, 3, 1), ("Tangent", 3, 2, 0, 1)]
        if abs(r - r2) < 1e-9:
            C.append(("Equal", 0, 1))
            if abs(d.y) < 1e-9:
                C.append(("Horizontal", 2))
            elif abs(d.x) < 1e-9:
                C.append(("Vertical", 2))
            D += [("r", ("Radius", 0, r))]
        else:
            D += [("r", ("Radius", 0, r)), ("r2", ("Radius", 1, r2))]
        D += [("length", ("Distance", 0, 3, 1, 3, d.Length))]
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
    # The wrong value is said back, and a PartDesign feature's name is told
    # apart from a sketch shape (QA 1126f: kind "fillet" in sketch_add).
    kinds = "line, polyline, arc, arc3, circle, circle3, ellipse, parabola, hyperbola, bspline, rectangle, rounded_rectangle, polygon, slot, arc_slot or point"
    if k is None:
        # No kind at all (QA 1126h: kind "None" for an item that had type).
        other = next((f for f in ("type", "shape", "kind_") if f in item), None)
        raise ToolError("invalid_input", "the item has no kind" + (f' (it has {other}: {json.dumps(item[other])}; the field is kind)' if other else "")
                        + f". The kinds: line, polyline, arc, arc3, circle, circle3, ellipse, parabola, hyperbola, bspline, rectangle, rounded_rectangle, polygon, slot, arc_slot or point.")
    said = str(k)
    feature = {"fillet": "pd_fillet", "chamfer": "pd_chamfer", "pad": "pd_pad", "pocket": "pd_pocket", "hole": "pd_hole", "extrude": "pd_pad"}.get(said.lower())
    if feature:
        raise ToolError("invalid_input", f'kind "{said}" is not a sketch shape: {feature} makes it on the body, from a sketch or its edges. The sketch kinds: {kinds}.')
    raise ToolError("invalid_input", f'kind "{said}" is not a sketch_add kind. The kinds: {kinds}.')


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


CON_FIELDS = ("type", "refs", "value", "name")
CON_EXAMPLE = '{ "type": "tangent", "refs": [0, 1] } makes line 0 tangent to circle 1'
# Fields models wrote for refs (local-model runs, 24 Nov: a, b).
CON_REF_WORDS = ("a", "b", "c", "point", "points", "geometry", "geometries", "geo", "ref", "first", "second", "line", "circle", "edges", "ids")
CON_VALUE_WORDS = ("length", "distance", "radius", "diameter", "angle", "size", "mm", "deg")


def con_keys(c, i):
    """One constraint checked for its fields: { type, refs, value, name }.
    A field written another way (kind, a, b, point …) is refused by name,
    with the right fields and one worked constraint; nothing is guessed
    (owner, 22 Nov; no aliases, 24 Nov). A reader."""
    if not isinstance(c, dict):
        return c
    extra = [k for k in c if k not in CON_FIELDS]
    if extra:
        hint = ""
        if "kind" in extra or "constraint" in extra:
            hint = " The constraint's kind goes in type."
        if any(k in extra for k in CON_REF_WORDS):
            hint += " Its geometry ids and points go in refs, one list, in order."
        if any(k in extra for k in CON_VALUE_WORDS):
            hint += " A size goes in value (mm or deg)."
        raise ToolError("invalid_input", f"constraints[{i}]: {', '.join(extra)}: not {'a field' if len(extra) == 1 else 'fields'} of a constraint.{hint} "
                                         f"A constraint has only type, refs, value and name. Example: {CON_EXAMPLE}.")
    if not c.get("type"):
        raise ToolError("invalid_input", f"constraints[{i}]: type is missing. Example: {CON_EXAMPLE}.")
    return c


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


SIDES = ("+x", "-x", "+y", "-y", "+z", "-z")


def both_given(plane, face):
    """sketch_new's refusal of plane and face together: what was sent, and
    the fact when plane holds a side (QA run 1126k lid: plane "-z" with
    face { side: "-z" }, and the model then took the example "Pad.Face3",
    a real side face, for the bottom)."""
    said = f"You sent plane {json.dumps(plane)} and face {json.dumps(face, default=str)}: send one of them."
    if str(plane).strip().lower() in SIDES:
        said += f" plane {json.dumps(plane)} is not a plane: a side goes in face {{ side: {json.dumps(str(plane).strip().lower())} }}."
    return (said + " plane is XY, XZ, YZ, a datum plane's name or a face's name as shape_query gives it."
            " face is { side: \"+z\" } (+z is the top, -z the bottom) or { at: [x,y,z], normal: [x,y,z] } on the body's solid.")


def item_over(sk, ids):
    """For one closed item of sketch sk (its geometry ids): "over the body"
    when the body has material under its outline on either side of the
    sketch, "off the body: …" when it has none, None when it cannot be
    told or the body has no solid yet (exact: the outline swept through the
    body and cut with its solid). QA 1126h: holes drawn at (45, 15) on a
    body that spans x -30..30, and the answer said nothing until the cut."""
    try:
        body = next((o for o in sk.InList if o.TypeId == "PartDesign::Body"), None)
        if body is None or body.Shape.isNull() or not body.Shape.Solids:
            return None
        edges = [sk.Geometry[g].toShape() for g in ids if not sk.getConstruction(g)]
        if not edges:
            return None
        wire = Part.Wire(Part.sortEdges(edges)[0])
        if not wire.isClosed():
            return None
        pl = sk.getGlobalPlacement() if hasattr(sk, "getGlobalPlacement") else sk.Placement
        face = Part.Face(wire).transformed(pl.toMatrix())  # in the world, as the body's solid
        n = pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        bb = geo.bound_box(body.Shape)
        d = bb.DiagonalLength + face.BoundBox.DiagonalLength + 1.0
        com = face.translated(n * -d).extrude(n * (2 * d)).common(body.Shape)
        if com.Volume > 1e-6:
            # Where, in the sketch's own x/y (QA 1126j: "over the body" when
            # a quarter of the outline was over it). Exact boxes of the
            # material under it and of the item itself.
            inv = pl.inverse().toMatrix()
            under, own = geo.bound_box(com.transformed(inv)), geo.bound_box(Part.Face(wire))
            span = lambda b: f"x {_mm(b.XMin)}..{_mm(b.XMax)}, y {_mm(b.YMin)}..{_mm(b.YMax)}"  # noqa: E731
            # Which side of the sketch holds it (QA 1126k: circles "over the
            # body" with all of it against the normal, and the pocket cut
            # the other way). z is the sketch's own: along its normal.
            tol = 1e-6
            side = ("along the normal" if under.ZMin >= -tol else "against the normal" if under.ZMax <= tol else "on both sides of the sketch")
            depth = f"{side} (z {_mm(under.ZMin)}..{_mm(under.ZMax)} from the sketch)"
            if span(under) == span(own):
                return f"over the body: material under {span(own)}, the same box as the item's, {depth}"
            return f"partly over the body: material under {span(under)} of the item's {span(own)}, {depth}"
        return (f"off the body: no material of {body.Label} under it on either side of the sketch "
                f"(the body: {pc.span_text(bb)})")
    except Exception:  # noqa: BLE001 - a reading only
        return None


def _mm(v):
    return f"{round(float(v), 4) + 0.0:g}"


def round_sizes(sk):
    """{id: (radius, cx, cy)} for each circle and arc: what solved_away
    compares after a solve."""
    out = {}
    for g, c in enumerate(sk.Geometry):
        if type(c).__name__ in ("Circle", "ArcOfCircle"):
            out[g] = (float(c.Radius), float(c.Center.x), float(c.Center.y))
    return out


def solved_away(sk, before, tol=1e-4):
    """The radii and centres a solve changed, in words: "arc 2: radius 12.5
    → 12.465" (QA 1126i: a tangent made a crank end 12.465 and no answer
    said so). Geometry the call did not move is left out; [] when none."""
    out = []
    try:
        now = round_sizes(sk)
        for g, (r0, x0, y0) in sorted(before.items()):
            if g not in now:
                continue
            r1, x1, y1 = now[g]
            kind = "circle" if type(sk.Geometry[g]).__name__ == "Circle" else "arc"
            bits = []
            if abs(r1 - r0) > tol:
                bits.append(f"radius {_mm(r0)} → {_mm(r1)}")
            if abs(x1 - x0) > tol or abs(y1 - y0) > tol:
                bits.append(f"centre [{_mm(x0)}, {_mm(y0)}] → [{_mm(x1)}, {_mm(y1)}]")
            if bits:
                out.append(f"{kind} {g}: " + ", ".join(bits))
    except Exception:  # noqa: BLE001 - a reading only
        return []
    return out


def arc_points(sk, ids):
    """For each arc among geometry ids: its id and its start, through (the
    middle of the arc) and end points in the sketch's x/y, so the side it
    bulges to is plain (QA 1126f: both arcs of a crank on the inside, and
    the answer said only the ids). [] on any error."""
    out = []
    try:
        for g in ids:
            c = sk.Geometry[g]
            if type(c).__name__ == "Circle":
                # A full circle: its centre, radius and diameter (QA 1126g: a
                # 13 mm hole drawn as radius 13).
                r = float(c.Radius)
                out.append({"id": g, "center": [round(c.Center.x, 3), round(c.Center.y, 3)], "r": round(r, 3), "d": round(2 * r, 3)})
                continue
            if type(c).__name__ != "ArcOfCircle":
                continue
            a0, a1 = c.FirstParameter, c.LastParameter
            p = [c.value(a0), c.value((a0 + a1) / 2), c.value(a1)]
            out.append({"id": g, "from": [round(p[0].x, 3), round(p[0].y, 3)], "through": [round(p[1].x, 3), round(p[1].y, 3)],
                        "to": [round(p[2].x, 3), round(p[2].y, 3)]})
    except Exception:  # noqa: BLE001
        return []
    return out


# Heuristic (blind QA, 26 Nov: coincident pairs that joined points about 170
# mm apart in a 200 mm crank, and the outline folded over): a coincident
# whose two points were farther apart than this share of the sketch's size
# (NEAR_GAP's share: nearer is a gap to close) and whose solve moved a point
# that far is named in the todo, so the shape is checked.
FAR_JOIN = NEAR_GAP


def far_joins(sk, ts):
    """[(words of the two points, (x1, y1), (x2, y2), gap mm, limit mm)] for
    each Coincident in constraint tuples ts whose points are now farther
    apart than FAR_JOIN of the sketch's size; [] on any error."""
    out = []
    try:
        try:
            size = sk.Shape.BoundBox.DiagonalLength
        except Exception:  # noqa: BLE001
            size = 0.0
        limit = max(FAR_JOIN * size, 1e-3)
        for t in ts:
            if t[0] != "Coincident" or len(t) < 5:
                continue
            a, b = sk.getPoint(t[1], t[2]), sk.getPoint(t[3], t[4])
            d = math.dist((a.x, a.y), (b.x, b.y))
            if d > limit:
                out.append(((t[1], t[2], t[3], t[4]), (a.x, a.y), (b.x, b.y), d, limit))
    except Exception:  # noqa: BLE001 - a reading only
        return []
    return out


def far_join_words(st, sk, far):
    """st (state_of's) with the todo words first for each far join whose
    solve moved one of its points more than the limit: "coincident joined
    the end of arc 0 (0.9, 20) and the start of line 3 (170.7, -12.5), 172
    mm apart: the shape moved; check it". Never raises."""
    words = []
    try:
        for (g1, p1, g2, p2), a, b, d, limit in far:
            try:
                na, nb = sk.getPoint(g1, p1), sk.getPoint(g2, p2)
                moved = max(math.dist(a, (na.x, na.y)), math.dist(b, (nb.x, nb.y)))
            except Exception:  # noqa: BLE001 - not read: said, as the join was far
                moved = d
            if moved <= limit:
                continue
            words.append(f"coincident joined {ref_words(sk, g1, p1)} {_at(a)} and {ref_words(sk, g2, p2)} {_at(b)}, "
                         f"{geo.r3(d):g} mm apart: the shape moved; check it")
    except Exception:  # noqa: BLE001
        return st
    if words:
        st = dict(st)
        st["todo"] = "; ".join(words + ([st["todo"]] if st.get("todo") else []))
    return st


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
    """sketch_new's on for a face: the face's centre and, beside it, where the
    sketch origin is (another point: the world origin's foot on the face)."""
    o = ", ".join(orient.num(c) for c in frame(pl)["origin"])
    return f"{what} (its centre); sketch origin at [{o}]"


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
               "frame": frame, "state_of": state_of, "fresh": fresh, "far_joins": far_joins, "far_join_words": far_join_words, "describe_geo": describe_geo, "describe_con": describe_con, "geo_kind": _geo_kind, "ext_count": ext_count,
               "con_words": con_words, "clashing": clashing, "build": build, "arc_points": arc_points, "both_given": both_given, "round_sizes": round_sizes, "solved_away": solved_away, "item_over": item_over, "remap": _remap, "ref": _ref, "make_constraint": make_constraint, "con_keys": con_keys, "con_index": con_index,
               "gid": gid, "face_frame": face_frame, "up_frame": up_frame, "axes": axes, "on_words": on_words, "geo_of_edge": geo_of_edge, "offset_out": offset_out, "edge_refs": edge_refs, "fillet": fillet, "fillet_made": fillet_made, "bounds": bounds,
               "font_file": _font, "text_outlines": text_outlines, "item_error": item_error, "body_extent": body_extent}
    return runners.tools(GROUP, s, helpers)
