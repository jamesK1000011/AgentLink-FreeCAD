# SPDX-License-Identifier: LGPL-2.1-or-later
# The Draft workbench's own parametric objects, beside draft.py's lettering,
# outlines and arrays: 2D shapes (wire, rectangle, circle, arc, ellipse,
# polygon, B-spline, Bezier, point), dimensions and labels, link arrays
# (ortho, polar, circular, along a path, at points), clones, the modify
# tools (move, rotate, scale, mirror, offset, upgrade, downgrade, join,
# 2D fillet), layers, hatches, Draft and Sketch each way, 2D views of a
# body and facebinders. Draft runs headless; its objects open in the GUI.

import os

import FreeCAD
import Draft

from .. import runners
from .. import geometry as geo
from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "draft"
INFO = ("Draft: lettering, SVG/DXF outlines, arrays, and Draft's own parametric 2D shapes, dimensions, labels, link arrays, clones, "
        "move/rotate/scale/mirror/offset, upgrade/downgrade, layers, hatches, Draft↔Sketch, 2D views, facebinders; surfaces and textures.")

V = FreeCAD.Vector


def v3(a, what, default=None):
    return picks.vec3(a, what, default)


def pl_of(a):
    n = picks.direction(a.get("normal"), "normal", (0, 0, 1))
    return FreeCAD.Placement(v3(a.get("at"), "at", (0, 0, 0)), FreeCAD.Rotation(V(0, 0, 1), n))


