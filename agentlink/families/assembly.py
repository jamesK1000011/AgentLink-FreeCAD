# SPDX-License-Identifier: LGPL-2.1-or-later
# Assemblies with FreeCAD's own Assembly workbench (the Ondsel solver): the
# parts put in an assembly, one held fixed, joints between their faces and
# edges — fixed, revolute, cylindrical, slider, ball, distance, parallel,
# perpendicular, angle — solved, and the result checked: where each part
# went, how many ways it can still move, and whether any two parts overlap.
# Faces and edges are picked by what they are (shape_query's queries), so a
# joint does not depend on FreeCAD's numbering.

import json
import math
import re
import time

import FreeCAD
import Part

import JointObject  # FreeCAD's Assembly workbench
import UtilsAssembly  # noqa: F401  — the joints' own helpers load through it

from .. import geometry as geo
from .. import runners
from ..protocol import ToolError
from . import measure as M
from . import picks

GROUP = "assembly"
INFO = "Assemblies (FreeCAD's Assembly workbench): parts put together, one grounded, joints between faces and edges solved; positions, freedom left and overlaps checked."

V = FreeCAD.Vector
KINDS = {k.lower(): k for k in JointObject.JointTypes}


def _view_provider(obj, kind):
    """FreeCAD's own view provider for a joint made from here, as its
    commands give one: without it a joint saved in the window comes back with
    no proxy, and every recompute after reopening fails ("'int' object has no
    attribute 'redrawJointPlacements'")."""
    if not getattr(FreeCAD, "GuiUp", False) or getattr(obj, "ViewObject", None) is None:
        return
    try:
        vo = obj.ViewObject
        if kind == "grounded":
            JointObject.ViewProviderGroundedJoint(vo)
        else:
            JointObject.ViewProviderJoint(vo)
        # Setting the proxy on an object that already has its view does not
        # run attach (it builds the joint's coordinate-system nodes,
        # switch_JCS1 …): run it here, as FreeCAD does for a new object.
        px = getattr(vo, "Proxy", None)
        if px is not None and hasattr(px, "attach") and not hasattr(px, "switch_JCS1") and kind != "grounded":
            px.attach(vo)
    except Exception:
        pass
# Joints between two elements; gears, belts and the like need more than this
# family asks for yet.
OFFERED = ["fixed", "revolute", "cylindrical", "slider", "ball", "distance", "parallel", "perpendicular", "angle"]
# the motion couplings, where this FreeCAD has them
OFFERED += [k for k in ("rackpinion", "screw", "gears", "belt") if k in KINDS]
# A chain is FreeCAD's belt joint, its ratio set by the sprockets' teeth.
if "belt" in KINDS:
    KINDS["chain"] = KINDS["belt"]
    OFFERED.append("chain")
# AssemblyObject.solve()'s codes as its own notes list them. FreeCAD 1.1's
# solve returns only three of them (AssemblyObject.cpp): 0, -1 (the solver
# threw) and -6 (nothing grounded); it does not count freedom left, and a
# joint that repeats another is dropped by the solver without a word. The
# others are kept for a release that returns them.
SOLVE = {0: "solved", -1: "solver error", -2: "redundant constraints", -3: "conflicting constraints", -4: "over-constrained", -5: "malformed constraints", -6: "no part is grounded"}
# The kinds FreeCAD's own joint panel offers Reverse for.
REVERSIBLE = {k.lower() for k in getattr(JointObject, "JointUsingReverse", ["Fixed", "Revolute", "Cylindrical", "Slider", "Distance", "Parallel"])}
LINKS = ("App::Link", "App::LinkElement")


def _typed(asm):
    """The assembly marked as one, as FreeCAD's Create Assembly does
    (assembly.Type = "Assembly"). JointObject reads it: without it a new
    joint always moves its second part, grounded or not, and never takes
    along the parts already joined to the one it moves."""
    try:
        if getattr(asm, "Type", None) != "Assembly" and asm.TypeId == "Assembly::AssemblyObject":
            asm.Type = "Assembly"
    except Exception:
        pass
    return asm


def _shape(o):
    """A part's shape where it stands. A link answers Shape with its
    target's own (App::Link hands on the linked object's properties), which
    leaves the link's placement out: Part.getShape places it."""
    if isinstance(o, _LinkPart):
        return o.Shape
    if getattr(o, "TypeId", "") in LINKS:
        return Part.getShape(o)
    return o.Shape


def _release():
    v = FreeCAD.Version()
    try:
        return int(v[0]), int(v[1])
    except (ValueError, IndexError):
        return (1, 1)


def _assemblies(doc):
    return [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"]


def _assembly(doc, ref):
    return picks.one_of(_assemblies(doc), ref, "assembly: say which — {labels}.", "assembly {ref}: the assemblies are {labels}.",
                        none="No assembly in the document: asm_new { parts } makes one.", nocase=True)


def _joints(asm):
    g = next((o for o in asm.Group if o.TypeId == "Assembly::JointGroup"), None)
    if g is None:
        g = asm.newObject("Assembly::JointGroup", "Joints")
    # Joints made before their view provider was set (or by another tool
    # without one) get FreeCAD's own, so the window's recompute works again.
    for j in getattr(g, "Group", []):
        vo = getattr(j, "ViewObject", None)
        if vo is not None and getattr(FreeCAD, "GuiUp", False) and not hasattr(getattr(vo, "Proxy", None), "switch_JCS1") and hasattr(j, "JointType"):
            _view_provider(j, "joint")
        elif vo is not None and getattr(FreeCAD, "GuiUp", False) and getattr(vo, "Proxy", None) in (None, 0) and hasattr(j, "ObjectToGround"):
            _view_provider(j, "grounded")
    return g


def _parts(asm):
    return [o for o in asm.Group if o.TypeId != "Assembly::JointGroup" and hasattr(o, "Shape") and not o.Shape.isNull()]


class _LinkPart:
    """A part an assembly holds through an App::Link (or a link's element),
    or inside a moved App::Part or sub-assembly: its shape as placed, for
    the overlap check. Label and Name as the object's own; obj the object
    itself."""

    def __init__(self, link, shape, frame=None):
        self.obj = link
        self.Label, self.Name = link.Label, link.Name
        self.Shape = shape
        self.Placement = getattr(link, "Placement", FreeCAD.Placement())
        if frame is not None:
            # inside a moved container: where it stands in the assembly
            self.Placement = frame.multiply(self.Placement)

    def getLinkedObject(self, *a):
        try:
            return self.obj.getLinkedObject(*a)
        except Exception:
            return self.obj


def _check_parts(asm):
    """Every part of an assembly for asm_check, shown or not: its own parts,
    those inside App::Parts and sub-assemblies, and those held through
    links (their shape as placed). (parts, hidden labels, left out labels).
    A part hidden in the window is still a part: a check that skipped
    hidden parts passed with a screw and the body it sits in left out."""
    out, hidden, left, seen = [], [], [], set()

    def walk(group, frame):
        # frame: where the container holding these stands in the assembly
        # (None at the assembly's own level); a part inside a moved App::Part
        # or sub-assembly keeps its shape in that container's own frame.
        for o in group or []:
            if o.Name in seen or o.TypeId == "Assembly::JointGroup":
                continue
            seen.add(o.Name)
            if o.TypeId in ("App::Part", "Assembly::AssemblyObject", "Assembly::AssemblyLink"):
                own = getattr(o, "Placement", None)
                inner = frame if own is None or own.isIdentity() else (own if frame is None else frame.multiply(own))
                walk(getattr(o, "Group", None), inner)
                continue
            if o.TypeId == "App::DocumentObjectGroup":
                walk(getattr(o, "Group", None), frame)
                continue
            part, sh = None, None
            try:
                # a link first: its Shape property is its target's, not placed
                sh = Part.getShape(o) if o.TypeId in LINKS else getattr(o, "Shape", None)
                if sh is not None and not sh.isNull() and sh.Solids:
                    if frame is not None:
                        sh = sh.copy()
                        sh.Placement = frame.multiply(sh.Placement)
                    part = _LinkPart(o, sh, frame) if (frame is not None or o.TypeId in LINKS) else o
            except Exception:
                part = None
            if part is None:
                if sh is not None or o.TypeId.startswith("App::Link"):
                    left.append(o.Label)
                continue
            if getattr(o, "Visibility", True) is False:
                hidden.append(o.Label)
            out.append(part)

    walk(asm.Group, None)
    return out, hidden, left


def ref_element(doc, r):
    """A joint reference's part and element, either form: [asm,
    ["Part.Face6", …]] (1.0) or [part, ["Face6", …]]."""
    if not r:
        return None, None, None
    o, subs = r[0], (r[1] if len(r) > 1 else [])
    sub = subs[0] if subs else ""
    path = sub.split(".")
    part = o
    if o.TypeId == "Assembly::AssemblyObject" and len(path) > 1:
        part = doc.getObject(path[0])
    name = path[-1]
    if not name and len(path) > 1 and part is not None:
        # a datum end ("LCS."): its frame where it stands now
        d = datum_end(part, ".".join(path[1:]) if part is not o else sub)
        return part, d, sub
    try:
        return part, part.Shape.getElement(name), name
    except Exception:
        return part, None, name


def _stem(label):
    """A label without the counter a workbench adds as it relabels
    ("M8x25-Screw219" -> "m8x25-screw")."""
    import re

    return re.sub(r"[\s_-]*\d+$", "", str(label)).lower()


def _part(asm, ref):
    parts = _parts(asm)
    for o in parts:
        if ref in (o.Label, o.Name) or str(ref).lower() == o.Label.lower():
            return o
    # A label a workbench has since counted up (Fasteners relabels its
    # screws on each recompute): the one part whose label differs only by
    # that counter.
    near = [o for o in parts if _stem(o.Label) == _stem(ref)]
    if len(near) == 1:
        return near[0]
    if len(near) > 1:
        raise ToolError("invalid_input", f"part {ref!r}: {len(near)} parts of {asm.Label} carry that label with another number ({', '.join(f'{o.Label} (object {o.Name})' for o in near)}) — name one by its object name, which stays the same when a workbench relabels it.")
    raise ToolError("not_found", f"part {ref!r} is not in {asm.Label}: its parts are {', '.join(o.Label for o in _parts(asm)) or 'none'} (asm_add puts one in).")


def _grounded(asm):
    out = []
    for j in _joints(asm).Group:
        g = getattr(j, "ObjectToGround", None)
        if g is not None:
            out.append(g)
    return out


def _placement(o):
    p = o.Placement
    axis, ang = p.Rotation.Axis, p.Rotation.Angle
    return {"at": geo.vec(p.Base), "axis": geo.vec(axis), "angle": round(ang * 180 / 3.141592653589793, 4)}


def _element(session, part, q, what):
    """One face or edge of a part: its name ("Face6", "Edge3") or a query as
    shape_query takes it ({ kind, normal, near, radius, type, … }); with
    several matching, near picks the closest. A datum inside the part (an
    LCS, a datum plane, line or point: by name or label, or { datum }) is
    its sub-name, "LCS." (datum_sub)."""
    if isinstance(q, dict) and q.get("datum") is not None:
        return datum_sub(part, q["datum"], what)
    if isinstance(q, str):
        if not _ELEMENT_NAME.match(q):
            return datum_sub(part, q, what)
        try:
            part.Shape.getElement(q)
        except Exception:
            raise ToolError("invalid_input", f"{what}: {part.Label} has no {q} — shape_query {{ body: \"{part.Label}\" }} lists its faces and edges, or give a query {{ kind: face|edge, normal, near, radius, type }} here.")
        return q
    if not isinstance(q, dict):
        raise ToolError("invalid_input", f"{what}: a face or edge — \"Face6\", or a query {{ kind: face|edge, normal, near, radius, type }} as shape_query takes.")
    query = query_of(part, q, what)
    query["body"] = part.Name  # by Name: a label can change on recompute
    _, _, hits = M.query(session, query)
    if not hits:
        raise ToolError("not_found", f"{what}: no {query.get('kind', 'face')} of {part.Label} matches {q} — shape_query {{ body: \"{part.Label}\" }} lists them.")
    if len(hits) > 1:
        near = query.get("near")
        if near is None:
            names = ", ".join(d.get("ref", "?") for _, _, d in hits[:8])
            raise ToolError("invalid_input", f"{what}: {len(hits)} match ({names}{' …' if len(hits) > 8 else ''}) — narrow it, or add near: [x, y, z] to take the closest.")
        p = picks.vec3(near if isinstance(near, list) else near.get("point"), "near")
        hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(p))[0])
    return hits[0][2]["ref"]


