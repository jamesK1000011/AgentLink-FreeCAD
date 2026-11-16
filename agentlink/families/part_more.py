# SPDX-License-Identifier: LGPL-2.1-or-later
# The rest of the Part workbench headless: section curves where bodies or a
# plane meet a body, 2D offsets of wires and flat faces, elements copied out
# as bodies of their own (and shells and solids built from faces), faces
# defeatured away, shapes reversed or closed into solids, and datums (point,
# line, plane, coordinate system) to attach and measure from.

import FreeCAD
import Part

from ..protocol import Tool, ToolError, bad
from ..tools import obj
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
    o = doc(s).addObject("Part::Feature", "Shape")
    o.Shape = shape
    o.Label = s.unique(label)
    doc(s).recompute()
    return o


def elements(s, refs, what):
    refs = picks.ref_list(refs)
    if not isinstance(refs, list) or not refs:
        raise bad(f"refs: [\"Box.Face3\", \"Box.Edge2\", …] ({what}, numbered from 1 as shape_query lists them) or whole objects by name.")
    out = []
    for r in refs:
        label, sub, sh = picks.resolve(s, r)
        if sub is None:
            out += list(sh.Faces) if what == "faces" else [sh]
        else:
            out.append(sh)
    return out


def tools(s):
    def section(a):
        b = picks.shaped(doc(s), a.get("body"), "body")
        size = b.Shape.BoundBox.DiagonalLength
        if a.get("plane") is not None:
            other = plane_face(a["plane"], size, b.Shape.BoundBox.Center)
            tool_o = None
        elif a.get("with"):
            tool_o = picks.shaped(doc(s), a["with"], "with")
            other = tool_o.Shape
        else:
            raise bad("with (another body's name) or plane { normal: [x,y,z], at: [x,y,z] }: what the body is cut by.")
        if tool_o is not None and a.get("parametric", True):
            o = doc(s).addObject("Part::Section", "Section")
            o.Base, o.Tool = b, tool_o
            o.Approximation = bool(a.get("approximate", False))
            o.Label = s.unique(a.get("name") or f"{b.Label} section")
            doc(s).recompute()
            sh = o.Shape
        else:
            sh = b.Shape.section(other)
            if not sh.Edges:
                bb = b.Shape.BoundBox
                raise ToolError("invalid_state", f"The plane misses {b.Label}: no section. Its box runs {[round(bb.XMin, 3), round(bb.YMin, 3), round(bb.ZMin, 3)]} to {[round(bb.XMax, 3), round(bb.YMax, 3), round(bb.ZMax, 3)]} — plane.at inside it. Nothing was added.")
            o = add(s, sh, a.get("name") or f"{b.Label} section")
        if not sh.Edges:
            raise ToolError("invalid_state", f"{b.Label} and {a.get('with')} do not meet: no section curves (measure gives the gap between them; part_transform moves one). Nothing was added.")
        out = {"section": o.Label, **shape_stats(sh)}
        if a.get("face") and sh.Edges:
            try:
                wires = [Part.Wire(es) for es in Part.sortEdges(sh.Edges)]
                closed = [w for w in wires if w.isClosed()]
                f = Part.makeFace(closed, "Part::FaceMakerBullseye")
                o.Shape = f if o.TypeId == "Part::Feature" else o.Shape
                if o.TypeId != "Part::Feature":
                    o2 = add(s, f, f"{o.Label} face")
                    out["face"] = o2.Label
                out["area_mm2"] = round(f.Area, 3)
            except Exception as e:
                out["faceNote"] = f"no face from the curves: {e}"
        s.snapshot("part_section")
        return out

    def offset2d(a):
        src = picks.shaped(doc(s), a.get("shape"), "shape")
        if a.get("distance") is None:
            raise bad("distance: mm, + outward, - inward.")
        d = float(a["distance"])
        sh = src.Shape
        if not (sh.Wires or sh.Faces):
            raise ToolError("invalid_state", f"shape: {src.Label} has no wire or face — a wire, sketch or flat face by name (part_extract copies a body's face out; part_section cuts an outline).")
        join = {"arc": 0, "tangent": 1, "intersection": 2}.get(a.get("join", "arc"))
        if join is None:
            raise bad("join: arc | tangent | intersection.")
        loops = [w for w in sh.Wires if w.isClosed()] if not sh.Faces else []
        if loops and len(loops) == len(sh.Wires):
            # FreeCAD's Offset2D of a bare closed wire goes astray: offset the
            # face it bounds and take its outline (the band with fill)
            try:
                face = Part.makeFace(loops, "Part::FaceMakerBullseye")
                grown = face.makeOffset2D(d, join, False, False, bool(a.get("intersection", False)))
            except Exception as e:
                raise ToolError("invalid_state", f"No offset of {src.Label} by {d} mm: {e} — a loop shrunk past half its own width vanishes, and the outline must be flat. Nothing was added.")
            if a.get("fill"):
                res = grown.cut(face) if d > 0 else face.cut(grown)
            else:
                res = grown.Faces[0].OuterWire if len(grown.Faces) == 1 else Part.makeCompound([f.OuterWire for f in grown.Faces])
            o = add(s, res, a.get("name") or f"{src.Label} offset")
            s.snapshot("part_offset2d")
            return {"offset": o.Label, **shape_stats(res), "note": "a plain shape (a closed wire's offset is taken through its face)"}
        o = doc(s).addObject("Part::Offset2D", "Offset2D")
        o.Source = src
        o.Value = d
        o.Join = join
        o.Fill = bool(a.get("fill", False))
        o.Intersection = bool(a.get("intersection", False))
        o.Label = s.unique(a.get("name") or f"{src.Label} offset")
        doc(s).recompute()
        if o.Shape.isNull() or not (o.Shape.Edges):
            msg = "; ".join(str(x) for x in (o.getStatusString(),)) if hasattr(o, "getStatusString") else ""
            doc(s).removeObject(o.Name)
            raise ToolError("invalid_state", f"No offset of {src.Label} by {d} mm ({msg}) — a wire shrunk past half its own width vanishes; a wire that is not flat cannot be offset in 2D (part_offset grows a solid). Nothing was added.")
        if not a.get("parametric", True):
            sh2 = o.Shape.copy()
            doc(s).removeObject(o.Name)
            o = add(s, sh2, a.get("name") or f"{src.Label} offset")
        s.snapshot("part_offset2d")
        return {"offset": o.Label, **shape_stats(o.Shape)}

    def extract(a):
        build = a.get("build", "copy")
        parts = elements(s, a.get("refs"), "faces" if build in ("shell", "solid") else "refs")
        if build == "copy":
            sh = parts[0].copy() if len(parts) == 1 else Part.makeCompound([p.copy() for p in parts])
        elif build in ("shell", "solid"):
            faces = [f for p in parts for f in p.Faces]
            if not faces:
                raise bad(f"refs: no face among them — build {build} takes faces (\"Box.Face3\") or whole objects with faces.")
            sh = Part.makeShell(faces)
            tol = float(a.get("tolerance", 0.01))
            if not sh.isClosed():
                # Sewn from the loose faces (a compound), not from the shell
                # makeShell already settled: that one kept its gaps.
                sew = _sew(Part.makeCompound(faces), tol)
                if sew.Shells:
                    sh = max(sew.Shells, key=lambda x: len(x.Faces))
            if build == "solid":
                shells = sh.Shells or [sh]
                if not shells[0].isClosed():
                    raise ToolError("invalid_state", f"The {len(faces)} faces leave a gap: a solid needs a closed shell, and tolerance {tol} mm did not close it — every face of the solid in refs, or a larger tolerance; build: \"shell\" keeps the open shell to look at. Nothing was added.")
                sh = Part.makeSolid(shells[0])
                if sh.Volume < 0:
                    sh.reverse()
        elif build == "wire":
            edges = [e for p in parts for e in p.Edges]
            if not edges:
                raise bad("refs: no edge among them — build wire takes edges (\"Box.Edge2\"), faces or whole objects.")
            ws = [Part.Wire(es) for es in Part.sortEdges(edges)]
            sh = ws[0] if len(ws) == 1 else Part.makeCompound(ws)
        elif build == "face":
            edges = [e for p in parts for e in p.Edges]
            ws = [Part.Wire(es) for es in Part.sortEdges(edges)]
            if not all(w.isClosed() for w in ws):
                raise ToolError("invalid_state", f"The edges make {len(ws)} wire(s), not all closed: no face — every edge of each loop in refs; build: \"wire\" shows what they join into. Nothing was added.")
            sh = Part.makeFace(ws, "Part::FaceMakerBullseye")
        else:
            raise bad("build: copy | wire | face | shell | solid.")
        o = add(s, sh, a.get("name") or ("Copy" if build == "copy" else build.capitalize()))
        s.snapshot("part_extract")
        return {"shape": o.Label, "build": build, **shape_stats(sh), "valid": bool(sh.isValid())}

    def defeature(a):
        b = picks.solid_body(s, a.get("body"))
        faces = a.get("faces")
        if not faces:
            raise bad("faces: [\"Face12\", …] of the body, numbered from 1 (shape_query { kind: \"face\" } lists them) — every face of the boss, hole or fillet to take away.")
        subs = []
        for f in faces:
            head, sub = picks.split_ref(f)
            if sub is None or not sub.startswith("Face"):
                raise bad(f"faces: {f!r} is not a face — \"Face12\".")
            subs.append(picks.element(b.Shape, sub, b.Label))
        before = b.Shape
        try:
            res = before.defeaturing(subs)
        except Exception as e:
            raise ToolError("invalid_state", f"Defeaturing refused: {e} — pick every face of the feature together (a hole's wall and its floor, a fillet's whole band); the faces around it must be able to grow over the gap. Nothing was changed.")
        if res.isNull() or not res.Solids or res.isSame(before):
            raise ToolError("invalid_state", "Defeaturing left the body as it was: pick all faces of one feature together (a hole's wall and floor, a fillet's whole band). Nothing was changed.")
        out = picks.bake(s, b, res, a.get("name"))
        s.snapshot("part_defeature")
        return {"body": out.Label, "facesBefore": len(before.Faces), "facesAfter": len(res.Faces),
                "volumeBefore_mm3": round(before.Volume, 3), "volume_mm3": round(res.Volume, 3)}

    def fix(a):
        b = picks.shaped(doc(s), a.get("body"), "body")
        op = a.get("op")
        sh = b.Shape.copy()
        notes = []
        if op == "reverse":
            sh.reverse()
            if sh.Solids and sh.Volume < 0:
                notes.append("a solid turned inside out has a negative volume — reverse it back if that was not the aim")
        elif op == "solid":
            shells = sh.Shells
            if not shells:
                try:
                    shells = [Part.makeShell(sh.Faces)]
                except Exception:
                    shells = []
            closed = [x for x in shells if x.isClosed()]
            if not closed:
                raise ToolError("invalid_state", f"{b.Label} has no closed shell: part_fix {{ op: \"sew\", tolerance }} joins its faces first; gaps wider than the tolerance need a face (surface_fill). Nothing was changed.")
            solids = [Part.makeSolid(x) for x in closed]
            for x in solids:
                if x.Volume < 0:
                    x.reverse()
            sh = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
        elif op == "sew":
            tol = float(a.get("tolerance", 0.01))
            sh = _sew(sh, tol)
            try:
                sh = sh.copy()
                sh.fix(tol, tol, tol)
            except Exception:
                pass
            notes.append(f"sewn at {tol} mm")
        elif op == "fix":
            tol = float(a.get("tolerance", 0.001))
            sh.fix(tol, tol, tol)
        else:
            raise bad("op: reverse (flip inside out) | solid (closed shells made solids) | sew (faces joined at tolerance) | fix (ShapeFix at tolerance).")
        if op == "reverse":
            if b.TypeId == "Part::Feature" and not a.get("name"):
                b.Shape = sh
                o = b
            else:
                o = add(s, sh, a.get("name") or f"{b.Label} reversed")
            doc(s).recompute()
        else:
            o = picks.bake(s, b, sh, a.get("name"))
        sh = o.Shape
        s.snapshot("part_fix")
        out = {"body": o.Label, "op": op, **shape_stats(sh), "valid": bool(sh.isValid()), "closed": bool(sh.Shells and all(x.isClosed() for x in sh.Shells))}
        if notes:
            out["notes"] = notes
        return out

    def datum(a):
        kind = a.get("kind", "plane")
        types = {"point": ["Part::DatumPoint", "PartDesign::Point"], "line": ["Part::DatumLine", "PartDesign::Line"],
                 "plane": ["Part::DatumPlane", "PartDesign::Plane"],
                 "csys": ["Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem"]}
        if kind not in types:
            raise bad("kind: point | line | plane | csys (a coordinate system).")
        pl = picks.placement(a)
        if a.get("normal") is not None and kind in ("plane", "line"):
            n = picks.direction(a["normal"], "normal")
            pl.Rotation = FreeCAD.Rotation(V(0, 0, 1), n)
        o = None
        tried = []
        for t in types[kind]:
            try:
                o = doc(s).addObject(t, kind.capitalize())
                break
            except Exception as e:
                tried.append(f"{t}: {e}")
                continue
        made = "datum"
        if o is None:
            # an older FreeCAD: a plain shape stands in
            made = "shape"
            if kind == "point":
                sh = Part.Vertex(V())
            elif kind == "line":
                sh = Part.makeLine(V(0, 0, -50), V(0, 0, 50))
            elif kind == "plane":
                sh = Part.makePlane(100, 100, V(-50, -50, 0))
            else:
                sh = Part.makeCompound([Part.makeLine(V(), V(20, 0, 0)), Part.makeLine(V(), V(0, 20, 0)), Part.makeLine(V(), V(0, 0, 20))])
            o = doc(s).addObject("Part::FeaturePython", kind.capitalize())
            try:
                o.addExtension("Part::AttachExtensionPython")
            except Exception as e:
                tried.append(f"attach: {e}")
            o.Shape = sh
        o.Placement = pl
        if a.get("to") and not (hasattr(o, "AttachmentSupport") or hasattr(o, "Support")):
            raise ToolError("invalid_state", "This FreeCAD cannot attach a datum here: " + "; ".join(tried))
        if a.get("to"):
            label, sub, el = picks.resolve(s, a["to"])
            target = picks.find(doc(s), label)
            prop = "AttachmentSupport" if hasattr(o, "AttachmentSupport") else "Support"
            setattr(o, prop, [(target, sub or "")])
            mode = a.get("mode")
            if not mode or mode == "Deactivated":
                elt = (sub or "")[:4]
                # One reference: FreeCAD's attacher modes that take a single
                # element (Attacher.cpp). A circle's or arc's edge has an
                # axis and a centre of curvature; a straight one has not.
                round_edge = False
                if elt == "Edge":
                    try:
                        round_edge = isinstance(el.Curve, Part.Circle)
                    except Exception:
                        round_edge = False
                if (kind, elt) == ("line", "Face"):
                    # A line normal to a face is FreeCAD's FaceNormal, which
                    # takes a face and a vertex: two references.
                    raise bad("A line datum on a face needs mode: FreeCAD's line normal to a face (FaceNormal) takes a face and a vertex, and to is one reference. "
                              "mode AxisOfInertia1 | AxisOfInertia2 | AxisOfInertia3 (through the face's centre of mass) or ObjectZ (the object's own z); "
                              "or to an edge (a straight one: the line along it; a circle's: its axis); or leave to out and place it with at and normal.")
                mode = {("point", "Vert"): "Vertex", ("point", "Edge"): "CenterOfCurvature" if round_edge else "CenterOfMass", ("point", "Face"): "CenterOfMass",
                        ("line", "Edge"): "AxisOfCurvature" if round_edge else "TwoPointLine", ("line", "Vert"): "ObjectZ",
                        ("plane", "Face"): "FlatFace", ("plane", "Edge"): "NormalToEdge", ("plane", "Vert"): "Translate",
                        ("csys", "Face"): "FlatFace", ("csys", "Edge"): "NormalToEdge", ("csys", "Vert"): "Translate"}.get((kind, elt), "ObjectXY")
            try:
                o.MapMode = mode
            except Exception:
                raise bad(f"mode {mode!r}: not a FreeCAD attachment mode — the modes: {', '.join(o.getEnumerationsOfProperty('MapMode'))}.")
            o.AttachmentOffset = pl
        o.Label = s.unique(a.get("name") or f"Datum {kind}")
        doc(s).recompute()
        if a.get("to") and getattr(o, "MapMode", "") == "Deactivated":
            tried.append("left unattached")
        elif a.get("to"):
            failed = False
            try:
                failed = not o.isValid()
            except Exception:
                failed = False
            if failed:
                raise ToolError("failed", f"The {kind} datum would not attach to {a['to']} as {o.MapMode}: {o.getStatusString()} — nothing was kept. With one reference: a plane or csys takes FlatFace (a flat face), "
                                "NormalToEdge (an edge), Translate (a vertex), ObjectXY (a whole object); a line TwoPointLine (a straight edge), AxisOfCurvature (a circle or arc); a point Vertex, CenterOfCurvature, CenterOfMass.")
        s.snapshot("part_datum")
        return {"datum": o.Label, "kind": kind, "type": o.TypeId, "made": made,
                "placement": picks.placement_json(o.Placement), **({"mode": o.MapMode} if a.get("to") else {}),
                **({"notes": tried} if a.get("to") and getattr(o, "MapMode", "") == "Deactivated" else {})}

    body = {"type": "string"}
    return [
        Tool("part_section", "Section curves where a body meets another body (with: a parametric Part::Section; parametric: false for a plain shape) or a plane { normal, at }; face: true also fills the closed loops into a face. Refused when they do not meet. Reply: section, edges, length_mm, closedLoops, area_mm2. Cut-lines, outlines at a height.",
             obj({"body": body, "with": body, "plane": {"type": "object"}, "face": {"type": "boolean"}, "approximate": {"type": "boolean"}, "parametric": {"type": "boolean"}, "name": body}, ["body"]), section, changes=True),
        Tool("part_offset2d", "Offset a flat wire, sketch or face in its plane (Part::Offset2D; a closed wire goes through its face, as a plain shape): distance mm (+ out, − in), join arc | tangent | intersection, fill: true for the band between the two, intersection: true to offset several wires as one. Refused when the loop vanishes or is not flat. Kerf and clearance outlines, gasket bands.",
             obj({"shape": body, "distance": {"type": "number"}, "join": {"type": "string", "enum": ["arc", "tangent", "intersection"]}, "fill": {"type": "boolean"}, "intersection": {"type": "boolean"}, "parametric": {"type": "boolean"}, "name": body}, ["shape", "distance"]), offset2d, changes=True),
        Tool("part_extract", "Copy elements out as a plain body of their own (Part's element copy and shape builder): refs [\"Box.Face3\", \"Box.Edge2\", whole objects], numbered from 1; build copy (as they are) | wire (edges joined) | face (closed edge loops filled) | shell (faces sewn at tolerance mm, 0.01) | solid (a closed shell made a solid; refused with a gap). Reply: shape, counts, valid.",
             obj({"refs": {"type": "array", "items": {}}, "build": {"type": "string", "enum": ["copy", "wire", "face", "shell", "solid"]}, "tolerance": {"type": "number"}, "name": body}, ["refs"]), extract, changes=True),
        Tool("part_defeature", "Take features off a solid by their faces (Part defeaturing): faces [\"Face12\", …] numbered from 1 — every face of a hole, boss or fillet together; the faces around grow over the gap. Renumbers faces; refused when OCC cannot close it. For simplifying imported bodies before FEA or CAM.",
             obj({"body": body, "faces": {"type": "array", "items": {"type": "string"}}, "name": body}, ["faces"]), defeature, changes=True),
        Tool("part_fix", "Repair a shape: op reverse (flip an inside-out solid) | solid (closed shells or faces made solids) | sew (faces joined within tolerance mm, 0.01) | fix (ShapeFix at tolerance, 0.001). Reply: valid, closed, solids, notes.",
             obj({"body": body, "op": {"type": "string", "enum": ["reverse", "solid", "sew", "fix"]}, "tolerance": {"type": "number"}, "name": body}, ["body", "op"]), fix, changes=True),
        Tool("part_datum", "A datum: kind point | line | plane | csys, at [x,y,z], normal (plane, line) or axis + angle; or attached by one reference (to \"Box.Face6\", an edge, a vertex), the placement then its offset. mode: a FreeCAD MapMode, by default by what to is (FlatFace, NormalToEdge, Translate; a line along a straight edge or a circle's axis; a point at a vertex or centre); a line on a face needs mode. Refused when it cannot attach.",
             obj({"kind": {"type": "string", "enum": ["point", "line", "plane", "csys"]}, "at": {"type": "array", "items": {"type": "number"}}, "normal": {}, "axis": {}, "angle": {"type": "number"}, "to": body, "mode": body, "name": body}), datum, changes=True),
    ]
