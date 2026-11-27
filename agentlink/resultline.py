# SPDX-License-Identifier: LGPL-2.1-or-later
"""The result line: the first field of a tool's answer (plain Python).

Every answer of a tool that changes the model starts with `result`: one
short text, made by code from numbers that were measured, by the same rule
for every part and every feature. A reader who cannot see the model must be
able to picture it from this line.

The rules (owner, 27 Nov):
  - A fixed sentence pattern for each fact. No shape word, no verdict, no
    guess. Where a number was not measured, the sentence is left out.
  - Numbers in mm, rounded to 2 places. World axes are X, Y and Z.
  - The only tolerance is the equality tolerance TOL that the answers
    already used (beyond_sides, added_sentence): 1e-3 mm.
  - A cap that hides items says how many are not shown.
  - A box against another box uses one set of words everywhere (against):
    "past -x by 5", "inside (10 from -x, 20 from +x)". World axes.

This module has only small pure functions: they take measured numbers and
return a sentence. The code that measures (families/pd_common.py,
families/sketch.py, tools.py) calls them. Tests: tests/test_result_line_1127.py.
"""

TOL = 1e-3  # mm: two numbers this near are equal (the tolerance of beyond_sides)

# What a tool did when the volume change is not known; the sign of a measured
# volume change decides the words otherwise (feature_head).
TOOL_PHRASE = {
    "pd_pad": "added material", "pd_revolution": "added material",
    "pd_pocket": "removed material", "pd_hole": "removed material", "pd_groove": "removed material",
}
# Dress-ups name their edges: the verb is the tool's, whatever the sign.
EDGE_VERB = {"pd_fillet": "rounded", "pd_chamfer": "bevelled"}


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