def query_of(part, q, what):
    """An element query as M.query takes it, from asm_joint's a or b: part
    and nearLocal taken out, nearLocal turned into near in the document's
    coordinates (where the part is now). No body."""
    query = {k: v for k, v in q.items() if k not in ("part", "nearLocal", "body")}
    if q.get("nearLocal") is not None:
        # Test drive of 20 Nov, finding 3: near is in the document's coordinates,
        # where the part is now; a point read off the part as modelled (its
        # own frame) picked the wrong hole once an earlier joint had moved it.
        if q.get("near") is not None:
            raise ToolError("invalid_input", f"{what}: near or nearLocal, not both — near is in document coordinates, nearLocal in the part's own frame.")
        query["near"] = geo.vec(local_to_world(part, picks.vec3(q["nearLocal"], "nearLocal")))
    return query


def local_to_world(part, p):
    """A point given in the part's own frame (as it was modelled) in the
    document's coordinates: through the placement its shape has now."""
    try:
        pl = _shape(part).Placement
    except Exception:  # noqa: BLE001
        pl = part.Placement
    v = V(*p) if not hasattr(p, "x") else p
    if hasattr(pl, "multVec"):
        return pl.multVec(v)
    return pl.Base + pl.Rotation.multVec(v)


def element_centre(part, el):
    """Where a joint element is now, in the document's coordinates: a
    round edge's or face's centre on its axis, a flat face's middle, else
    its centre of mass. [x, y, z], or None."""
    if is_datum_sub(el):
        d = datum_end(part, el)
        return geo.vec(d["Placement"].Base) if d is not None else None
    try:
        g = _shape(part).getElement(el)
        ax = joint_axis(g)
        return geo.vec(ax[0] if ax else g.CenterOfMass)
    except Exception:  # noqa: BLE001 - an element this cannot read: not said
        return None


def outward(part, el):
    """(point, outward unit normal) of a joint element in the document's
    coordinates, or None: a flat face's middle and the normal that points
    out of the part; a round edge's centre and the outward normal of the
    flat face it bounds (a hole's rim on a flat face). A round face, a
    straight edge or a free edge has no outward side here."""
    try:
        return _outward(part, el)
    except Exception:  # noqa: BLE001 - an element this cannot read: no gap
        return None


def _outward(part, el):
    try:
        shape = _shape(part)
        g = shape.getElement(el)
    except Exception:  # noqa: BLE001
        return None
    face = None
    if isinstance(g, Part.Face) and isinstance(g.Surface, Part.Plane):
        face, at = g, None
    elif isinstance(g, Part.Edge) and hasattr(g.Curve, "Axis"):
        axis = unit(g.Curve.Axis)
        try:
            near = shape.ancestorsOfType(g, Part.Face)
        except Exception:  # noqa: BLE001
            near = []
        flat = [f for f in near if isinstance(f.Surface, Part.Plane)]
        flat = [f for f in flat if abs(unit(_face_normal(f)).dot(axis)) > 0.999]
        if not flat:
            return None
        face, at = flat[0], g.Curve.Center
    if face is None:
        return None
    n = unit(_face_normal(face))
    return (face.CenterOfMass if at is None else at), n


def _face_normal(face):
    """A flat face's normal as it faces out of the solid (FreeCAD's normalAt
    follows the face's orientation)."""
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)


def joint_gap(ends):
    """The gap between the two joined elements across the joint, mm:
    positive apart, negative overlapping (one part's face inside the
    other). Measured along b's outward normal (a's when b has none), from
    where the elements are now. None when neither has an outward side."""
    (pa, ea), (pb, eb) = ends
    ob, oa = outward(pb, eb), outward(pa, ea)
    try:
        if ob is not None:
            ca = element_centre(pa, ea)
            if ca is None:
                return None
            return round(float((V(*ca) - ob[0]).dot(ob[1])), 4)
        if oa is not None:
            cb = element_centre(pb, eb)
            if cb is None:
                return None
            return round(float((V(*cb) - oa[0]).dot(oa[1])), 4)
    except Exception:  # noqa: BLE001
        return None
    return None


GAP_TOL = 1e-3


def gap_set(doc, asm, j, ends, want):
    """The joint's offset set so the gap across it is want (mm, positive
    apart), whichever way FreeCAD's offset runs for these two parts: the
    offset moved by the difference, the result measured, and the other way
    tried when it went the wrong way. (code, words, gap, offset mm)."""
    code, said = _status(asm)
    g0 = joint_gap(ends)
    if code != 0 or g0 is None:
        return code, said, g0, None
    base = float(j.Offset2.Base.z) if hasattr(j, "Offset2") else 0.0
    rot = j.Offset2.Rotation if hasattr(j, "Offset2") else FreeCAD.Rotation()
    d = float(want) - g0
    if abs(d) <= GAP_TOL:
        return code, said, g0, base
    best = (abs(g0 - want), code, said, g0, base)
    for z in (base + d, base - d):
        j.Offset2 = FreeCAD.Placement(V(0, 0, z), rot)
        doc.recompute()
        code, said = _status(asm)
        g = joint_gap(ends)
        if code == 0 and g is not None:
            if abs(g - want) <= GAP_TOL:
                return code, said, g, z
            if abs(g - want) < best[0]:
                best = (abs(g - want), code, said, g, z)
    _err, code, said, g, z = best
    j.Offset2 = FreeCAD.Placement(V(0, 0, z), rot)
    doc.recompute()
    code, said = _status(asm)
    return code, said, joint_gap(ends), z


def _status(asm):
    try:
        code = asm.solve()
    except Exception as e:
        return -1, f"solver error: {e}"
    return code, SOLVE.get(code, f"code {code}")


def _fastener_diameter(o):
    """A Fasteners Workbench screw's nominal diameter in mm (its "diameter"
    property, "M8" or "M8x1"), else None."""
    import re

    src = o
    try:
        if hasattr(o, "getLinkedObject"):
            src = o.getLinkedObject(True) or o
    except Exception:
        src = o
    for d in (getattr(src, "diameter", None), getattr(src, "Diameter", None), getattr(o, "diameter", None)):
        m = re.match(r"^\s*M(\d+(?:\.\d+)?)", d) if isinstance(d, str) else None
        if m:
            return float(m.group(1))
    # "Auto" (sized from the hole): the screw's own label carries the size
    if getattr(src, "Proxy", None) is not None and type(src.Proxy).__name__.startswith("FS"):
        m = re.search(r"\bM(\d+(?:\.\d+)?)x", src.Label) or re.search(r"\bM(\d+(?:\.\d+)?)x", o.Label)
        if m:
            return float(m.group(1))
    return None


def _thread_engagement(screw, other, common):
    """Where a screw overlaps a part only in the ring between its minor and
    nominal diameter round its own axis, it is threaded into it, as meant:
    the engagement length, else None. A screw through solid material fills
    the core too, and stays an overlap."""
    d = _fastener_diameter(screw)
    if not d:
        return None
    try:
        import Part
        pl = screw.Placement
        axis = pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        base = pl.Base - axis * 500
        outer = Part.makeCylinder(d / 2 + 0.05, 1000, base, axis)
        inner = Part.makeCylinder(0.33 * d, 1000, base, axis)  # tap drills run down to 0.75 d
        ring = outer.cut(inner)
        inside = common.common(ring).Volume
        if common.Volume <= 0 or inside / common.Volume < 0.95:
            return None
        area = 3.141592653589793 / 4 * (d ** 2 - (0.85 * d) ** 2)
        return {"screw": screw.Label, "size": f"M{d:g}", "engaged": round(common.Volume / area, 1),
                "note": "the screw's thread in a tapped hole, as meant — not counted against the verdict"}
    except Exception:
        return None


class _Late(Exception):
    """A sweep's time ran out in the middle of a step."""


def _boxes_near(ba, bb, gap=0.0):
    """Two bounding boxes within gap mm of each other; with no gap, boxes
    that only touch do not count (parts that touch do not overlap)."""
    try:
        if gap <= 0:
            return (ba.XMin < bb.XMax and bb.XMin < ba.XMax and ba.YMin < bb.YMax and bb.YMin < ba.YMax
                    and ba.ZMin < bb.ZMax and bb.ZMin < ba.ZMax)
        return (ba.XMin - gap <= bb.XMax and bb.XMin - gap <= ba.XMax and ba.YMin - gap <= bb.YMax and bb.YMin - gap <= ba.YMax
                and ba.ZMin - gap <= bb.ZMax and bb.ZMin - gap <= ba.ZMax)
    except Exception:  # noqa: BLE001 - a box that cannot be read is checked
        return True


def _face_boxes(solid):
    try:
        return [f.BoundBox for f in solid.Faces]
    except Exception:  # noqa: BLE001
        return []


def _solid_common(x, y, fx=None, fy=None):
    """(volume, common or None, a boolean made) of two solids whose boxes
    meet: the cut that asm_sweep, asm_joint and asm_check share. A solid
    whose surface stays out of the other solid's box (no face box of the
    other meets it) is all inside or all outside the other: one point test,
    no boolean. fx, fy: the solids' face boxes, when already read."""
    bx, by = x.BoundBox, y.BoundBox
    try:
        fy = _face_boxes(y) if fy is None else fy
        if fy and not any(_boxes_near(fb, bx, 1e-6) for fb in fy):
            return (x.Volume, x, False) if y.isInside(x.Vertexes[0].Point, 1e-6, True) else (0.0, None, False)
        fx = _face_boxes(x) if fx is None else fx
        if fx and not any(_boxes_near(fb, by, 1e-6) for fb in fx):
            return (y.Volume, y, False) if x.isInside(y.Vertexes[0].Point, 1e-6, True) else (0.0, None, False)
    except Exception:  # noqa: BLE001 - no point test here: the boolean decides
        pass
    c = x.common(y)
    return (c.Volume if c.Solids else 0.0), c, True


class _Prep:
    """A part's shape for one overlap pass, read once: its box, its solids,
    each solid's box, and each solid's face boxes when first needed."""

    def __init__(self, sh):
        self.shape, self.box = sh, sh.BoundBox
        try:
            self.solids = list(sh.Solids) or [sh]
        except Exception:  # noqa: BLE001
            self.solids = [sh]
        self.boxes = [x.BoundBox for x in self.solids]
        self._faces = {}

    def faces(self, i):
        if i not in self._faces:
            self._faces[i] = _face_boxes(self.solids[i])
        return self._faces[i]


