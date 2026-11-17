# SPDX-License-Identifier: LGPL-2.1-or-later
# Text and free surfaces on parts: lettering raised from or cut into a face
# (a label on a bin, a part number, a logo's words) from a TrueType font,
# and a surface filled across a boundary of edges and thickened into a
# solid — what Draft's ShapeString and the Surface workbench's Filling do,
# by Part's own functions so they run without the window.

import glob
import os

import FreeCAD
import Part

from .. import runners
from ..protocol import ToolError
from . import measure as M
from . import picks

GROUP = "draft"
INFO = ("Draft: lettering raised from or cut into a face from a TrueType font, SVG/DXF outlines, arrays, and Draft's own parametric 2D shapes, "
        "dimensions, labels, link arrays, clones, move/rotate/scale/mirror/offset, upgrade/downgrade, layers, hatches, Draft↔Sketch, 2D views, facebinders, heal.")

V = FreeCAD.Vector


def fonts():
    """TrueType fonts this computer has, FreeCAD's own first."""
    roots = [os.path.join(FreeCAD.getResourceDir(), "Mod"), os.path.join(FreeCAD.getHomePath(), "Mod"),
             "/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
             "/usr/share/fonts", "C:/Windows/Fonts"]
    out = []
    for r in roots:
        out += sorted(glob.glob(os.path.join(r, "**", "*.ttf"), recursive=True))[:200]
    return list(dict.fromkeys(out))


def font_file(name):
    if name and os.path.isfile(os.path.expanduser(name)):
        return os.path.expanduser(name)
    have = fonts()
    if not have:
        raise ToolError("unavailable", "No TrueType font found on this computer: give font, the path to a .ttf.")
    if name:
        hit = next((f for f in have if name.lower() in os.path.basename(f).lower()), None)
        if hit is None:
            raise ToolError("not_found", f"font {name!r}: none by that name — e.g. {', '.join(os.path.basename(f) for f in have[:8])}.")
        return hit
    pref = ("DejaVuSans.ttf", "Arial.ttf", "Helvetica", "LiberationSans-Regular", "osifont-lgpl3fe", "osifont")
    for p in pref:
        hit = next((f for f in have if p.lower() in os.path.basename(f).lower() and "italic" not in os.path.basename(f).lower()), None)
        if hit:
            return hit
    return have[0]


def text_faces(text, font, size, tracking=0.0):
    """The lettering as planar faces in XY, the baseline along X from 0."""
    chars = Part.makeWireString(text, font, size, tracking)
    faces = []
    for wires in chars:
        ws = [w if isinstance(w, Part.Wire) else Part.Wire(w) for w in wires]
        ws = [w for w in ws if w.isClosed()]
        if not ws:
            continue
        try:
            f = Part.makeFace(ws, "Part::FaceMakerBullseye")
        except Exception:
            f = Part.makeFace(ws, "Part::FaceMakerCheese")
        faces += f.Faces
    if not faces:
        raise ToolError("failed", f"The font made no closed letters of {text!r}.")
    return Part.makeCompound(faces)


def face_frame(face, point=None):
    """A frame on a planar face, as one reads it: origin the point (else the
    face's centre), Z its outward normal; on a face facing up or down X is
    world X, on a wall X runs level, left to right seen from outside."""
    if not isinstance(face.Surface, Part.Plane):
        raise ToolError("invalid_input", "face: lettering goes on a flat face.")
    c = point if point is not None else face.CenterOfMass
    u0, u1, v0, v1 = face.ParameterRange
    n = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    n.normalize()
    if abs(n.z) > 0.99:
        x = V(1, 0, 0) if n.z > 0 else V(-1, 0, 0)
    else:
        x = V(0, 0, 1).cross(n)
        x.normalize()
    y = n.cross(x)
    m = FreeCAD.Matrix(x.x, y.x, n.x, c.x, x.y, y.y, n.y, c.y, x.z, y.z, n.z, c.z, 0, 0, 0, 1)
    return FreeCAD.Placement(m), n