def reading(o):
    sh = getattr(o, "Shape", None)
    out = {"object": o.Label, "type": (getattr(getattr(o, "Proxy", None), "Type", None) or o.TypeId.split("::")[-1])}
    if sh is not None and not sh.isNull():
        if sh.Edges:
            out["length"] = round(sum(e.Length for e in sh.Edges), 4)
        if sh.Faces:
            out["area"] = round(sh.Area, 4)
        if sh.Solids:
            out["volume"] = round(sh.Volume, 4)
        out["box"] = geo.box_json(sh, 3)["size"]
    return out


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def active():
        # Draft makes objects in the active document
        if FreeCAD.ActiveDocument is not doc():
            FreeCAD.setActiveDocument(doc().Name)

    def named(o, name, default):
        # unique among the others: Draft has already given it a label of its own
        if o is not None:
            want = name or default
            taken = {x.Label for x in doc().Objects if x is not o}
            lab, n = want, 2
            while lab in taken:
                lab = f"{want} {n}"
                n += 1
            o.Label = lab
        return o

    def finish(objs, tool, extra=None):
        objs = [o for o in (objs if isinstance(objs, list) else [objs]) if o is not None]
        if not objs:
            doc().recompute()
            raise ToolError("failed", "Draft made nothing from that.")
        return picks.finish(s, tool, lambda: reading(objs[0]) if len(objs) == 1 else {"objects": [reading(o) for o in objs]},
                            objs=objs, refuse="Draft refused it: {msg} — nothing was kept.", extra=extra)

    def objs_of(refs, what="objects"):
        refs = picks.ref_list(refs, f"{what}: [names].")
        return [picks.find(doc(), r) for r in refs]

    # ---- shapes ----

    def draft_shape(a):
        active()
        kind = a.get("kind")
        face = a.get("face")
        if face is not None and not isinstance(face, bool):
            raise bad("face: true (a closed shape is a filled face) or false (its outline only); left out, Draft's Make Face preference decides (true as installed).")
        pl = pl_of(a)

        def over0(key, what):
            v = picks.num(a.get(key), key)
            if v <= 0:
                raise bad(f"{key}: {what}, mm, over 0.")
            return v

        if kind in ("wire", "bspline", "bezier"):
            # points are where they are given: at and normal do not move them
            pts = [v3(p, "points") for p in (a.get("points") or [])]
            closed = bool(a.get("closed"))
            if kind != "bezier" and len(pts) > 2 and pts[0].isEqual(pts[-1], 1e-9):
                pts, closed = pts[:-1], True  # Draft closes a curve whose ends are the same point
            if len(pts) < 2 or (len(pts) == 2 and pts[0].isEqual(pts[1], 1e-9)):
                raise bad("points: two or more different [x, y, z].")
            if closed and len(pts) < 3:
                raise bad("closed: needs three or more points.")
            fn = {"wire": Draft.make_wire, "bspline": Draft.make_bspline, "bezier": Draft.make_bezcurve}[kind]
            o = fn(pts, closed=closed, face=face)
        elif kind == "rectangle":
            o = Draft.make_rectangle(over0("length", "its size along x"), over0("height", "its size along y"), placement=pl, face=face)
        elif kind in ("circle", "arc"):
            r = over0("radius", "the radius")
            kw = {"placement": pl, "face": face}
            if kind == "arc":
                st, en = picks.num(a.get("start", 0), "start"), picks.num(a.get("end", 90), "end")
                if abs(st - en) % 360 < 1e-9:
                    raise bad("start, end: degrees, counter-clockwise from x, and not the same angle (kind circle makes the whole circle).")
                kw.update(startangle=st, endangle=en)
            o = Draft.make_circle(r, **kw)
        elif kind == "ellipse":
            o = Draft.make_ellipse(over0("major", "the long axis, end to end") / 2, over0("minor", "the short axis, end to end") / 2, placement=pl, face=face)
        elif kind == "polygon":
            sides = a.get("sides", 6)
            if isinstance(sides, bool) or not isinstance(sides, int) or sides < 3:
                raise bad("sides: a whole number, 3 or more.")
            o = Draft.make_polygon(sides, over0("radius", "the radius of the circle it is drawn on"), inscribed=bool(a.get("inscribed", True)), placement=pl, face=face)
        elif kind == "point":
            p = v3(a.get("at"), "at")
            o = Draft.make_point(p.x, p.y, p.z)
        else:
            raise bad("kind: wire, rectangle, circle, arc, ellipse, polygon, bspline, bezier or point.")
        return finish(named(o, a.get("name"), kind.capitalize()), "draft_shape")

    # ---- dimensions and labels ----

    def draft_dimension(a):
        active()
        kind = a.get("kind", "linear")
        line = v3(a.get("at"), "at") if a.get("at") is not None else None

        def shape_of(o):
            sh = getattr(o, "Shape", None)
            if sh is None or sh.isNull():
                raise bad(f"object: {o.Label} has no shape to measure — a Draft shape, a sketch or a body.")
            return sh

        def make():
            if kind == "linear":
                if a.get("object"):
                    o = picks.find(doc(), a["object"])
                    n = len(shape_of(o).Vertexes)
                    vs = a.get("vertices", [1, 2])
                    if not (isinstance(vs, list) and len(vs) == 2 and all(isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= n for i in vs) and vs[0] != vs[1]):
                        raise bad(f"vertices: [i, j], two different vertex numbers of {o.Label}, counted from 1 as Vertex1 … Vertex{n} (shape_query lists them).")
                    return Draft.make_linear_dimension_obj(o, vs[0], vs[1], line)
                p1, p2 = v3(a.get("from"), "from"), v3(a.get("to"), "to")
                if p1.isEqual(p2, 1e-9):
                    raise bad("from, to: two different points.")
                return Draft.make_linear_dimension(p1, p2, line)
            if kind in ("radius", "diameter"):
                o = picks.find(doc(), a.get("object"))
                edges = shape_of(o).Edges
                k = a.get("edge", 1)
                if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= len(edges):
                    raise bad(f"edge: which edge of {o.Label}, counted from 1 as Edge1 … Edge{len(edges)}.")
                if getattr(getattr(edges[k - 1], "Curve", None), "TypeId", "") != "Part::GeomCircle":
                    round_ = [i for i, e in enumerate(edges, 1) if getattr(getattr(e, "Curve", None), "TypeId", "") == "Part::GeomCircle"]
                    raise bad(f"edge: Edge{k} of {o.Label} is not a circle or an arc — " + (f"its round edges: {', '.join(str(i) for i in round_[:12])}." if round_ else "it has no round edge; kind linear measures between points."))
                return Draft.make_radial_dimension_obj(o, k, kind, line)
            if kind == "angular":
                ang = a.get("angles") or [0, 90]
                if not (isinstance(ang, list) and len(ang) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in ang)):
                    raise bad("angles: [a, b] degrees, counter-clockwise from x about normal.")
                return Draft.make_angular_dimension(v3(a.get("center"), "center", (0, 0, 0)), [float(x) for x in ang], line or V(10, 10, 0),
                                                    picks.direction(a.get("normal"), "normal", (0, 0, 1)))
            raise bad("kind: linear (from, to — or object and vertices [i, j]), radius / diameter (object, edge), angular (center, angles [a, b]).")

        n0 = len(doc().Objects)
        try:
            d = make()
        except AttributeError as e:
            # With the window up Draft asks the active 3D view which way it
            # looks; a spreadsheet, a drawing page or the start page in front
            # has no view direction.
            for x in doc().Objects[n0:]:
                doc().removeObject(x.Name)
            if FreeCAD.GuiUp and "getViewDirection" in str(e):
                raise ToolError("invalid_state", "Draft needs the model's 3D view in front to make a dimension, and another tab is (a drawing page, a spreadsheet, the start page): bring the 3D view's tab to the front in FreeCAD, then call this again. Nothing was kept.")
            raise
        out = finish(named(d, a.get("name"), "Dimension"), "draft_dimension")
        try:
            if hasattr(d, "Distance"):
                out["measures"] = round(float(d.Distance), 4)
            else:
                # Draft works the angle out in its view provider (the window);
                # the same sum here, so the reply is right without one.
                a1, a2 = float(d.FirstAngle), float(d.LastAngle)
                out["measures"] = round(a2 - a1 if a2 > a1 else 360 - a1 + a2, 4)
            out["unit"] = "deg" if kind == "angular" else "mm"
        except Exception:
            pass
        return out

    def draft_label(a):
        active()
        tp = v3(a.get("target"), "target")
        at = v3(a.get("at"), "at", (tp.x + 20, tp.y + 20, tp.z))
        kw = {"target_point": tp, "placement": FreeCAD.Placement(at, FreeCAD.Rotation())}
        if a.get("object"):
            label, sub, _ = picks.resolve(s, a["object"])
            kw["target_object"] = picks.find(doc(), label)
            if sub:
                kw["subelements"] = sub
        show = a.get("show", "custom")
        kinds = {"custom": "Custom", "name": "Label", "area": "Area", "length": "Length", "position": "Position", "material": "Material", "tag": "Tag"}
        if show not in kinds:
            raise bad(f"show: {', '.join(kinds)}.")
        if show != "custom" and kw.get("target_object") is None:
            raise bad(f"show {show}: needs object (\"Body\", or \"Body.Face6\" / \"Body.Edge3\" for the area or length of one element); show custom takes text instead.")
        kw["label_type"] = kinds[show]
        if show == "custom":
            kw["custom_text"] = str(a.get("text") or "Label").split("\n")
        o = Draft.make_label(**kw)
        doc().recompute()
        text = [str(x) for x in (getattr(o, "Text", []) or []) if str(x)]
        if not text and show in ("area", "length", "position", "name") and kw.get("target_object") is not None:
            # Draft's label reads these itself when it recomputes; this is only for a release that left the text empty.
            t_o = kw["target_object"]
            el = t_o.Shape.getElement(kw["subelements"]) if kw.get("subelements") else t_o.Shape
            text = [{"area": lambda: f"{el.Area:.2f} mm²", "length": lambda: f"{el.Length:.2f} mm",
                     "position": lambda: "{:.2f}, {:.2f}, {:.2f}".format(*el.BoundBox.Center),
                     "name": lambda: t_o.Label}[show]()]
            o.LabelType = "Custom"
            o.CustomText = text
        return finish(named(o, a.get("name"), "Label"), "draft_label", {"text": text})

    # ---- arrays and clones ----

    def draft_link_array(a):
        active()
        base = picks.find(doc(), a.get("object"))
        kind = a.get("kind", "ortho")
        link = bool(a.get("link", True))
        def whole(key, default, least):
            v = a.get(key, default)
            if isinstance(v, bool) or not isinstance(v, int) or v < least:
                raise bad(f"{key}: a whole number, {least} or more.")
            return v

        if kind == "ortho":
            cnt, spc = a.get("count") or [2, 2, 1], a.get("spacing") or [10, 10, 10]
            if not (isinstance(cnt, list) and 1 <= len(cnt) <= 3 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in cnt)):
                raise bad("count: [nx, ny, nz] whole numbers, each 1 or more (the original counts as one).")
            if not (isinstance(spc, list) and 1 <= len(spc) <= 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in spc)):
                raise bad("spacing: [dx, dy, dz] mm from one copy to the next (not the gap between them).")
            n = cnt + [1, 1, 1]
            sp = [float(x) for x in spc] + [10, 10, 10]
            if any(n[i] > 1 and sp[i] == 0 for i in range(3)):
                raise bad("spacing: not 0 along a direction that has more than one copy — they would lie on top of each other.")
            o = Draft.make_ortho_array(base, V(sp[0], 0, 0), V(0, sp[1], 0), V(0, 0, sp[2]), n[0], n[1], n[2], use_link=link)
        elif kind == "polar":
            o = Draft.make_polar_array(base, whole("count", 6, 2), picks.num(a.get("angle", 360), "angle"), v3(a.get("center"), "center", (0, 0, 0)), use_link=link)
        elif kind == "circular":
            rs, ts = picks.num(a.get("ringSpacing", 20), "ringSpacing"), picks.num(a.get("tangentSpacing", 10), "tangentSpacing")
            if rs <= 0 or ts <= 0:
                raise bad("ringSpacing (between rings) and tangentSpacing (between copies along a ring): mm, over 0.")
            # rings counts the original at the centre as the first ring
            o = Draft.make_circular_array(base, rs, ts, whole("rings", 3, 2), whole("symmetry", 1, 1), use_link=link)
        elif kind == "path":
            path = picks.find(doc(), a.get("path"), "path")
            if not getattr(getattr(path, "Shape", None), "Edges", None):
                raise bad(f"path: {path.Label} has no edges to follow — a Draft wire, a sketch or another object with edges.")
            o = Draft.make_path_array(base, path, whole("count", 4, 1), align=bool(a.get("align")), use_link=link)
        elif kind == "points":
            pts = picks.find(doc(), a.get("points"), "points")
            if not (getattr(getattr(pts, "Shape", None), "Vertexes", None) or hasattr(pts, "Mesh") or hasattr(pts, "Points")):
                raise bad(f"points: {pts.Label} holds no points — a sketch or compound of points, a Draft wire (its vertices), a mesh or a point cloud.")
            o = Draft.make_point_array(base, pts, use_link=link)
        else:
            raise bad("kind: ortho (count [nx, ny, nz], spacing [dx, dy, dz]), polar (count, angle, center), circular (rings, ringSpacing, tangentSpacing), path (path, count, align), points (points: a compound or sketch of points).")
        out = finish(named(o, a.get("name"), f"{kind.capitalize()} array"), "draft_link_array")
        out["count"] = getattr(o, "Count", None)
        out["of"] = base.Label
        out["note"] = "Parametric: object_set changes its counts and spacing; the copies follow the original (hidden in the window while the array shows it)."
        return out

    def draft_clone(a):
        active()
        o = picks.find(doc(), a.get("object"))
        sc = a.get("scale")
        # make_clone's second argument is a displacement, not a scale: the
        # scale goes on the clone's own Scale property.
        if sc is not None:
            if isinstance(sc, (int, float)) and not isinstance(sc, bool):
                sc = [sc, sc, sc]
            if not (isinstance(sc, list) and len(sc) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in sc)):
                raise ToolError("invalid_input", "scale: a factor above 0, or [sx, sy, sz].")
        if getattr(o, "Shape", None) is None:
            raise bad(f"object: {o.Label} has no shape to clone ({o.TypeId}).")
        c = Draft.make_clone(o)
        if sc is not None:
            if "Scale" not in c.PropertiesList:
                # a BIM object clones as a BIM object (CloneOf), which has no Scale
                doc().removeObject(c.Name)
                raise bad(f"scale: {o.Label} is a BIM object, and its clone cannot be scaled — leave scale out, or draft_modify op scale with copy: true.")
            c.Scale = V(*[float(x) for x in sc])
            doc().recompute()
        if a.get("move"):
            c.Placement = FreeCAD.Placement(v3(a["move"], "move"), FreeCAD.Rotation()).multiply(c.Placement)
        return finish(named(c, a.get("name"), f"{o.Label} clone"), "draft_clone", {"of": o.Label})

    # ---- modify ----

    def pointed(o):
        if "Points" not in o.PropertiesList or getattr(getattr(o, "Proxy", None), "Type", "") not in ("Wire", "BSpline", "BezCurve"):
            raise bad(f"{o.Label} is not a Draft wire, B-spline or Bezier curve (they hold points; draft_shape makes them, draft_from_sketch turns a sketch's lines into wires).")
        pl = o.Placement
        return [pl.multVec(p) for p in o.Points], pl

    def set_points(o, pts, pl):
        inv = pl.inverse()
        o.Points = [inv.multVec(p) for p in pts]

    def edit_points(op, objs, a):
        """The point edits Draft does by hand: split, stretch, trim/extend, wire ↔ B-spline."""
        if op == "split":
            if len(objs) != 1:
                raise bad("split: one wire.")
            o = objs[0]
            pts, pl = pointed(o)
            closed = bool(getattr(o, "Closed", False))
            n = len(pts) if closed else len(pts) - 1  # a closed wire's last segment runs back to its first point
            k = a.get("edge", 0)
            if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= n:
                raise bad(f"edge: which segment of {o.Label}, 1 … {n} (segment 1 runs from its first point to its second).")
            if closed:
                # As Draft's Split does on a closed wire: that segment becomes a
                # wire of its own and the rest stays as one open wire (at is not used).
                p, q = pts[k - 1], pts[k % len(pts)]
                set_points(o, pts[k:] + pts[:k] if k < len(pts) else list(pts), pl)
                o.Closed = False
                other = Draft.make_wire([p, q], closed=False)
                other.Label = s.unique(f"{o.Label} split", other)
                return [o, other]
            p, q = pts[k - 1], pts[k]
            if a.get("at") is not None:
                # onto the segment, as Draft projects the picked point
                d = q - p
                t = (v3(a.get("at"), "at") - p).dot(d) / (d.Length ** 2)
                if not 1e-9 < t < 1 - 1e-9:
                    raise bad(f"at: lies beyond segment {k} of {o.Label}, which runs from {[round(c, 3) for c in p]} to {[round(c, 3) for c in q]} — a point between them, or leave at out for its middle.")
                cut = p + d * t
            else:
                cut = (p + q) * 0.5
            first, second = pts[:k] + [cut], [cut] + pts[k:]
            set_points(o, first, pl)
            other = Draft.make_wire(second, closed=False)
            other.Label = s.unique(f"{o.Label} split", other)
            return [o, other]
        if op == "stretch":
            box = a.get("box")
            if not (isinstance(box, list) and len(box) == 2):
                raise bad("box: [[xmin, ymin, zmin], [xmax, ymax, zmax]] — the points inside it move.")
            lo, hi = v3(box[0], "box"), v3(box[1], "box")
            by = v3(a.get("by"), "by")
            moved = 0
            for o in objs:
                pts, pl = pointed(o)
                new = []
                for p in pts:
                    inside = all(min(getattr(lo, c), getattr(hi, c)) - 1e-9 <= getattr(p, c) <= max(getattr(lo, c), getattr(hi, c)) + 1e-9 for c in "xyz")
                    new.append(p + by if inside else p)
                    moved += inside
                set_points(o, new, pl)
            if not moved:
                raise ToolError("failed", "No point lies inside the box: nothing was stretched.")
            return objs
        if op == "extend":
            by = float(a.get("length", 0))
            for o in objs:
                pts, pl = pointed(o)
                if len(pts) < 2:
                    continue
                if a.get("end", "end") == "start":
                    d = pts[0] - pts[1]
                    L = d.Length  # before normalize(), which changes d in place
                    if L + by <= 0:
                        raise bad("length: trims past the whole first segment.")
                    pts[0] = pts[1] + d.normalize() * (L + by)
                else:
                    d = pts[-1] - pts[-2]
                    L = d.Length
                    if L + by <= 0:
                        raise bad("length: trims past the whole last segment.")
                    pts[-1] = pts[-2] + d.normalize() * (L + by)
                set_points(o, pts, pl)
            return objs
        made = []
        for o in objs:
            pts, _pl = pointed(o)
            closed = bool(getattr(o, "Closed", False))
            n = Draft.make_bspline(pts, closed=closed) if op == "to_bspline" else Draft.make_wire(pts, closed=closed)
            label = o.Label
            made.append(n)
            if a.get("delete", True):
                # what used the old one now uses the new one
                picks.repoint(doc(), o, n)
                doc().removeObject(o.Name)
            n.Label = s.unique(label, n)
        return made

    def alive(o):
        # False for an object Draft has removed from the document
        try:
            return o.Document is not None and o.Name is not None
        except Exception:
            return False

    def draft_modify(a):
        active()
        op = a.get("op")
        objs = objs_of(a.get("objects"))
        copy = bool(a.get("copy"))
        n0 = len(doc().Objects)
        labels = ", ".join(o.Label for o in objs)
        if op == "move":
            r = Draft.move(objs, v3(a.get("by"), "by"), copy=copy)
        elif op == "rotate":
            r = Draft.rotate(objs, picks.num(a.get("angle", 90), "angle"), v3(a.get("center"), "center", (0, 0, 0)), picks.direction(a.get("axis"), "axis", (0, 0, 1)), copy=copy)
        elif op == "scale":
            f = a.get("factor", 2)
            f = [f, f, f] if isinstance(f, (int, float)) and not isinstance(f, bool) else f
            if not (isinstance(f, list) and len(f) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x != 0 for x in f)):
                raise bad("factor: a number, or [sx, sy, sz] — none of them 0 (a negative one mirrors).")
            r = Draft.scale(objs, V(*[float(x) for x in f]), v3(a.get("center"), "center", (0, 0, 0)), copy=copy)
        elif op == "mirror":
            p1, p2 = v3(a.get("from"), "from"), v3(a.get("to"), "to")
            if p1.isEqual(p2, 1e-9):
                raise bad("from, to: two different points of the mirror line (it lies in Draft's working plane, XY unless one was set in the window).")
            r = Draft.mirror(objs, p1, p2)
        elif op == "offset":
            if len(objs) != 1:
                raise bad("offset: one wire or shape.")
            o = objs[0]
            kind_ = getattr(getattr(o, "Proxy", None), "Type", "")
            by = v3(a.get("by"), "by")
            if by.Length < 1e-9:
                raise bad("by: [x, y, z] from the first edge to where its offset copy goes — its length is the distance, its direction the side.")
            if kind_ == "BSpline":
                # Draft's own offset of a B-spline takes the new points, worked out in its window
                raise bad(f"offset: {o.Label} is a Draft B-spline, which Draft offsets only in its window — part_offset2d offsets any flat curve.")
            if kind_ == "Circle":
                # Draft takes the new radius here, not a vector: the radius of the circle through the first vertex moved by `by`
                sh = o.Shape
                start = sh.Vertexes[0].Point if sh.Vertexes else o.Placement.multVec(V(float(o.Radius), 0, 0))
                delta = (start + by - o.Placement.Base).Length
                if delta < 1e-9:
                    raise bad("by: moves the circle's first vertex onto its centre — a radius over 0 is needed.")
            else:
                delta = by
            try:
                r = Draft.offset(o, delta, copy=copy)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError("failed", f"Draft could not offset {o.Label} by that: {e} — a smaller distance, the other side, or part_offset2d for a shape Draft's offset does not take.")
            if r is None:
                raise ToolError("failed", f"Draft could not offset {o.Label} — part_offset2d offsets any flat face or wire.")
        elif op in ("upgrade", "downgrade"):
            was = [(o, getattr(o, "Closed", None)) for o in objs]
            r = (Draft.upgrade if op == "upgrade" else Draft.downgrade)(objs, delete=bool(a.get("delete", True)))
            made_ = list(r[0]) if isinstance(r, (list, tuple)) and r and isinstance(r[0], (list, tuple)) else []
            if not made_:
                # Draft closes an open Draft wire in place: nothing new, but done
                made_ = [o for o, c in was if c is False and alive(o) and getattr(o, "Closed", None) is True]
            if not made_:
                raise ToolError("failed", f"Nothing to {op}: {labels} {'are already as far as they go (edges that meet upgrade to a wire, a closed wire to a face, faces that close a volume to a solid)' if op == 'upgrade' else 'cannot be taken apart further'}.")
            r = made_
        elif op == "join":
            if len(objs) < 2:
                raise bad("join: two or more Draft wires whose ends meet.")
            for o in objs:
                if getattr(getattr(o, "Proxy", None), "Type", "") != "Wire":
                    raise bad(f"join: {o.Label} is not a Draft wire (draft_shape kind wire makes them; op upgrade joins other edges that meet into one wire).")
            left = Draft.join_wires(objs)
            # join_wires answers the wires left, joined or not
            if left is None or len(left) >= len(objs):
                raise ToolError("failed", f"Nothing joined: no two of {labels} share an end point (within Draft's tolerance). Nothing was changed.")
            r = list(left)
        elif op == "fillet":
            if len(objs) != 2:
                raise bad("fillet: two lines or wires that meet.")
            rad = picks.num(a.get("radius", 5), "radius")
            if rad <= 0:
                raise bad("radius: mm, over 0.")
            r = Draft.make_fillet(objs, rad, chamfer=bool(a.get("chamfer")), delete=bool(a.get("delete")))
            if r is None:
                raise ToolError("failed", f"No {'chamfer' if a.get('chamfer') else 'fillet'} of {rad:g} mm fits between {labels}: they must be two single edges (lines or arcs) that share an end point, and the radius must fit on both. Nothing was changed.")
        elif op in ("split", "stretch", "extend", "to_bspline", "to_wire"):
            r = edit_points(op, objs, a)
        else:
            raise bad("op: move (by), rotate (angle, center, axis), scale (factor, center), mirror (from, to: a line in the plane), offset (by: a vector to the first vertex's side), upgrade, downgrade, join, fillet (radius, chamfer), split (at a point, edge n), stretch (box [[min], [max]], by), extend (length mm, end start | end; negative trims), to_bspline, to_wire.")
        if r is None and op in ("move", "rotate", "scale", "mirror"):
            raise ToolError("failed", f"Draft could not {op} {labels}: an object whose placement is locked, or (scale) one with no shape. Nothing was changed.")
        made = [] if op in ("split", "stretch", "extend", "to_bspline", "to_wire", "join") else [o for o in doc().Objects[n0:]]  # those answer all their results themselves
        res = made or ([r] if r is not None and not isinstance(r, (list, tuple, bool)) else list(r) if isinstance(r, (list, tuple)) else objs)
        res = [(x[0] if x else None) if isinstance(x, (list, tuple)) else x for x in res if x is not None]
        res = [x for x in res if x is not None]
        res = [x for x in res if alive(x) and hasattr(x, "Label")]
        extra = {"op": op}
        if op == "upgrade" and len(res) >= 2:
            # Edges are joined where their ends meet within FreeCAD's 1e-7 mm: ends a
            # hair further apart (points typed to six decimals) stay two wires, and
            # nothing else says why.
            ends = []
            for x in res:
                sh = getattr(x, "Shape", None)
                for w in (getattr(sh, "Wires", None) or []) if sh is not None and not sh.Faces else []:
                    if not w.isClosed():
                        vs = w.OrderedVertexes
                        ends += [(x.Label, vs[0].Point), (x.Label, vs[-1].Point)]
            near = min(((p.distanceToPoint(q), la, lb) for i, (la, p) in enumerate(ends) for lb, q in ends[i + 1:] if la != lb), default=None)
            if near and 1e-7 < near[0] <= 0.01:
                extra["note"] = (f"{near[1]} and {near[2]} end {near[0]:.2g} mm apart and were not joined: FreeCAD joins ends that meet within 1e-7 mm. "
                                 "Give their points with every decimal (or move one end onto the other), then upgrade again.")
        return finish(res or [o for o in objs if alive(o)], "draft_modify", extra)

    # ---- layers, hatches ----

    def draft_layer(a):
        active()
        name = a.get("name")
        if not isinstance(name, str) or not name.strip():
            raise bad("name: the layer's name (an existing layer by that name is used, else one is made).")
        lw = a.get("lineWidth")
        if lw is not None and (isinstance(lw, bool) or not isinstance(lw, (int, float)) or lw <= 0):
            raise bad("lineWidth: screen pixels, over 0.")
        lay = next((o for o in doc().Objects if getattr(getattr(o, "Proxy", None), "Type", "") == "Layer" and name in (o.Label, o.Name)), None)
        made = lay is None
        if made:
            kw = {"name": name}
            if lw:
                kw["line_width"] = float(lw)
            lay = Draft.make_layer(**kw)
        elif lw and FreeCAD.GuiUp and hasattr(getattr(lay, "ViewObject", None), "LineWidth"):
            lay.ViewObject.LineWidth = float(lw)
        if a.get("objects"):
            grp = list(lay.Group)
            for o in objs_of(a["objects"]):
                if getattr(getattr(o, "Proxy", None), "Type", "") in ("Layer", "LayerContainer"):
                    raise bad(f"objects: {o.Label} is a layer itself — layers do not nest.")
                if o not in grp:
                    grp.append(o)
            lay.Group = grp  # Draft takes each out of the layer it was on
        extra = None if FreeCAD.GuiUp else {"note": "No window here: the layer groups the objects, but its line width and colours show only once the file is open in FreeCAD."}
        return picks.finish(s, "draft_layer", lambda: {"layer": lay.Label, "made": made, "objects": [o.Label for o in lay.Group]}, extra=extra)

    def draft_hatch(a):
        active()
        base = picks.find(doc(), a.get("object"))
        sh = getattr(base, "Shape", None)
        if sh is None or sh.isNull() or not any(f.findPlane() is not None for f in sh.Faces):
            raise bad(f"object: {base.Label} has no flat face to hatch — a closed Draft shape made with face: true, a face, or a body (each flat face is hatched). draft_modify op upgrade makes a closed wire a face.")
        sc = picks.num(a.get("scale", 1), "scale")
        if sc <= 0:
            raise bad("scale: over 0 (1 draws the pattern at its own spacing in mm; FCPAT's Diagonal4 is 4 mm apart).")
        pat = a.get("file")
        if pat:
            pat = paths.local(s, pat)
        else:
            pat = os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "PAT", "FCPAT.pat")
        if not os.path.isfile(pat) or not pat.lower().endswith(".pat"):
            raise ToolError("not_found", f"file: no .pat file at {pat} — leave file out for FreeCAD's own FCPAT.pat.")
        name = a.get("pattern", "Diagonal4")
        with open(pat, encoding="utf-8", errors="replace") as f:
            names = [ln[1:].split(",")[0].strip() for ln in f if ln.startswith("*")]
        if name not in names:
            raise bad(f"pattern: one of {', '.join(names[:20])}{' …' if len(names) > 20 else ''} (in {os.path.basename(pat)}).")
        h = Draft.make_hatch(base, pat, name, sc, picks.num(a.get("rotation", 0), "rotation"))
        out = finish(named(h, a.get("name"), f"{base.Label} hatch"), "draft_hatch", {"pattern": name, "file": os.path.basename(pat)})
        if "length" not in out:
            out["warning"] = "The hatch drew no lines (see the report view): a larger face or a smaller scale, and check the pattern file."
        return out

    # ---- Draft and Sketch, 2D views, facebinders ----

    def draft_from_sketch(a):
        active()
        objs = objs_of(a.get("objects"))
        for o in objs:
            if not getattr(getattr(o, "Shape", None), "Edges", None):
                raise bad(f"objects: {o.Label} has no edges to turn into Draft objects — a sketch, a wire or a shape with edges.")
        r = Draft.draftify(objs, makeblock=bool(a.get("block")), delete=bool(a.get("delete")))
        res = r if isinstance(r, list) else [r]
        return finish([x for x in res if x is not None], "draft_from_sketch")

    def draft_2d_view(a):
        active()
        base = picks.find(doc(), a.get("object"))
        d = picks.direction(a.get("direction"), "direction", (0, 0, 1))
        kind_ = getattr(getattr(base, "Proxy", None), "Type", "")
        if a.get("section") and kind_ != "SectionPlane":
            # Shape2DView's cut modes read the cutting plane off a BIM section plane; on anything else they draw nothing
            raise bad(f"section: Draft draws cut faces only of a BIM section plane (bim_section makes one; give it as object), and {base.Label} is not one. For a cut through a body: part_section, or td_section on a drawing.")
        sh_ = getattr(base, "Shape", None)
        if kind_ not in ("SectionPlane", "BuildingPart", "IfcAnnotation") and not base.isDerivedFrom("App::DocumentObjectGroup") and (sh_ is None or sh_.isNull()):
            raise bad(f"object: {base.Label} has no shape to project — a body, a shape, or a group of them.")
        mk = getattr(Draft, "make_shape_2d_view", None) or Draft.make_shape2dview
        try:
            v = mk(base, d)
        except TypeError:
            v = mk(base, projection=d)
        if a.get("hidden") and "HiddenLines" in v.PropertiesList:
            v.HiddenLines = True
        if a.get("section") and "ProjectionMode" in v.PropertiesList:
            v.ProjectionMode = "Cutfaces"
        out = finish(named(v, a.get("name"), f"{base.Label} 2D view"), "draft_2d_view", {"use": "export (DXF) writes it; draft_dimension measures on it."})
        if "length" not in out:
            out["warning"] = "The view came out empty: nothing of the object shows from that direction, or FreeCAD could not project it (see the report view)."
        return out

    def draft_facebinder(a):
        active()
        sel = []
        for r in a.get("faces") or []:
            label, sub, _ = picks.resolve(s, r)
            if not sub or not sub.startswith("Face"):
                raise bad(f"{r}: a face (\"Body.Face6\").")
            sel.append((picks.find(doc(), label), [sub]))
        if not sel:
            raise bad("faces: [\"Body.Face6\", …].")
        try:
            fb = Draft.make_facebinder(sel)
        except Exception:
            fb = Draft.make_facebinder([(o, tuple(sub)) for o, sub in sel])
        if a.get("extrusion") and "Extrusion" in fb.PropertiesList:
            fb.Extrusion = picks.num(a["extrusion"], "extrusion")
        if a.get("offset") and "Offset" in fb.PropertiesList:
            fb.Offset = picks.num(a["offset"], "offset")
        return finish(named(fb, a.get("name"), "Facebinder"), "draft_facebinder", {"note": "It follows the faces; extrusion makes a skin of that thickness (a gasket, a pad on a face)."})

    xyz = {"type": "array", "items": {}}
    # ---- working-plane proxies and annotation styles ----

    def draft_plane(a):
        """A saved working plane (Draft's working-plane proxy): at a point
        with a normal, or on a face of a body; the sketches and Draft shapes
        that follow can be laid on it."""
        if a.get("face"):
            label, sub, f = picks.resolve(s, a["face"])
            if not sub or not sub.startswith("Face") or f.findPlane() is None:
                raise ToolError("invalid_input", "face: a flat face (\"Box.Face6\").")
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            at = f.CenterOfMass
        else:
            at = picks.vec3(a.get("at", [0, 0, 0]), "at")
            n = picks.direction(a.get("normal", [0, 0, 1]), "normal")
        rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), n)
        if a.get("rotate"):
            rot = rot.multiply(FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), float(a["rotate"])))
        pl = FreeCAD.Placement(at, rot)
        mk = getattr(Draft, "make_workingplaneproxy", None) or getattr(Draft, "makeWorkingPlaneProxy", None)
        if mk is None:
            raise ToolError("unavailable", "This FreeCAD's Draft has no working-plane proxy.")
        active()
        n0 = len(s.doc.Objects)
        try:
            o = mk(pl)
        except AttributeError as e:
            # With the window up the proxy stores the 3D view's camera: another tab in front has none.
            for x in s.doc.Objects[n0:]:
                s.doc.removeObject(x.Name)
            if FreeCAD.GuiUp:
                raise ToolError("invalid_state", f"Draft stores the 3D view's camera with a working plane, and the tab in front is not a 3D view ({e}): bring the model's 3D view to the front in FreeCAD, then call this again. Nothing was kept.")
            raise
        o.Label = s.unique(a.get("name") or "Working plane", o)
        s.doc.recompute()
        s.snapshot("draft_plane")
        x = rot.multVec(FreeCAD.Vector(1, 0, 0))
        return {"plane": o.Label, "origin": [round(c, 3) for c in at], "normal": [round(c, 4) for c in n], "xAxis": [round(c, 4) for c in x], "step": len(s.steps),
                "note": "In FreeCAD's window a double-click on it makes it the working plane; here it records the plane for drawings and sketches to use."}

    # Draft 1.1 keeps start and end arrows apart and an arrow's type as its
    # index in ARROW_TYPES; it reads a style back comparing each value's
    # Python type with its default's (draftutils.utils.repair_annotation_style),
    # and a string where it wants a number is passed to float().
    ARROWS = ("Dot", "Circle", "Arrow", "Tick", "Tick-2", "None")
    STYLE_KEYS = {"ArrowSize": float, "ArrowSizeStart": float, "ArrowSizeEnd": float, "ArrowType": "arrow", "ArrowTypeStart": "arrow", "ArrowTypeEnd": "arrow",
                  "Decimals": int, "DimOvershoot": float, "ExtLines": float, "ExtOvershoot": float, "FontName": str, "FontSize": float,
                  "LineColor": int, "LineSpacing": float, "LineWidth": int, "ScaleMultiplier": float, "ShowLine": bool, "ShowUnit": bool, "TextColor": int,
                  "TextSpacing": float, "UnitOverride": str}

    def style_value(k, v):
        kind = STYLE_KEYS[k]
        if kind == "arrow":
            if isinstance(v, str):
                hit = next((i for i, n in enumerate(ARROWS) if n.lower() == v.strip().lower()), None)
                if hit is None:
                    raise ToolError("invalid_input", f"values.{k}: one of {', '.join(ARROWS)} (or its index 0 … {len(ARROWS) - 1}).")
                return hit
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < len(ARROWS):
                raise ToolError("invalid_input", f"values.{k}: one of {', '.join(ARROWS)} (or its index 0 … {len(ARROWS) - 1}).")
            return v
        if kind is bool:
            if not isinstance(v, bool):
                raise ToolError("invalid_input", f"values.{k}: true or false.")
            return v
        if kind is str:
            if not isinstance(v, str):
                raise ToolError("invalid_input", f"values.{k}: text.")
            return v
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ToolError("invalid_input", f"values.{k}: a number" + (" (a colour: 0xRRGGBBAA as one whole number, e.g. 255 for black)." if k.endswith("Color") else "."))
        return kind(v)

    def draft_style(a):
        """Annotation styles as Draft keeps them (the document's Meta
        Draft_Style_<name>): set, list, delete, and apply to dimensions, labels
        and texts."""
        import json

        d = s.doc
        meta = dict(d.Meta or {})
        action = a.get("action", "list")
        styles = {}
        for k, v in meta.items():
            if k.startswith("Draft_Style_"):
                try:
                    styles[k[len("Draft_Style_"):]] = json.loads(v)
                except ValueError:
                    styles[k[len("Draft_Style_"):]] = {}
        if action == "list":
            return {"styles": styles}
        name = a.get("name")
        if not name or not isinstance(name, str):
            raise ToolError("invalid_input", "name: the style's name.")

        def users(of):
            out = []
            if FreeCAD.GuiUp:
                for o in d.Objects:
                    vo = getattr(o, "ViewObject", None)
                    try:
                        if vo is not None and "AnnotationStyle" in vo.PropertiesList and vo.AnnotationStyle == of:
                            out.append(o)
                    except Exception:
                        pass
            return out

        def offer(vo, names):
            # the style list of an annotation is fixed when it is made: offer today's styles, keeping its own
            try:
                cur = vo.AnnotationStyle
            except Exception:
                cur = ""
            vo.AnnotationStyle = [""] + list(names)
            if cur in names:
                vo.AnnotationStyle = cur

        if action == "delete":
            if name not in styles:
                raise ToolError("not_found", f"style {name!r}: not in this document — its styles: {', '.join(styles) or 'none'}.")
            using = users(name)
            meta.pop("Draft_Style_" + name, None)
            d.Meta = meta
            for o in using:
                offer(o.ViewObject, [n for n in styles if n != name])
            s.snapshot("draft_style")
            return {"deleted": name, **({"unstyled": [o.Label for o in using]} if using else {})}
        if action == "set":
            vals = dict(styles.get(name, {}))
            given = a.get("values") or {}
            if not isinstance(given, dict) or (not given and name not in styles):
                raise ToolError("invalid_input", f"values: {{ key: value }} — keys {', '.join(STYLE_KEYS)}.")
            for k, v in given.items():
                if k not in STYLE_KEYS:
                    raise ToolError("invalid_input", f"values.{k}: one of {', '.join(STYLE_KEYS)}.")
                v = style_value(k, v)
                if k in ("ArrowSize", "ArrowType"):  # one value for both ends
                    vals.pop(k, None)
                    vals[k + "Start"] = vals[k + "End"] = v
                else:
                    vals[k] = v
            for k in ("ArrowType", "ArrowTypeStart", "ArrowTypeEnd"):  # a name written by an older Agent Link
                if isinstance(vals.get(k), str):
                    hit = next((i for i, n in enumerate(ARROWS) if n.lower() == vals[k].lower()), None)
                    if hit is None:
                        vals.pop(k)
                    else:
                        vals[k] = hit
            meta["Draft_Style_" + name] = json.dumps(vals)
            d.Meta = meta
            shown = []
            for o in users(name):  # what already wears the style follows it, as Draft's style editor does
                vo = o.ViewObject
                for k, v in vals.items():
                    if k in vo.PropertiesList:
                        try:
                            setattr(vo, k, (v | 0x000000FF) if vo.getTypeIdOfProperty(k) == "App::PropertyColor" else v)
                        except Exception:
                            pass
                shown.append(o.Label)
            s.snapshot("draft_style")
            return {"style": name, "values": vals, **({"updated": shown} if shown else {})}
        if action == "apply":
            if name not in styles:
                raise ToolError("not_found", f"style {name!r}: not in this document — its styles: {', '.join(styles) or 'none'} (draft_style action set makes one).")
            if not a.get("objects"):
                raise ToolError("invalid_input", "objects: the dimensions, labels and texts to show in the style.")
            done, later, why = [], [], None
            for r in a.get("objects") or []:
                o = picks.find(d, r)
                vo = getattr(o, "ViewObject", None)
                if vo is not None and "AnnotationStyle" in getattr(vo, "PropertiesList", []):
                    try:
                        offer(vo, list(styles))
                        vo.AnnotationStyle = name
                        done.append(o.Label)
                        continue
                    except Exception as e:
                        why = str(e)
                elif FreeCAD.GuiUp:
                    raise ToolError("invalid_input", f"objects: {o.Label} is not a Draft dimension, label or text (they carry an annotation style).")
                if "AgentLinkStyle" not in o.PropertiesList:
                    o.addProperty("App::PropertyString", "AgentLinkStyle", "AgentLink", "The Draft annotation style to show it in")
                o.AgentLinkStyle = name
                later.append(o.Label)
            s.snapshot("draft_style")
            out = {"style": name, "applied": done}
            if later:
                out["recorded"] = later
                out["note"] = (f"FreeCAD refused the style on these ({why}): its name is recorded on them only." if why else
                               "No window here to show styles: the name is recorded on them (property AgentLinkStyle); call apply again once the file is open in FreeCAD's window.")
            return out
        raise ToolError("invalid_input", "action: list | set (name, values) | apply (name, objects) | delete (name).")

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": doc, "active": active, "named": named, "finish": finish, "objs_of": objs_of}
    return runners.tools(GROUP, s, helpers) + [
        Tool("draft_plane", "A saved working plane (Draft's working-plane proxy): at [x,y,z] with normal, or on a flat face (\"Box.Face6\"); rotate degrees about the normal; name. It records the plane (reply: origin, normal, xAxis) and does not switch Draft's working plane. With the window up the 3D view must be the tab in front.",
             obj({"at": {"type": "array", "items": {"type": "number"}}, "normal": {"type": "array", "items": {"type": "number"}}, "face": {"type": "string"}, "rotate": {"type": "number"}, "name": {"type": "string"}}), draft_plane, changes=True),
        Tool("draft_style", "Draft annotation styles, kept in the document as Draft keeps them: action list | set (name, values { FontSize, FontName, ArrowSize, ArrowType (Dot, Circle, Arrow, Tick, Tick-2, None), Decimals, ShowUnit, UnitOverride, LineWidth, TextColor, LineColor (0xRRGGBBAA numbers), ScaleMultiplier, ExtLines, ExtOvershoot, DimOvershoot, LineSpacing, TextSpacing, ShowLine }) | apply (name, objects: dimensions, labels) | delete. Styles show only in the window: without one, apply only records the name (reply: recorded).",
             obj({"action": {"type": "string", "enum": ["list", "set", "apply", "delete"]}, "name": {"type": "string"}, "values": {"type": "object"}, "objects": {"type": "array", "items": {"type": "string"}}}), draft_style, changes=True),
        Tool("draft_shape", "A Draft 2D shape (parametric: object_set edits it): kind wire | bspline | bezier (points where given, closed; at and normal do not move these) | rectangle (length along x, height along y, corner at `at`) | circle (radius) | arc (radius, start, end degrees counter-clockwise from x) | ellipse (major, minor: whole axes) | polygon (sides, radius; inscribed false: flats on the radius) | point (at). at and normal place it. A closed shape is a filled face unless face: false. Reply: object, type, length, area, box.",
             obj({"kind": {"type": "string"}, "points": {"type": "array", "items": {}}, "closed": {"type": "boolean"}, "length": {"type": "number"}, "height": {"type": "number"}, "radius": {"type": "number"}, "start": {"type": "number"}, "end": {"type": "number"},
                  "major": {"type": "number"}, "minor": {"type": "number"}, "sides": {"type": "integer"}, "inscribed": {"type": "boolean"}, "face": {"type": "boolean"}, "at": xyz, "normal": xyz, "name": {"type": "string"}}, ["kind"]), draft_shape, changes=True),
        Tool("draft_dimension", "A Draft dimension in the 3D model (on a drawing: td_dim): kind linear (from, to; or object and vertices [i, j], numbered from 1, following it) | radius / diameter (object, edge: a circle or arc's number from 1) | angular (center, angles [a, b] degrees counter-clockwise, normal); at: a point the dimension line passes through (left out: on the measured line). Reply: measures, unit. With the window up the 3D view must be the tab in front. Looks: draft_style.",
             obj({"kind": {"type": "string"}, "from": xyz, "to": xyz, "object": {"type": "string"}, "vertices": {"type": "array", "items": {}}, "edge": {"type": "integer"}, "center": xyz, "angles": {"type": "array", "items": {}}, "normal": xyz, "at": xyz, "name": {"type": "string"}}), draft_dimension, changes=True),
        Tool("draft_label", "A Draft label: a leader from target [x,y,z] to text at [x,y,z]; show custom (text, \\n for lines) | name | area | length | position | material | tag of object (\"Body\", or \"Body.Face6\" / \"Body.Edge3\" for one element), which it follows. Reply: text.",
             obj({"target": xyz, "at": xyz, "object": {"type": "string"}, "show": {"type": "string"}, "text": {"type": "string"}, "name": {"type": "string"}}, ["target"]), draft_label, changes=True),
        Tool("draft_link_array", "A Draft array of any object, parametric (the copies follow it; the original is hidden in the window): kind ortho (count [nx,ny,nz] including the original, spacing [dx,dy,dz] from one copy to the next) | polar (count, angle, center; about z) | circular (rings counting the original, ringSpacing, tangentSpacing, symmetry) | path (path, count, align) | points (points: an object whose points place the copies); link: false makes real shapes, not links. Reply: count, of, box. object_set changes it (NumberX, IntervalX, NumberPolar, Angle …).",
             obj({"object": {"type": "string"}, "kind": {"type": "string"}, "count": {}, "spacing": {"type": "array", "items": {}}, "angle": {"type": "number"}, "center": xyz, "rings": {"type": "integer"}, "ringSpacing": {"type": "number"}, "tangentSpacing": {"type": "number"},
                  "symmetry": {"type": "integer"}, "path": {"type": "string"}, "align": {"type": "boolean"}, "points": {"type": "string"}, "link": {"type": "boolean"}, "name": {"type": "string"}}, ["object"]), draft_link_array, changes=True),
        Tool("draft_clone", "A Draft clone: a copy that follows the original (it starts on top of it); scale (a factor or [x,y,z]), move [x,y,z]. Reply: object, of, box.",
             obj({"object": {"type": "string"}, "scale": {}, "move": xyz, "name": {"type": "string"}}, ["object"]), draft_clone, changes=True),
        Tool("draft_modify", "Draft's modify tools on objects: op move (by) | rotate (angle, center, axis) | scale (factor, center) | mirror (from, to: the mirror line in XY; a new Mirror object) | offset (one object; by: a vector from its first edge) | upgrade (edges → wire → face → solid, one stage a call) | downgrade | join (Draft wires sharing end points) | fillet (two single edges that meet: radius, chamfer) | split (a Draft wire on segment edge n, from 1, at point at or its middle) | stretch (the points inside box [[min], [max]] moved by) | extend (length mm at end start | end; negative trims) | to_bspline | to_wire; copy: true leaves the originals (move, rotate, scale, offset); delete: false keeps upgrade / downgrade inputs. Reply: op, each result's object, type, length, area, box. guide_read draft has each op's rules.",
             obj({"op": {"type": "string"}, "objects": {"type": "array", "items": {"type": "string"}}, "by": xyz, "angle": {"type": "number"}, "center": xyz, "axis": xyz, "factor": {}, "from": xyz, "to": xyz,
                  "radius": {"type": "number"}, "chamfer": {"type": "boolean"}, "copy": {"type": "boolean"}, "delete": {"type": "boolean"}, "at": xyz, "edge": {"type": "integer"}, "box": {"type": "array", "items": {}}, "length": {"type": "number"}, "end": {"type": "string", "enum": ["start", "end"]}}, ["op", "objects"]), draft_modify, changes=True),
        Tool("draft_layer", "A Draft layer (made if new) and objects put on it: name, objects (each leaves its old layer), lineWidth pixels. Without the window only the grouping happens. Reply: layer, made, objects.",
             obj({"name": {"type": "string"}, "objects": {"type": "array", "items": {"type": "string"}}, "lineWidth": {"type": "number"}}, ["name"]), draft_layer, changes=True),
        Tool("draft_hatch", "Hatch an object's flat faces with a PAT pattern, as lines in the model (a Hatch object that follows it): object, pattern (default Diagonal4; FreeCAD's FCPAT.pat lists them, or file: your own .pat), scale (1: the pattern's own mm spacing), rotation degrees. Reply: pattern, file, length; warning when no lines were drawn. A wrong pattern name is refused with the names.",
             obj({"object": {"type": "string"}, "pattern": {"type": "string"}, "file": {"type": "string"}, "scale": {"type": "number"}, "rotation": {"type": "number"}, "name": {"type": "string"}}, ["object"]), draft_hatch, changes=True),
        Tool("draft_from_sketch", "Sketches or shapes made Draft objects (Draft's draftify): objects; straight runs become Draft wires, a lone circle or arc a Draft circle, runs with curves stay plain shapes. block: true compounds the results; delete: true removes the originals.",
             obj({"objects": {"type": "array", "items": {"type": "string"}}, "block": {"type": "boolean"}, "delete": {"type": "boolean"}}, ["objects"]), draft_from_sketch, changes=True),
        Tool("draft_2d_view", "A 2D view of a body projected along direction (Draft's Shape2DView, parametric; default from above, laid on XY): hidden: true adds hidden lines. section: true (cut faces only) needs object to be a BIM section plane (bim_section); for a body use part_section. Reply: object, length, box; warning when empty.",
             obj({"object": {"type": "string"}, "direction": xyz, "hidden": {"type": "boolean"}, "section": {"type": "boolean"}, "name": {"type": "string"}}, ["object"]), draft_2d_view, changes=True),
        Tool("draft_facebinder", "A facebinder: faces [\"Body.Face6\" …] as a surface that follows them; extrusion mm makes it a skin, offset moves it off. Reply: object, area, volume, box.",
             obj({"faces": {"type": "array", "items": {"type": "string"}}, "extrusion": {"type": "number"}, "offset": {"type": "number"}, "name": {"type": "string"}}, ["faces"]), draft_facebinder, changes=True),
    ]