def _common_volume(sa, sb, gap=0.0, stats=None, pa=None, pb=None):
    """(volume, common shape or None) of two shapes, solid by solid, and
    only the solids whose boxes meet: one boolean of two big compounds took
    most of a sweep's step (bicycle test drive of 20 Nov). A solid whose
    surface stays out of the other's box is a point test (_solid_common).
    stats: a dict that gets booleans and pointTests added."""
    pa = pa or _Prep(sa)
    pb = pb or _Prep(sb)
    vol, first = 0.0, None
    for i, x in enumerate(pa.solids):
        bx = pa.boxes[i]
        for k, y in enumerate(pb.solids):
            if not _boxes_near(bx, pb.boxes[k], gap):
                continue
            v, c, made = _solid_common(x, y, pa.faces(i), pb.faces(k))
            if stats is not None:
                key = "booleans" if made else "pointTests"
                stats[key] = stats.get(key, 0) + 1
            if v > 1e-9:
                vol += v
                if first is None:
                    first = c
    return vol, first


def _pair_hit(a, b, sa, sb, clearance, out, near, stats=None, pa=None, pb=None):
    """One pair of parts checked: an overlap row into out, or with
    clearance a row into near when the parts are closer than it."""
    try:
        vol, common = _common_volume(sa, sb, clearance, stats, pa, pb)
    except Exception:
        vol, common = 0.0, None
    if vol > 1e-3 and common is not None:
        c = common.BoundBox.Center
        row = {"parts": [a.Label, b.Label], "volume": round(vol, 3), "at": geo.vec(c)}
        eng = _thread_engagement(a, b, common) or _thread_engagement(b, a, common)
        if eng:
            row["thread"] = eng
        out.append(row)
        return
    if clearance > 0:
        d, pts, _ = sa.distToShape(sb)
        if d < clearance:
            near.append({"parts": [a.Label, b.Label], "gap": round(d, 4), "at": geo.vec(pts[0][0])})


def _overlaps(parts, clearance=0.0, deadline=None, focus=None, stats=None):
    """Pairs of parts that overlap (their common volume), and, with
    clearance, those closer than it. Each part's shape is read once; only
    pairs whose boxes meet are cut, solid by solid (_common_volume).
    focus: part names; only pairs with at least one of them are cut, and
    stats["notChecked"] counts the other pairs whose boxes meet (bicycle
    runs of 21 Nov: asm_joint cut every pair of 32 parts, 119 s). stats: a
    dict that gets pairs, booleans, pointTests (and notChecked). deadline
    (a _clock() time): _Late when it passes before every pair is cut."""
    out, near = [], []
    stats = {} if stats is None else stats
    for k in ("pairs", "booleans", "pointTests"):
        stats.setdefault(k, 0)
    if focus is not None:
        stats.setdefault("notChecked", 0)
    prep = {}

    def got(o):
        k = id(o)
        if k not in prep:
            prep[k] = _Prep(_shape(o))
        return prep[k]

    gap = max(clearance, 0.0)
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if deadline is not None and _clock() > deadline:
                raise _Late()
            pa, pb = got(a), got(b)
            if not _boxes_near(pa.box, pb.box, gap):
                continue
            if focus is not None and a.Name not in focus and b.Name not in focus:
                stats["notChecked"] += 1
                continue
            stats["pairs"] += 1
            _pair_hit(a, b, pa.shape, pb.shape, clearance, out, near, stats, pa, pb)
    return out, near


def moved_names(parts, before, tol=1e-6):
    """Names of the parts whose placement is not the one in before
    ({ name: placement }); a part not in before counts as moved."""
    out = set()
    for o in parts:
        b = before.get(o.Name)
        try:
            if b is None or not o.Placement.isSame(b, tol):
                out.add(o.Name)
        except Exception:  # noqa: BLE001
            out.add(o.Name)
    return out


def joint_overlaps(asm, ends, before):
    """asm_joint's overlaps after the solve: only pairs with a part the
    solve moved or one of the joint's two parts; a pair of two parts that
    stayed put keeps whatever overlap it had before (asm_check lists it).
    (hits without threads, stats)."""
    ps = _parts(asm)
    focus = moved_names(ps, before) | {e[0].Name for e in ends}
    stats = {}
    hits = _overlaps(ps, 0.0, None, focus, stats)[0]
    return [h for h in hits if not h.get("thread")], stats


def sweep_pairs(parts, motion, only=None, skip=None):
    """Bicycle test drive of 20 Nov (finding 1): the pairs a sweep checks.
    motion: { part name: what moves it } for the parts that move (the
    joint's group, each driven part); a pair of parts that move together
    (or stay together) keeps its overlap through the whole sweep, so it is
    not checked: only pairs with motion between them. only: labels or
    names, pairs of two of these only; skip: these in no pair.
    ([(a, b)], { "still": n, "notListed": n, "skipped": n })."""
    def named(o, names):
        return names is not None and (o.Name in names or o.Label in names)

    pairs, left = [], {"still": 0, "notListed": 0, "skipped": 0}
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if named(a, skip) or named(b, skip):
                left["skipped"] += 1
            elif only is not None and not (named(a, only) and named(b, only)):
                left["notListed"] += 1
            elif motion.get(a.Name) == motion.get(b.Name):
                left["still"] += 1
            else:
                pairs.append((a, b))
    return pairs, left


def _parallel(u, v, tol=1e-6):
    try:
        return abs(abs(u.normalize().dot(v.normalize())) - 1.0) <= tol
    except Exception:  # noqa: BLE001
        return False


def _on_axis(p, centre, axis, tol=1e-4):
    try:
        d = p - centre
        return (d - axis * d.dot(axis)).Length <= tol
    except Exception:  # noqa: BLE001
        return False


def _axisym(solid, centre, axis):
    """True when the solid stays the same shape when it turns about the axis
    through centre: each face lies on a plane across the axis, or on a
    cylinder, cone, sphere, torus or surface of revolution with this axis,
    each circle edge has this axis, and the centre of mass is on it (a
    tire, a rim, a hub of revolution). A face of any other kind (a hole off
    the axis, a tooth, a flat side) makes it False."""
    try:
        axis = FreeCAD.Vector(axis).normalize()
        if not _on_axis(solid.CenterOfMass, centre, axis, 1e-3):
            return False
        faces = solid.Faces
        if not faces:
            return False
        for f in faces:
            srf = f.Surface
            kind = type(srf).__name__
            if kind == "Plane":
                if not _parallel(srf.Axis, axis):
                    return False
            elif kind in ("Cylinder", "Cone", "Toroid"):
                if not (_parallel(srf.Axis, axis) and _on_axis(srf.Center, centre, axis)):
                    return False
            elif kind == "Sphere":
                if not _on_axis(srf.Center, centre, axis):
                    return False
            elif kind == "SurfaceOfRevolution":
                if not (_parallel(srf.Direction, axis) and _on_axis(srf.Location, centre, axis)):
                    return False
            else:
                return False
        for e in solid.Edges:
            c = getattr(e, "Curve", None)
            if type(c).__name__ == "Circle" and not (_parallel(c.Axis, axis) and _on_axis(c.Center, centre, axis)):
                return False
        return True
    except Exception:  # noqa: BLE001 - a solid that cannot be read is not taken as round
        return False


class _SweepCuts:
    """The overlap volumes of one sweep, solid by solid (bicycle runs of
    21 Nov, finding 1: 63 pair checks took about 13 s a step). Only solids
    whose boxes meet are cut. A solid pair that cannot change through the
    sweep is cut once: both solids stay put, or the moving one is round
    about its own turning axis (a tire under a calliper). A solid whose
    surface stays out of the other solid's box is all inside it or all
    outside it: one point test, no boolean. booleans counts the cuts made."""

    def __init__(self, motion, axes):
        self.motion, self.axes = motion, axes  # axes: {part name: (centre, axis)} of the parts that turn
        self.round, self.vols, self.faces = {}, {}, {}
        self.booleans = self.reused = 0

    def still(self, name, i, solid):
        if name not in self.motion:
            return True
        key = (name, i)
        if key not in self.round:
            ax = self.axes.get(name)
            self.round[key] = bool(ax) and _axisym(solid, ax[0], ax[1])
        return self.round[key]

    def face_boxes(self, name, i, solid, still):
        key = (name, i)
        if still and key in self.faces:
            return self.faces[key]
        try:
            out = [f.BoundBox for f in solid.Faces]
        except Exception:  # noqa: BLE001
            out = []
        if still:
            self.faces[key] = out
        return out

    def _cut(self, x, y, fx, fy):
        v, _c, made = _solid_common(x, y, fx, fy)
        self.booleans += 1 if made else 0
        return v

    def volume(self, a, b, sa, sb):
        try:
            la, lb = list(sa.Solids) or [sa], list(sb.Solids) or [sb]
        except Exception:  # noqa: BLE001
            la, lb = [sa], [sb]
        vol = 0.0
        for i, x in enumerate(la):
            bx = x.BoundBox
            sx = None
            for k, y in enumerate(lb):
                if not _boxes_near(bx, y.BoundBox):
                    continue
                if sx is None:
                    sx = self.still(a.Name, i, x)
                sy = self.still(b.Name, k, y)
                key = (a.Name, i, b.Name, k)
                if sx and sy and key in self.vols:
                    self.reused += 1
                    v = self.vols[key]
                else:
                    try:
                        v = self._cut(x, y, self.face_boxes(a.Name, i, x, sx), self.face_boxes(b.Name, k, y, sy))
                    except Exception:  # noqa: BLE001
                        v = 0.0
                    if sx and sy:
                        self.vols[key] = v
                vol += v if v > 1e-9 else 0.0
        return vol


def sweep_labels(asm, labels, what):
    """parts and skip of asm_sweep: each a part of the assembly (label or
    name), else refused; a set of names and labels, or None when not given."""
    if labels is None:
        return None
    if isinstance(labels, str):
        labels = [labels]
    if not isinstance(labels, (list, tuple)):
        raise ToolError("invalid_input", f"{what}: a list of part labels (asm_list names them).")
    have = _parts(asm)
    out = set()
    for x in labels:
        o = next((p for p in have if p.Label == x or p.Name == x), None)
        if o is None:
            raise ToolError("invalid_input", f"{what}: {x!r} is not a part of {asm.Label} — asm_list names them: {', '.join(sorted(p.Label for p in have)[:30])}.")
        out |= {o.Name, o.Label}
    return out


def _health(session, tool, changed):
    """The assembly solver's own status after a call of this family (the
    shared health check, agentlink/health.py): one line an assembly.
    FreeCAD 1.1's solve answers 0 (solved), -1 (the solver threw) or -6
    (nothing grounded) only; "solved" is not "fully constrained" — it does
    not count the freedom left. After any changing call, joint ends kept
    with a query are read and picked again where a face was renumbered
    (repick); the solver's line then follows too."""
    doc = getattr(session, "doc", None)
    if doc is None:
        return None
    asms = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"][:3]
    own = str(getattr(tool, "group", "")).startswith("assembly")
    out = []
    for asm in asms:
        # Any changing call can renumber a part's faces (a Part boolean):
        # the joint ends kept with a query are read, and picked again.
        try:
            picked = repick(doc, asm)
        except Exception:  # noqa: BLE001 - the health check never fails the call
            picked = []
        out += picked
        # A change to an object that a joint names (an LCS's AttachmentOffset
        # flipped, a datum moved) moves nothing joined to it until the
        # assembly solves again (bicycle runs, 20 Nov, finding 7): solved here.
        try:
            follow = joined_changed(doc, asm, changed)
        except Exception:  # noqa: BLE001 - the health check never fails the call
            follow = []
        if not own and not follow and not any(x.get("repicked") for x in picked):
            continue
        # Bicycle L5 build (21 Nov, finding 2): a joint's frames (Placement1,
        # Placement2) are made from its ends when it is made; they are made
        # again from the changed LCS here, as asm_joint does, before the solve.
        named = joints_naming(doc, asm, changed) if follow else []
        before = {o.Name: o.Placement.copy() for o in _parts(asm)} if named else {}
        for j in named:
            try:
                j.Proxy.updateJCSPlacements(j)
            except Exception:  # noqa: BLE001 - the joint keeps its frames; the check below says so
                pass
        code, words = _status(asm)
        line = f"{asm.Label}: assembly {words}"
        apart = []
        if named and code == 0:
            code, words, apart = settle_fixed(doc, asm, named, before)
            line = f"{asm.Label}: assembly {words}"
        if follow and not own:
            moved = sorted(o.Label for o in _parts(asm) if o.Name in before and not o.Placement.isSame(before[o.Name], 1e-6))
            if apart:
                line += f" again, but the fixed joint{'s' if len(apart) != 1 else ''} {', '.join(a['joint'] for a in apart)} on {', '.join(follow[:4])} did not follow: " + "; ".join(f"{a['joint']} frames {a['mm']} mm, {a['degrees']} degrees apart" for a in apart[:3])
                out.append({"line": line, "red": True, "joints": apart[:6],
                            "todo": f"asm_joint_remove {apart[0]['joint']}, then asm_joint again on the same LCS (keep: false): a new joint takes the LCS as it is now"})
                continue
            if before:
                line += f" again: the parts joined to {', '.join(follow[:4])} follow it ({'moved: ' + ', '.join(moved[:6]) if moved else 'no part moved'})"
            else:
                line += f" again: the parts joined to {', '.join(follow[:4])} follow it"
        if code == 0:
            out.append({"line": line})
        elif code == -6:
            out.append({"line": line, "red": True, "todo": "asm_ground { part } fixes one part so the solver has a frame"})
        else:
            out.append({"line": line, "red": True, "todo": "asm_list names the joints (asm_check the parts joined to nothing); asm_joint_remove the one that fights another, or history_undo"})
    return out


