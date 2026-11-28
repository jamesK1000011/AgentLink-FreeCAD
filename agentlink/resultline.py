# SPDX-License-Identifier: LGPL-2.1-or-later
"""The result record: the `result` field of a tool's answer (plain Python).

Owner, 28 Nov: answers are records. `result` is a dict of the facts that a
measure gave and that no other key of the same answer has: typed numbers
and names, boxes as { x: [min, max], y: [min, max], z: [min, max] } (mm),
no sentence. A fact that is another key of the answer (volumeChange,
solids, bounds, where, opens, notGiven …) is not said again here. The rules:
  - Numbers in mm, rounded to 2 places. World axes are X, Y and Z.
  - The only tolerance is the equality tolerance TOL that the answers
    already used (beyond_sides): 1e-3 mm. The words "added" and "removed"
    follow the sign of the volume change rounded to 2 places; a change that
    rounds to 0 has no material word.
  - A cap that hides items says how many are not shown.
  - A box against another box uses one record everywhere (against_rec):
    { x: { past: { "-x": 5 } } } or { x: { inside: { "-x": 10, "+x": 20 } } }.

This module has only small pure functions: they take measured numbers and
return a record. The code that measures (families/pd_common.py,
families/sketch.py, tools.py) calls them. Tests:
tests/test_result_records_1128.py.
"""

TOL = 1e-3  # mm: two numbers this near are equal (the tolerance of beyond_sides)

# What a tool did when the volume change is not known; the sign of a measured
# volume change decides the word otherwise (material).
TOOL_MATERIAL = {
    "pd_pad": "added", "pd_revolution": "added",
    "pd_pocket": "removed", "pd_hole": "removed", "pd_groove": "removed",
}


# ---- numbers ---------------------------------------------------------------------------------

def num(x):
    """A number in mm: 2 places at most, no trailing zeros, no "-0", no exponent."""
    v = round(float(x), 2) + 0.0
    if v == 0:
        return "0"
    return f"{v:.2f}".rstrip("0").rstrip(".")


def signed(x):
    """"+6000" or "-196.35"; "0" for no change."""
    v = num(x)
    return v if v == "0" or v.startswith("-") else "+" + v


def span(lo, hi):
    """"a..b"; one number when both ends are equal within TOL."""
    return num(lo) if abs(hi - lo) <= TOL else f"{num(lo)}..{num(hi)}"


def box_text(box):
    """A box (xmin, xmax, ymin, ymax, zmin, zmax) as "x 0..60, y 0..30, z 0..5"."""
    return ", ".join(f"{ax} {span(box[2 * i], box[2 * i + 1])}" for i, ax in enumerate("xyz"))


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def solids_text(now, was=None):
    """"The body is 2 solids (was 1)." """
    if now is None:
        return ""
    return f"The body is {plural(now, 'solid')}" + (f" (was {was})." if was is not None else ".")


def body_change_text(body, vol0, vol1, box0=None, box1=None, solids0=None, solids1=None):
    """What one call changed of a body, from its volume, box and solids
    before and after: "This call changed Body: volume change -196.35 mm³,
    now 14053.65 mm³." or "After this call the volume of Body is 14250 mm³:
    volume change 0 mm³." Then the two boxes when they differ, and the
    solids when their count differs. (Not part of the result record: it is
    the words of used_change, the answer of a call that changed a sketch
    that a feature uses.)"""
    delta = vol1 - vol0
    if num(delta) == "0":  # the number as it is said: no other limit
        out = [f"After this call the volume of {body} is {num(vol1)} mm³: volume change 0 mm³."]
    else:
        out = [f"This call changed {body}: volume change {signed(delta)} mm³, now {num(vol1)} mm³."]
    if box0 is not None and box1 is not None and any(abs(a - b) > TOL for a, b in zip(box0, box1)):
        out.append(f"The body before is {box_text(box0)}. The body now is {box_text(box1)}.")
    if solids0 is not None and solids1 is not None and solids0 != solids1:
        out.append(solids_text(solids1, solids0))
    return " ".join(out)


