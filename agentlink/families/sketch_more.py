# SPDX-License-Identifier: LGPL-2.1-or-later
# More Sketcher, beside sketch.py: copy, move, rotate and scale geometry,
# rectangular and polar arrays, extend a curve, join two, a carbon copy of
# another sketch, edges projected from binders and other sketches, B-spline
# conversion, and validate — the Sketcher's own repair: missing
# coincidences, degenerate geometry, redundant and invalid constraints,
# and its auto-constrainer.

import math

import FreeCAD
import Part

from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import pd_common as pc
from . import picks
from .sketch import SOLVE, ext_count

GROUP = "sketch"
INFO = ("Sketches: bodies, sketches on planes and faces, geometry and constraints, offset, external edges, fillet/trim/split/mirror, "
        "copy/move/rotate/scale, arrays, extend, join, carbon copy, projection from binders, B-spline conversion, validate and repair, the solver's state.")

V = FreeCAD.Vector


def ids_of(sk, geos, what="geometry"):
    n = len(sk.Geometry)
    if geos is None:
        return [i for i in range(n) if not sk.getConstruction(i)]
    if not isinstance(geos, list) or not geos or not all(isinstance(g, int) and not isinstance(g, bool) for g in geos):
        raise bad(f"{what}: a list of geometry ids, e.g. [0, 1] — sketch_state lists them; left out, every non-construction one.")
    out = [g for g in geos if 0 <= g < n]
    if len(out) != len(geos):
        raise bad(f"{what}: {[g for g in geos if not 0 <= g < n]} not in {sk.Label}, whose ids are 0 to {n - 1} (sketch_state lists them).")
    return out


def solver_lists(sk):
    """The solver's lists after the last solve, as constraint ids from 0
    (FreeCAD counts them from 1): { conflicting, redundant, malformed }."""
    out = {}
    for k, p in (("conflicting", "ConflictingConstraints"), ("redundant", "RedundantConstraints"), ("malformed", "MalformedConstraints")):
        try:
            v = [int(i) - 1 for i in (getattr(sk, p, None) or [])]
        except Exception:
            v = []
        if v:
            out[k] = v
    return out