def joints_naming(doc, asm, changed):
    """The joints of asm (not the ground) with an end on a changed object
    that is not a part itself: an LCS or datum in a part, on either side."""
    if not changed:
        return []
    names = {o.Name for o in changed}
    parts = {o.Name for o in getattr(asm, "Group", []) if o.TypeId != "Assembly::JointGroup"} | {asm.Name}
    g = next((o for o in getattr(asm, "Group", []) if o.TypeId == "Assembly::JointGroup"), None)  # read only
    out = []
    for j in list(getattr(g, "Group", None) or []):
        if getattr(j, "ObjectToGround", None) is not None:
            continue
        hit = False
        for prop in ("Reference1", "Reference2"):
            r = getattr(j, prop, None)
            try:
                for sub in (r[1] if r and len(r) > 1 else []) or []:
                    segs = [x for x in str(sub).split(".")[:-1] if x]
                    if any(x in names and x not in parts for x in segs):
                        hit = True
            except Exception:  # noqa: BLE001
                continue
        if hit:
            out.append(j)
    return out


def jcs_global(j, prop, part):
    """A joint end's frame in the document, as FreeCAD's solver reads it:
    the part's placement, the named object in the part, then the joint's
    own PlacementN (which holds its offset)."""
    pl = getattr(j, "Placement" + prop[-1], None) or FreeCAD.Placement()
    return part.Placement.multiply(ref_in_part(j, prop, part)).multiply(pl)


FRAME_MM, FRAME_DEG = 1e-3, 1e-3


def frames_apart(j, p1, p2):
    """(mm, degrees) between the two ends' frames of a joint."""
    g1, g2 = jcs_global(j, "Reference1", p1), jcs_global(j, "Reference2", p2)
    d = g1.inverse().multiply(g2)
    return float(d.Base.Length), abs(math.degrees(float(d.Rotation.Angle)))


def settle_fixed(doc, asm, joints, before):
    """After the solve that follows a change to an LCS a joint names: each
    fixed joint's two frames must meet. Where they do not (the live miss: a
    part stayed put after its LCS was turned), the part on the moving side
    (b, or a when b is grounded) is put where they meet and the assembly
    solved again. A part the second solve does not keep there goes back.
    (code, words, [{ joint, mm, degrees }] still apart)."""
    held = {o.Name for o in _grounded(asm)}
    names = {o.Name for o in getattr(asm, "Group", []) or []}
    code, words = 0, SOLVE.get(0, "solved")
    apart, fixed = [], []
    for j in joints:
        if _kind(j) != "fixed":
            continue
        p1 = end_part(doc, getattr(j, "Reference1", None), names)
        p2 = end_part(doc, getattr(j, "Reference2", None), names)
        if p1 is None or p2 is None:
            continue
        try:
            mm, deg = frames_apart(j, p1, p2)
        except Exception:  # noqa: BLE001 - frames not readable: the solver's word stands
            continue
        if mm <= FRAME_MM and deg <= FRAME_DEG:
            continue
        if p2.Name in held and p1.Name in held:
            apart.append({"joint": j.Label, "mm": round(mm, 3), "degrees": round(deg, 3)})
            continue
        side, other, prop = (p2, p1, "Reference2") if p2.Name not in held else (p1, p2, "Reference1")
        try:
            meet = jcs_global(j, "Reference1" if prop == "Reference2" else "Reference2", other)
            own = side.Placement.inverse().multiply(jcs_global(j, prop, side))
            side.Placement = meet.multiply(own.inverse())
            fixed.append((j, p1, p2))
        except Exception:  # noqa: BLE001
            apart.append({"joint": j.Label, "mm": round(mm, 3), "degrees": round(deg, 3)})
    if fixed:
        code, words = _status(asm)
        for j, p1, p2 in fixed:
            try:
                mm, deg = frames_apart(j, p1, p2)
            except Exception:  # noqa: BLE001
                continue
            if mm > FRAME_MM or deg > FRAME_DEG:
                apart.append({"joint": j.Label, "mm": round(mm, 3), "degrees": round(deg, 3)})
        if apart or code != 0:
            _put_back(asm, before)
            code, words = _status(asm)
    return code, words, apart


def joined_names(doc, asm):
    """The names of the objects the joints of asm name: each reference's
    object and the objects in its sub-name path ("Part.LCS.", "LCS.Face1")."""
    out = set()
    g = next((o for o in getattr(asm, "Group", []) if o.TypeId == "Assembly::JointGroup"), None)  # read only
    for j in list(getattr(g, "Group", None) or []):
        if getattr(j, "ObjectToGround", None) is not None:
            continue
        for prop in ("Reference1", "Reference2"):
            r = getattr(j, prop, None)
            if not r:
                continue
            try:
                if r[0] is not None:
                    out.add(r[0].Name)
                for sub in (r[1] if len(r) > 1 else []) or []:
                    for seg in str(sub).split(".")[:-1]:
                        if seg and doc.getObject(seg) is not None:
                            out.add(seg)
            except Exception:  # noqa: BLE001
                continue
    return out


def joined_changed(doc, asm, changed):
    """Labels of the changed objects (the call's) that a joint of asm names,
    the joined parts themselves left out (their placements are the
    solver's)."""
    if not changed:
        return []
    names = joined_names(doc, asm)
    parts = {o.Name for o in getattr(asm, "Group", []) if o.TypeId != "Assembly::JointGroup"} | {asm.Name}
    return [o.Label for o in changed if o.Name in names and o.Name not in parts]


def ref_label(doc, r):
    """A joint's reference as asm_list shows it, "Part.Element": either
    form, [asm, ["Part.Face6", …]] (1.0) or [part, ["Face6", …]]; a
    reference with no element is its part's label; None for none."""
    if not r:
        return None
    o, subs = r[0], (r[1] if len(r) > 1 else [])
    if not subs:
        return o.Label
    path = subs[0].split(".")
    if not path[-1] and len(path) > 1:
        # a datum end ("LCS." or 1.0's "Part.LCS."): Part.LCS by labels
        d = doc.getObject(path[-2])
        label = d.Label if d is not None else path[-2]
        if o.TypeId == "Assembly::AssemblyObject" and len(path) > 2:
            p = doc.getObject(path[0])
            return f"{p.Label if p else path[0]}.{label}"
        return f"{o.Label}.{label}"
    if o.TypeId == "Assembly::AssemblyObject" and len(path) > 1:
        p = doc.getObject(path[0])
        return f"{p.Label if p else path[0]}.{path[-1]}"
    return f"{o.Label}.{path[-1]}"


def joint_axis(el):
    """Where a joint on this element turns and slides, as asm_joint puts
    it: a flat face's middle and normal; a round edge's or face's axis; a
    straight edge's start and run; a datum end (LCS, datum plane …) its
    origin and its own z axis. None for anything else."""
    if is_datum_end(el):
        return el["Placement"].Base, el["Placement"].Rotation.multVec(V(0, 0, 1))
    if isinstance(el, Part.Face):
        srf = el.Surface
        if isinstance(srf, Part.Plane):
            u0, u1, v0, v1 = el.ParameterRange
            n = el.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            return el.CenterOfMass, n
        if hasattr(srf, "Axis") and hasattr(srf, "Center"):
            return srf.Center, srf.Axis
    if isinstance(el, Part.Edge) and hasattr(el.Curve, "Axis"):
        return el.Curve.Center, el.Curve.Axis
    if isinstance(el, Part.Edge):
        p0 = el.valueAt(el.FirstParameter)
        return p0, el.valueAt(el.LastParameter) - p0
    return None


def unit(v):
    """A copy of v, one long."""
    v = V(v)
    v.normalize()
    return v


def radius_of(part, el):
    """The radius of a part's round element (an edge's curve, a face's
    surface), for a coupling's figures left out; None where it has none."""
    try:
        g = part.Shape.getElement(el)
        c = getattr(g, "Curve", None) or getattr(g, "Surface", None)
        return float(c.Radius)
    except Exception:
        return None


def joint_refs(asm, ends):
    """The two references a joint is given, from (part, element) pairs.
    1.0 reads a reference from the assembly down (the part's name, then the
    element); later releases from the part itself."""
    if _release() < (1, 1):
        return [[asm, [f"{part.Name}.{el}", f"{part.Name}.{el}"]] for part, el in ends]
    return [[part, [el, el]] for part, el in ends]


def turn_over(doc, asm, j):
    """As the joint panel's Reverse button does: the part turned over on
    the joint, then solved; the solver keeps the nearer way round. The
    solve's (code, words)."""
    j.Proxy.flipOnePart(j)
    doc.recompute()
    return _status(asm)


COUPLE = ("gears", "belt", "rackpinion", "screw")


def end_part(doc, r, names=None):
    """The part of the assembly a joint reference ends on: its object when
    that is a part (names: the assembly's part names, None for any), else
    the first object of its sub-name path that is one ("Crankset.LCS." held
    from a container). None for no reference."""
    if not r:
        return None
    p = ref_element(doc, r)[0]
    if p is None or names is None or p.Name in names:
        return p
    for sub in (r[1] if len(r) > 1 else []) or []:
        for seg in str(sub).split(".")[:-1]:
            if seg in names:
                return doc.getObject(seg)
    return p


def _kind(x):
    return str(getattr(x, "JointType", "")).lower()


def rigid_from(doc, joints, seeds, stop, names=None):
    """The parts held to seeds by fixed joints, at any depth (a spoke set
    fixed to a hub fixed to the wheel): { name: part }, seeds left out.
    stop: names never added (grounded parts, the parts that already move)."""
    out, todo = {}, list(seeds)
    seen = {o.Name for o in seeds}
    while todo:
        cur = todo.pop()
        for x in joints:
            if _kind(x) != "fixed" or getattr(x, "ObjectToGround", None) is not None:
                continue
            q1 = end_part(doc, getattr(x, "Reference1", None), names)
            q2 = end_part(doc, getattr(x, "Reference2", None), names)
            for here, there in ((q1, q2), (q2, q1)):
                if here is None or there is None or here.Name != cur.Name:
                    continue
                if there.Name in seen or there.Name in stop:
                    continue
                seen.add(there.Name)
                out[there.Name] = there
                todo.append(there)
    return out


