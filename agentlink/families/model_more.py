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
from .. import paths, pointfiles
from ..protocol import Tool, ToolError, bad
from ..tools import obj
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
    s = session
    doc = lambda: s.doc  # noqa: E731

    def added(o, tool, extra=None):
        return picks.finish(s, tool, lambda: {"object": o.Label, "type": o.TypeId.split("::")[-1], **stats_of(o.Shape)}, objs=[o], refuse="FreeCAD refused it: {msg} — nothing was kept.", extra=extra)

    def new_obj(kind, label):
        lab = s.unique(label)
        o = doc().addObject(kind, label.replace(" ", ""))
        o.Label = lab
        return o

    # ---- wires and curves ----

    def wire_points(a):
        """points, or points_file (+ key) read on this side."""
        if a.get("points_file") is not None:
            if a.get("points") is not None:
                raise bad("points or points_file, not both.")
            f = a["points_file"]
            if not isinstance(f, str) or not f.strip():
                raise bad("points_file: a file's path (.json or .csv).")
            return pointfiles.one_outline(paths.in_file(s, "part_wire", f, "points_file"), a.get("key"), "points_file")
        return a.get("points") or []

    def fit_of(c, pts):
        """How far the curve lies from the points it was drawn through."""
        try:
            worst = max((c.value(c.parameter(p)) - p).Length for p in pts)
            return {"maxDistance": round(worst, 5)}
        except Exception:
            return None

    def part_wire(a):
        kind = a.get("kind")
        fit = None
        name = a.get("name") or kind.capitalize() if kind else None
        if kind == "line":
            p, q = picks.vec3(a.get("from"), "from"), picks.vec3(a.get("to"), "to")
            if (p - q).Length < 1e-9:
                raise bad("from and to: two different points.")
            o = new_obj("Part::Line", name)
            o.X1, o.Y1, o.Z1 = p.x, p.y, p.z
            o.X2, o.Y2, o.Z2 = q.x, q.y, q.z
        elif kind in ("circle", "arc"):
            r = picks.number(a, "radius", gt=0, msg="radius: above 0.")
            o = new_obj("Part::Circle", name)
            o.Radius = r
            if kind == "arc":
                a1, a2 = picks.num(a.get("start", 0), "start"), picks.num(a.get("end", 90), "end")
                if not (0 <= a1 <= 360 and 0 <= a2 <= 360) or abs(a1 - a2) < 1e-9:
                    # Part::Circle keeps Angle1 and Angle2 within 0 … 360.
                    raise bad("start and end: degrees within 0 … 360, counter-clockwise from the circle's x, and not equal (an arc through 0 runs start 300, end 60).")
                o.Angle1, o.Angle2 = a1, a2
            o.Placement = frame(a)
        elif kind == "ellipse":
            major, minor = picks.num(a.get("major"), "major"), picks.num(a.get("minor"), "minor")
            if minor > major or minor <= 0:
                raise bad("major and minor: the ellipse's full length and width in mm, major ≥ minor > 0 (major lies along its x).")
            o = new_obj("Part::Ellipse", name)
            o.MajorRadius, o.MinorRadius = major / 2, minor / 2
            o.Placement = frame(a)
        elif kind == "polygon":
            if a.get("points") is not None and a.get("radius") is None:
                raise bad("polygon is a regular polygon (sides, radius to corners). For a shape through your points: part_wire { kind: \"polyline\", points, closed: true }, or part_extrude { profile: { points } } for a solid at once.")
            n = int(a.get("sides", 6))
            if n < 3:
                raise bad("sides: 3 or more.")
            rad = picks.number(a, "radius", gt=0, msg="radius: centre to a corner, above 0 mm.")
            o = new_obj("Part::RegularPolygon", name)
            o.Polygon = n
            o.Circumradius = rad
            o.Placement = frame(a)
        elif kind == "helix":
            pitch = picks.number(a, "pitch", gt=0, msg="pitch: mm a turn, above 0.")
            height = picks.number(a, "height", gt=0, msg="height: mm, above 0.")
            rad = picks.number(a, "radius", gt=0, msg="radius: mm, above 0.")
            if height / pitch > 1e4:
                # Part::Helix: "Number of turns too high (> 1e4)"
                raise bad(f"height / pitch is {height / pitch:.0f} turns: FreeCAD's helix takes 10000 at most — a larger pitch or a lower height.")
            taper = picks.num(a.get("taper") or 0, "taper")
            if abs(taper) > 89.9:
                raise bad("taper: degrees the helix widens (+) or narrows (-) by, within -89.9 … 89.9.")
            o = new_obj("Part::Helix", name)
            o.Pitch, o.Height, o.Radius = pitch, height, rad
            if taper:
                o.Angle = taper
            if a.get("leftHanded"):
                o.LocalCoord = "Left-handed"
            o.Placement = frame(a)
        elif kind == "spiral":
            growth = picks.number(a, "growth", ge=0, msg="growth: mm the radius grows a turn, 0 or more.")
            turns = picks.number(a, "turns", gt=0, msg="turns: above 0.")
            rad = picks.number(a, "radius", 1, ge=0, msg="radius: where it starts, 0 or more mm.")
            o = new_obj("Part::Spiral", name)
            o.Growth, o.Rotations, o.Radius = growth, turns, rad
            o.Placement = frame(a)
        elif kind == "plane":
            ln = picks.number(a, "length", gt=0, msg="length: along the plane's x, above 0 mm.")
            wd = picks.number(a, "width", gt=0, msg="width: along the plane's y, above 0 mm.")
            o = new_obj("Part::Plane", name)
            o.Length, o.Width = ln, wd
            o.Placement = frame(a)
        elif kind == "polyline":
            pts = [picks.vec3(p, "points") for p in wire_points(a)]
            closed = bool(a.get("closed"))
            if len(pts) > 2 and (pts[0] - pts[-1]).Length < 1e-9:
                pts, closed = pts[:-1], True  # given closed: the last point repeats the first
            if len(pts) < (3 if closed else 2):
                raise bad("points: two or more [x, y, z] corners (three or more when closed).")
            if any((pts[i] - pts[i + 1]).Length < 1e-9 for i in range(len(pts) - 1)):
                raise bad("points: two corners in a row are the same point.")
            o = new_obj("Part::Polygon", name)
            o.Nodes = pts
            o.Close = closed
        elif kind == "bspline":
            pts = [picks.vec3(p, "points") for p in wire_points(a)]
            closed = bool(a.get("closed"))
            if len(pts) > 3 and (pts[0] - pts[-1]).Length < 1e-9:
                pts, closed = pts[:-1], True  # given closed: the last point repeats the first
            if len(pts) < (3 if closed else 2):
                raise bad("points: two or more [x, y, z] it passes through (three or more when closed).")
            if any((pts[i] - pts[i + 1]).Length < 1e-9 for i in range(len(pts) - 1)):
                raise bad("points: two in a row are the same point.")
            c = Part.BSplineCurve()
            try:
                # Closed: a periodic curve, smooth through the seam too.
                c.interpolate(pts, PeriodicFlag=closed)
            except Exception as e:
                raise bad(f"points: no smooth curve through them ({e}) — points far apart along it, in order, none doubled.")
            o = new_obj("Part::Feature", name)
            w = Part.Wire([c.toShape()])
            if closed and not w.isClosed():
                raise ToolError("failed", "The B-spline did not close — check the points run round in order.")
            o.Shape = w
            fit = fit_of(c, pts)
        else:
            raise bad("kind: line { from, to } | circle { radius } | arc { radius, start, end } | ellipse { major, minor } | polygon { sides, radius } | polyline { points, closed } | helix { pitch, height, radius } | spiral { growth, turns, radius } | plane { length, width } | bspline { points, closed }.")
        extra = {"use": "A profile or path for part_extrude, part_revolve, part_loft, part_sweep (a helix as a path: a spring or thread), part_ruled."}
        if fit:
            extra["fit"] = fit
        return added(o, "part_wire", extra)

    # ---- split, compounds ----

    def bop_feature(proxy, view, name):
        """A BOPTools feature in the session's document. BOPTools' own
        make* add to FreeCAD.ActiveDocument, which is not always this one;
        this is what they do, on the right document."""
        f = doc().addObject("Part::FeaturePython", name)
        proxy(f)
        if FreeCAD.GuiUp and getattr(f, "ViewObject", None) is not None:
            view(f.ViewObject)
        return f

    def part_split(a):
        import BOPTools.SplitFeatures as SF

        mode = a.get("mode", "slice")

        def named(refs, what):
            out = []
            for r in refs or []:
                if isinstance(r, str) and picks.split_ref(r)[1]:
                    raise bad(f"{what}: {r!r} is an element — whole objects by name here. part_extract {{ refs: [\"{r}\"] }} copies a face out as an object that can cut; part_wire {{ kind: \"plane\" }} makes a plane.")
                out.append(picks.shaped(doc(), r, what))
            return out

        objs = named(a.get("bodies"), "bodies")
        if mode == "slice":
            if len(objs) != 1:
                raise bad("slice: bodies [the one to cut] (one), tools [the objects that cut it: a plane from part_wire, a face copied out by part_extract, other bodies].")
            tl = named(a.get("tools"), "tools")
            if not tl:
                raise bad("tools: the objects that cut it, by name — a plane (part_wire { kind: \"plane\" }, larger than the body's section), a face copied out (part_extract), or bodies.")
            f = bop_feature(SF.FeatureSlice, SF.ViewProviderSlice, s.unique(a.get("name") or "Slice").replace(" ", "_"))
            f.Base = objs[0]
            f.Tools = tl
            f.Mode = "Split" if a.get("split", True) else "Standard"
        elif mode in ("fragments", "xor"):
            if len(objs) < 2:
                raise bad(f"{mode}: bodies, two or more by name (tools is for mode slice).")
            if mode == "fragments":
                f = bop_feature(SF.FeatureBooleanFragments, SF.ViewProviderBooleanFragments, s.unique(a.get("name") or "Fragments").replace(" ", "_"))
            else:
                f = bop_feature(SF.FeatureXOR, SF.ViewProviderXOR, s.unique(a.get("name") or "Xor").replace(" ", "_"))
            f.Objects = objs
            if mode == "fragments" and a.get("split", True):
                f.Mode = "Split"
        else:
            raise bad("mode: slice { bodies [one], tools } | fragments { bodies } | xor { bodies }.")
        doc().recompute()
        if not f.isValid() or f.Shape.isNull():
            msg = f.getStatusString()
            doc().removeObject(f.Name)
            raise ToolError("failed", f"The {mode} failed: {msg} — nothing was kept. The tools must cross the bodies; part_section {{ body, with }} shows whether they meet.")
        pieces = [{"volume": round(x.Volume, 3), "center": geo.vec(x.CenterOfMass)} for x in f.Shape.Solids]
        out = {"object": f.Label, "mode": mode, "pieces": len(pieces), "solids": pieces[:20]}
        if mode == "slice" and pieces and len(objs[0].Shape.Solids) >= len(pieces):
            out["note"] = f"Not cut: still {len(pieces)} piece(s) — the tools do not pass right through {objs[0].Label} (a plane must reach past the body on every side)."
        if a.get("explode"):
            out["bodies"] = explode_into(f, a.get("name") or f.Label)
        for o in objs + (tl if mode == "slice" else []):
            if hasattr(o, "Visibility"):
                o.Visibility = False
        picks.finish(s, "part_split", out, recompute=False)
        if not a.get("explode"):
            out["next"] = "explode: true (or part_compound { explode }) makes each piece a body of its own."
        return out

    def explode_into(o, base):
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

    def part_compound(a):
        if a.get("explode"):
            o = picks.shaped(doc(), a["explode"])
            if len(o.Shape.Solids) < 2:
                raise bad(f"explode: {o.Label} is {len(o.Shape.Solids)} solid, nothing to take apart — it takes a body of several solids (a part_split result, a fuse: false array).")
            made = explode_into(o, a.get("name") or o.Label)
            return picks.finish(s, "part_compound", lambda: {"from": o.Label, "bodies": made}, recompute=False)
        objs = [picks.shaped(doc(), r) for r in (a.get("bodies") or [])]
        if len(objs) < 2:
            raise bad("bodies: two or more objects by name to group into one compound, or explode: the name of a body of several solids.")
        c = new_obj("Part::Compound", a.get("name") or "Compound")
        c.Links = objs
        return added(c, "part_compound", {"of": [o.Label for o in objs], "note": "A compound keeps its parts separate (no fusing): one object to move, export or pattern."})

    # ---- refine, repair, attach ----

    def part_refine(a):
        o = picks.solid_body(s, a.get("body"))
        tip = getattr(o, "Tip", None) if o.TypeId == "PartDesign::Body" else None
        if tip is not None and "Refine" in tip.PropertiesList and not a.get("fix") and not a.get("name"):
            # A PartDesign Body refines itself: its tip feature's Refine,
            # so the history stays and the body stays a Body.
            before = len(o.Shape.Faces)
            tip.Refine = True
            doc().recompute()
            snd = geo.soundness(o.Shape)
            s.snapshot("part_refine")
            return {"body": o.Label, "faces": {"before": before, "after": len(o.Shape.Faces)}, "done": [f"Refine turned on for {tip.Label}, the body's tip (it stays parametric)"],
                    "sound": snd["ok"], **({"problems": snd["problems"]} if not snd["ok"] else {}), "step": len(s.steps)}
        sh = o.Shape
        before = len(sh.Faces)
        tol = float(a.get("tolerance", 0))
        fixed = sh.copy()
        notes = []
        if a.get("fix"):
            try:
                fixed.fix(tol or 1e-3, tol or 1e-3, tol or 1e-3)
                notes.append("fixed")
            except Exception as e:
                notes.append(f"fix failed: {e}")
            if not fixed.Solids and fixed.Shells:
                try:
                    fixed = Part.makeSolid(Part.Shell(fixed.Faces) if len(fixed.Shells) != 1 else fixed.Shells[0])
                    notes.append("closed shell made solid")
                except Exception as e:
                    notes.append(f"no solid from the shell: {e}")
        ref = fixed.removeSplitter()
        o2 = picks.bake(s, o, ref, a.get("name"))
        snd = geo.soundness(o2.Shape)
        return picks.finish(s, "part_refine", lambda: {"body": o2.Label, "faces": {"before": before, "after": len(o2.Shape.Faces)}, "done": notes + ["coplanar faces merged"], "sound": snd["ok"], **({"problems": snd["problems"]} if not snd["ok"] else {})}, recompute=False)

    def part_attach(a):
        o = picks.find(doc(), a.get("body"))
        if "AttachmentOffset" not in o.PropertiesList:
            raise bad(f"body: {o.Label} is a {o.TypeId}, which has no attachment — FreeCAD's own primitives, wires and datums attach (part_primitive, part_wire, part_datum {{ to }}); a modelling result is a plain shape: part_transform or object_align places it.")
        ref = a.get("to")
        if not isinstance(ref, str) or not ref:
            raise bad("to: a face, edge or vertex as \"Body.Face6\" (shape_query finds it), or a whole object's name (a datum from part_datum, a body).")
        head, sub = picks.split_ref(ref)
        if sub is None:
            tgt, sub = picks.find(doc(), ref, "to"), ""
        elif head is None:
            raise bad(f"to: {ref!r} names no object — \"Body.{ref}\".")
        else:
            label, sub, _ = picks.resolve(s, ref)
            tgt = picks.find(doc(), label)
        if tgt is o:
            raise bad("to: another object than itself.")
        # One reference: the modes of FreeCAD's attacher that take a single
        # face (flat), edge, vertex or a whole object's placement.
        mode = a.get("mode") or ("FlatFace" if sub.startswith("Face") else "NormalToEdge" if sub.startswith("Edge") else "Translate" if sub.startswith("Vertex") else "ObjectXY")
        modes = list(o.getEnumerationsOfProperty("MapMode") or [])
        if modes and mode not in modes:
            raise bad(f"mode {mode!r}: not a FreeCAD attachment mode. With one reference — a flat face: FlatFace; an edge: NormalToEdge, FrenetNB, Concentric (a circle or arc); a vertex: Translate; a whole object: ObjectXY, ObjectXZ, ObjectYZ. All: {', '.join(modes)}.")
        prop = "AttachmentSupport" if "AttachmentSupport" in o.PropertiesList else "Support"
        setattr(o, prop, [(tgt, sub)])
        o.MapMode = mode
        o.AttachmentOffset = FreeCAD.Placement(picks.vec3(a.get("offset"), "offset", (0, 0, 0)), FreeCAD.Rotation(V(0, 0, 1), float(a.get("rotate", 0))))
        doc().recompute()
        if not o.isValid():
            raise ToolError("failed", f"{o.Label} would not attach to {ref} as {mode}: {o.getStatusString()} — nothing was changed. With one reference: FlatFace takes a flat face; NormalToEdge or FrenetNB an edge; Concentric a circle or arc; Translate a vertex; ObjectXY a whole object.")
        return picks.finish(s, "part_attach", lambda: {"body": o.Label, "attachedTo": ref, "mode": o.MapMode, "placement": picks.placement_json(o.Placement), "note": f"It follows {tgt.Label} from now on."}, recompute=False)

    # ---- faces, ruled surfaces, projection, sections ----

    def part_face(a):
        refs = a.get("from") or []
        wires = []
        for r in refs:
            o = picks.shaped(doc(), r, "from")
            ws = o.Shape.Wires or ([Part.Wire(Part.__sortEdges__(o.Shape.Edges))] if o.Shape.Edges else [])
            wires += ws
        if not wires:
            raise bad("from: [names] of closed wires or sketches (whole objects) — the outline and any holes inside it.")
        if not all(w.isClosed() for w in wires):
            raise bad(f"from: {sum(1 for w in wires if not w.isClosed())} of the {len(wires)} wires are open — every wire must be closed (part_wire {{ closed: true }}; a sketch's open ends joined).")
        try:
            face = Part.makeFace(wires, "Part::FaceMakerBullseye")
        except Exception as e:
            raise ToolError("failed", f"No face from those wires ({e}): they must be flat, in one plane, and not cross.")
        o = new_obj("Part::Feature", a.get("name") or "Face")
        o.Shape = face
        return added(o, "part_face")

    def part_ruled(a):
        def curve(key):
            # A whole object (its one edge or wire), or one edge of it as
            # Part::RuledSurface's Curve1 / Curve2 take: (object, ["Edge3"]).
            ref = a.get(key)
            if not isinstance(ref, str) or not ref:
                raise bad(f"{key}: an edge or wire by name (a part_wire, a sketch), or one edge of a body as \"Box.Edge3\".")
            head, sub = picks.split_ref(ref)
            if sub is None:
                x = picks.shaped(doc(), ref, key)
                if not x.Shape.Edges:
                    raise bad(f"{key}: {x.Label} has no edge.")
                return (x, [])
            if head is None or not sub.startswith("Edge"):
                raise bad(f"{key}: {ref!r} — an edge with its object, \"Box.Edge3\" (a face has several: name one).")
            x = picks.shaped(doc(), head, key)
            picks.element(x.Shape, sub, x.Label)
            return (x, [sub])

        c1, c2 = curve("a"), curve("b")
        o = new_obj("Part::RuledSurface", a.get("name") or "Ruled")
        o.Curve1, o.Curve2 = c1, c2
        if a.get("reversed"):
            o.Orientation = "Reversed"
        return added(o, "part_ruled", {"note": "A surface, not a solid: surface_thicken gives it thickness."})

    def part_project(a):
        src = picks.shaped(doc(), a.get("shape"), "shape")
        ref = a.get("onto")
        if not isinstance(ref, str) or ".Face" not in ref:
            raise bad("onto: one face with its body, as \"Body.Face6\" (shape_query { kind: \"face\" } finds it).")
        _, _, face = picks.resolve(s, ref)
        d = picks.direction(a.get("direction"), "direction", (0, 0, -1)) if a.get("direction") is not None else None
        edges = src.Shape.Edges
        if not edges:
            raise bad(f"shape: {src.Label} has no edges to project — a wire, sketch or body by name.")
        # OCCT projects one edge or wire at a time
        got, missed = [], 0
        for w in (src.Shape.Wires or [Part.Wire([e]) for e in edges]):
            try:
                r = face.makeParallelProjection(w, d) if d is not None else face.project(w.Edges)
                if not r.isNull() and r.Edges:
                    got += r.Edges
                else:
                    missed += 1
            except Exception:
                missed += 1
        res = Part.Compound(got) if got else Part.Shape()
        if res.isNull() or not res.Edges:
            raise ToolError("failed", f"Nothing of {src.Label} landed on {ref}: " + ("it misses the face along that direction — direction points from the shape towards the face." if d is not None else "along the face's normals it misses the face — give direction [x, y, z] from the shape towards it.") + " Nothing was added.")
        o = new_obj("Part::Feature", a.get("name") or f"{src.Label} on face")
        o.Shape = res
        extra = {"onto": ref, "how": ("along " + str(geo.vec(d))) if d is not None else "along the face's normals"}
        if missed:
            extra["missed"] = f"{missed} wire(s) did not land on the face"
        return added(o, "part_project", extra)

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

    def part_slices(a):
        o = picks.solid_body(s, a.get("body"))
        n = picks.direction(a.get("normal"), "normal", (0, 0, 1))
        bb = o.Shape.BoundBox
        # The box's reach along the normal: over all eight corners (two
        # opposite ones are the ends only when the normal's parts share a sign).
        span = [x * n.x + y * n.y + z * n.z for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax) for z in (bb.ZMin, bb.ZMax)]
        lo, hi = min(span), max(span)
        if a.get("at") is not None:
            ds = [picks.num(x, "at") for x in a["at"]]
            if not ds:
                raise bad("at: [distances along the normal from the origin, mm], or count.")
            if len(ds) > 500:
                raise bad("at: 500 distances at most a call.")
        else:
            k = int(a.get("count", 5))
            if not 1 <= k <= 500:
                raise bad("count: 1 … 500 slices, spread evenly through the body (or at: [distances]).")
            ds = [lo + (hi - lo) * (i + 1) / (k + 1) for i in range(k)]
        wires, rows = [], []
        for dv in ds:
            ws = o.Shape.slice(n, dv)
            wires += ws
            rows.append({"at": round(dv, 4), "wires": len(ws), "length": round(sum(w.Length for w in ws), 3), "area": section_area(ws)})
        if not wires:
            raise ToolError("failed", f"No slice met {o.Label} along {geo.vec(n)} at those distances: the body runs from {lo:.3g} to {hi:.3g} mm along that normal (measured from the origin). at inside that range, or count. Nothing was added.")
        c = new_obj("Part::Feature", a.get("name") or f"{o.Label} slices")
        c.Shape = Part.Compound(wires)
        out = added(c, "part_slices", {"normal": geo.vec(n), "range": [round(lo, 3), round(hi, 3)], "slices": rows})
        out["use"] = "export writes them as DXF for a laser (and a cutting add-on, where installed); a sketch can be made from one."
        return out

    # ---- mesh to solid ----

    def part_from_mesh(a):
        import Mesh

        if a.get("file"):
            import os

            p = paths.local(s, a["file"])
            if not os.path.isfile(p):
                raise ToolError("not_found", f"{p}: no such file.")
            m = Mesh.Mesh(p)
            label = os.path.splitext(os.path.basename(p))[0]
        else:
            if not a.get("mesh"):
                raise bad("mesh (a mesh object's name) or file (an STL, OBJ, PLY … path): one of them.")
            src = picks.find(doc(), a.get("mesh"), "mesh")
            if not src.isDerivedFrom("Mesh::Feature"):
                raise bad(f"mesh: {src.Label} is a {src.TypeId}, not a mesh — a mesh object's name (object_list shows them), or file.")
            m, label = src.Mesh, src.Label
        limit = int(a.get("maxFacets", 60000))
        if m.CountFacets > limit:
            raise ToolError("invalid_input", f"{m.CountFacets} triangles, over maxFacets ({limit}): every triangle becomes a face of the solid, which is slow to make and slower in every boolean after — reduce it first (meshobj_decimate), or raise maxFacets.")
        if m.CountFacets < 4:
            raise bad(f"The mesh has {m.CountFacets} triangles: no closed solid from it.")
        tol = picks.number(a, "tolerance", 0.05, gt=0, msg="tolerance: mm within which triangle edges are sewn, above 0 (0.05 by default).")
        sh = Part.Shape()
        try:
            sh.makeShapeFromMesh(m.Topology, tol)
        except Exception as e:
            raise ToolError("failed", f"FreeCAD could not make faces from the mesh ({e}): repair it first (meshobj_repair). Nothing was added.")
        # A mesh of several pieces sews into several shells: the largest
        # is made the solid, and the note says the others were left out.
        shells = sorted(sh.Shells, key=lambda x: -len(x.Faces))
        try:
            sol = Part.makeSolid(Part.makeShell(sh.Faces) if not shells else shells[0])
        except Exception as e:
            raise ToolError("failed", f"The mesh does not close into a solid ({e}): fill its holes first (meshobj_repair), or a larger tolerance where edges lie a hair apart. Nothing was added.")
        if a.get("refine", True):
            try:
                sol = sol.removeSplitter()
            except Exception:
                pass
        o = new_obj("Part::Feature", a.get("name") or f"{label} solid")
        o.Shape = sol
        snd = geo.soundness(sol)
        note = "Flat triangles merged where they lie in one plane (refine); curved areas stay faceted — for a clean model, fit features instead."
        if len(shells) > 1:
            note = (f"The mesh sewed into {len(shells)} separate shells: only the largest ({len(shells[0].Faces)} of {len(sh.Faces)} triangles) was made the solid — "
                    "split the mesh first (meshobj_split) and convert each piece. ") + note
        return added(o, "part_from_mesh", {"triangles": m.CountFacets, "sound": snd["ok"], **({"problems": snd["problems"]} if not snd["ok"] else {}), "note": note})

    at_n = {"at": {"type": "array", "items": {}}, "normal": {"type": "array", "items": {}}}
    return [
        Tool("part_wire", "A wire, curve or flat face as FreeCAD's own parametric object: kind line (from, to) | circle (radius) | arc (radius, start, end: 0–360° counter-clockwise) | ellipse (major, minor: full sizes) | polygon (regular: sides, radius to corners) | polyline (points, the corners in place, closed) | helix (pitch, height, radius, taper, leftHanded) | spiral (growth per turn, turns, radius) | plane (length, width) | bspline (points it passes through; closed: a smooth periodic loop; fit.maxDistance is how far it lies from them). at and normal place it: its centre (a plane's corner, a helix's base) at at, its z along normal. polyline and bspline take points_file (a .json list of [x,y,z] or a .csv of x,y,z rows in the session's folder; key picks one list) instead of points, so long lists are not sent in the call. Profiles and paths for extrude, sweep, loft; a plane cuts in part_split.",
             obj({"kind": {"type": "string"}, "from": {"type": "array", "items": {}}, "to": {"type": "array", "items": {}}, "radius": {"type": "number"}, "start": {"type": "number"}, "end": {"type": "number"}, "major": {"type": "number"}, "minor": {"type": "number"},
                  "sides": {"type": "integer"}, "pitch": {"type": "number"}, "height": {"type": "number"}, "taper": {"type": "number"}, "leftHanded": {"type": "boolean"}, "growth": {"type": "number"}, "turns": {"type": "number"},
                  "length": {"type": "number"}, "width": {"type": "number"}, "points": {"type": "array", "items": {}}, "points_file": {"type": "string"}, "key": {}, "closed": {"type": "boolean"}, "name": {"type": "string"}, **at_n}, ["kind"]), part_wire, changes=True),
        Tool("part_split", "Split bodies (Part's BOPTools, parametric; inputs hidden, not removed): mode slice (bodies [one], tools [objects by name that cut right through it: a part_wire plane, a face copied out by part_extract, bodies]) | fragments (bodies: every piece where they overlap, kept apart) | xor (bodies: what is in an odd number of them); explode: true makes each piece a body. Reply: object, pieces, solids [{ volume, center }]; note when a slice cut nothing.",
             obj({"mode": {"type": "string", "enum": ["slice", "fragments", "xor"]}, "bodies": {"type": "array", "items": {"type": "string"}}, "tools": {"type": "array", "items": {"type": "string"}}, "split": {"type": "boolean"}, "explode": {"type": "boolean"}, "name": {"type": "string"}}, ["bodies"]), part_split, changes=True),
        Tool("part_compound", "Group bodies into one compound (kept apart, not fused; it follows its parts): bodies [names] — or explode: the name of a body of several solids, each copied out as a body (the original hidden).",
             obj({"bodies": {"type": "array", "items": {"type": "string"}}, "explode": {"type": "string"}, "name": {"type": "string"}}), part_compound, changes=True),
        Tool("part_refine", "Merge a body's coplanar and co-cylindrical faces left by booleans (refine); a PartDesign Body gets its tip's Refine turned on and stays parametric. fix: true first repairs it (ShapeFix at tolerance mm, 0.001) and makes a closed shell a solid. Renumbers faces. Reply: faces { before, after }, done, sound.",
             obj({"body": {"type": "string"}, "fix": {"type": "boolean"}, "tolerance": {"type": "number"}, "name": {"type": "string"}}), part_refine, changes=True),
        Tool("part_attach", "Attach a primitive, wire or datum (not a plain modelling result) so it follows its support: to \"Body.Face6\", an edge, a vertex or a whole object; mode, a FreeCAD MapMode, by default FlatFace (flat face) | NormalToEdge (edge) | Translate (vertex) | ObjectXY (object); also Concentric, FrenetNB … (modes needing two references are not reachable). offset [x, y, z] and rotate degrees in the support's frame. Trap: a later boolean on the support renumbers its faces.",
             obj({"body": {"type": "string"}, "to": {"type": "string"}, "mode": {"type": "string"}, "offset": {"type": "array", "items": {}}, "rotate": {"type": "number"}}, ["body", "to"]), part_attach, changes=True),
        Tool("part_face", "A flat face from closed wires or sketches in one plane: from [object names], the outline and any holes inside it (found by nesting).", obj({"from": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}}, ["from"]), part_face, changes=True),
        Tool("part_ruled", "A ruled surface (parametric) of straight lines between two curves: a and b each an edge or wire by name, or one edge of a body as \"Box.Edge3\". reversed: true if it twists. A surface, not a solid (surface_thicken).",
             obj({"a": {"type": "string"}, "b": {"type": "string"}, "reversed": {"type": "boolean"}, "name": {"type": "string"}}, ["a", "b"]), part_ruled, changes=True),
        Tool("part_project", "Project a wire's, sketch's or body's edges onto one face: shape (a name), onto \"Body.Face6\", direction [x, y, z] from the shape towards the face (left out: along the face's normals). Lettering wrapped onto a curved face, an outline traced onto a surface. Reply: edges, length, missed (wires that did not land).",
             obj({"shape": {"type": "string"}, "onto": {"type": "string"}, "direction": {"type": "array", "items": {}}, "name": {"type": "string"}}, ["shape", "onto"]), part_project, changes=True),
        Tool("part_slices", "Cross-sections of a body: normal [x, y, z] (default z), count (1–500, evenly through it) or at [distances along the normal from the origin]; each slice's wires, length and material area (inner loops are holes), kept as one compound; range is the body's reach along the normal. Layer outlines, laser-cut stacks.",
             obj({"body": {"type": "string"}, "normal": {"type": "array", "items": {}}, "count": {"type": "integer"}, "at": {"type": "array", "items": {"type": "number"}}, "name": {"type": "string"}}), part_slices, changes=True),
        Tool("part_from_mesh", "A mesh made a solid, every triangle a face: mesh (an object) or file (STL, OBJ …); tolerance sews it, refine (default) merges flat triangles. For a closed, modest mesh: over maxFacets (60000) refused (meshobj_decimate first); thousands of faces already make it and every later boolean slow, the window frozen meanwhile. Of several pieces only the largest becomes the solid (note says so).",
             obj({"mesh": {"type": "string"}, "file": {"type": "string"}, "tolerance": {"type": "number"}, "refine": {"type": "boolean"}, "maxFacets": {"type": "integer"}, "name": {"type": "string"}}), part_from_mesh, changes=True),
    ]