def state(sk):
    try:
        code = sk.solve()
    except Exception:
        code = -1
    out = {"sketch": sk.Label, "geometry": len(sk.Geometry), "constraints": len(sk.Constraints), "solver": SOLVE.get(code, f"code {code}")}
    dof = getattr(sk, "DoF", None)
    if dof is not None:
        out["dof"] = dof
    out.update(solver_lists(sk))
    try:
        w = sk.Shape.Wires
        out["wires"] = len(w)
        out["closedWires"] = sum(1 for x in w if x.isClosed())
    except Exception:
        pass
    return out


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def sketch(a):
        return pc.sketch_of(doc(), a.get("sketch"), None)

    def kept(sk):
        """The sketch as it is, to put back if a change fails: some Sketcher
        calls change it outside the document's undo."""
        return ([g.copy() for g in sk.Geometry], [sk.getConstruction(i) for i in range(len(sk.Geometry))], [c.clone() if hasattr(c, "clone") else c for c in sk.Constraints])

    def restore(sk, snap):
        geo, cons_flags, cons = snap
        try:
            sk.deleteAllConstraints()
            sk.deleteAllGeometry()
            if geo:
                sk.addGeometry(geo, False)
                for i, f in enumerate(cons_flags):
                    if f:
                        sk.setConstruction(i, True)
            if cons:
                sk.addConstraint(cons)
            doc().recompute()
        except Exception:
            pass

    def done(sk, tool, extra=None):
        def check():
            b = pc.newly_broken(doc())  # not what was failing before the call
            if b:
                raise ToolError("failed", f"That breaks {b[0]['object']}: {b[0]['error']} — nothing was kept. sketch_state reads the sketch as it is; a feature built on it needs its profile closed.")
        return picks.finish(s, tool, lambda: state(sk), check=check, extra=extra)

    def new_ids(sk, before):
        return list(range(before, len(sk.Geometry)))

    # ---- copy, move, rotate, scale ----

    def transformed_copies(sk, geos, m):
        out = []
        for g in geos:
            gg = sk.Geometry[g].copy()
            gg.transform(m)
            out.append(gg)
        return out

    def sketch_copy(a):
        sk = sketch(a)
        geos = ids_of(sk, a.get("geometry"))
        before = len(sk.Geometry)
        keep = not a.get("move")
        if a.get("by") is not None:
            d = pc.vec2(a["by"], "by")
            v = V(d[0], d[1], 0)
            if keep:
                sk.addCopy(geos, v, bool(a.get("clone")))
            else:
                sk.addMove(geos, v)
            what = f"by {[d.x, d.y]}"
        elif a.get("rotate") is not None or a.get("scale") is not None:
            if a.get("rotate") is not None:
                r = a["rotate"]
                c = pc.vec2(r.get("center", [0, 0]), "rotate.center")
                ang = float(r.get("angle", 90))
                m = FreeCAD.Placement(V(), FreeCAD.Rotation(V(0, 0, 1), ang), V(c[0], c[1], 0)).toMatrix()
                what = f"rotated {ang:g}° about {[c.x, c.y]}"
            else:
                sc = a["scale"]
                c = pc.vec2(sc.get("center", [0, 0]), "scale.center")
                f = float(sc.get("factor", 2))
                if f <= 0:
                    raise bad("scale.factor: a number above 0 (2 doubles, 0.5 halves).")
                m = FreeCAD.Matrix()
                m.move(V(-c[0], -c[1], 0))
                m2 = FreeCAD.Matrix()
                # Uniform in all three: OCCT reads a matrix's scale as the cube
                # root of its determinant, so (f, f, 1) scaled by f**(2/3).
                m2.scale(f, f, f)
                m = m2.multiply(m)
                m3 = FreeCAD.Matrix()
                m3.move(V(c[0], c[1], 0))
                m = m3.multiply(m)
                what = f"scaled ×{f:g} about {[c.x, c.y]}"
            copies = transformed_copies(sk, geos, m)
            sk.addGeometry(copies, False)
            if not keep:
                sk.delGeometries(sorted(geos))
                before -= len(geos)
        else:
            raise bad("Give one of by [dx, dy] (mm), rotate { center: [x, y], angle: degrees ccw } or scale { center: [x, y], factor }.")
        made = new_ids(sk, before) if keep else "the originals, moved (ids renumbered when rotated or scaled)"
        return done(sk, "sketch_copy", {"did": ("copied " if keep else "moved ") + what, "new": made})

    def sketch_array(a):
        sk = sketch(a)
        geos = ids_of(sk, a.get("geometry"))
        before = len(sk.Geometry)
        if a.get("polar"):
            p = a["polar"]
            c = pc.vec2(p.get("center", [0, 0]), "polar.center")
            n = int(p.get("count", 6))
            span = float(p.get("angle", 360))
            if n < 2:
                raise bad("polar.count: 2 or more, the original counted (6 gives five copies).")
            step = span / n if abs(span - 360) < 1e-9 else span / (n - 1)
            for k in range(1, n):
                m = FreeCAD.Placement(V(), FreeCAD.Rotation(V(0, 0, 1), step * k), V(c[0], c[1], 0)).toMatrix()
                sk.addGeometry(transformed_copies(sk, geos, m), False)
            what = f"{n} round {[c.x, c.y]} over {span:g}°"
        else:
            rows, cols = int(a.get("rows", 1)), int(a.get("cols", 2))
            if rows < 1 or cols < 1 or rows * cols < 2:
                raise bad("rows and cols: 1 or more each, the original counted, and at least two in all (rows 2, cols 3 makes five copies).")
            d = pc.vec2(a.get("spacing", [10, 10]), "spacing")
            if (cols > 1 and abs(d.x) < 1e-9) or (rows > 1 and abs(d.y) < 1e-9):
                raise bad("spacing [dx, dy]: dx is the step from column to column (along x), dy from row to row (along y), mm — neither may be 0 when there is more than one, or the copies land on each other.")
            # addRectangularArray(geos, vector, clone, n along the vector, n
            # across it, constrain, perpscale): FreeCAD's own names for the two
            # counts are (rows, cols), but the first runs along the vector, and
            # the step across is perpscale × (vector.y, -vector.x)
            # (SketchObject::addCopy). Columns along +x, rows along +y:
            if cols > 1:
                vec, along, across, scale = V(d.x, 0, 0), cols, rows, -d.y / d.x
            else:
                vec, along, across, scale = V(0, d.y, 0), rows, 1, 1.0
            try:
                sk.addRectangularArray(geos, vec, bool(a.get("clone")), along, across, bool(a.get("constrain")), scale)
            except Exception as e:
                raise ToolError("failed", f"The array could not be made: {e} — nothing was added. With constrain or clone, try without (plain copies), then constrain them with sketch_constrain.") from None
            what = f"{rows} rows × {cols} columns at {[d.x, d.y]}"
        return done(sk, "sketch_array", {"did": what, "new": new_ids(sk, before)})

    # ---- extend, join ----

    def sketch_extend(a):
        sk = sketch(a)
        g = a.get("geo")
        if not isinstance(g, int) or isinstance(g, bool) or not 0 <= g < len(sk.Geometry):
            raise bad(f"geo: the id of a line or an arc of a circle in {sk.Label} (0 to {len(sk.Geometry) - 1}; sketch_state lists them).")
        kind = type(sk.Geometry[g]).__name__
        if kind not in ("LineSegment", "ArcOfCircle"):
            raise bad(f"geo {g} is a {kind}: FreeCAD extends lines and arcs of circles only. For another curve: sketch_edit move its end point, or sketch_edit split / trim.")
        end = a.get("end", 2)
        if end not in (1, 2) or isinstance(end, bool):
            raise bad("end: 1 (the start) or 2 (the end) — sketch_state shows which is which (from/to, start/end).")
        if a.get("to") is not None:
            t = a["to"]
            if kind != "LineSegment":
                raise bad("to: works for a line; for an arc give by, mm along the arc.")
            if not isinstance(t, int) or isinstance(t, bool) or not 0 <= t < len(sk.Geometry) or t == g:
                raise bad(f"to: the id of another curve in {sk.Label} (0 to {len(sk.Geometry) - 1}) for the line to reach.")
            # as far as another curve: measured along the line to where it meets it
            tgt = sk.Geometry[t].toShape()
            p = sk.getPoint(g, end)
            other = sk.getPoint(g, 1 if end == 2 else 2)
            dvec = p - other
            dvec.normalize()
            far = Part.LineSegment(p, p + dvec * 10000).toShape()
            dist, pts, _ = far.distToShape(tgt)
            if dist > 1e-6:
                raise ToolError("not_found", f"Line {g} does not meet geometry {t} going on from its {'start' if end == 1 else 'end'}: try the other end, or give by (mm).")
            inc = (pts[0][0] - p).Length
            if inc < 1e-9:
                raise ToolError("invalid_state", f"Line {g} already reaches geometry {t} at that end: nothing to extend.")
            turn = inc
        else:
            by = a.get("by", 0)
            if not isinstance(by, (int, float)) or isinstance(by, bool) or by == 0:
                raise bad("Give by (mm to add at that end; negative shortens; along the arc for an arc) or to (the id of a curve a line should reach).")
            inc = turn = float(by)
            if kind == "ArcOfCircle":
                # FreeCAD's increment for an arc is an angle in radians
                # (SketchObject::extend): mm along the arc / its radius.
                turn = inc / sk.Geometry[g].Radius
        try:
            sk.extend(g, turn, end)
        except Exception as e:
            raise ToolError("failed", f"Geometry {g} would not extend by {inc:g} mm at vertex {end}: {e} — its constraints hold that end (sketch_state lists them; sketch_edit deleteConstraints frees it).") from None
        return done(sk, "sketch_extend", {"extended": g, "end": end, "by": round(inc, 4)})

    def sketch_join(a):
        sk = sketch(a)
        x, y = a.get("a"), a.get("b")
        if not (isinstance(x, list) and isinstance(y, list) and len(x) == len(y) == 2):
            raise bad("a and b: [geo, vertex] each, vertex 1 (start) or 2 (end) — the two ends, of two different curves, to join into one B-spline.")
        n = len(sk.Geometry)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in x + y) or not (0 <= x[0] < n and 0 <= y[0] < n) or x[0] == y[0] or x[1] not in (1, 2) or y[1] not in (1, 2):
            raise bad(f"a and b: [geo, vertex] of two different curves in {sk.Label} (ids 0 to {n - 1}), vertex 1 (start) or 2 (end) — FreeCAD cannot join a curve to itself.")
        cont = a.get("continuity", 0)
        if cont not in (0, 1):
            raise bad("continuity: 0 (the two meet at a corner) or 1 (smooth).")
        try:
            sk.join(x[0], x[1], y[0], y[1], cont)
        except Exception as e:
            raise ToolError("failed", f"The join failed: {e} — nothing was changed. Both must be open curves (not circles, ellipses or closed B-splines), both construction or both not.") from None
        made = [i for i, g in enumerate(sk.Geometry) if "BSpline" in type(g).__name__]
        return done(sk, "sketch_join", {"joined": [x, y], **({"bspline": made[-1]} if made else {}),
                                        "note": "The two curves were replaced by one B-spline (with its poles as construction geometry): ids changed, read sketch_state."})

    # ---- carbon copy, projection ----

    def sketch_carbon(a):
        sk = sketch(a)
        src = pc.sketch_of(doc(), a.get("from"), None)
        if src is sk:
            raise bad("from: another sketch than the one copied into.")
        before = len(sk.Geometry)
        try:
            sk.carbonCopy(src.Name, bool(a.get("construction", False)))
        except Exception as e:
            raise ToolError("failed", f"No carbon copy from {src.Label}: {e} — nothing was added. FreeCAD refuses a source that is built from {sk.Label} (a loop), one in another App::Part, and one in another body that has outside (external) geometry.") from None
        return done(sk, "sketch_carbon", {"from": src.Label, "new": new_ids(sk, before), "note": "Geometry and constraints copied in the sketches' own x/y (the planes are not compared); each copied dimension is bound by expression to its source's, so it follows the source."})

    def sketch_project(a):
        sk = sketch(a)
        src = next((o for o in doc().Objects if a.get("from") in (o.Label, o.Name)), None)
        if src is None or not hasattr(src, "Shape"):
            raise ToolError("not_found", f"from {a.get('from')!r}: no such object with a shape — give the name of a binder (pd_binder makes one from another body), a datum or another sketch in this sketch's body (feature_list names them). For the body's own solid: sketch_external.")
        edges = a.get("edges")
        names = []
        if edges:
            for e in edges:
                if isinstance(e, str) and e.startswith(("Edge", "Vertex")):
                    names.append(e)
                elif isinstance(e, dict):
                    names += pc.find_edges(src.Shape, [e])
                else:
                    raise bad("edges: \"Edge3\", { near: [x, y, z], kind } or shape_query's filters each; left out, every edge.")
        else:
            names = [f"Edge{i + 1}" for i in range(len(src.Shape.Edges))]
        if not names:
            raise bad(f"{src.Label} has no edges to bring in.")
        before = ext_count(sk)
        added = 0
        for n in names:
            try:
                if a.get("defining"):
                    sk.addExternal(src.Name, n, True)
                else:
                    sk.addExternal(src.Name, n)
                added += 1
            except TypeError as e:
                raise ToolError("unavailable", f"defining: this FreeCAD ({'.'.join(FreeCAD.Version()[:3])}) takes no defining external geometry ({e}) — leave defining out and trace the edges with sketch_add instead.") from None
            except Exception as e:
                raise ToolError("failed", f"{src.Label}.{n} would not come in: {e} — nothing was added. FreeCAD takes outside geometry from the sketch's own body only (from another body: pd_binder first, then project the binder), not from anything built from {sk.Label}, and each edge once.") from None
        ids = [-(3 + i) for i in range(before, ext_count(sk))]
        out = done(sk, "sketch_project", {"from": src.Label, "edges": added, "ids": ids,
                                          "note": "External ids count down from -3, in the order brought in; constrain to them with sketch_constrain. defining: true makes them part of the profile (FreeCAD 1.1 on)."})
        return out

    def sketch_to_bspline(a):
        sk = sketch(a)
        geos = ids_of(sk, a.get("geometry"))
        for g in sorted(geos, reverse=True):
            try:
                sk.convertToNURBS(g)
            except Exception as e:
                raise ToolError("failed", f"Geometry {g} ({type(sk.Geometry[g]).__name__}) would not convert: {e} — nothing was changed. Lines, arcs, circles, ellipses and their arcs convert; points do not: leave it out of geometry.") from None
        return done(sk, "sketch_to_bspline", {"converted": geos})

    # ---- validate and repair ----

    def sketch_validate(a):
        sk = sketch(a)
        prec = float(a.get("precision", 0.01))
        found = {}
        try:
            found["degenerate"] = int(sk.detectDegeneratedGeometries(prec))
        except Exception:
            pass
        try:
            found["missingCoincidences"] = int(sk.detectMissingPointOnPointConstraints(prec, False) or 0)
        except Exception:
            try:
                sk.detectMissingPointOnPointConstraints(prec)
                found["missingCoincidences"] = len(sk.MissingPointOnPointConstraints) if hasattr(sk, "MissingPointOnPointConstraints") else None
            except Exception:
                pass
        try:
            # True when they are all valid, whatever its doc string says
            found["invalidConstraints"] = not bool(sk.evaluateConstraints())
        except Exception:
            pass
        st = state(sk)
        for k in ("redundant", "conflicting", "malformed"):
            if st.get(k):
                found[k] = st[k]
        fixed = []
        if a.get("fix"):
            snap = kept(sk)
            try:
                return repair(sk, prec, found, st, fixed, a)
            except ToolError:
                restore(sk, snap)
                raise
            except Exception as e:
                restore(sk, snap)
                raise ToolError("failed", f"Repair stopped: {e} — the sketch is as it was. Close the gaps by hand (sketch_constrain coincident), or drop autoconstrain.")
        out = {**st, "found": found, "next": "fix: true repairs what can be (autoconstrain: true also adds coincident/horizontal/vertical where the geometry already is). Conflicting constraints are not repaired: sketch_edit deleteConstraints."}
        return out

    def repair(sk, prec, found, st, fixed, a):
        if found.get("degenerate"):
            sk.removeDegeneratedGeometries(prec)
            fixed.append("degenerate geometry removed")
        if found.get("missingCoincidences"):
            try:
                sk.makeMissingPointOnPointCoincident(False)
                fixed.append("missing coincidences added")
            except Exception as e:
                fixed.append(f"coincidences not added: {e}")
        if found.get("invalidConstraints"):
            sk.validateConstraints()
            fixed.append("invalid constraints removed")
        if st.get("redundant"):
            sk.autoRemoveRedundants(True)
            fixed.append("redundant constraints removed")
        if a.get("autoconstrain"):
            # the auto-constrainer's steps one by one, leaving out equality
            # (FreeCAD's whole run can fail there and stop the rest)
            n0 = len(sk.Constraints)
            sk.detectMissingPointOnPointConstraints(prec, False)
            sk.makeMissingPointOnPointCoincident(True)
            sk.detectMissingVerticalHorizontalConstraints(math.radians(float(a.get("angle", 1))))
            sk.makeMissingVerticalHorizontal(True)
            fixed.append(f"{len(sk.Constraints) - n0} coincident / horizontal / vertical constraints added")
        sk.solve()
        if solver_lists(sk).get("redundant"):
            sk.autoRemoveRedundants(True)
            fixed.append("redundant constraints removed")
            sk.solve()
        clash = solver_lists(sk).get("conflicting")
        if clash:
            raise ToolError("failed", f"Constraints {clash} conflict after the repair — nothing was kept; sketch_state names them, sketch_edit deleteConstraints the one that is wrong, then validate again.")
        return done(sk, "sketch_validate", {"found": found, "fixed": fixed})

    geo_ids = {"type": "array", "items": {"type": "integer"}}
    sk_ref = {"type": "string", "description": "The sketch's name; may be left out when there is one."}
    # ---- B-spline editing, merging, mirroring, attachment ----

    def sketch_bspline(a):
        sk = sketch(a)
        g = a.get("geo")
        if not isinstance(g, int) or not 0 <= g < len(sk.Geometry) or "BSpline" not in type(sk.Geometry[g]).__name__:
            raise bad("geo: the id of a B-spline in the sketch (sketch_state lists kinds; sketch_to_bspline converts other curves).")
        op = a.get("op")
        snap = kept(sk)
        try:
            if op == "degree":
                by = int(a.get("by", 1))
                if by > 0:
                    sk.increaseBSplineDegree(g, by)
                elif by < 0:
                    if not hasattr(sk, "decreaseBSplineDegree"):
                        raise ToolError("unavailable", "This FreeCAD cannot lower a B-spline's degree: draw it again with sketch_add bspline { interpolate: false, degree }.")
                    # Answers False, with no error, when it could not.
                    if sk.decreaseBSplineDegree(g, -by) is False:
                        raise ValueError(f"the degree of {g} could not be lowered by {-by}")
                else:
                    raise bad("by: how many degrees to raise (+1) or lower (-1), not 0.")
            elif op == "knot":
                if a.get("param") is not None:
                    sk.insertBSplineKnot(g, float(a["param"]), int(a.get("multiplicity", 1)))
                else:
                    sk.modifyBSplineKnotMultiplicity(g, int(a.get("knot", 1)), int(a.get("by", 1)))
            else:
                raise bad("op: degree (by +1 / -1) | knot (param: insert one there, multiplicity; or knot: its index from 1, by: its multiplicity up or down).")
        except ToolError:
            raise
        except Exception as e:
            restore(sk, snap)
            raise ToolError("failed", f"Sketcher refused: {e} — the B-spline is as it was. A knot's index runs from 1 to the count of knots, param lies inside its knot range, and a multiplicity cannot pass the degree (the reply of a successful call lists knots and multiplicities).") from None
        doc().recompute()
        bs = [x for x in sk.Geometry if "BSpline" in type(x).__name__]
        geo = sk.Geometry[g] if g < len(sk.Geometry) and "BSpline" in type(sk.Geometry[g]).__name__ else bs[-1]
        return done(sk, "sketch_bspline", {"geo": g, "degree": int(geo.Degree), "poles": int(geo.NbPoles), "knots": [round(k, 4) for k in geo.getKnots()],
                                           "multiplicities": list(geo.getMultiplicities())})

    def copy_frame(src, sk):
        sup = pc.support_prop(src)
        if getattr(src, sup, None):
            setattr(sk, pc.support_prop(sk), getattr(src, sup))
            sk.MapMode = src.MapMode
            sk.MapReversed = src.MapReversed
            sk.AttachmentOffset = src.AttachmentOffset
        else:
            sk.Placement = src.Placement

    def new_beside(src):
        body = next((p for p in src.InList if p.TypeId == "PartDesign::Body"), None)
        return body.newObject("Sketcher::SketchObject", "Sketch") if body else doc().addObject("Sketcher::SketchObject", "Sketch")

    def sketch_merge(a):
        refs = a.get("sketches")
        if not isinstance(refs, list) or len(refs) < 2:
            raise bad("sketches: the names of two or more sketches to merge into a new one (on the first one's plane) — feature_list names them.")
        srcs = [pc.sketch_of(doc(), r, None) for r in refs]
        first = srcs[0]
        sk = new_beside(first)
        copy_frame(first, sk)
        sk.Label = s.unique(a.get("name") or "Merged sketch")
        inv = first.Placement.inverse()
        lost = 0
        for src in srcs:
            base = len(sk.Geometry)
            m = inv.multiply(src.Placement).toMatrix()
            gs = []
            for gg in src.Geometry:
                c = gg.copy()
                c.transform(m)
                gs.append(c)
            if gs:
                sk.addGeometry(gs, False)
                for i in range(len(gs)):
                    if src.getConstruction(i):
                        sk.setConstruction(base + i, True)
            for c in src.Constraints:
                try:
                    cc = c.clone() if hasattr(c, "clone") else c
                    if cc.First >= 0:
                        cc.First += base
                    if getattr(cc, "Second", -2000) >= 0:
                        cc.Second += base
                    if getattr(cc, "Third", -2000) >= 0:
                        cc.Third += base
                    sk.addConstraint(cc)
                except Exception:
                    # One to outside geometry, which is not brought over.
                    lost += 1
        if a.get("remove"):
            for src in srcs:
                doc().removeObject(src.Name)
        return done(sk, "sketch_merge", {"sketch": sk.Label, "from": [x.Label for x in srcs],
                                         **({"constraintsLeftOut": lost, "note": "Constraints to outside (external) geometry were not brought over: sketch_external / sketch_project it again and constrain."} if lost else {})})

    def sketch_mirror(a):
        src = sketch(a)
        about = a.get("about", "y")
        M = FreeCAD.Matrix()
        if about == "y":
            M.A11 = -1
        elif about == "x":
            M.A22 = -1
        elif about == "origin":
            M.A11 = M.A22 = -1
        else:
            raise bad("about: \"x\" (flip over the x axis, up-down), \"y\" (left-right, the default) or \"origin\".")
        sk = new_beside(src)
        copy_frame(src, sk)
        gs = []
        for gg in src.Geometry:
            if about != "origin" and type(gg).__name__ == "ArcOfCircle":
                # A mirror turns an arc's sense round, and Sketcher keeps
                # arcs counter-clockwise: the mirrored arc runs from the
                # image of the end to the image of the start.
                c0, p0, p1 = (V(M.A11 * q.x, M.A22 * q.y, 0) for q in (gg.Center, gg.EndPoint, gg.StartPoint))
                a0, a1 = math.atan2(p0.y - c0.y, p0.x - c0.x), math.atan2(p1.y - c0.y, p1.x - c0.x)
                if a1 <= a0:
                    a1 += 2 * math.pi
                gs.append(Part.ArcOfCircle(Part.Circle(c0, V(0, 0, 1), gg.Radius), a0, a1))
                continue
            c = gg.copy()
            c.transform(M)
            gs.append(c)
        if gs:
            sk.addGeometry(gs, False)
            for i in range(len(gs)):
                if src.getConstruction(i):
                    sk.setConstruction(i, True)
        sk.Label = s.unique(a.get("name") or f"{src.Label} mirrored")
        return done(sk, "sketch_mirror", {"sketch": sk.Label, "from": src.Label, "about": about, "note": "Geometry only: constrain the copy (sketch_validate autoconstrain) to edit it by sizes."})

    def sketch_attach(a):
        sk = sketch(a)
        b = next((p for p in sk.InList if p.TypeId == "PartDesign::Body"), None)
        if b is None:
            raise ToolError("invalid_state", f"{sk.Label} is in no body: attach works on a body's sketch — sketch_new makes one in a body, and sketch_carbon copies this one into it.")
        if ("plane" in a) == ("face" in a):
            raise bad("Give plane (XY, XZ, YZ, a datum plane's name or \"Pad.Face3\") or face { at: [x,y,z], normal: [x,y,z] }, one of them, not both.")
        link, what = pc.plane_ref(b, a["plane"] if "plane" in a else a["face"], "plane")
        moved = _order_after(b, sk, link[0])
        setattr(sk, pc.support_prop(sk), [(link[0], link[1][0])])
        sk.MapMode = "FlatFace"
        sk.MapReversed = bool(a.get("flip", False))
        off = float(a.get("offset", 0))
        rot = float(a.get("rotate", 0))
        sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, off), FreeCAD.Rotation(V(0, 0, 1), rot))
        doc().recompute()
        if not sk.isValid():
            raise ToolError("failed", f"{sk.Label} would not attach to {what}: {sk.getStatusString()} — it stays where it was. A sketch needs a flat face or a plane.")
        out = {"sketch": sk.Label, "on": what, "support": f"{link[0].Label}.{link[1][0]}" if link[1][0] else link[0].Label, "offset": off, "rotate": rot}
        if moved:
            out["moved"] = f"{sk.Label} now comes after {link[0].Label} in {b.Label}: its support is built before it."
        return done(sk, "sketch_attach", out)

    def _order_after(b, sk, owner):
        """A sketch in the body attached to a feature built after it would
        point forward (a cyclic support FreeCAD warns about on every
        recompute): a sketch nothing is built from yet is moved after that
        feature; one a feature uses is refused. True when it moved."""
        if not hasattr(owner, "isDerivedFrom") or not owner.isDerivedFrom("PartDesign::Feature"):
            return False
        g = list(b.Group)
        if sk not in g or owner not in g or g.index(owner) < g.index(sk):
            return False
        users = [o for o in sk.InList if o is not b and o is not owner and b.hasObject(o) and o.isDerivedFrom("PartDesign::Feature")]
        if users or owner in sk.InListRecursive:
            raise ToolError("invalid_state", f"{owner.Label} (whose face it is) is built after {sk.Label}"
                            + (f", and {', '.join(u.Label for u in users)} is built from {sk.Label}" if users else "")
                            + ": attaching would make the sketch hang on a later feature (a cyclic support). Attach to an earlier face or plane, or make a new sketch on that face (sketch_new { face }).")
        try:
            b.removeObject(sk)
            b.insertObject(sk, owner, True)
        except Exception as e:
            raise ToolError("failed", f"{sk.Label} comes before {owner.Label} in {b.Label} and could not be moved after it ({e}): make a new sketch on that face (sketch_new {{ face }}).")
        return True

    return [
        Tool("sketch_copy", "Copy geometry in a sketch (move: true moves it instead): geometry [ids] (default every non-construction one), and by [dx, dy] (clone: true keeps copies equal to the originals), rotate { center, angle deg ccw } or scale { center, factor }. by copies the constraints among them too; rotate and scale give plain geometry. Answers new: the copies' ids.",
             obj({"sketch": sk_ref, "geometry": geo_ids, "by": {"type": "array", "items": {}}, "rotate": {"type": "object"}, "scale": {"type": "object"}, "move": {"type": "boolean"}, "clone": {"type": "boolean"}}), sketch_copy, changes=True),
        Tool("sketch_array", "An array of geometry in a sketch: rows (along y), cols (along x) and spacing [dx, dy] mm, the original counted (constrain: true keeps the spacing as constraints; clone: true keeps copies equal), or polar { center, count, angle (default 360) }. Answers new: the ids added.",
             obj({"sketch": sk_ref, "geometry": geo_ids, "rows": {"type": "integer"}, "cols": {"type": "integer"}, "spacing": {"type": "array", "items": {}}, "constrain": {"type": "boolean"}, "clone": {"type": "boolean"}, "polar": {"type": "object"}}), sketch_array, changes=True),
        Tool("sketch_extend", "Lengthen (or shorten) a line or arc of a circle at one end: geo, end 1 | 2 (default 2), by mm (negative shortens; along the arc for an arc), or to: another curve's id a line should reach.",
             obj({"sketch": sk_ref, "geo": {"type": "integer"}, "end": {"type": "integer"}, "by": {"type": "number"}, "to": {"type": "integer"}}, ["geo"]), sketch_extend, changes=True),
        Tool("sketch_join", "Join two open curves' ends into one B-spline: a [geo, vertex], b [geo, vertex] (vertex 1 | 2, different curves), continuity 0 (corner) or 1 (smooth). It replaces both: ids change; answers bspline, its id.",
             obj({"sketch": sk_ref, "a": {"type": "array", "items": {}}, "b": {"type": "array", "items": {}}, "continuity": {"type": "integer"}}, ["a", "b"]), sketch_join, changes=True),
        Tool("sketch_carbon", "Copy another sketch's geometry and constraints into this one (Sketcher's carbon copy): from, construction: true brings it as construction. Its dimensions stay bound to the source's by expression. Answers new: the ids added.",
             obj({"sketch": sk_ref, "from": {"type": "string"}, "construction": {"type": "boolean"}}, ["from"]), sketch_carbon, changes=True),
        Tool("sketch_project", "Bring edges of a binder, datum or another sketch of the same body into this sketch as external geometry: from, edges [\"Edge3\" | { near, kind }] (default all), defining: true makes them part of the profile (FreeCAD 1.1 on). Answers ids (-3 down, in order) for sketch_constrain. The body's own solid: sketch_external.",
             obj({"sketch": sk_ref, "from": {"type": "string"}, "edges": {"type": "array", "items": {}}, "defining": {"type": "boolean"}}, ["from"]), sketch_project, changes=True),
        Tool("sketch_to_bspline", "Convert geometry to B-splines in place (to reshape by poles, or join): geometry [ids]. Geometry ids stay; its constraints other than end-point coincidences are removed.", obj({"sketch": sk_ref, "geometry": geo_ids}), sketch_to_bspline, changes=True),
        Tool("sketch_bspline", "Edit a B-spline in a sketch: geo, op degree (by: +1 raises, -1 lowers) | knot (param: insert a knot there, multiplicity; or knot: its index from 1 and by: raise/lower its multiplicity — a corner at 0 continuity). Answers degree, poles, knots, multiplicities.",
             obj({"sketch": {"type": "string"}, "geo": {"type": "integer"}, "op": {"type": "string", "enum": ["degree", "knot"]}, "by": {"type": "integer"}, "param": {"type": "number"},
                  "knot": {"type": "integer"}, "multiplicity": {"type": "integer"}}, ["geo", "op"]), sketch_bspline, changes=True),
        Tool("sketch_merge", "Merge sketches into a new one on the first's plane, geometry and constraints kept (not those to outside geometry): sketches [names]; remove: true deletes the originals. Answers sketch: its label.",
             obj({"sketches": {"type": "array", "items": {"type": "string"}}, "remove": {"type": "boolean"}, "name": {"type": "string"}}, ["sketches"]), sketch_merge, changes=True),
        Tool("sketch_mirror", "A mirrored copy of a whole sketch as a new sketch on the same plane: about y (left-right) | x (up-down) | origin. Geometry only, no constraints. Answers sketch: its label.",
             obj({"sketch": {"type": "string"}, "about": {"type": "string", "enum": ["x", "y", "origin"]}, "name": {"type": "string"}}), sketch_mirror, changes=True),
        Tool("sketch_attach", "Move a sketch onto another plane (Sketcher's map/reorient): plane XY | XZ | YZ | a datum plane | \"Pad.Face3\", or face { at, normal, feature? }; offset mm along its normal, rotate deg in it, flip. A face is bound to the feature that made it (the earliest in the body that has it, or feature), not the tip; a sketch that sits before that feature is moved after it (refused when a feature is built from it).",
             obj({"sketch": {"type": "string"}, "plane": {"type": "string"}, "face": {"type": "object"}, "offset": {"type": "number"}, "rotate": {"type": "number"}, "flip": {"type": "boolean"}}), sketch_attach, changes=True),
        Tool("sketch_validate", "Check a sketch the way Sketcher's Validate does: degenerate geometry, ends that touch with no coincidence, invalid, redundant and conflicting constraints (precision mm); answers found. fix: true repairs what it can (not conflicts; a failed repair leaves the sketch as it was); autoconstrain: true also adds the obvious coincident/horizontal/vertical constraints.",
             obj({"sketch": sk_ref, "precision": {"type": "number"}, "fix": {"type": "boolean"}, "autoconstrain": {"type": "boolean"}, "angle": {"type": "number"}}), sketch_validate, changes=True),
    ]