def carried(doc, asm, j, moving, fixed_side, grounded):
    """What moves with a joint's moving part: the parts joined to it by
    other joints, short of grounded parts and the part it turns on. A
    coupling drives its other part, it does not carry it along. A
    reference held from a container ("Crankset.LCS.") counts as its part.
    ({ name: part }, the other joints that carry, the couplings)."""
    group, todo = {moving.Name: moving}, [moving]
    all_j = [x for x in _joints(asm).Group if x is not j and getattr(x, "ObjectToGround", None) is None]
    couplings = [x for x in all_j if _kind(x) in COUPLE]
    others = [x for x in all_j if x not in couplings]
    names = {o.Name for o in getattr(asm, "Group", []) or []}
    held = {o.Name for o in grounded}
    while todo:
        cur = todo.pop()
        for x in others:
            q1 = end_part(doc, getattr(x, "Reference1", None), names)
            q2 = end_part(doc, getattr(x, "Reference2", None), names)
            for here, there in ((q1, q2), (q2, q1)):
                if here is not None and there is not None and here.Name == cur.Name and there.Name not in group and there.Name not in held and there.Name != getattr(fixed_side, "Name", None):
                    group[there.Name] = there
                    todo.append(there)
    return group, others, couplings


def held_back(doc, asm, group, driven, grounded):
    """Bicycle L5 build (21 Nov, finding 1): grounded parts fixed to a part
    that moves. A grounded part never moves, so the sweep leaves it where it
    is and it seems to collide. [label]."""
    names = {o.Name for o in getattr(asm, "Group", []) or []}
    moving = set(group) | {d["part"].Name for d in driven} | {n for d in driven for n in d.get("carries", {})}
    held = {o.Name: o for o in grounded}
    out = []
    for x in _joints(asm).Group:
        if _kind(x) != "fixed" or getattr(x, "ObjectToGround", None) is not None:
            continue
        q1 = end_part(doc, getattr(x, "Reference1", None), names)
        q2 = end_part(doc, getattr(x, "Reference2", None), names)
        for here, there in ((q1, q2), (q2, q1)):
            if here is not None and there is not None and here.Name in moving and there.Name in held and there.Label not in out:
                out.append(there.Label)
    return out


def driven_parts(doc, couplings, others, group, turning, grounded=()):
    """Parts driven through a coupling: each on its own joint (revolute or
    slider to something that stays), moved by the coupling's ratio — gears
    turn the other way by r1 / r2, a belt the same way; a rack slides
    r · π / 180 mm a degree of its pinion, a screw's nut pitch / 360.
    Bicycle L5 build (21 Nov, finding 1): the parts fixed to a driven part
    (any depth: the rim, tire and spoke set on the rear hub) move with it
    (carries), and a coupling that ends on a part fixed to the one with the
    joint (a cog fixed to the hub) drives that one.
    [{ part, how: turn | slide, factor, centre, axis, via, carries }]."""
    driven = []
    held = {o.Name for o in grounded}
    taken = set(group)
    for c in couplings:
        q1 = ref_element(doc, getattr(c, "Reference1", None))[0]
        q2 = ref_element(doc, getattr(c, "Reference2", None))[0]
        if q1 is None or q2 is None:
            continue
        if q1.Name in group and q2.Name not in group:
            end, first = q2, True
        elif q2.Name in group and q1.Name not in group:
            end, first = q1, False
        else:
            continue
        own = None
        # the coupling's end, then the parts fixed to it: the first on a joint of its own
        for dvn in [end] + list(rigid_from(doc, others, [end], taken | held).values()):
            for x in others:
                r1_, e1_ = ref_element(doc, getattr(x, "Reference1", None))[:2]
                r2_, e2_ = ref_element(doc, getattr(x, "Reference2", None))[:2]
                if _kind(x) not in ("revolute", "slider", "cylindrical"):
                    continue
                if r1_ is not None and r1_.Name == dvn.Name and (r2_ is None or r2_.Name not in group):
                    own = (x, e1_, dvn)
                elif r2_ is not None and r2_.Name == dvn.Name and (r1_ is None or r1_.Name not in group):
                    own = (x, e2_, dvn)
                if own:
                    break
            if own:
                break
        if own is None or own[1] is None:
            continue
        dvn = own[2]
        if dvn.Name in taken:
            continue
        dax = joint_axis(own[1])
        if dax is None:
            continue
        ck = _kind(c)
        r1v, r2v = float(getattr(c, "Distance", 0) or 0), float(getattr(c, "Distance2", 0) or 0)
        if ck in ("gears", "belt"):
            if r1v <= 0 or r2v <= 0:
                continue
            ratio = (r1v / r2v) if first else (r2v / r1v)
            factor, how = (-ratio if ck == "gears" else ratio), "turn"
        elif ck == "rackpinion":
            factor, how = (r1v * math.pi / 180.0), "slide"  # mm a degree of the pinion
        else:
            factor, how = (r1v / 360.0), "slide"  # screw: mm a degree
        if not turning and how == "turn":
            continue
        dc, dv = dax
        carries = rigid_from(doc, others, [dvn], taken | held)
        taken |= {dvn.Name} | set(carries)
        driven.append({"part": dvn, "how": how, "factor": factor, "centre": dc, "axis": unit(dv), "via": c.Label, "carries": carries})
    return driven


def driven_rows(driven):
    """asm_sweep's driven: [{ part, via, turns | slides, per, carries }]."""
    out = []
    for d in driven:
        row = {"part": d["part"].Label, "via": d["via"], d["how"] + "s": "degrees" if d["how"] == "turn" else "mm", "per": round(d["factor"], 5)}
        if d.get("carries"):
            row["carries"] = sorted(o.Label for o in d["carries"].values())
        out.append(row)
    return out


# A sweep stops before the call's limit (about 80 s, the card says): this
# long for its steps, the rest for the answer. _clock is swapped in tests.
SWEEP_BUDGET = 60.0
_clock = time.monotonic


def sweep_run(doc, asm, j, group, driven, centre, axis, turning, lo, hi, steps, clearance, budget=None, only=None, skip=None):
    """The sweep itself: the group turned about (or slid along) the axis to
    each of steps + 1 values from lo to hi, the driven parts by their
    ratio, the pairs of parts with motion between them checked for overlap
    at each, and every part put back after whatever happened (which is why
    this is code: the steps have no "finally"). Values count from where the
    joint was made: an asm_pose since is taken off. A row a step: { at,
    driven, overlaps, closer }. Test drive of 20 Nov (bicycle, finding 6):
    the steps stop when the next one would pass the budget (seconds,
    SWEEP_BUDGET), or when the time runs out inside a step. Finding 1 of
    the later runs (25 parts, two spoke sets of 32 solids: not one step in
    60 s): only pairs with motion between them (sweep_pairs; only, skip),
    boxes first (with the clearance), each part's shape read once while it
    stays put. Later runs of 21 Nov (63 pair checks, about 13 s a step):
    no recompute a step (a part's shape follows its placement), the volumes
    solid by solid with _SweepCuts (a still pair or a round part turning
    about its own axis is cut once), and the next step judged by the time
    of the last one, not the mean (the first step makes the cuts that the
    later steps use again). (rows, stopped, counts): stopped is the index
    of the first step not done, None when all were done; counts { checked,
    skipped, booleans, reused }: pairs cut or measured, pairs left out,
    the solid cuts made, and the solid pairs whose volume was kept, over
    the steps done."""
    budget = SWEEP_BUDGET if budget is None else budget
    t0 = _clock()
    deadline = t0 + budget if budget and budget > 0 else None
    every = _parts(asm)
    kept = {o.Name: o.Placement.copy() for o in every}
    motion = {o.Name: "joint" for o in group.values()}
    for d in driven:
        for o in [d["part"]] + list(d.get("carries", {}).values()):
            motion[o.Name] = "driven " + d["part"].Name
    pairs, left = sweep_pairs(every, motion, only, skip)
    left_out = sum(left.values())
    still = {}  # the shapes of the parts that stay put, read once
    gap = max(float(clearance or 0.0), 0.0)
    rows, stopped = [], None
    counts = {"checked": 0, "skipped": 0}
    axes = {}
    if turning:
        axes.update({o.Name: (centre, axis) for o in group.values()})
    for d in driven:
        if d["how"] == "turn":
            for o in [d["part"]] + list(d.get("carries", {}).values()):
                axes[o.Name] = (d["centre"], d["axis"])
    cuts = None
    last = None
    try:
        posed = float(getattr(j, "AgentLinkPose", 0.0) or 0.0)
        for k in range(steps + 1):
            now = _clock()
            if deadline is not None and rows and now + last > deadline:
                stopped = k
                break
            began = now
            v = lo + (hi - lo) * k / steps
            if turning:
                r = FreeCAD.Rotation(axis, v - posed)
                move = FreeCAD.Placement(centre - r.multVec(centre), r)
            else:
                move = FreeCAD.Placement(axis * (v - posed), FreeCAD.Rotation())
            for o in group.values():
                o.Placement = move.multiply(kept[o.Name])
            if cuts is None:
                cuts = _SweepCuts(motion, axes)
            row = {"at": round(v, 3)}
            for d in driven:
                amount = (v - posed) * d["factor"]
                if d["how"] == "turn":
                    r = FreeCAD.Rotation(d["axis"], amount)
                    dm = FreeCAD.Placement(d["centre"] - r.multVec(d["centre"]), r)
                else:
                    dm = FreeCAD.Placement(d["axis"] * amount, FreeCAD.Rotation())
                for o in [d["part"]] + list(d.get("carries", {}).values()):
                    if o.Name in kept:
                        o.Placement = dm.multiply(kept[o.Name])
                row.setdefault("driven", {})[d["part"].Label] = round(amount, 3)
            moved = {}

            def shape_of(o):
                if o.Name in motion:
                    if o.Name not in moved:
                        moved[o.Name] = _shape(o)
                    return moved[o.Name]
                if o.Name not in still:
                    still[o.Name] = _shape(o)
                return still[o.Name]

            hits, near, n = [], [], 0
            late = False
            for a, b in pairs:
                if deadline is not None and _clock() > deadline:
                    late = True
                    break
                sa, sb = shape_of(a), shape_of(b)
                if not _boxes_near(sa.BoundBox, sb.BoundBox, gap):
                    continue
                n += 1
                try:
                    vol = cuts.volume(a, b, sa, sb)
                except Exception:  # noqa: BLE001
                    vol = 0.0
                if vol > 1e-3:
                    hits.append({"parts": [a.Label, b.Label], "volume": round(vol, 3)})
                elif clearance > 0:
                    try:
                        dd, pts, _ = sa.distToShape(sb)
                        if dd < clearance:
                            near.append({"parts": [a.Label, b.Label], "gap": round(dd, 4), "at": geo.vec(pts[0][0])})
                    except Exception:  # noqa: BLE001
                        pass
            if late:
                stopped = k
                break
            last = _clock() - began
            counts["checked"] += n
            counts["skipped"] += left_out + len(pairs) - n
            if hits:
                row["overlaps"] = [{"parts": h["parts"], "volume": h["volume"]} for h in hits]
            if clearance > 0 and near:
                row["closer"] = near
            rows.append(row)
    finally:
        for o in _parts(asm):
            if o.Name in kept:
                o.Placement = kept[o.Name]
        doc.recompute()
        _status(asm)
    counts["booleans"], counts["reused"] = (cuts.booleans, cuts.reused) if cuts else (0, 0)
    return rows, stopped, counts


