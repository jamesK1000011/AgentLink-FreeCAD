# SPDX-License-Identifier: LGPL-2.1-or-later
# The rest of the Part workbench headless: section curves where bodies or a
# plane meet a body, 2D offsets of wires and flat faces, elements copied out
# as bodies of their own (and shells and solids built from faces), faces
# defeatured away, shapes reversed or closed into solids, and datums (point,
# line, plane, coordinate system) to attach and measure from.

import FreeCAD
import Part

from .. import runners
from . import picks

GROUP = "model"
INFO = "Part extras: sections, 2D offsets, elements copied out, shells/solids from faces, defeaturing, reverse/solid fixes, datums."

V = FreeCAD.Vector


def _sew(shape, tol):
    """Faces joined where they meet within tol mm. Returns the joined shape.

    sewShape ignores its tolerance on FreeCAD 1.1 (a 0.05 mm gap stays open
    at 0.1), so when it leaves the shell open the faces are fused with a
    fuzzy value of tol instead: edges within tol become one, wider gaps stay
    open."""
    faces = [f.copy() for f in shape.Faces]
    if not faces:
        return shape
    sew = Part.makeCompound([f.copy() for f in faces])
    try:
        sew.sewShape(float(tol))
    except Exception:
        pass
    if sew.Shells and all(x.isClosed() for x in sew.Shells):
        return sew
    if len(faces) < 2:
        return sew
    try:
        fused = faces[0].multiFuse(faces[1:], float(tol))
        shell = Part.Shell(fused.Faces)
        if shell.isClosed() or not sew.Shells:
            return shell
    except Exception:
        pass
    return sew


def doc(s):
    return s.doc


def plane_face(spec, size, near=None):
    """A square of the plane through at with that normal, large enough to
    cross the body, centred where the body's centre falls on it."""
    n = picks.direction(spec.get("normal", [0, 0, 1]), "plane.normal")
    at = picks.vec3(spec.get("at", [0, 0, 0]), "plane.at")
    pl = Part.makePlane(size * 2, size * 2, V(), n)
    c = pl.BoundBox.Center
    target = near if near is not None else at
    target = target - n * n.dot(target - at)  # onto the plane
    pl.translate(target - c)
    return pl


def shape_stats(sh):
    """A made shape's counts and sizes as these tools answer them: length,
    area and volume only where it has edges, faces or solids, and how many
    closed loops its edges join into."""
    out = {"edges": len(sh.Edges), "faces": len(sh.Faces), "solids": len(sh.Solids)}
    if sh.Edges:
        out["length_mm"] = round(sum(e.Length for e in sh.Edges), 3)
    if sh.Faces:
        out["area_mm2"] = round(sh.Area, 3)
    if sh.Solids:
        out["volume_mm3"] = round(sh.Volume, 3)
    loops = 0
    try:
        for es in Part.sortEdges(list(sh.Edges)):
            if Part.Wire(es).isClosed():
                loops += 1
    except Exception:
        loops = sum(1 for w in sh.Wires if w.isClosed())
    out["closedLoops"] = loops
    return out


def add(s, shape, label):
    """shape as a new plain body under a label not yet taken, recomputed."""
    o = doc(s).addObject("Part::Feature", "Shape")
    o.Shape = shape
    o.Label = s.unique(label)
    doc(s).recompute()
    return o


# FreeCAD's datum types by kind: Part's own first, PartDesign's where a build has only those.
DATUMS = {"point": ["Part::DatumPoint", "PartDesign::Point"], "line": ["Part::DatumLine", "PartDesign::Line"],
          "plane": ["Part::DatumPlane", "PartDesign::Plane"],
          "csys": ["Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem"]}


def datum_shape(kind):
    """The plain shape that stands for a datum on a FreeCAD without datum
    objects: a vertex, a 100 mm line along z, a 100 mm square in xy, or
    three 20 mm lines along the axes (csys), all about the origin."""
    if kind == "point":
        return Part.Vertex(V())
    if kind == "line":
        return Part.makeLine(V(0, 0, -50), V(0, 0, 50))
    if kind == "plane":
        return Part.makePlane(100, 100, V(-50, -50, 0))
    return Part.makeCompound([Part.makeLine(V(), V(20, 0, 0)), Part.makeLine(V(), V(0, 20, 0)), Part.makeLine(V(), V(0, 0, 20))])


def is_round(edge):
    """Whether an edge is a circle's or an arc's: it has an axis and a centre
    of curvature for a datum to take; a straight one has not."""
    try:
        return isinstance(edge.Curve, Part.Circle)
    except Exception:
        return False


def tools(s):
    """These Part tools are data (agentlink/data/tools.json, "family":
    "part_more"; run by agentlink/runners.py's steps runner): each entry has
    the tool's words, its checks with their refusals, the order of its steps
    and its answer. What is here is what those entries call by name
    (docs/data-tools.md)."""

    def picked(refs, what):
        """Each reference's shape, in order: an element as itself, a whole
        object as its faces where faces are wanted (what "faces"), else as
        its whole shape."""
        out = []
        for r in refs:
            label, sub, sh = picks.resolve(s, r)
            if sub is None:
                out += list(sh.Faces) if what == "faces" else [sh]
            else:
                out.append(sh)
        return out

    # What the tools' entries (agentlink/data/tools.json, "family": "part_more") call by name.
    # FreeCAD's and Part's own are reached when called, not here: the module may be a trimmed one.
    helpers = {"doc": lambda: doc(s), "unique": lambda label: s.unique(label), "snapshot": lambda tool: s.snapshot(tool),
               "find": lambda ref, what="object": picks.find(doc(s), ref, what), "shaped": lambda ref, what="body": picks.shaped(doc(s), ref, what),
               "solid_body": lambda ref: picks.solid_body(s, ref), "resolve": lambda ref: picks.resolve(s, ref), "split_ref": picks.split_ref,
               "element": picks.element, "bake": lambda base, shape, name=None: picks.bake(s, base, shape, name), "direction": picks.direction,
               "ref_list": picks.ref_list, "placement_of": picks.placement, "placement_json": picks.placement_json,
               # FreeCAD's own
               "V": V, "rotation": lambda *x: FreeCAD.Rotation(*x), "as_wire": lambda edges: Part.Wire(edges), "sort_edges": lambda edges: Part.sortEdges(edges),
               "compound": lambda shapes: Part.makeCompound(shapes), "make_shell": lambda faces: Part.makeShell(faces), "as_solid": lambda shell: Part.makeSolid(shell),
               "flat_face": lambda wires: Part.makeFace(wires, "Part::FaceMakerBullseye"),
               # the family's
               "plane_face": plane_face, "shape_stats": shape_stats, "add_shape": lambda shape, label: add(s, shape, label), "picked": picked, "sewn": _sew,
               "DATUMS": DATUMS, "datum_shape": datum_shape, "is_round": is_round}
    return runners.tools(GROUP, s, helpers, family="part_more")
