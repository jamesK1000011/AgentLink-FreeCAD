# SPDX-License-Identifier: LGPL-2.1-or-later
# More of the Part workbench, beside model.py: wires and curves (FreeCAD's
# own parametric line, circle, ellipse, polygon, helix, spiral and plane, or
# a B-spline through points), splitting (slice, Boolean fragments, XOR),
# compounds made and taken apart, refine and repair, a face from wires,
# ruled surfaces, projection onto a face, a stack of cross-sections, a
# primitive attached to a face, and a mesh made a solid.

import FreeCAD
import Part

from .. import geometry as geo
from .. import paths, pointfiles, runners
from . import picks

GROUP = "model"
INFO = ("Part modelling: primitives, wires and curves (helix, spiral …), booleans, split / slice / fragments, compounds, move/rotate/mirror/scale/arrays, "
        "fillets and chamfers, offset and shell, extrude, revolve, loft, sweep, ruled surfaces, projection, cross-sections, refine and repair, attachment, mesh to solid.")

V = FreeCAD.Vector


def frame(a):
    """A placement from at [x, y, z] and normal (the curve's Z), as FreeCAD's
    primitives take one."""
    at = picks.vec3(a.get("at"), "at", (0, 0, 0))
    n = picks.direction(a.get("normal"), "normal", (0, 0, 1))
    return FreeCAD.Placement(at, FreeCAD.Rotation(V(0, 0, 1), n))


def stats_of(sh):
    """A made wire's, face's or body's counts and sizes, as part_wire and its
    kin answer them: length, area and volume only where it has edges, faces
    or solids; closed: every wire of it is."""
    out = {"edges": len(sh.Edges), "wires": len(sh.Wires), "faces": len(sh.Faces), "solids": len(sh.Solids)}
    if sh.Edges:
        out["length"] = round(sum(e.Length for e in sh.Edges), 4)
    if sh.Faces:
        out["area"] = round(sh.Area, 4)
    if sh.Solids:
        out["volume"] = round(sh.Volume, 4)
    try:
        out["closed"] = bool(sh.Wires and all(w.isClosed() for w in sh.Wires))
    except Exception:
        pass
    bb = sh.BoundBox
    out["box"] = [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]
    return out