def sweep_rest(j, lo, hi, steps, stopped):
    """The call that goes on where a sweep stopped (finding 6): the same
    step size, from the first value not done to the end. None when the
    sweep was done."""
    if stopped is None:
        return None
    return {"joint": j.Label, "from": round(lo + (hi - lo) * stopped / steps, 3), "to": round(hi, 3), "steps": max(steps - stopped, 1)}


# Overlaps that stay the same through the whole sweep are there from the
# start (a press fit, a part modelled into another): the motion does not
# make them. Same volume: within STATIC_ABS mm³ or STATIC_REL of it.
STATIC_ABS, STATIC_REL = 0.01, 0.01


def split_static(rows):
    """Test drive of 20 Nov (bicycle, finding 7): the overlaps present at
    the first step with the same volume at every step, out of the rows.
    (rows with only the contacts the motion makes, [{ parts, volume }] of
    the static ones). One row alone proves nothing: all its overlaps stay."""
    if len(rows) < 2:
        return rows, []

    def key(h):
        return tuple(sorted(h["parts"]))

    def vol(row, k):
        return next((h["volume"] for h in row.get("overlaps", ()) if key(h) == k), 0.0)

    static = []
    for h in rows[0].get("overlaps", ()):
        v0 = h["volume"]
        if all(abs(vol(r, key(h)) - v0) <= max(STATIC_ABS, STATIC_REL * v0) for r in rows):
            static.append({"parts": list(h["parts"]), "volume": v0})
    if not static:
        return rows, []
    keys = {key(h) for h in static}
    out = []
    for r in rows:
        left = [h for h in r.get("overlaps", ()) if key(h) not in keys]
        out.append({**{k: v for k, v in r.items() if k != "overlaps"}, **({"overlaps": left} if left else {})})
    return out, static


# ---- asm_joint: keep, flips, chains (test drive of 20 Nov, bicycle findings 3, 4, 5) ----------

KEEP_TOL_MM, KEEP_TOL_DEG = 1e-3, 1e-3


def _turned(a, b):
    """Degrees between two placements' rotations, 0 … 180."""
    try:
        d = abs(math.degrees(a.Rotation.inverted().multiply(b.Rotation).Angle)) % 360.0
    except Exception:  # noqa: BLE001
        return 0.0
    return min(d, 360.0 - d)


def moved_most(before, parts):
    """The most any part moved from its placement in before: (mm, degrees)."""
    mm = deg = 0.0
    for o in parts:
        b = before.get(o.Name)
        if b is None:
            continue
        mm = max(mm, (o.Placement.Base - b.Base).Length)
        deg = max(deg, _turned(b, o.Placement))
    return mm, deg


def _put_back(asm, before):
    for o in _parts(asm):
        if o.Name in before:
            o.Placement = before[o.Name].copy()


def keep_offset(doc, asm, j, ends, before):
    """Finding 3: the joint's offset that holds the parts where they stand
    (before: their placements before the joint), so the solve moves
    nothing. A joint's frames meet as part·PlacementN·OffsetN; which side
    FreeCAD puts the offset on is tried, as gap_set tries its sign: the
    first that moves nothing is kept, else the one that moves least.
    (code, words, { property, at, axis, angle, moved: { mm, degrees } }),
    or None when the joint's frames cannot be read."""
    (pa, _ea), (pb, _eb) = ends
    if pa.Name not in before or pb.Name not in before:
        return None
    pl1, pl2 = getattr(j, "Placement1", None), getattr(j, "Placement2", None)
    if pl1 is None or pl2 is None or not hasattr(j, "Offset2"):
        return None
    # Runs finding 2: a joint's frame is PlacementN in the frame of the
    # object its reference names (an LCS inside the part, a feature in a
    # Body), not of the part: FreeCAD's marker is part⁻¹ · object · PlacementN
    # (AssemblyObject::handleOneSideOfJoint). With an LCS turned 90° about x
    # and the part's origin off the joint, part · PlacementN put the frame
    # elsewhere, and the offset found moved the part.
    g1 = before[pa.Name].multiply(ref_in_part(j, "Reference1", pa)).multiply(pl1)
    g2 = before[pb.Name].multiply(ref_in_part(j, "Reference2", pb)).multiply(pl2)
    tries = [("Offset2", g2.inverse().multiply(g1)), ("Offset2", g1.inverse().multiply(g2))]
    if hasattr(j, "Offset1"):
        tries += [("Offset1", g1.inverse().multiply(g2)), ("Offset1", g2.inverse().multiply(g1))]
    best = last = None
    for prop, off in tries:
        for name in ("Offset1", "Offset2"):
            if hasattr(j, name):
                setattr(j, name, off if name == prop else FreeCAD.Placement())
        _put_back(asm, before)
        doc.recompute()
        code, said = _status(asm)
        mm, deg = moved_most(before, _parts(asm))
        row = last = (code != 0, mm + deg / 10.0, prop, off, code, said, mm, deg)
        if best is None or row[:2] < best[:2]:
            best = row
        if code == 0 and mm <= KEEP_TOL_MM and deg <= KEEP_TOL_DEG:
            break
    _bad, _score, prop, off, code, said, mm, deg = best
    if best is not last:
        for name in ("Offset1", "Offset2"):
            if hasattr(j, name):
                setattr(j, name, off if name == prop else FreeCAD.Placement())
        _put_back(asm, before)
        doc.recompute()
        code, said = _status(asm)
        mm, deg = moved_most(before, _parts(asm))
    return code, said, dict(property=prop, **_placement_of(off), moved={"mm": round(mm, 4), "degrees": round(deg, 4)})


def ref_in_part(j, prop, part):
    """The placement of the object a joint's reference names (an LCS, a
    feature in a Body) in its part's own frame: part⁻¹ · object, both
    global, as FreeCAD's solver reads a joint's end. Identity when the
    reference names the part itself, or cannot be read."""
    ref = getattr(j, prop, None)
    try:
        import UtilsAssembly as UA

        obj_g = UA.getGlobalPlacement(ref)
        part_g = UA.getGlobalPlacement(ref, part)
        return part_g.inverse().multiply(obj_g)
    except Exception:  # noqa: BLE001
        return FreeCAD.Placement()


def _placement_of(p):
    return {"at": geo.vec(p.Base), "axis": geo.vec(p.Rotation.Axis), "angle": round(math.degrees(p.Rotation.Angle), 4)}


def joint_plane(j, ends, which=0):
    """(origin, unit normal) of the plane across the joint's axis, in the
    document's coordinates: the joint's frame on end which (0: a, 1: b),
    else that element's axis. None when neither can be read."""
    try:
        import UtilsAssembly as UA

        g = UA.getJcsGlobalPlc(getattr(j, f"Placement{which + 1}"), getattr(j, f"Reference{which + 1}"))
        return V(g.Base), unit(g.Rotation.multVec(V(0, 0, 1)))
    except Exception:  # noqa: BLE001
        pass
    try:
        ax = joint_axis(_shape(ends[which][0]).getElement(ends[which][1]))
        return (V(ax[0]), unit(ax[1])) if ax else None
    except Exception:  # noqa: BLE001
        return None


def side_check(asm, j, ends, before):
    """Runs finding 3: for each part the solve moved, which side of the
    joint's plane its centre is on, before and after (mm along the joint's
    z, + or −): a revolute on a Concentric LCS put a crank's drive side on
    the left. The plane is the frame on the end whose part stayed put.
    [{ part, before, after, crossed }]."""
    moved = [o for o in _parts(asm) if o.Name in before and not o.Placement.isSame(before[o.Name], 1e-6)]
    if not moved:
        return []
    names = {o.Name for o in moved}
    which = 1 if ends[0][0].Name in names and ends[1][0].Name not in names else 0
    plane = joint_plane(j, ends, which)
    if plane is None:
        return []
    out = []
    for o in moved:
        c1 = _centre(o)
        if c1 is None:
            continue
        # the centre where the part stood: the same point of the part, at its old placement
        back = before[o.Name].multiply(o.Placement.inverse())
        c0 = back.Base + back.Rotation.multVec(c1)
        d0, d1 = (c0 - plane[0]).dot(plane[1]), (c1 - plane[0]).dot(plane[1])
        crossed = abs(d0) > GAP_TOL and abs(d1) > GAP_TOL and (d0 > 0) != (d1 > 0)
        out.append({"part": o.Label, "before": round(d0, 3), "after": round(d1, 3), "crossed": crossed})
    return out


def _centre(o):
    try:
        sh = _shape(o)
        return V(sh.BoundBox.Center)
    except Exception:  # noqa: BLE001
        return None


def auto_flip(doc, asm, j, ends, before=None):
    """Finding 4, autoFlip: true (the old way): with parts overlapping after
    the solve, the moved part turned over on the joint, kept when that
    lessens the overlap. (code, words, flipped, crossed): crossed names
    each part the flip put on the other side of the joint's plane (its
    centre), as a crankset's chainring on the wrong side of its frame.
    before ({ name: placement } before the joint): only pairs with a part
    the solve or the flip moved, or a joint's part, are cut."""
    code, said = _status(asm)
    focus = None
    if before is not None:
        focus = moved_names(_parts(asm), before) | {e[0].Name for e in ends}
    hits = _overlaps(_parts(asm), focus=focus)[0]
    if code != 0 or not hits:
        return code, said, False, []
    vol0 = sum(h["volume"] for h in hits)
    kept = {o.Name: o.Placement.copy() for o in _parts(asm)}
    plane = joint_plane(j, ends)
    sides = {}
    if plane is not None:
        for o in _parts(asm):
            c = _centre(o)
            if c is not None:
                sides[o.Name] = (c - plane[0]).dot(plane[1])
    code2, said2 = turn_over(doc, asm, j)
    if focus is not None:
        focus = focus | moved_names(_parts(asm), kept)
    second = _overlaps(_parts(asm), focus=focus)[0]
    if code2 == 0 and sum(h["volume"] for h in second) < vol0 - 1e-6:
        crossed = []
        for o in _parts(asm):
            if o.Name not in sides or o.Placement.isSame(kept[o.Name], 1e-6):
                continue
            c = _centre(o)
            d0, d1 = sides[o.Name], ((c - plane[0]).dot(plane[1]) if c is not None else None)
            if d1 is not None and abs(d0) > GAP_TOL and abs(d1) > GAP_TOL and (d0 > 0) != (d1 > 0):
                crossed.append({"part": o.Label, "before": round(d0, 3), "after": round(d1, 3)})
        return code2, said2, True, crossed
    for o in _parts(asm):
        o.Placement = kept[o.Name]
    doc.recompute()
    code, said = _status(asm)
    return code, said, False, []


def overlap_words(hits):
    """"Base/Lid 350 mm³, …" for a warning."""
    return ", ".join(f"{'/'.join(h['parts'])} {h['volume']:g} mm³" for h in hits)


# The pitch of a bicycle chain (1/2 in), mm: a sprocket's pitch radius is
# taken as teeth · pitch / 2π, so the ratio is the teeth's exactly.
CHAIN_PITCH = 12.7


def teeth_in(part, look):
    """The features with NumberOfTeeth in a part (a Body, a link's target,
    or the part itself) whose type or class name has look in it
    ("Sprocket": PartDesign's Sprocket; "Gear": its InvoluteGear), and
    pd_gear's profiles, which keep the teeth in AgentLinkTeeth and the kind
    in AgentLinkKind ("sprocket", "gear"). [(feature, teeth)]."""
    found, seen, todo = [], set(), [part]
    try:
        tgt = part.getLinkedObject(True)
        if tgt is not None and tgt is not part:
            todo.append(tgt)
    except Exception:  # noqa: BLE001
        pass
    while todo:
        o = todo.pop(0)
        if o is None or getattr(o, "Name", None) in seen:
            continue
        seen.add(o.Name)
        n = getattr(o, "NumberOfTeeth", None)
        if n is None:
            # pd_gear's sprocket is a plain sketch: its teeth are in AgentLinkTeeth, its kind in AgentLinkKind
            n = getattr(o, "AgentLinkTeeth", None)
        names = (str(getattr(o, "TypeId", "")), type(getattr(o, "Proxy", None)).__name__, str(getattr(o, "AgentLinkKind", "")))
        if n is not None and any(look.lower() in x.lower() for x in names):
            try:
                found.append((o, int(n)))
            except (TypeError, ValueError):
                pass
        todo.extend(getattr(o, "Group", None) or [])
        todo.extend(getattr(o, "OutListRecursive", None) or [])
    return found