def and_(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---- RL-F: a solid feature -------------------------------------------------------------------

def feature_head(label, tool, delta):
    """The tool's verb and the signed volume change: "Pad added material,
    volume change +6000 mm³." The sign of a measured change decides the
    words; the tool's own words are used when there is none."""
    if delta is None:
        return f"{label} {TOOL_PHRASE.get(tool, 'changed the body')}."
    if abs(delta) <= 1e-2:  # FreeCAD's volume noise, as settle reads it
        return f"{label} left the volume as it was."
    word = "added" if delta > 0 else "removed"
    return f"{label} {word} material, volume change {signed(delta)} mm³."


def against(new, old, tol=TOL, axes=(0, 1, 2)):
    """The new box against the old box on each axis: "x inside (10 from -x,
    20 from +x); y past +y by 5; z past -z by 20 and past +z by 15". Boxes
    as (xmin, xmax, ymin, ymax, zmin, zmax). Every axis of axes is said. An
    axis that is inside says the measured distance to each side of the old
    box (27 Nov QA: "x inside" did not say where along x)."""
    out = []
    for i in axes:
        ax = "xyz"[i]
        parts = []
        if new[2 * i] < old[2 * i] - tol:
            parts.append(f"past -{ax} by {num(old[2 * i] - new[2 * i])}")
        if new[2 * i + 1] > old[2 * i + 1] + tol:
            parts.append(f"past +{ax} by {num(new[2 * i + 1] - old[2 * i + 1])}")
        if parts:
            out.append(f"{ax} {' and '.join(parts)}")
        else:
            lo, hi = max(new[2 * i] - old[2 * i], 0.0), max(old[2 * i + 1] - new[2 * i + 1], 0.0)
            out.append(f"{ax} inside ({num(lo)} from -{ax}, {num(hi)} from +{ax})")
    return "; ".join(out)


def lies_text(name, new, old, flat=False):
    """Where a box lies against a named box: "Against the body (x 0..60, y
    0..30, z 0..5): x past -x by 2.5; y inside (5 from -y, 10 from +y); z
    inside (5 from -z, 0 from +z)." The old box is said, so the reader has
    what was compared. flat: the old box is a flat face's; an axis along
    which it has no size (within TOL) is left out."""
    axes = [i for i in range(3) if not (flat and abs(old[2 * i + 1] - old[2 * i]) <= TOL)]
    if not axes:
        return ""
    return f"Against {name} ({box_text(old)}): {against(new, old, axes=axes)}."


def profiles_text(n, looked, part, none, cut=True):
    """The profiles of a feature's sketch that did not do all that their
    area gives: "2 of 2 profiles cut in part (75% and 25% of the volume that
    each area gives over the same depth)." "1 of 2 profiles cut nothing."
    part: the measured shares (percent) of those that did a part; none: how
    many did nothing; looked: how many of the n profiles were measured. ""
    when every measured profile did all of it."""
    verb, zero = ("cut", "cut nothing") if cut else ("added", "added nothing")
    of = f"of {n} profile{'' if n == 1 else 's'}"
    out = []
    if part:
        shares = and_([f"{float(p):.4g}%" for p in part])
        each = "its area gives" if len(part) == 1 else "each area gives"
        out.append(f"{len(part)} {of} {verb} in part ({shares} of the volume that {each} over the same depth).")
    if none:
        out.append(f"{none} {of} {zero}.")
    if out and looked < n:
        out.append(f"{looked} {of} were measured.")
    return " ".join(out)


def body_change_text(body, vol0, vol1, box0=None, box1=None, solids0=None, solids1=None):
    """What one call changed of a body, from its volume, box and solids
    before and after: "This call changed Body: volume change -196.35 mm³,
    now 14053.65 mm³." or "This call left the volume of Body as it was
    (14250 mm³)." Then the two boxes when they differ, and the solids when
    their count differs."""
    delta = vol1 - vol0
    if abs(delta) <= 1e-2:  # FreeCAD's volume noise, as feature_head reads it
        out = [f"This call left the volume of {body} as it was ({num(vol1)} mm³)."]
    else:
        out = [f"This call changed {body}: volume change {signed(delta)} mm³, now {num(vol1)} mm³."]
    if box0 is not None and box1 is not None and any(abs(a - b) > TOL for a, b in zip(box0, box1)):
        out.append(f"The body before is {box_text(box0)}. The body now is {box_text(box1)}.")
    if solids0 is not None and solids1 is not None and solids0 != solids1:
        out.append(solids_text(solids1, solids0))
    return " ".join(out)


def region_text(boxes, more, cut):
    """The world box of the new or the removed material; one box for each
    separate piece, then how many pieces are not shown."""
    what = "The removed material is" if cut else "The new material is"
    if len(boxes) == 1 and not more:
        return f"{what} {box_text(boxes[0])}."
    n = len(boxes) + more
    said = "; ".join(box_text(b) for b in boxes)
    return f"{what} in {n} pieces: {said}" + (f"; {more} more not shown." if more else ".")


def touch_text(faces, more, gap, touching):
    """What the new material meets of the body before. faces: the side
    words of the body's faces it lies on ("+z at z 5"); more: faces not
    looked at (a cap); gap: the least distance to the body, mm, or None
    when not measured; touching: whether that distance is zero, or None."""
    if faces:
        tail = f" and {more} more not shown" if more else ""
        return f"It touches the body on {and_(faces)}{tail}."
    if touching is True:
        return "It touches the body but shares no face with it." + (f" {more} faces were not looked at." if more else "")
    if touching is False:
        return "It touches the body nowhere" + (f" (nearest gap {num(gap)} mm)." if gap is not None else ".")
    return ""


def opens_text(faces, more, looked=True):
    """Where a cut opens the body (the faces of the body before that the
    removed material lies on)."""
    if faces:
        tail = f" and {more} more not shown" if more else ""
        return f"It opens on {and_(faces)}{tail}."
    if not looked:
        return ""
    return "It opens on no face of the body: it is closed inside it."


def solids_text(now, was=None):
    """"The body is 2 solids (was 1)." """
    if now is None:
        return ""
    return f"The body is {plural(now, 'solid')}" + (f" (was {was})." if was is not None else ".")


def feature_result(label, tool, delta, region=None, region_more=0, old_box=None, body_box=None, cut=False,
                   faces=None, faces_more=0, gap=None, touching=None, looked=True, solids=None, solids_was=None, note="", profiles=""):
    """The result line of a solid feature, in the fixed order:
    1 verb and volume change; 2 the box of the new or removed material (for
    the first feature, the body's box); 3 the body's box before; 4 the
    region against it on x, y, z; 5 contact (a cut: where it opens);
    6 solids now and before. region: a list of boxes (one for each piece);
    old_box None: there was no body before. note: a fact that was not
    measured and why, said as it came. profiles: profiles_text's words
    (a profile that did a part, or nothing), said after 5."""
    out = [feature_head(label, tool, delta)]
    if region and old_box is not None:
        out.append(region_text(region, region_more, cut))
        out.append(f"The body before is {box_text(old_box)}.")
        union = (min(b[0] for b in region), max(b[1] for b in region), min(b[2] for b in region),
                 max(b[3] for b in region), min(b[4] for b in region), max(b[5] for b in region))
        out.append(f"Against the body before: {against(union, old_box)}.")
        out.append(opens_text(faces or [], faces_more, looked) if cut else touch_text(faces or [], faces_more, gap, touching))
    elif old_box is None and body_box is not None:
        if solids is not None:
            return " ".join([out[0], f"The body is {plural(solids, 'solid')}, {box_text(body_box)}."])
        out.append(f"The body is {box_text(body_box)}.")
    elif old_box is not None:
        out.append(f"The body before is {box_text(old_box)}.")
        if body_box is not None:
            out.append(f"The body now is {box_text(body_box)}.")
    if profiles:
        out.append(profiles)
    if note:
        out.append(note)
    out.append(solids_text(solids, solids_was))
    return " ".join(t for t in out if t)


def dressup_result(label, tool, delta, n_edges, size_words, edge_lines, solids=None, solids_was=None):
    """The result line of a fillet or a chamfer: the edge words that the
    answer already had, and the radius or size read from the feature."""
    verb = EDGE_VERB.get(tool, "changed")
    head = f"{label} {verb} {plural(n_edges, 'edge')}"
    if size_words:
        head += f", {size_words}"
    head += f", volume change {signed(delta)} mm³." if delta is not None else "."
    out = [head]
    if edge_lines:
        out.append("Edges: " + "; ".join(edge_lines) + ".")
    out.append(solids_text(solids, solids_was))
    return " ".join(t for t in out if t)


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


def sketch_ranges_text(xr, yr):
    return f"x {span(*xr)}, y {span(*yr)}"


# ---- RL-SN: sketch_new -----------------------------------------------------------------------

def sketch_new_result(label, support, axes, body=None, face=None):
    """"Sketch Base is on XY. x runs +X; … The body spans sketch x -40..40,
    y -30..30, and along the normal 0..10." support: where it is (plane
    name or face words); axes: orient.axes_line's words; body: ((xmin, xmax),
    (ymin, ymax), (nmin, nmax)) in the sketch frame or None; face: the
    same for the face the sketch is on (its x and y are said)."""
    out = [f"Sketch {label} is on {support}.", axes]
    if body is not None:
        out.append(f"The body spans sketch x {span(*body[0])}, y {span(*body[1])}, and along the normal {span(*body[2])}"
                   " (0 is the sketch plane; + is the way the normal points).")
    else:
        out.append("The body has no solid yet.")
    if face is not None:
        out.append(f"The face spans sketch x {span(*face[0])}, y {span(*face[1])}.")
    return " ".join(out)


# ---- RL-SA: sketch_add -----------------------------------------------------------------------

def id_text(ids):
    """"ids 0-3", "id 4", "ids 0, 2 and 5": runs of three or more joined with a dash."""
    ids = sorted(int(i) for i in ids)
    if not ids:
        return "no ids"
    runs, start = [], 0
    for k in range(1, len(ids) + 1):
        if k == len(ids) or ids[k] != ids[k - 1] + 1:
            runs.append(ids[start:k])
            start = k
    words = []
    for r in runs:
        words += [f"{r[0]}-{r[-1]}"] if len(r) >= 3 else [str(i) for i in r]
    return ("id " if len(ids) == 1 else "ids ") + and_(words)


def pt(p):
    return f"({num(p[0])}, {num(p[1])})"


def default_text(default):
    """"center not given, so center is [0, 0]": an input that places the
    shape, which the call did not give, and the value the tool used."""
    return "; ".join(f"{k} not given, so {k} is [{', '.join(num(c) for c in v)}]" for k, v in (default or {}).items())


def shape_text(kind, ids, xr=None, yr=None, world=None, circle=None, arc=None, line=None, default=None):
    """One shape of a sketch_add call: "rectangle, ids 0-3: sketch x 0..30,
    y 5..45; world x -30..0, y 30, z 5..45." circle: (centre, radius); arc:
    (start, middle, end); line: (start, end). The middle point of an arc is
    the point halfway along it: it shows the side the arc bulges to.
    default: {input: value} of a place that the call did not give (said
    first)."""
    head = f"{kind}, {id_text(ids)}"
    facts = []
    if default:
        facts.append(default_text(default))
    if circle is not None:
        facts.append(f"centre {pt(circle[0])}, radius {num(circle[1])}")
    if arc is not None:
        facts.append(f"start {pt(arc[0])}, middle {pt(arc[1])}, end {pt(arc[2])}")
    if line is not None:
        facts.append(f"from {pt(line[0])} to {pt(line[1])}")
    if xr is not None and yr is not None:
        facts.append(f"sketch {sketch_ranges_text(xr, yr)}")
    if world is not None:
        facts.append(f"world {box_text(world)}")
    return head + (": " + "; ".join(facts) if facts else "") + "."


def wires_text(wires, closed, open_ends):
    """"The sketch has 1 wire, 1 closed, 0 open ends." Any count may be None."""
    parts = []
    if wires is not None:
        parts.append(plural(wires, "wire"))
    if closed is not None:
        parts.append(f"{closed} closed")
    if open_ends is not None:
        parts.append(plural(open_ends, "open end"))
    return "The sketch has " + ", ".join(parts) + "." if parts else ""


def sketch_add_result(shapes, wires=None, closed=None, open_ends=None, lies=()):
    """The result line of sketch_add: its shapes (shape_text), where the
    call's shapes lie against the sketch's face and the body (lies_text's
    sentences), then the wires."""
    return " ".join(t for t in [*shapes, *lies, wires_text(wires, closed, open_ends)] if t)


# ---- RL-SC: sketch_constrain -----------------------------------------------------------------

def moves_text(moves, more=0):
    """Each join that moved geometry, with the distance each of its points
    moved (mm): moves is [(words of the join, [(words of a point, mm), …])]
    with the points that moved only. No lower limit but TOL."""
    out = [f"The join of {join} moved " + " and ".join(f"{p} by {num(d)} mm" for p, d in pts) + "." for join, pts in moves]
    if more:
        out.append(f"{more} more joins not shown.")
    return " ".join(out)


def constraint_result(added, dof_before, dof_after, moves=(), spans=None, more=0):
    """The result line of sketch_constrain. added: the constraints in words
    (con_words); dof_before and dof_after: FreeCAD's degrees of freedom or
    None; moves: moves_text's; spans: ((xmin, xmax), (ymin, ymax)) of the
    sketch's shapes after the solve, or None; more: joins not shown (a cap)."""
    out = [f"Added {and_(added)}." if added else "Added no constraint."]
    if dof_before is not None and dof_after is not None:
        out.append(f"Degrees of freedom: {dof_before} before, {dof_after} after.")
    elif dof_after is not None:
        out.append(f"Degrees of freedom after: {dof_after}.")
    m = moves_text(moves, more)
    if m:
        out.append(m)
    if spans is not None:
        out.append(f"After the solve the sketch's shapes span sketch {sketch_ranges_text(*spans)}.")
    return " ".join(out)


# ---- RL-BC: body_check -----------------------------------------------------------------------

def body_check_result(label, solids, solids_said=None, valid=None, closed=None, box=None, volume=None):
    """The result line of body_check: "Body is 2 separate solids that do not
    touch (nearest gap 12.5 mm); valid, closed; box x 0..60, y …; volume 9000
    mm³." solids_said: the words that say whether the solids touch (given
    when there are several)."""
    first = solids_said if solids_said else (plural(solids, "solid") if solids is not None else None)
    parts = []
    if first:
        parts.append(first)
    flags = []
    if valid is not None:
        flags.append("valid" if valid else "not valid")
    if closed is not None:
        flags.append("closed" if closed else "not closed")
    if flags:
        parts.append(", ".join(flags))
    if box is not None:
        parts.append(f"box {box_text(box)}")
    if volume is not None:
        parts.append(f"volume {num(volume)} mm³")
    return f"{label} is " + "; ".join(parts) + "." if parts else f"{label} was read."


# ---- fast ------------------------------------------------------------------------------------

def fast_lines(rows):
    """The result lines of a fast block's calls, in order: rows is [(step,
    tool, the call's answer)]; a call whose answer has no result string has
    no line."""
    out = []
    for step, tool, answer in rows:
        r = answer.get("result") if isinstance(answer, dict) else None
        if isinstance(r, str) and r:
            out.append(f"{step} {tool}: {r}")
    return out