def tools(session):
    """These Part tools are data (agentlink/data/tools.json, "family":
    "model_more"; run by agentlink/runners.py's steps runner): each entry has
    the tool's words, its checks with their refusals, the order of its steps
    and its answer. What is here is what those entries call by name: the
    family's finishing code and the small functions that are geometry or
    FreeCAD's API (docs/data-tools.md)."""
    s = session
    doc = lambda: s.doc  # noqa: E731

    def added(o, tool, extra=None):
        """A made object's answer: recompute, FreeCAD's refusal with nothing
        kept when it is not valid, the snapshot, then its label, type and
        stats_of its shape, the tool's own fields (extra) and the step."""
        return picks.finish(s, tool, lambda: {"object": o.Label, "type": o.TypeId.split("::")[-1], **stats_of(o.Shape)}, objs=[o], refuse="FreeCAD refused it: {msg} — nothing was kept.", extra=extra)

    def settled(tool, read=None):
        """The tail of a tool that has already recomputed: the snapshot, the answer (read) and the step."""
        return picks.finish(s, tool, read, recompute=False)

    def new_obj(kind, label):
        """A new object of that type under a label not yet taken (its name the label without spaces)."""
        lab = s.unique(label)
        o = doc().addObject(kind, label.replace(" ", ""))
        o.Label = lab
        return o

    # ---- wires and curves ----

    def outline_file(f, key=None):
        """The one outline of a points file in the session's folder (.json or .csv; key picks one list), read on this side."""
        return pointfiles.one_outline(paths.in_file(s, "part_wire", f, "points_file"), key, "points_file")

    def fit_of(c, pts):
        """How far the curve lies from the points it was drawn through."""
        try:
            worst = max((c.value(c.parameter(p)) - p).Length for p in pts)
            return {"maxDistance": round(worst, 5)}
        except Exception:
            return None

    # ---- split, compounds ----

    def split_features():
        """BOPTools' split features (slice, Boolean fragments, XOR), loaded when a split is asked."""
        import BOPTools.SplitFeatures as SF

        return SF

    def bop_feature(proxy, view, name):
        """A BOPTools feature in the session's document. BOPTools' own
        make* add to FreeCAD.ActiveDocument, which is not always this one;
        this is what they do, on the right document."""
        f = doc().addObject("Part::FeaturePython", name)
        proxy(f)
        if FreeCAD.GuiUp and getattr(f, "ViewObject", None) is not None:
            view(f.ViewObject)
        return f

    def explode_into(o, base):
        """Each solid of o copied out as a body of its own ("base 1", "base 2" …), o hidden; the new bodies' labels."""
        made = []
        for i, sol in enumerate(o.Shape.Solids, 1):
            n = doc().addObject("Part::Feature", "Body")
            n.Label = s.unique(f"{base} {i}")
            n.Shape = sol.copy()
            made.append(n.Label)
        if hasattr(o, "Visibility"):
            o.Visibility = False
        doc().recompute()
        return made

    # ---- sections ----

    def section_area(ws):
        """The material area of one cross-section: its closed outlines as
        faces, a loop inside another taken as a hole (a tube's section is
        the ring, not the two discs added)."""
        loops = [w for w in ws if w.isClosed()]
        if not loops:
            return 0.0
        try:
            return round(Part.makeFace(loops, "Part::FaceMakerBullseye").Area, 3)
        except Exception:
            return round(sum(Part.Face(w).Area for w in loops), 3)

    # ---- mesh to solid ----

    def mesh_module():
        """FreeCAD's Mesh module, loaded when a mesh is asked for (a build without it fails here, before anything is read)."""
        import Mesh

        return Mesh

    def stem(p):
        """A file's name without its folder and extension."""
        import os

        return os.path.splitext(os.path.basename(p))[0]

    def isfile(p):
        """Whether p is a file that is there."""
        import os

        return os.path.isfile(p)

    def attach_check(o, tgt, sub, mode):
        """Why o cannot attach to (tgt, sub) as mode, worked out on a copy of
        its attacher before anything is set (FreeCAD prints a red
        "PositionBySupport: …" in the Report view for every attachment
        property set that does not fit); None when it fits, or when this
        FreeCAD gives no attacher to ask."""
        if mode == "Deactivated":
            return None
        try:
            att = o.Attacher  # already a copy; copied again so the check plainly changes nothing of o
            if att is None:
                return None
            eng = att.copy()
            eng.References = [(tgt, sub)]
            eng.Mode = mode
        except Exception:  # noqa: BLE001 — no copy to ask: the recompute's check stays
            return None
        try:
            eng.calculateAttachedPlacement(o.Placement)
        except Exception as e:  # noqa: BLE001 — the attacher's own reason
            return str(e) or type(e).__name__
        return None

    # What the tools' entries (agentlink/data/tools.json, "family": "model_more") call by name.
    # FreeCAD's and Part's own are reached when called, not here: the module may be a trimmed one.
    helpers = {"doc": doc, "unique": lambda label: s.unique(label), "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps),
               "added": added, "settled": settled, "new_obj": new_obj,
               "find": lambda ref, what="object": picks.find(doc(), ref, what), "shaped": lambda ref, what="body": picks.shaped(doc(), ref, what),
               "solid_body": lambda ref: picks.solid_body(s, ref), "resolve": lambda ref: picks.resolve(s, ref), "split_ref": picks.split_ref,
               "element": picks.element, "bake": lambda base, shape, name=None: picks.bake(s, base, shape, name), "num": picks.num, "vec3": picks.vec3,
               "direction": picks.direction, "placement_json": picks.placement_json, "vec": lambda v: geo.vec(v), "soundness": lambda sh: geo.soundness(sh), "refine_harm": lambda b, r: geo.refine_harm(b, r),
               "local": lambda p: paths.local(s, p),
               # FreeCAD's own
               "V": V, "placement": lambda *x: FreeCAD.Placement(*x), "rotation": lambda *x: FreeCAD.Rotation(*x), "as_wire": lambda edges: Part.Wire(edges),
               "as_shell": lambda faces: Part.Shell(faces), "make_shell": lambda faces: Part.makeShell(faces), "as_solid": lambda shell: Part.makeSolid(shell),
               "compound": lambda shapes: Part.Compound(shapes), "flat_face": lambda wires: Part.makeFace(wires, "Part::FaceMakerBullseye"),
               "empty_shape": lambda: Part.Shape(), "bspline": lambda: Part.BSplineCurve(), "in_order": lambda edges: Part.__sortEdges__(edges),
               "read_mesh": lambda p: mesh_module().Mesh(p),
               # the family's
               "frame": frame, "stats_of": stats_of, "outline_file": outline_file, "fit_of": fit_of, "split_features": split_features, "bop_feature": bop_feature,
               "explode_into": explode_into, "section_area": section_area, "mesh_module": mesh_module, "stem": stem, "isfile": isfile,
               "attach_check": attach_check}
    return runners.tools(GROUP, s, helpers, family="model_more")