def pitch_of(o):
    """A sprocket's chain pitch in mm as pd_gear keeps it (AgentLinkPitch), or None."""
    v = getattr(o, "AgentLinkPitch", None)
    v = getattr(v, "Value", v)
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def coupling_teeth(ends, kind, teeth1, teeth2, pitch=None):
    """Finding 5: the teeth of a chain's sprockets (or gears', a toothed
    belt's pulleys), given or read from the parts (chain: a PartDesign
    Sprocket in each; gears: an InvoluteGear). None when there are none
    to go by. Else { teeth1, teeth2, ratio: teeth1 / teeth2, from, radius1,
    radius2 }: the radii teeth · pitch / 2π, so the joint's ratio is the
    teeth's."""
    look = {"chain": "Sprocket", "gears": "Gear"}.get(kind)
    got, said, pitches = [], [], []
    for (part, _el), given, which in zip(ends, (teeth1, teeth2), ("teeth1", "teeth2")):
        if given is not None:
            n = picks.num(given, which)
            if n <= 0 or n != int(n):
                raise ToolError("invalid_input", f"{which}: a whole number of teeth, more than 0 (got {given}).")
            got.append(int(n))
            said.append(f"{which} {int(n)} given")
            continue
        found = teeth_in(part, look) if look else []
        if len(found) > 1:
            raise ToolError("invalid_input", f"{which}: {part.Label} holds {len(found)} parts with teeth ({', '.join(f'{o.Label} {n}' for o, n in found)}) — give {which}.")
        if found:
            o, n = found[0]
            got.append(n)
            prop = "NumberOfTeeth" if getattr(o, "NumberOfTeeth", None) is not None else "AgentLinkTeeth"
            said.append(f"{which} {n} read from {part.Label}'s {o.Label} ({prop})")
            pitches.append(pitch_of(o))
        else:
            got.append(None)
    if got == [None, None]:
        return None
    if None in got:
        i = got.index(None)
        which, part = ("teeth1", "teeth2")[i], ends[i][0]
        where = f"no {look} with NumberOfTeeth in {part.Label}" if look else f"{kind} reads no teeth from the parts"
        raise ToolError("invalid_input", f"{which}: {where} — give {which}, or give radius1 and radius2 without teeth.")
    p = float(pitch) if kind == "chain" and pitch else CHAIN_PITCH
    if kind == "chain" and not pitch and pitches and all(x is not None and abs(x - pitches[0]) < 1e-9 for x in pitches):
        # the sprockets' own chain pitch (pd_gear keeps it in AgentLinkPitch)
        p = pitches[0]
        said.append(f"pitch {p:g} mm read from the sprockets (AgentLinkPitch)")
    t1, t2 = got
    return {"teeth1": t1, "teeth2": t2, "ratio": round(t1 / t2, 6), "from": "; ".join(said),
            "radius1": t1 * p / (2 * math.pi), "radius2": t2 * p / (2 * math.pi)}


# ---- datum ends: joints on an LCS or a datum inside a part ------------------------------------
# FreeCAD 1.1's Assembly reads a whole datum as a joint end when the
# reference's element is empty: [part, ["LCS.", "LCS."]] (UtilsAssembly.
# getObject walks the names from the part down; findPlacement gives the
# datum's own frame for an empty element). The joint then sits on the
# datum's origin along its z axis. A datum is not a face: a boolean or an
# edit of the part's solid does not rename it, so the joint stays on.

_ELEMENT_NAME = re.compile(r"^(Face|Edge|Vertex)\d+$")
DATUM_TYPES = ("App::LocalCoordinateSystem", "App::DatumElement", "Part::Datum")
_DATUM_IDS = {"App::LocalCoordinateSystem", "App::Origin", "App::Plane", "App::Line", "App::Point", "Part::LocalCoordinateSystem", "Part::Datum",
              "PartDesign::CoordinateSystem", "PartDesign::Plane", "PartDesign::Line", "PartDesign::Point", "Part::DatumPlane", "Part::DatumLine", "Part::DatumPoint"}


def is_datum_end(el):
    """A datum joint end as ref_element gives it: { datum: the object,
    Placement: its frame in the document's coordinates } (a plain dict, so
    reading one changes nothing). joint_axis reads it."""
    return isinstance(el, dict) and "datum" in el and "Placement" in el


def is_datum(o):
    try:
        if any(o.isDerivedFrom(t) for t in DATUM_TYPES):
            return True
    except Exception:  # noqa: BLE001
        pass
    return getattr(o, "TypeId", "") in _DATUM_IDS


def is_datum_sub(el):
    """A joint element that names a whole datum: "LCS." (empty element)."""
    return isinstance(el, str) and el.endswith(".") and len(el) > 1


def _root(part):
    """The object whose children hold the part's datums: a link's target."""
    if getattr(part, "TypeId", "") in LINKS:
        try:
            return part.getLinkedObject(True) or part
        except Exception:  # noqa: BLE001
            return part
    return part


def _children(o):
    """What can hold a datum below o: its group, an LCS's or origin's own
    planes, axes and point, a Body's or App::Part's origin."""
    out = []
    for k in ("Group", "OriginFeatures"):
        out += [x for x in (getattr(o, k, None) or []) if x is not None]
    org = getattr(o, "Origin", None)
    if org is not None and not isinstance(org, (str, bytes)) and hasattr(org, "Name"):
        out.append(org)
    seen, uniq = set(), []
    for x in out:
        if x.Name not in seen:
            seen.add(x.Name)
            uniq.append(x)
    return uniq


def _datums(part, depth=4):
    """Every datum below a part: [(object, path of names)], path from the
    part down ("Body.LCS" in an App::Part, "LCS" in a Body)."""
    out, todo = [], [(c, [c.Name]) for c in _children(_root(part))]
    while todo:
        o, path = todo.pop(0)
        if is_datum(o):
            out.append((o, path))
        if len(path) < depth:
            todo += [(c, path + [c.Name]) for c in _children(o)]
    return out


def datum_sub(part, ref, what):
    """The sub-name of a datum inside a part, as a joint reference ends in
    it: "LCS." or "Body.LCS." — the datum named by object name, label, or a
    dotted path of them ("LCS.XY_Plane"). Refused when the part holds no
    such datum, or two."""
    ref = str(ref).strip().rstrip(".")
    found = _datums(part)
    if not found:
        kind = getattr(part, "TypeId", "")
        raise ToolError("invalid_input", f"{what}: {part.Label} has no {ref} — no face or edge of that name, and {part.Label} ({kind}) holds no LCS or datum. "
                        f"A joint on a datum needs it inside the part: pd_datum {{ kind: lcs, body }} in a Body, or put the part and a coordinate system in an App::Part and join that.")
    want = ref.split(".")

    def named(o, w):
        return w == o.Name or w.lower() == str(o.Label).lower()

    hits = []
    for o, path in found:
        objs = path  # names from the part down
        if len(want) == 1:
            if named(o, want[0]):
                hits.append((o, path))
        elif len(objs) >= len(want):
            tail = [x for x in objs[-len(want):]]
            chain = [_obj_of(part, n) for n in tail]
            if all(c is not None and named(c, w) for c, w in zip(chain, want)):
                hits.append((o, path))
    if not hits:
        names = ", ".join(sorted({o.Label for o, _ in found}))
        raise ToolError("invalid_input", f"{what}: {part.Label} has no {ref} — no face or edge of that name, and no datum of that name or label. Its datums: {names}. "
                        "shape_query lists its faces and edges.")
    if len(hits) > 1:
        raise ToolError("invalid_input", f"{what}: {len(hits)} datums of {part.Label} are named {ref} ({', '.join('.'.join(p) for _, p in hits)}) — give the path, e.g. \"{'.'.join(hits[0][1])}\".")
    return ".".join(hits[0][1]) + "."


def _obj_of(part, name):
    doc = getattr(part, "Document", None)
    o = doc.getObject(name) if doc is not None else None
    if o is None:
        r = _root(part)
        d = getattr(r, "Document", None)
        o = d.getObject(name) if d is not None else None
    return o


def _pmul(pl, v):
    """A point through a placement."""
    if hasattr(pl, "multVec"):
        return pl.multVec(v)
    return pl.Base + pl.Rotation.multVec(v)


def datum_end(part, sub):
    """The datum a joint end names ("LCS." or "Body.LCS.", from the part
    down) and its frame in the document's coordinates: the part's placement
    times each placement on the way down. None when a name is gone."""
    names = [n for n in str(sub).split(".") if n]
    if not names:
        return None
    pl = getattr(part, "Placement", None) or FreeCAD.Placement()
    obj = None
    for n in names:
        obj = _obj_of(part, n)
        if obj is None:
            return None
        own = getattr(obj, "Placement", None)
        if own is not None:
            pl = pl * own  # a new placement (no method: Matrix.multiply changes its own)
    if obj is None or not is_datum(obj):
        return None
    return {"datum": obj, "Placement": pl}


def end_text(end):
    """A joint end as an answer says it: Part.Face6, or Part.LCS by labels."""
    part, el = end
    if is_datum_sub(el):
        d = datum_end(part, el)
        return f"{part.Label}.{d['datum'].Label if d is not None else el.rstrip('.').split('.')[-1]}"
    return f"{part.Label}.{el}"


# ---- stored element queries and the re-pick ---------------------------------------------------
# A face picked by a query ({ kind, normal, near, radius … }) is kept on the
# joint (property AgentLinkQuery, JSON): the query, the element it picked,
# where that element was (its centre and size, in the document's
# coordinates) and the part's frame then. A Part boolean renumbers the faces
# of a plain shape, so the joint's FaceN can be gone or be another face. The
# health check after each changing call reads each kept end; when its
# element is gone or is no longer the face it was, the query runs again on
# the part and the joint is pointed at what it finds — or it stays broken,
# with the reason, when the query finds nothing or two equal matches.

QUERY_PROP = "AgentLinkQuery"
REPICK_MAX = 60  # joint ends read per health check
SIG_TOL = 1e-3   # mm: an element's centre that has not moved


def _plc_list(pl):
    q = pl.Rotation.Q
    return [float(pl.Base.x), float(pl.Base.y), float(pl.Base.z)] + [float(x) for x in q]


def _plc_of(xs):
    return FreeCAD.Placement(V(*xs[:3]), FreeCAD.Rotation(*xs[3:7]))


def _frame(part):
    try:
        return _shape(part).Placement
    except Exception:  # noqa: BLE001
        return getattr(part, "Placement", FreeCAD.Placement())


def element_sig(part, el):
    """Where an element is and how big: { at: centre [x, y, z] in the
    document's coordinates, size: area or length, kind }. None when the
    part has no such element."""
    try:
        g = _shape(part).getElement(el)
    except Exception:  # noqa: BLE001
        return None
    try:
        kind = g.ShapeType
        if kind == "Vertex":
            c, size = g.Point, 0.0
        else:
            c, size = g.CenterOfMass, float(g.Area if kind == "Face" else g.Length)
        return {"at": [round(float(c.x), 6), round(float(c.y), 6), round(float(c.z), 6)], "size": round(size, 6), "kind": kind}
    except Exception:  # noqa: BLE001
        return None