def outline_faces(path):
    """The closed outlines of an SVG or DXF file as planar faces in XY (holes
    kept as holes), and how many open curves were left out."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise ToolError("not_found", f"path: no file at {path}.")
    ext = os.path.splitext(path)[1].lower()
    keep = FreeCAD.ActiveDocument
    try:
        tmp = FreeCAD.newDocument("AgentLinkOutline", hidden=True)
    except TypeError:
        tmp = FreeCAD.newDocument("AgentLinkOutline")
    try:
        if ext == ".svg":
            import importSVG

            importSVG.insert(path, tmp.Name)
        elif ext == ".dxf":
            import Import

            try:
                Import.readDXF(path, tmp.Name)
            except Exception as e:
                raise ToolError("failed", f"FreeCAD could not read the DXF: {e} — save it as DXF R12 or 2000, or as SVG.")
        else:
            raise ToolError("invalid_input", "path: an .svg or .dxf file.")
        tmp.recompute()
        edges = []
        for o in tmp.Objects:
            sh = getattr(o, "Shape", None)
            if sh is not None and not sh.isNull():
                edges += sh.Edges
    finally:
        tmp_name = tmp.Name
        keep_name = keep.Name if keep is not None else None
        FreeCAD.closeDocument(tmp_name)
        if keep_name and keep_name != tmp_name:
            FreeCAD.setActiveDocument(keep_name)
    if not edges:
        raise ToolError("failed", "The file has no curves FreeCAD reads: paths and shapes, not images or text (turn text into paths first).")
    closed, open_ = [], 0
    for group in Part.sortEdges(edges):
        try:
            w = Part.Wire(group)
        except Exception:
            open_ += 1
            continue
        if w.isClosed():
            closed.append(w)
        else:
            open_ += 1
    if not closed:
        raise ToolError("failed", f"No closed outline in the file ({open_} open curve(s)): close the paths, or trace the artwork as filled shapes.")
    # Flat on XY whatever plane the file put them on.
    bb = Part.makeCompound(closed).BoundBox
    if bb.ZLength > 1e-6:
        raise ToolError("failed", "The outlines are not flat in one plane.")
    try:
        f = Part.makeFace(closed, "Part::FaceMakerBullseye")
    except Exception:
        f = Part.makeFace(closed, "Part::FaceMakerCheese")
    f.translate(V(0, 0, -bb.ZMin))
    return f, open_


def place_on(o, face, flat, at, rotate, depth, mode):
    """Flat faces in XY, centred, turned and stood on a body's face: the
    solid to join (emboss) or cut (engrave), and its box."""
    pl, n = face_frame(face, at)
    bb = flat.BoundBox
    flat = flat.copy()
    flat.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, 0))
    if rotate:
        flat.rotate(V(0, 0, 0), V(0, 0, 1), float(rotate))
    flat.transformShape(pl.toMatrix())
    solid = flat.extrude(n * (depth if mode == "emboss" else -depth))
    if mode == "engrave":
        # Started a hair above the face, so the cut opens cleanly.
        solid.translate(n * 0.01)
    return solid, flat.BoundBox


def tools(session):
    s = session

    def pick_face(o, q):
        if isinstance(q, str):
            try:
                return o.Shape.getElement(q)
            except Exception:
                raise ToolError("invalid_input", f"face: {o.Label} has no {q}.")
        query = {**q, "body": o.Label, "kind": "face"}
        query.pop("at", None)
        _, _, hits = M.query(s, query)
        if not hits:
            raise ToolError("not_found", f"face: no face of {o.Label} matches {q} — shape_query lists them.")
        if len(hits) > 1:
            near = q.get("near")
            if near is None:
                hits = sorted(hits, key=lambda h: -h[1].Area)
            else:
                p = picks.vec3(near if isinstance(near, list) else near.get("point"), "near")
                hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(p))[0])
        return hits[0][1]

    def _curve(r, what, body=None):
        """An edge or wire from a reference ("Body.Edge3", a sketch) or
        { points: [[x,y,z] …], closed } (a smooth curve through them)."""
        if isinstance(r, dict) and "points" in r:
            pts = [FreeCAD.Vector(*picks.vec3(p, f"{what}.points")) for p in r["points"]]
            if len(pts) < 2:
                raise ToolError("invalid_input", f"{what}.points: two or more [x, y, z].")
            closed = bool(r.get("closed"))
            if len(pts) == 2:
                return Part.Wire([Part.LineSegment(pts[0], pts[1]).toShape()])
            bs = Part.BSplineCurve()
            bs.interpolate(pts, PeriodicFlag=closed)
            return Part.Wire([bs.toShape()])
        label, sub, el = picks.resolve(s, r, body)
        edges = [el] if isinstance(el, Part.Edge) else list(getattr(el, "Edges", []) or [])
        if not edges:
            raise ToolError("invalid_input", f"{what}: an edge (\"Box.Edge3\"), a sketch or wire, or {{ points: [[x,y,z] …] }}.")
        try:
            return Part.Wire(Part.sortEdges(edges)[0])
        except Exception:
            raise ToolError("invalid_input", f"{what}: its edges do not join into one curve.")

    def _thicken(shape, t, side, what="the surface"):
        t = picks.num(t, "thickness")
        if t <= 0:
            raise ToolError("invalid_input", "thickness: mm, over 0 (side picks which way).")
        side = side or "out"
        if side not in ("out", "in", "both"):
            raise ToolError("invalid_input", "side: out (along the surface's normal), in, or both (half each way).")
        try:
            if side == "both":
                base = shape.makeOffsetShape(-t / 2.0, 1e-3)
                solid = base.makeOffsetShape(t, 1e-3, fill=True)
            else:
                solid = shape.makeOffsetShape(t if side == "out" else -t, 1e-3, fill=True)
        except Exception as e:
            raise ToolError("failed", f"{what} could not be thickened {t:g} mm: {e} — thinner, or another side (it cannot be thicker than its tightest bend is round).")
        if not solid.Solids:
            try:
                solid = Part.makeSolid(solid)
            except Exception:
                pass
        return solid, t

    def _finish(shape, a, tool, extra):
        t = a.get("thickness")
        warnings = []
        surf = shape
        if t is not None:
            shape, t = _thicken(shape, t, a.get("side"))
            if t < 0.8:
                warnings.append(f"{t:g} mm is under two printed lines (0.8 mm with a 0.4 mm nozzle): it may print with gaps or not at all.")
            if not shape.isValid():
                warnings.append("The thickened solid is not valid: body_check it; a thinner thickness or a gentler surface usually mends it.")
        o = s.doc.addObject("Part::Feature", (a.get("name") or "Surface").replace(" ", "_"))
        o.Label = a.get("name") or "Surface"
        o.Shape = shape
        s.doc.recompute()
        s.snapshot(tool)
        out = {"object": o.Label, "area": round(surf.Area, 2), "solid": bool(shape.Solids), **extra, "step": len(s.steps)}
        if shape.Solids:
            out["volume"] = round(shape.Volume, 2)
        bb = shape.BoundBox
        out["size"] = [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)]
        if warnings:
            out["warnings"] = warnings
        if not shape.Solids:
            out["next"] = "thickness: mm to make it a solid to print — or surface_thicken { surface } later."
        return out

    def along_path(w, count, align):
        """Where count copies go along a curve: the first stays, the rest
        are moved to points spread along it (a closed curve's last point is
        its first, so it is left out); align turns each as the curve turns
        from its start."""
        pts = w.discretize(Number=count if not w.isClosed() else count + 1)[:count]
        start = pts[0]
        e0 = w.Edges[0]
        t0 = e0.tangentAt(e0.FirstParameter)
        places = []
        for p in pts:
            if align:
                best = min(w.Edges, key=lambda e: e.distToShape(Part.Vertex(p))[0])
                t = best.tangentAt(best.Curve.parameter(p))
                rot = FreeCAD.Rotation(t0, t)
                places.append(FreeCAD.Placement(p - rot.multVec(start), rot))
            else:
                places.append(FreeCAD.Placement(p - start, FreeCAD.Rotation()))
        return places

    def refined(res, several):
        """A union of copies with its coplanar faces merged when that works:
        on 1.1.3 removeSplitter answers "Null shape" for copies that do not
        touch (five beads along a path), and the plain union is the answer
        there."""
        try:
            fine = res.removeSplitter() if several else res
            if not fine.isNull() and fine.isValid() and abs(fine.Volume - res.Volume) <= 1e-6 * max(abs(res.Volume), 1.0):
                return fine
        except Exception:
            pass
        return res

    # The tools themselves are data (agentlink/data/tools.json, "family":
    # "draft"; run by agentlink/runners.py's steps runner: docs/data-tools.md).
    # What their entries call by name:
    helpers = {"doc": lambda: s.doc, "body": lambda ref: s.body(ref), "bake": lambda base, shape, name=None: picks.bake(s, base, shape, name),
               "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps), "finish": _finish, "num": picks.num, "vec3": picks.vec3,
               "resolve": lambda ref, body=None: picks.resolve(s, ref, body), "basename": os.path.basename,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "vertex": Part.Vertex, "as_wire": Part.Wire, "as_shell": Part.Shell,
               "sort_edges": Part.sortEdges, "filled_face": Part.makeFilledFace, "make_loft": Part.makeLoft, "bspline_surface": Part.BSplineSurface,
               "is_edge": lambda x: isinstance(x, Part.Edge), "is_face": lambda x: isinstance(x, Part.Face),
               "is_surface": lambda x: isinstance(x, (Part.Face, Part.Shell)),
               # the family's
               "fonts": fonts, "font_file": font_file, "text_faces": text_faces, "face_frame": face_frame, "outline_faces": outline_faces, "place_on": place_on,
               "pick_face": pick_face, "curve": _curve, "point": lambda p, what: FreeCAD.Vector(*picks.vec3(p, what)), "along_path": along_path,
               "refined": refined}
    return runners.tools(GROUP, s, helpers, family="draft")