def n2(x):
    """A number in mm as a number: 2 places at most, never -0.0."""
    return round(float(x), 2) + 0.0


def box_rec(box):
    """A box (xmin, xmax, ymin, ymax, zmin, zmax) as { x: [min, max], y: [min, max], z: [min, max] } (mm)."""
    return {ax: [n2(box[2 * i]), n2(box[2 * i + 1])] for i, ax in enumerate("xyz")}


def range_rec(pair):
    """(min, max) as [min, max] (mm)."""
    return [n2(pair[0]), n2(pair[1])]




# ---- RL-F: a solid feature -------------------------------------------------------------------

def material(tool, delta):
    """"added" or "removed": the sign of the volume change as it is rounded to
    2 places; the tool's own word when the change is not known; None when the
    change rounds to 0 (the volumeChange key says 0)."""
    if delta is None:
        return TOOL_MATERIAL.get(tool)
    if num(delta) == "0":
        return None
    return "added" if delta > 0 else "removed"


def against_rec(new, old, tol=TOL, axes=(0, 1, 2)):
    """The new box against the old box on each axis, as a record: on an axis
    that goes past, { x: { past: { "-x": 5, "+x": 2 } } } (the sides that it
    goes past, mm); on an axis that is inside, { x: { inside: { "-x": 10,
    "+x": 20 } } } (the distance to each side of the old box). Boxes as
    (xmin, xmax, ymin, ymax, zmin, zmax)."""
    out = {}
    for i in axes:
        ax = "xyz"[i]
        past = {}
        if new[2 * i] < old[2 * i] - tol:
            past[f"-{ax}"] = n2(old[2 * i] - new[2 * i])
        if new[2 * i + 1] > old[2 * i + 1] + tol:
            past[f"+{ax}"] = n2(new[2 * i + 1] - old[2 * i + 1])
        if past:
            out[ax] = {"past": past}
        else:
            out[ax] = {"inside": {f"-{ax}": n2(max(new[2 * i] - old[2 * i], 0.0)), f"+{ax}": n2(max(old[2 * i + 1] - new[2 * i + 1], 0.0))}}
    return out


def lies_rec(name, new, old, flat=False):
    """Where a box lies against a named box: { against: "body", box: {…
    the old box}, axes: against_rec's }. flat: the old box is a flat face's;
    an axis along which it has no size (within TOL) is left out. {} when no
    axis is left."""
    axes = [i for i in range(3) if not (flat and abs(old[2 * i + 1] - old[2 * i]) <= TOL)]
    if not axes:
        return {}
    return {"against": name, "box": box_rec(old), "axes": against_rec(new, old, axes=axes)}


def profiles_rec(n, looked, part, none):
    """The profiles of a feature's sketch that did not do all that their area
    gives: { profileCount, partialProfilePercent: [75, 25] (the share of the
    volume that each such area gives over the same depth), idleProfiles: how
    many did nothing, profilesMeasured (when fewer than profileCount) }. {}
    when every measured profile did all of it."""
    out = {}
    if part:
        out["partialProfilePercent"] = [float(f"{p:.4g}") for p in part]
    if none:
        out["idleProfiles"] = int(none)
    if out:
        out["profileCount"] = n
        if looked < n:
            out["profilesMeasured"] = looked
    return out


def touch_rec(faces, more, gap, touching):
    """What the new material meets of the body before: { touching: true,
    faces: ["+z at z 5"], facesNotLooked: 3 } or { touching: true, faces: []
    } (touches, shares no face) or { touching: false, gap: 12.5 }. faces:
    the side words of the body's faces it lies on; more: faces not looked at
    (a cap); gap: the least distance to the body, mm, or None; touching:
    whether that distance is zero, or None (not measured: {})."""
    if faces:
        out = {"touching": True, "faces": list(faces)}
        if more:
            out["facesNotLooked"] = more
        return out
    if touching is True:
        return {"touching": True, "faces": []}
    if touching is False:
        return {"touching": False, **({"gap": n2(gap)} if gap is not None else {})}
    return {}