def pick_note(part, q, el):
    """What to keep of a pick by query, at the time of the pick: the query
    (near in the document's coordinates) and the part's frame. None for an
    element given by name or a datum: there is no query to run again."""
    if not isinstance(q, dict) or q.get("datum") is not None or is_datum_sub(el):
        return None
    try:
        query = query_of(part, q, "query")
    except ToolError:
        return None
    return {"query": query, "element": el, "frame0": _plc_list(_frame(part))}


def _same_sig(a, b):
    if not a or not b or a.get("kind") != b.get("kind"):
        return False
    if abs(float(a["size"]) - float(b["size"])) > 1e-6 + 1e-6 * abs(float(a["size"])):
        return False
    return (V(*a["at"]) - V(*b["at"])).Length <= SIG_TOL


def _moved_query(query, delta):
    """A query's points and directions taken along by a rigid move of its
    part (delta, in the document's coordinates). x, y, z and inside follow a
    move without a turn; with a turn they are dropped (near stays)."""
    out = dict(query)
    turned = abs(delta.Rotation.Angle) > 1e-9
    near = out.get("near")
    if near is not None:
        if isinstance(near, dict) and near.get("point") is not None:
            out["near"] = dict(near, point=geo.vec(_pmul(delta, V(*near["point"]))))
        elif isinstance(near, (list, tuple)):
            out["near"] = geo.vec(_pmul(delta, V(*near)))
    for k in ("normal", "axis"):
        if isinstance(out.get(k), (list, tuple)) and len(out[k]) == 3:
            out[k] = geo.vec(delta.Rotation.multVec(V(*out[k])))
    for k in ("x", "y", "z", "inside"):
        if k not in out:
            continue
        if turned:
            out.pop(k)
        elif k == "inside" and isinstance(out[k], dict):
            out[k] = {m: geo.vec(V(*out[k][m]) + delta.Base) for m in ("min", "max") if m in out[k]}
        elif k in ("x", "y", "z"):
            out[k] = float(out[k]) + float(getattr(delta.Base, k))
    return out


def keep_notes(j, ends, notes):
    """The query of each end picked by one, kept on the joint after its
    solve: the query taken along with its part (the solve moved it), the
    element's place now and the part's frame now."""
    keep = {}
    for i, (end, note) in enumerate(zip(ends, notes)):
        if not note:
            continue
        part, el = end
        f0, f1 = _plc_of(note["frame0"]), _frame(part)
        delta = f1.multiply(f0.inverse())
        keep[f"Reference{i + 1}"] = {"query": _moved_query(note["query"], delta), "element": el, "sig": element_sig(part, el), "frame": _plc_list(f1)}
    if not keep:
        return None
    try:
        if QUERY_PROP not in j.PropertiesList:
            j.addProperty("App::PropertyString", QUERY_PROP, "AgentLink", "The element queries of this joint's ends, to pick them again when a face is renumbered (JSON)")
        setattr(j, QUERY_PROP, json.dumps(keep))
    except Exception:  # noqa: BLE001 - the joint works without its notes
        return None
    return keep


def notes_of(j):
    try:
        raw = getattr(j, QUERY_PROP, "") if QUERY_PROP in j.PropertiesList else ""
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return {}


def requery(part, query):
    """The stored query run on the part as it is now: [(ref, element)]."""
    kind, hits = M.filter_shape(_shape(part), query)
    return [(d["ref"], el) for _i, el, d in hits]


def repick_choice(hits, query):
    """(ref, None) for the one element a query finds, or (None, why)."""
    if not hits:
        return None, "the stored query finds nothing now"
    if len(hits) == 1:
        return hits[0][0], None
    near = query.get("near")
    if near is None:
        return None, f"the stored query finds {len(hits)} ({', '.join(r for r, _ in hits[:6])}) and has no near point"
    p = picks.vec3(near.get("point") if isinstance(near, dict) else near, "near")
    ranked = sorted(((el.distToShape(Part.Vertex(p))[0], r) for r, el in hits), key=lambda x: x[0])
    if ranked[1][0] - ranked[0][0] <= 1e-6:
        return None, f"the stored query finds two equal matches ({ranked[0][1]}, {ranked[1][1]})"
    return ranked[0][1], None


def _resub(sub, new, doc):
    """A reference's sub-name with its element put to new: the object names
    before it kept ("Part.Face6" in 1.0's form), the element (with any "?"
    or mapped prefix) replaced."""
    segs = str(sub).split(".")
    keep = []
    for s_ in segs[:-1]:
        if doc.getObject(s_) is None:
            break
        keep.append(s_)
    return ".".join(keep + [new])


def _broken(sub, part, name):
    if "?" in str(sub):
        return True
    try:
        _shape(part).getElement(name.lstrip("?"))
        return False
    except Exception:  # noqa: BLE001
        return True


def repick(doc, asm):
    """The re-pick of the health check, over an assembly's joints: each end
    kept with a query is read; one whose element is gone or changed is
    picked again by its query and the joint pointed at it. Lines for the
    health check: [{ line, red, todo }]; nothing when all ends stand."""
    out, seen = [], 0
    g = next((o for o in getattr(asm, "Group", []) if o.TypeId == "Assembly::JointGroup"), None)  # read only: no group made here
    for j in list(getattr(g, "Group", None) or []):
        if getattr(j, "ObjectToGround", None) is not None:
            continue
        notes, changed = notes_of(j), False
        for prop in ("Reference1", "Reference2"):
            if seen >= REPICK_MAX:
                return out
            ref = getattr(j, prop, None)
            if not ref or len(ref) < 2 or not ref[1]:
                continue
            seen += 1
            subs = list(ref[1])
            part, _g, name = ref_element(doc, ref)
            if part is None or is_datum_sub(subs[0]):
                continue
            name = str(name).lstrip("?")
            note = notes.get(prop)
            gone = _broken(subs[0], part, name)
            if not note:
                if gone:
                    out.append({"line": f"{j.Label}: {part.Label}.{name} is broken, and the joint has no stored query to pick it again", "red": True,
                                "todo": f"asm_joint_remove {j.Label} and join again: an LCS in the part (pd_datum {{ kind: lcs }}) holds through booleans"})
                continue
            now = None if gone else element_sig(part, name)
            if now is not None and _same_sig(now, note.get("sig")):
                frame = _plc_list(_frame(part))
                if frame != note.get("frame"):
                    # the element stands where it stood, the frame is new: a
                    # Part boolean puts the result in the document's
                    # coordinates and the object's placement to none
                    note["frame"], changed = frame, True
                continue
            if now is not None and note.get("sig") and note.get("frame"):
                # the same element, the part moved with no change to it
                f0, f1 = _plc_of(note["frame"]), _frame(part)
                delta = f1.multiply(f0.inverse())
                moved = dict(note["sig"], at=geo.vec(_pmul(delta, V(*note["sig"]["at"]))))
                if _same_sig(now, moved):
                    note["query"], note["frame"], note["sig"], changed = _moved_query(note["query"], delta), _plc_list(f1), now, True
                    continue
            try:
                new, why = repick_choice(requery(part, note["query"]), note["query"])
            except Exception as e:  # noqa: BLE001 - a query this cannot run: said, kept broken
                new, why = None, f"the stored query fails ({e})"
            if new is None:
                if gone or now is not None:
                    out.append({"line": f"{j.Label}: {part.Label}.{name} is {'broken' if gone else 'another element now'}; not picked again: {why}", "red": True,
                                "todo": f"asm_joint_remove {j.Label} and join again: an LCS in the part (pd_datum {{ kind: lcs }}) holds through booleans"})
                continue
            if new != name or gone:
                try:
                    setattr(j, prop, [ref[0], [_resub(x, new, doc) for x in subs]])
                    try:
                        j.Proxy.updateJCSPlacements(j)
                    except Exception:  # noqa: BLE001
                        pass
                except Exception as e:  # noqa: BLE001
                    out.append({"line": f"{j.Label}: {part.Label}.{name} is broken; FreeCAD did not take {new} ({e})", "red": True,
                                "todo": f"asm_joint_remove {j.Label} and join again"})
                    continue
                out.append({"line": f"{j.Label}: re-picked {name} -> {new} on {part.Label} (stored query)", "repicked": True})
            note.update(element=new, sig=element_sig(part, new), frame=_plc_list(_frame(part)))
            changed = True
        if changed:
            try:
                setattr(j, QUERY_PROP, json.dumps(notes))
            except Exception:  # noqa: BLE001
                pass
    return out


def tools(session):
    s = session
    try:
        from .. import health

        health.register("assembly", _health)
    except Exception:
        pass

    def doc():
        """The session's document; refused when there is none."""
        if s.doc is None:
            raise ToolError("invalid_state", "No document: doc_new first.")
        return s.doc

    # What the tools' entries (agentlink/data/tools.json, group "assembly", no family) call by name.
    # FreeCAD's and the Assembly workbench's own are reached when called, not here.
    helpers = {"doc": doc, "body": lambda ref: s.body(ref), "num": picks.num, "vec": lambda v: geo.vec(v),
               # FreeCAD's own and the Assembly workbench's
               "V": lambda *x: FreeCAD.Vector(*x), "placement": lambda *x: FreeCAD.Placement(*x), "rotation": lambda *x: FreeCAD.Rotation(*x),
               "grounded_joint": lambda g, o: JointObject.GroundedJoint(g, o),
               "joint_proxy": lambda j, kind: JointObject.Joint(j, JointObject.JointTypes.index(KINDS[kind])),
               # the family's
               "assembly": lambda ref: _assembly(doc(), ref), "typed": _typed, "joints": _joints, "parts": _parts, "part_of": _part, "grounded": _grounded,
               "placement_of": _placement, "element": lambda part, q, what: _element(s, part, q, what), "status": _status,
               "element_centre": element_centre, "joint_gap": joint_gap, "gap_set": lambda asm, j, ends, want: gap_set(doc(), asm, j, ends, want), "overlaps": _overlaps,
               "check_parts": _check_parts, "view_provider": _view_provider, "ref_label": lambda r: ref_label(doc(), r),
               "ref_pair": lambda r: ref_element(doc(), r)[:2], "joint_axis": joint_axis, "unit": unit, "radius_of": radius_of, "joint_refs": joint_refs,
               "turn_over": lambda asm, j: turn_over(doc(), asm, j), "carried": lambda asm, j, moving, fixed, grounded: carried(doc(), asm, j, moving, fixed, grounded),
               "driven_parts": lambda couplings, others, group, turning, grounded=(): driven_parts(doc(), couplings, others, group, turning, grounded),
               "driven_rows": driven_rows, "held_back": lambda asm, group, driven, grounded: held_back(doc(), asm, group, driven, grounded),
               "sweep_run": lambda asm, j, *rest: sweep_run(doc(), asm, j, *rest), "sweep_labels": sweep_labels, "sweep_rest": sweep_rest, "split_static": split_static,
               # test drive of 20 Nov (bicycle): keep, flips, chains by teeth
               "keep_offset": lambda asm, j, ends, before: keep_offset(doc(), asm, j, ends, before),
               "auto_flip": lambda asm, j, ends, before=None: auto_flip(doc(), asm, j, ends, before), "joint_overlaps": joint_overlaps, "side_check": side_check, "overlap_words": overlap_words,
               "coupling_teeth": coupling_teeth,
               "pick_note": pick_note, "keep_notes": keep_notes, "end_text": end_text,
               # tables
               "OFFERED": OFFERED, "KINDS": KINDS, "REVERSIBLE": REVERSIBLE}
    return runners.tools(GROUP, s, helpers)
