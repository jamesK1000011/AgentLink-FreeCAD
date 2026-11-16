# SPDX-License-Identifier: LGPL-2.1-or-later
# Assemblies with FreeCAD's own Assembly workbench (the Ondsel solver): the
# parts put in an assembly, one held fixed, joints between their faces and
# edges — fixed, revolute, cylindrical, slider, ball, distance, parallel,
# perpendicular, angle — solved, and the result checked: where each part
# went, how many ways it can still move, and whether any two parts overlap.
# Faces and edges are picked by what they are (shape_query's queries), so a
# joint does not depend on FreeCAD's numbering.

import math

import FreeCAD
import Part

import JointObject  # FreeCAD's Assembly workbench
import UtilsAssembly  # noqa: F401  — the joints' own helpers load through it

from .. import geometry as geo
from ..protocol import Tool, ToolError
from ..tools import obj
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
    several matching, near picks the closest."""
    if isinstance(q, str):
        try:
            part.Shape.getElement(q)
        except Exception:
            raise ToolError("invalid_input", f"{what}: {part.Label} has no {q} — shape_query {{ body: \"{part.Label}\" }} lists its faces and edges, or give a query {{ kind: face|edge, normal, near, radius, type }} here.")
        return q
    if not isinstance(q, dict):
        raise ToolError("invalid_input", f"{what}: a face or edge — \"Face6\", or a query {{ kind: face|edge, normal, near, radius, type }} as shape_query takes.")
    query = {k: v for k, v in q.items() if k not in ("part",)}
    query["body"] = part.Name  # by Name: a label can change on recompute
    _, _, hits = M.query(session, query)
    if not hits:
        raise ToolError("not_found", f"{what}: no {query.get('kind', 'face')} of {part.Label} matches {q} — shape_query {{ body: \"{part.Label}\" }} lists them.")
    if len(hits) > 1:
        near = q.get("near")
        if near is None:
            names = ", ".join(d.get("ref", "?") for _, _, d in hits[:8])
            raise ToolError("invalid_input", f"{what}: {len(hits)} match ({names}{' …' if len(hits) > 8 else ''}) — narrow it, or add near: [x, y, z] to take the closest.")
        p = picks.vec3(near if isinstance(near, list) else near.get("point"), "near")
        hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(p))[0])
    return hits[0][2]["ref"]


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


def _overlaps(parts, clearance=0.0):
    """Pairs of parts that overlap (their common volume), and, with
    clearance, those closer than it."""
    out, near = [], []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            sa, sb = _shape(a), _shape(b)
            if not sa.BoundBox.intersect(sb.BoundBox) and clearance <= 0:
                continue
            try:
                common = sa.common(sb)
                vol = common.Volume if common.Solids else 0.0
            except Exception:
                vol = 0.0
            if vol > 1e-3:
                c = common.BoundBox.Center
                row = {"parts": [a.Label, b.Label], "volume": round(vol, 3), "at": geo.vec(c)}
                eng = _thread_engagement(a, b, common) or _thread_engagement(b, a, common)
                if eng:
                    row["thread"] = eng
                out.append(row)
                continue
            if clearance > 0:
                d, pts, _ = sa.distToShape(sb)
                if d < clearance:
                    near.append({"parts": [a.Label, b.Label], "gap": round(d, 4), "at": geo.vec(pts[0][0])})
    return out, near


def _health(session, tool, changed):
    """The assembly solver's own status after a call of this family (the
    shared health check, agentlink/health.py): one line an assembly.
    FreeCAD 1.1's solve answers 0 (solved), -1 (the solver threw) or -6
    (nothing grounded) only; "solved" is not "fully constrained" — it does
    not count the freedom left."""
    if not str(getattr(tool, "group", "")).startswith("assembly"):
        return None
    out = []
    asms = [o for o in session.doc.Objects if o.TypeId == "Assembly::AssemblyObject"][:3]
    for asm in asms:
        code, words = _status(asm)
        line = f"{asm.Label}: assembly {words}"
        if code == 0:
            out.append({"line": line})
        elif code == -6:
            out.append({"line": line, "red": True, "todo": "asm_ground { part } fixes one part so the solver has a frame"})
        else:
            out.append({"line": line, "red": True, "todo": "asm_list names the joints (asm_check the parts joined to nothing); asm_joint_remove the one that fights another, or history_undo"})
    return out


def tools(session):
    s = session
    try:
        from .. import health

        health.register("assembly", _health)
    except Exception:
        pass

    def doc():
        if s.doc is None:
            raise ToolError("invalid_state", "No document: doc_new first.")
        return s.doc

    def asm_new(a):
        refs = a.get("parts") or []
        if not isinstance(refs, list) or not refs:
            raise ToolError("invalid_input", "parts: the bodies to put together, by label — session_state lists them.")
        parts = [s.body(r) for r in refs]
        asm = doc().addObject("Assembly::AssemblyObject", (a.get("name") or "Assembly").replace(" ", "_"))
        asm.Label = a.get("name") or "Assembly"
        _typed(asm)
        _joints(asm)
        for o in parts:
            for p in list(o.InList):
                if p.TypeId == "Assembly::AssemblyObject" and p is not asm:
                    raise ToolError("invalid_state", f"{o.Label} is in {p.Label} already: a part is in one assembly. Join it there (asm_joint {{ assembly: \"{p.Label}\" }}), or put {p.Label} itself into another with asm_sub. Nothing was made.")
            asm.addObject(o)
        ground = a.get("ground", parts[0].Label)
        if ground:
            g = _joints(asm).newObject("App::FeaturePython", "GroundedJoint")
            JointObject.GroundedJoint(g, _part(asm, ground))
            _view_provider(g, "grounded")
        doc().recompute()
        return {"assembly": asm.Label, "parts": [o.Label for o in parts], "grounded": [o.Label for o in _grounded(asm)],
                "next": "asm_joint between the parts' faces and edges; each joint solves the assembly."}

    def asm_add(a):
        asm = _assembly(doc(), a.get("assembly"))
        added = []
        for r in a.get("parts") or []:
            o = s.body(r)
            if o in asm.Group:
                continue
            asm.addObject(o)
            added.append(o.Label)
        if not added:
            raise ToolError("invalid_input", f"parts: bodies not in {asm.Label} yet, by label — every one named is in it already (asm_list lists its parts; session_state the bodies).")
        doc().recompute()
        return {"assembly": asm.Label, "added": added, "parts": [o.Label for o in _parts(asm)]}

    def asm_ground(a):
        asm = _assembly(doc(), a.get("assembly"))
        o = _part(asm, a.get("part"))
        want = a.get("grounded", True)
        jg = _joints(asm)
        have = [j for j in jg.Group if getattr(j, "ObjectToGround", None) == o]
        if want and not have:
            g = jg.newObject("App::FeaturePython", "GroundedJoint")
            JointObject.GroundedJoint(g, o)
            _view_provider(g, "grounded")
        if not want:
            for j in have:
                doc().removeObject(j.Name)
        doc().recompute()
        return {"assembly": asm.Label, "grounded": [x.Label for x in _grounded(asm)]}

    def asm_joint(a):
        asm = _typed(_assembly(doc(), a.get("assembly")))
        kind = str(a.get("kind", "")).lower()
        if kind not in OFFERED:
            raise ToolError("invalid_input", f"kind: one of {', '.join(OFFERED)} (got {a.get('kind')!r}).")
        if not _grounded(asm):
            raise ToolError("invalid_state", f"No part of {asm.Label} is grounded: asm_ground {{ part }} the one that stays put first.")
        ends = []
        for side in ("a", "b"):
            e = a.get(side)
            if not isinstance(e, dict) or "part" not in e:
                raise ToolError("invalid_input", f"{side}: {{ part, element }} — element \"Face6\" or a query {{ kind: face|edge, normal, near, radius, type }}.")
            part = _part(asm, e["part"])
            el = _element(s, part, e.get("element", {"kind": "face", **{k: v for k, v in e.items() if k not in ('part', 'element')}}), f"{side}.element")
            ends.append((part, el))
        if ends[0][0] is ends[1][0]:
            raise ToolError("invalid_input", f"a and b are both on {ends[0][0].Label}: a joint is between two parts of the assembly (asm_list names them).")
        # Keyed by Name: a workbench that relabels its objects on recompute
        # (Fasteners counts its screws' labels up) made a lookup by label
        # after the solve fail with a bare KeyError.
        before = {o.Name: o.Placement.copy() for o in _parts(asm)}
        j = _joints(asm).newObject("App::FeaturePython", a.get("name") or KINDS[kind])
        JointObject.Joint(j, JointObject.JointTypes.index(KINDS[kind]))
        _view_provider(j, "joint")
        if a.get("name"):
            j.Label = a["name"]
        if kind == "distance":
            j.Distance = picks.num(a.get("distance", 0), "distance")
        if kind == "angle":
            j.Angle = picks.num(a.get("angle", 90), "angle")
        if kind in ("rackpinion", "screw", "gears", "belt"):
            # the couplings' figures: a pitch radius, a lead, or each wheel's radius
            # — read off round elements when not given
            def radius_of(part, el):
                try:
                    g = part.Shape.getElement(el)
                    c = getattr(g, "Curve", None) or getattr(g, "Surface", None)
                    return float(c.Radius)
                except Exception:
                    return None

            r1 = a.get("radius1") if a.get("radius1") is not None else (a.get("pitch") if kind == "screw" else radius_of(*ends[0]))
            if r1 is None or float(r1) <= 0:
                raise ToolError("invalid_input", {"rackpinion": "radius1: the pinion's pitch radius, mm (or give its round edge).",
                                                  "screw": "pitch: mm the nut moves per turn.",
                                                  "gears": "radius1: the first gear's pitch radius, mm (or give its round edge).",
                                                  "belt": "radius1: the first pulley's radius, mm (or give its round edge)."}[kind])
            j.Distance = float(r1)
            if kind in ("gears", "belt"):
                r2 = a.get("radius2") if a.get("radius2") is not None else radius_of(*ends[1])
                if r2 is None or float(r2) <= 0:
                    raise ToolError("invalid_input", "radius2: the second wheel's radius, mm (or give its round edge).")
                j.Distance2 = float(r2)
        off = a.get("offset")
        rot = a.get("rotate")

        if off is not None or rot is not None:
            j.Offset2 = FreeCAD.Placement(V(0, 0, picks.num(off or 0, "offset")), FreeCAD.Rotation(V(0, 0, 1), picks.num(rot or 0, "rotate")))

        def turn_over():
            # As the task panel's Reverse button does: the part turned over on
            # the joint, then solved; the solver keeps the nearer way round.
            j.Proxy.flipOnePart(j)
            doc().recompute()
            return _status(asm)

        # 1.0 reads a reference from the assembly down (the part's name, then
        # the element); later releases from the part itself.
        if _release() < (1, 1):
            refs = [[asm, [f"{part.Name}.{el}", f"{part.Name}.{el}"]] for part, el in ends]
        else:
            refs = [[part, [el, el]] for part, el in ends]
        try:
            j.Proxy.setJointConnectors(j, refs)
        except Exception as e:
            raise ToolError("failed", f"FreeCAD could not make the {kind} joint between {ends[0][0].Label}.{ends[0][1]} and {ends[1][0].Label}.{ends[1][1]}: {e}")
        # The joint's frames on each element, worked out again here: later
        # releases leave that to the window's selection, which there is none
        # of headless.
        try:
            j.Proxy.updateJCSPlacements(j)
        except Exception:
            pass
        # As the joint panel's OK does: the placements the solve kept for its
        # own undo are dropped, or the next joint made starts by putting the
        # parts back where they were before this one (Joint.__init__ calls
        # setJointConnectors with nothing, which undoes the last solve).
        try:
            asm.clearUndo()
        except Exception:
            pass
        doc().recompute()
        code, said = _status(asm)
        flipped = False
        if code == 0 and a.get("reverse"):
            code, said = turn_over()
            flipped = True
        # FreeCAD lines the joint's frames up as the elements' geometry
        # runs, which can put a lid into its box instead of on it. Two parts
        # overlapping after the solve, and no reverse said: the other way is
        # tried, and kept when it overlaps less.
        if code == 0 and a.get("reverse") is None and kind in REVERSIBLE:
            first, _ = _overlaps(_parts(asm))
            if first:
                vol0 = sum(h["volume"] for h in first)
                kept = {o.Name: o.Placement.copy() for o in _parts(asm)}
                code2, said2 = turn_over()
                second, _ = _overlaps(_parts(asm))
                if code2 == 0 and sum(h["volume"] for h in second) < vol0 - 1e-6:
                    code, said, flipped = code2, said2, True
                else:
                    for o in _parts(asm):
                        o.Placement = kept[o.Name]
                    doc().recompute()
                    code, said = _status(asm)
        if code != 0:
            hint = ("asm_ground { part } holds one part first." if code == -6 else
                    "The solver could not put the parts where all the joints ask: this one fights another on the same parts (asm_list shows them; asm_joint_remove takes one out), "
                    "or the elements cannot meet that way — pick other elements, or for parts far out of place try reverse: true.")
            raise ToolError("failed", f"The {kind} joint leaves {asm.Label} unsolved: {said} — nothing was kept. {hint}")
        moved = {}
        for o in _parts(asm):
            b = before.get(o.Name)
            if b is None:
                continue  # a part the solve brought in: nothing to compare
            if not o.Placement.isSame(b, 1e-6):
                moved[o.Label] = {"from": geo.vec(b.Base), "to": _placement(o), "by": round((o.Placement.Base - b.Base).Length, 4)}
        hits, _ = _overlaps(_parts(asm))
        hits = [h for h in hits if not h.get("thread")]
        out = {"joint": j.Label, "kind": kind, "a": f"{ends[0][0].Label}.{ends[0][1]}", "b": f"{ends[1][0].Label}.{ends[1][1]}", "solve": said, "moved": moved}
        if flipped:
            out["flipped"] = True if a.get("reverse") else "turned over to stop the parts overlapping (reverse: false keeps it as FreeCAD first put it)"
        if hits:
            out["overlaps"] = hits
            out["warning"] = "Parts overlap after the solve: a face picked the wrong way round, or the parts do not fit — reverse: true flips the second part, or check the sizes."
        return out

    def asm_list(a):
        asm = _assembly(doc(), a.get("assembly"))
        joints = []
        for j in _joints(asm).Group:
            if getattr(j, "ObjectToGround", None) is not None:
                continue
            r1, r2 = getattr(j, "Reference1", None), getattr(j, "Reference2", None)

            def ref(r):
                if not r:
                    return None
                o, subs = r[0], (r[1] if len(r) > 1 else [])
                if not subs:
                    return o.Label
                path = subs[0].split(".")
                if o.TypeId == "Assembly::AssemblyObject" and len(path) > 1:
                    p = doc().getObject(path[0])
                    return f"{p.Label if p else path[0]}.{path[-1]}"
                return f"{o.Label}.{path[-1]}"

            joints.append({"joint": j.Label, "kind": str(getattr(j, "JointType", "?")).lower(), "a": ref(r1), "b": ref(r2), "suppressed": bool(getattr(j, "Suppressed", False))})
        code, said = _status(asm)
        return {"assembly": asm.Label, "parts": [{"part": o.Label, "placement": _placement(o), "grounded": o in _grounded(asm)} for o in _parts(asm)], "joints": joints, "solve": said}

    def _ref_element(r):
        return ref_element(doc(), r)[:2]

    def _axis(el):
        """Where a joint on this element turns and slides, as asm_joint puts
        it: a flat face's middle and normal; a round edge's or face's axis."""
        import Part

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

    def asm_sweep(a):
        asm = _assembly(doc(), a.get("assembly"))
        name = a.get("joint")
        j = next((x for x in _joints(asm).Group if x.Label == name or x.Name == name), None)
        if j is None or getattr(j, "ObjectToGround", None) is not None:
            raise ToolError("not_found", f"joint {name!r}: not in {asm.Label} — asm_list names them.")
        kind = str(getattr(j, "JointType", "")).lower()
        if kind not in ("revolute", "slider", "cylindrical"):
            raise ToolError("invalid_input", f"{j.Label} is {kind}: a sweep moves a revolute (turning, degrees), slider or cylindrical (sliding, mm) joint.")
        turning = kind == "revolute" or (kind == "cylindrical" and a.get("turn"))
        # left out, the joint's own limits (asm_limits) bound the sweep
        pre = "Angle" if turning else "Length"
        lim_lo = getattr(j, f"{pre}Min", None) if getattr(j, f"Enable{pre}Min", False) else None
        lim_hi = getattr(j, f"{pre}Max", None) if getattr(j, f"Enable{pre}Max", False) else None
        lo = float(a.get("from", lim_lo if lim_lo is not None else 0))
        hi = float(a.get("to", lim_hi if lim_hi is not None else (90 if turning else 10)))
        steps = int(a.get("steps", 12))
        if not 1 <= steps <= 72:
            raise ToolError("invalid_input", f"steps: 1 to 72 (got {steps}); each step checks every pair of parts — for a closer look sweep a shorter from/to range.")
        clearance = float(a.get("clearance", 0))
        p1, e1 = _ref_element(j.Reference1)
        p2, e2 = _ref_element(j.Reference2)
        grounded = _grounded(asm)
        # The part that moves: the second, unless it is the grounded one.
        fixed_side, moving, el = (p1, p2, e1) if p2 not in grounded else (p2, p1, e2)
        ax = _axis(el) if el is not None else None
        if ax is None or moving is None:
            raise ToolError("failed", f"The axis of {j.Label} could not be read from its elements.")
        centre, axis = ax
        axis = V(axis)
        axis.normalize()
        # What moves with it: parts joined to it by other joints, short of
        # grounded parts and the part it turns on.
        group, todo = {moving.Name: moving}, [moving]
        COUPLE = ("gears", "belt", "rackpinion", "screw")
        all_j = [x for x in _joints(asm).Group if x is not j and getattr(x, "ObjectToGround", None) is None]
        couplings = [x for x in all_j if str(getattr(x, "JointType", "")).lower() in COUPLE]
        # a coupling drives its other part, it does not carry it along
        others = [x for x in all_j if x not in couplings]
        while todo:
            cur = todo.pop()
            for x in others:
                q1, _ = _ref_element(getattr(x, "Reference1", None))
                q2, _ = _ref_element(getattr(x, "Reference2", None))
                for here, there in ((q1, q2), (q2, q1)):
                    if here is not None and there is not None and here.Name == cur.Name and there.Name not in group and there not in grounded and there is not fixed_side:
                        group[there.Name] = there
                        todo.append(there)
        # Parts driven through a coupling: each on its own joint (revolute or
        # slider to something that stays), moved by the coupling's ratio.
        driven = []
        for c in couplings:
            q1, _ = _ref_element(getattr(c, "Reference1", None))
            q2, _ = _ref_element(getattr(c, "Reference2", None))
            if q1 is None or q2 is None:
                continue
            if q1.Name in group and q2.Name not in group:
                dvn, first = q2, True
            elif q2.Name in group and q1.Name not in group:
                dvn, first = q1, False
            else:
                continue
            own = None
            for x in others:
                r1_, e1_ = _ref_element(getattr(x, "Reference1", None))
                r2_, e2_ = _ref_element(getattr(x, "Reference2", None))
                if str(getattr(x, "JointType", "")).lower() not in ("revolute", "slider", "cylindrical"):
                    continue
                if r1_ is not None and r1_.Name == dvn.Name and (r2_ is None or r2_.Name not in group):
                    own = (x, e1_)
                elif r2_ is not None and r2_.Name == dvn.Name and (r1_ is None or r1_.Name not in group):
                    own = (x, e2_)
                if own:
                    break
            if own is None or own[1] is None:
                continue
            dax = _axis(own[1])
            if dax is None:
                continue
            ck = str(c.JointType).lower()
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
            dv = V(dv)
            dv.normalize()
            driven.append({"part": dvn, "how": how, "factor": factor, "centre": dc, "axis": dv, "via": c.Label})
        kept = {o.Name: o.Placement.copy() for o in _parts(asm)}
        out_steps = []
        try:
            # values from where the joint was made: an asm_pose since is taken off
            posed = float(getattr(j, "AgentLinkPose", 0.0) or 0.0)
            for k in range(steps + 1):
                v = lo + (hi - lo) * k / steps
                if turning:
                    r = FreeCAD.Rotation(axis, v - posed)
                    move = FreeCAD.Placement(centre - r.multVec(centre), r)
                else:
                    move = FreeCAD.Placement(axis * (v - posed), FreeCAD.Rotation())
                for o in group.values():
                    o.Placement = move.multiply(kept[o.Name])
                row = {"at": round(v, 3)}
                for d in driven:
                    amount = (v - posed) * d["factor"]
                    if d["how"] == "turn":
                        r = FreeCAD.Rotation(d["axis"], amount)
                        dm = FreeCAD.Placement(d["centre"] - r.multVec(d["centre"]), r)
                    else:
                        dm = FreeCAD.Placement(d["axis"] * amount, FreeCAD.Rotation())
                    d["part"].Placement = dm.multiply(kept[d["part"].Name])
                    row.setdefault("driven", {})[d["part"].Label] = round(amount, 3)
                doc().recompute()
                hits, near = _overlaps(_parts(asm), clearance)
                if hits:
                    row["overlaps"] = [{"parts": h["parts"], "volume": h["volume"]} for h in hits]
                if clearance > 0 and near:
                    row["closer"] = near
                out_steps.append(row)
        finally:
            for o in _parts(asm):
                if o.Name in kept:
                    o.Placement = kept[o.Name]
            doc().recompute()
            _status(asm)
        unit = "degrees" if turning else "mm"
        bad = [r["at"] for r in out_steps if r.get("overlaps")]
        clear_run = []
        for r in out_steps:
            if r.get("overlaps"):
                break
            clear_run.append(r["at"])
        out = {"joint": j.Label, "kind": kind, "unit": unit, "from": lo, "to": hi, "moves": sorted(o.Label for o in group.values()),
               **({"driven": [{"part": d["part"].Label, "via": d["via"], d["how"] + "s": "degrees" if d["how"] == "turn" else "mm",
                               "per": round(d["factor"], 5)} for d in driven]} if driven else {}),
               "axis": {"through": [round(c, 3) for c in centre], "along": [round(c, 4) for c in axis]}, "steps": out_steps,
               "verdict": "collides" if bad else "clear",
               "note": f"{' and '.join(sorted(o.Label for o in group.values()))} turned (or slid) about the joint's axis and put back after. Steps are {abs(hi - lo) / steps:g} {unit} apart: a collision between two steps is not seen — more steps to look closer. A chain of moving joints beyond this one is carried along rigidly, not solved."}
        if bad:
            out["collidesAt"] = bad
            out["clearFromStart"] = [clear_run[0], clear_run[-1]] if clear_run else None
        return out

    def asm_joint_remove(a):
        asm = _assembly(doc(), a.get("assembly"))
        name = a.get("joint")
        hit = next((j for j in _joints(asm).Group if name in (j.Label, j.Name)), None)
        if hit is None:
            raise ToolError("not_found", f"joint {name!r} is not in {asm.Label}: asm_list lists its joints (a grounding is taken off with asm_ground {{ part, grounded: false }}).")
        doc().removeObject(hit.Name)
        doc().recompute()
        code, said = _status(asm)
        return {"assembly": asm.Label, "removed": name, "solve": said}

    def asm_check(a):
        asm = _assembly(doc(), a.get("assembly"))
        clearance = picks.num(a.get("clearance", 0), "clearance")
        code, said = _status(asm)
        parts, hidden, left = _check_parts(asm)
        hits, near = _overlaps(parts, clearance)
        # each part's own object (a linked part's is its link), where it is the assembly's own
        own = [x for x in (getattr(o, "obj", o) for o in parts) if x in asm.Group]
        free = [o.Label for o in own if o not in _grounded(asm) and not asm.isPartConnected(o)] if hasattr(asm, "isPartConnected") else []
        out = {"assembly": asm.Label, "solve": said, "parts": len(parts), "overlaps": hits}
        if hidden:
            out["hidden"] = f"checked though hidden: {', '.join(hidden)}"
        if left:
            out["notChecked"] = f"no solid to check: {', '.join(left)}"
        if clearance > 0:
            out["closerThan"] = {"clearance": clearance, "pairs": near}
        if free:
            out["notConnected"] = free
            out["note"] = "Parts joined to nothing grounded float free: a joint to the grounded part, or asm_ground."
        real = [h for h in hits if not h.get("thread")]
        if len(real) < len(hits):
            out["threads"] = len(hits) - len(real)
        out["verdict"] = "clear" if not real and said == "solved" else "fix"
        return out

    part_end = {"type": "object", "description": "{ part, element } — element \"Face6\" or a query { kind: face|edge, normal, near, radius, type } as shape_query takes; near picks the closest of several."}
    asm_ref = {"type": "string", "description": "The assembly's label; may be left out when there is one."}
    return [
        Tool("asm_new", "Put bodies together in a new assembly (FreeCAD's Assembly workbench): parts by label — the bodies themselves move into it (not links), and a body is in one assembly only. The first is grounded (held fixed) unless ground names another or is false; with nothing grounded no joint solves. Reply: assembly, parts, grounded. Then asm_joint between them.",
             obj({"parts": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}, "ground": {}}, ["parts"]), asm_new, changes=True),
        Tool("asm_add", "Put more bodies into an assembly: parts by label (moved in, not linked; ones already in are skipped). They float free until asm_joint ties them to a grounded part. Reply: added, parts.", obj({"assembly": asm_ref, "parts": {"type": "array", "items": {"type": "string"}}}, ["parts"]), asm_add, changes=True),
        Tool("asm_ground", "Hold a part fixed where it stands (grounded: true, the default) or let it move again (false). An assembly needs at least one grounded part: with none every solve answers \"no part is grounded\". Reply: grounded, every part held.", obj({"assembly": asm_ref, "part": {"type": "string"}, "grounded": {"type": "boolean"}}, ["part"]), asm_ground, changes=True),
        Tool("asm_joint",
             "Join two parts and solve (needs a grounded part): kind fixed (no motion), revolute (turns about the joint's axis), cylindrical (turns and slides), slider (slides only), ball, distance (distance mm between the elements; round faces count from their surface), parallel, perpendicular, angle (angle degrees, 90); couplings, which tie one motion to another for asm_sweep and need each part's own revolute or slider too: rackpinion (radius1, the pinion's pitch radius), screw (pitch mm a turn), gears and belt (radius1, radius2 — read off round edges when left out). a and b each a part and a face or edge on it — a flat face puts the joint at its middle along its normal; a round edge or cylindrical face, on its axis. offset mm along b's joint normal and rotate degrees about it; reverse: true turns the moved part over (false keeps FreeCAD's way; left out, it is turned over when that stops parts overlapping). Which part moves: the one not yet joined to a grounded part (a when neither is), with what is joined to it; a grounded part never. Reply: joint, solve, moved { part: from, to, by }, flipped, overlaps with a warning. Unsolved is refused, nothing kept. FreeCAD 1.1's solver answers only solved or solver error — not freedom left, nor a joint that repeats another: asm_check and asm_sweep show what still moves.",
             obj({"assembly": asm_ref, "kind": {"type": "string", "enum": OFFERED}, "a": part_end, "b": part_end, "offset": {"type": "number"}, "rotate": {"type": "number"}, "distance": {"type": "number"}, "angle": {"type": "number"}, "radius1": {"type": "number"}, "radius2": {"type": "number"}, "pitch": {"type": "number"}, "reverse": {"type": "boolean"}, "name": {"type": "string"}}, ["kind", "a", "b"]),
             asm_joint, changes=True),
        Tool("asm_list", "An assembly: parts [{ part, placement { at, axis, angle degrees }, grounded }], joints [{ joint, kind, a, b as Part.Element, suppressed }] and solve. It runs the solver to answer solve, which puts a part dragged off its joints back; nothing else changes.", obj({"assembly": asm_ref}), asm_list),
        Tool("asm_joint_remove", "Remove a joint (by label or object name; asm_list lists them) and solve again. Parts stay where they stand; one left joined to nothing grounded floats free (asm_check: notConnected). Reply: removed, solve.", obj({"assembly": asm_ref, "joint": {"type": "string"}}, ["joint"]), asm_joint_remove, changes=True),
        Tool("asm_sweep", "Move a revolute joint through angles (from, to degrees; 0 to 90, or its asm_limits) or a slider or cylindrical one along its axis (mm; 0 to 10; turn: true turns a cylindrical) in steps (12, at most 72), checking every pair of parts for overlap at each (clearance mm also lists pairs closer). from and to count from where the joint stands now. The moving part carries the parts joined beyond it rigidly; gears, belt, rackpinion and screw drive theirs by ratio; a closed loop (a four-bar) is not followed. Reply: moves, driven, axis, steps [{ at, overlaps, closer }], verdict clear | collides, collidesAt, clearFromStart; every part is put back. Does the lid open fully, does the arm swing past the post. Each step cuts every pair of parts (a call is dropped after about 80 s): with many parts, fewer steps or a shorter range, not a job.",
             obj({"assembly": asm_ref, "joint": {"type": "string"}, "from": {"type": "number"}, "to": {"type": "number"}, "steps": {"type": "integer"}, "clearance": {"type": "number"}, "turn": {"type": "boolean"}}, ["joint"]), asm_sweep),
        Tool("asm_check", "Check an assembly: every part of it, shown or hidden (hidden names those checked though hidden), inside App::Parts and sub-assemblies and through links too, each where it stands: solve; overlaps [{ parts, volume mm³, at }] (a screw's thread in a tapped hole is marked thread and not counted against the verdict); with clearance mm, closerThan pairs; notConnected, parts joined to nothing grounded (the solver leaves them and their joints out without a word). verdict clear | fix. Freedom left is not counted (FreeCAD 1.1 does not report it): asm_sweep shows what a joint lets move. Every pair of parts is cut against each other, so dozens of parts take a while. view_render shows it; section cuts it open at a fit.",
             obj({"assembly": asm_ref, "clearance": {"type": "number"}}), asm_check),
    ]