def feature_result(tool, delta, region=None, region_more=0, old_box=None, cut=False, faces=None, faces_more=0,
                   gap=None, touching=None, looked=True, solids=None, solids_was=None, profiles=None):
    """The result record of a solid feature: the facts that its answer has no
    other key for. material: "added" | "removed"; pieces: one box for each
    separate piece of the new or removed material when there are several
    (the one box is the answer's added or removed key), piecesNotShown;
    bodyBefore: the body's box before (the answer's bounds is the body now);
    againstBefore: the region's box against it (against_rec); touches: for
    added material (touch_rec); opensNotLooked: faces of the removed material
    that were not looked at (the answer's opens lists where it opens);
    solidsWas; profile counts (profiles_rec's keys). A fact that was not
    measured is left out. region: a list of boxes (one for each piece);
    old_box None: there was no body before."""
    out = {}
    m = material(tool, delta)
    if m:
        out["material"] = m
    if old_box is not None:
        out["bodyBefore"] = box_rec(old_box)
        if region:
            if len(region) > 1 or region_more:
                out["pieces"] = [box_rec(b) for b in region]
                if region_more:
                    out["piecesNotShown"] = region_more
            union = (min(b[0] for b in region), max(b[1] for b in region), min(b[2] for b in region),
                     max(b[3] for b in region), min(b[4] for b in region), max(b[5] for b in region))
            out["againstBefore"] = against_rec(union, old_box)
            if cut:
                if faces_more:
                    out["opensNotLooked"] = faces_more
                if not looked:
                    out["opensLooked"] = False
            else:
                got = touch_rec(faces or [], faces_more, gap, touching)
                if got:
                    out["touches"] = got
    if profiles:
        out.update(profiles)
    if solids is not None and solids_was is not None:
        out["solidsWas"] = solids_was
    return out


def dressup_result(n_edges, size=None, edges=None, solids=None, solids_was=None, changed=None):
    """The result record of a fillet or a chamfer: edgesGiven (what FreeCAD
    was given), edgesChanged (a measured count, or None when not measured:
    an edge counts when its mid-point is not on the body's surface after the
    feature), the size read from the feature (size, size2, angle: mm and
    degrees), edgesNotShown (when the answer's `on` lists fewer edges than
    were given), solidsWas. The edge records are the answer's `on`: they are
    not said again."""
    out = {"edgesGiven": n_edges}
    if changed is not None:
        out["edgesChanged"] = changed
    out.update(size or {})
    if edges and n_edges > len(edges):
        out["edgesNotShown"] = n_edges - len(edges)
    if solids is not None and solids_was is not None:
        out["solidsWas"] = solids_was
    return out


# ---- the sketch frame ------------------------------------------------------------------------
# A frame is (origin, x axis, y axis, normal): four world 3-tuples.

def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def box_corners(box):
    return [(x, y, z) for x in box[0:2] for y in box[2:4] for z in box[4:6]]


def frame_ranges(frame, box):
    """A world box in the sketch's own frame: ((xmin, xmax), (ymin, ymax),
    (nmin, nmax)), n along the normal from the sketch plane: from the eight
    corners of the box."""
    o, xa, ya, na = frame
    pts = [tuple(c[i] - o[i] for i in range(3)) for c in box_corners(box)]
    out = []
    for ax in (xa, ya, na):
        v = [_dot(p, ax) for p in pts]
        out.append((min(v), max(v)))
    return tuple(out)


def world_box(frame, xr, yr):
    """The world box of the rectangle xr by yr (sketch x and y ranges) in the
    sketch plane: (xmin, xmax, ymin, ymax, zmin, zmax)."""
    o, xa, ya, _na = frame
    pts = [tuple(o[i] + x * xa[i] + y * ya[i] for i in range(3)) for x in xr for y in yr]
    return tuple(v for i in range(3) for v in (min(p[i] for p in pts), max(p[i] for p in pts)))


def extent_rec(xr, yr):
    """The sketch's x and y ranges as { x: [min, max], y: [min, max] } (mm)."""
    return {"x": range_rec(xr), "y": range_rec(yr)}


# ---- RL-SA: sketch_add -----------------------------------------------------------------------

def pt_rec(p):
    return [n2(p[0]), n2(p[1])]


def shape_rec(xr=None, yr=None, world=None, circle=None, arc=None, line=None):
    """One shape of a sketch_add call, as a record of what was measured:
    circle { center, radius }, arc { start, middle, end } (the middle point
    is the point halfway along the arc: it shows the side the arc bulges
    to), line { from, to }, sketchExtent { x, y } and worldBox (mm). circle:
    (centre, radius); arc: (start, middle, end); line: (start, end). The
    ids, the kind and the inputs that were not given are the answer's added."""
    out = {}
    if circle is not None:
        out["circle"] = {"center": pt_rec(circle[0]), "radius": n2(circle[1])}
    if arc is not None:
        out["arc"] = {"start": pt_rec(arc[0]), "middle": pt_rec(arc[1]), "end": pt_rec(arc[2])}
    if line is not None:
        out["line"] = {"from": pt_rec(line[0]), "to": pt_rec(line[1])}
    if xr is not None and yr is not None:
        out["sketchExtent"] = extent_rec(xr, yr)
    if world is not None:
        out["worldBox"] = box_rec(world)
    return out


def sketch_add_result(shapes, open_ends=None, lies=()):
    """The result record of sketch_add: shapes (shape_rec for each added
    item, in the order of the answer's added), lies (lies_rec of the call's
    shapes against the sketch's face and the body), openEnds (the sketch's
    open ends; wires and closedWires are the answer's state)."""
    out = {"shapes": list(shapes)}
    if lies:
        out["lies"] = [x for x in lies if x]
    if open_ends is not None:
        out["openEnds"] = open_ends
    return out


# ---- RL-SC: sketch_constrain -----------------------------------------------------------------

def constraint_result(constraints, dof_before=None, moves=(), spans=None, more=0):
    """The result record of sketch_constrain. constraints: describe_con's
    records { id, type, refs, … } of the constraints added; dof_before:
    FreeCAD's degrees of freedom before (the answer's state has them after);
    moves: [{ join: [[geo, vertex], [geo, vertex]], moved: [{ ref: [geo,
    vertex], mm }] }] for each join that moved geometry (the points that
    moved only; no lower limit but MOVE_TOL); spans: ((xmin, xmax), (ymin,
    ymax)) of the sketch's shapes after the solve, or None; more: joins not
    shown (a cap)."""
    out = {"constraints": list(constraints)}
    if dof_before is not None:
        out["dofBefore"] = dof_before
    if moves:
        out["moved"] = list(moves)
    if more:
        out["joinsNotShown"] = more
    if spans is not None:
        out["sketchExtent"] = extent_rec(*spans)
    return out


# ---- RL-BC: body_check -----------------------------------------------------------------------

def body_check_result(gap=None):
    """The result record of body_check: what its other keys (valid, closed,
    solids, volume, bounds, checkGeometry) do not have: for several solids,
    the least distance between two of them (mm) and whether two touch
    (FreeCAD's confusion tolerance, 1e-7 mm). {} for one solid."""
    if gap is None:
        return {}
    return {"nearestGap": n2(gap), "solidsTouch": gap <= 1e-7}


# ---- fast ------------------------------------------------------------------------------------

def fast_steps(rows):
    """One record for each call of a fast block that ran and has a result of
    its own, in order (the records of session_state's steps,
    protocol.step_line: { call, tool, object, volumeChange, historyStep …
    }): rows is [(step, tool, the call's answer)]. A call whose answer has
    no result (a read) has no record: the block's answer stays short."""
    from .protocol import step_line

    out = []
    for step, tool, answer in rows:
        r = answer.get("result") if isinstance(answer, dict) else None
        if r:
            out.append(step_line(step, tool, answer))
    return out
