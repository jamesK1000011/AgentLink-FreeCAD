# SPDX-License-Identifier: LGPL-2.1-or-later
# The Surface workbench's own parametric features, beside draft.py's plain
# surfaces: a surface through sections, one bounded by edges (stretched,
# Coons, curved), a surface extended past its edges, faces sewn into a shell
# (and a closed one made a solid), surfaces cut by one another, and blend
# curves joining two edges smoothly. Each follows the edges it was made from.

import Part
import Surface  # noqa: F401 — loads the Surface features; the family is left out without it

from .. import geometry as geo
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "surface"
INFO = "Surface workbench features (parametric): sections, boundary surfaces (stretched/Coons/curved), extend, sewing into shells and solids, surface cuts, blend curves; surfaces filled across edges, lofted through curves, fitted to points or a polynomial, thickened into solids."


def reading(o):
    sh = o.Shape
    out = {"object": o.Label, "type": o.TypeId.split("::")[-1], "faces": len(sh.Faces), "edges": len(sh.Edges)}
    if sh.Faces:
        out["area"] = round(sh.Area, 3)
    if sh.Solids:
        out["volume"] = round(sh.Volume, 3)
    elif sh.Edges:
        out["length"] = round(sum(e.Length for e in sh.Edges), 3)
    out["shells"] = len(sh.Shells)
    out["closed"] = bool(sh.Shells and all(x.isClosed() for x in sh.Shells))
    return out


def chain(edges, refs, tol=1e-4, closed=True):
    """Which boundary edges run backwards, so that each starts where the one before ends
    (the feature takes them as given); refused where two do not meet."""
    def ends(e):
        # The curve's own ends: the feature reverses the curve under the edge
        # (ReversedList), whichever way the edge is turned in its body.
        return e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)

    for first in (False, True):
        a0, a1 = ends(edges[0])
        start, cur = (a1, a0) if first else (a0, a1)
        flags, ok = [first], True
        for e in edges[1:]:
            b0, b1 = ends(e)
            if (b0 - cur).Length <= tol:
                flags.append(False)
                cur = b1
            elif (b1 - cur).Length <= tol:
                flags.append(True)
                cur = b0
            else:
                ok = False
                break
        if ok:
            if closed and (cur - start).Length > tol:
                raise bad("edges: the last does not come back to where the first starts — the boundary must close.")
            return flags
    if not closed:
        raise bad("edges: two curves must share an end (a corner); the surface spans between them.")
    raise bad(f"edges: they do not meet end to end in the order given ({', '.join(map(str, refs))}) — list them going round the boundary.")


def tools(session):
    s = session
    doc = lambda: s.doc

    def new(kind, label):
        lab = s.unique(label)
        o = doc().addObject(kind, label.replace(" ", ""))
        o.Label = lab
        return o

    def done(o, tool, extra=None, hint=""):
        return picks.finish(s, tool, lambda: reading(o), objs=[o], broken=lambda o: not o.isValid() or o.Shape.isNull(),
                            refuse="{kind} failed: {msg} — nothing was kept." + (" " + hint if hint else ""), extra=extra)

    def edge_ref(r, what):
        """"Body.Edge3", or a whole wire/sketch by name (all its edges)."""
        if not isinstance(r, str):
            raise bad(f"{what}: \"Body.Edge3\" or a wire's name.")
        label, sub, _ = picks.resolve(s, r)
        o = picks.find(doc(), label)
        if sub:
            if not sub.startswith("Edge"):
                raise bad(f"{what}: an edge, not {sub}.")
            return o, [sub]
        n = len(o.Shape.Edges)
        if not n:
            raise bad(f"{what}: {o.Label} has no edges.")
        return o, [f"Edge{i + 1}" for i in range(n)]

    def surface_sections(a):
        refs = a.get("sections") or []
        links = [edge_ref(r, "sections") for r in refs] if isinstance(refs, list) else []
        n = sum(len(subs) for _, subs in links)
        if n < 2:
            raise bad("sections: two or more curves in the order the surface passes through them — each \"Body.Edge3\", or the name of a wire or sketch (every edge of it is a section of its own).")
        o = new("Surface::Sections", a.get("name") or "Sections")
        o.NSections = links
        return done(o, "surface_sections", {"sections": n},
                    hint="Each section must be one open curve, all running the same way (a twisted surface means one runs backwards), none crossing the next.")

    def surface_boundary(a):
        refs = a.get("edges") or []
        ft = {"stretched": "Stretched", "coons": "Coons", "curved": "Curved"}.get(a.get("fill", "stretched"))
        if ft is None:
            raise bad("fill: stretched (flattest), coons (smooth across), curved (round).")
        bl = [edge_ref(r, "edges") for r in refs] if isinstance(refs, list) else []
        edges = [ob.Shape.getElement(sub) for ob, subs in bl for sub in subs]
        if not 2 <= len(edges) <= 4:
            # a wire or sketch named whole counts each of its edges
            raise bad(f"edges: two to four boundary curves in all that meet end to end, going round — these are {len(edges)}. More sides: surface_fill takes any closed boundary.")
        # Three or four curves go round the surface; two meet at a corner, the surface between them.
        flags = chain(edges, refs, closed=len(edges) > 2)
        o = new("Surface::GeomFillSurface", a.get("name") or "Boundary surface")
        o.BoundaryList = bl
        o.ReversedList = flags
        o.FillType = ft
        try:
            return done(o, "surface_boundary", {"fill": ft.lower(), "sides": len(edges)},
                        hint="The curves must meet at their ends within FreeCAD's tolerance; fill stretched is the most forgiving, and surface_fill takes any closed boundary.")
        except ToolError as e:
            if ft == "Stretched" or "disjoint" not in str(e) or len(edges) < 3:
                raise
            why = e.message
        # FreeCAD's Coons and curved fills need the opposite curves to match
        # (degree, knots) and report any mismatch as disjoint: a smooth
        # N-sided filling through the same edges instead.
        f = new("Surface::Filling", a.get("name") or "Boundary surface")
        f.BoundaryEdges = [(ob, sub) for ob, subs in bl for sub in subs]
        f.BoundaryOrder = [0] * len(edges)
        try:
            out = done(f, "surface_boundary")
        except ToolError:
            raise ToolError("failed", f"{why} — and a filling through the edges failed too; fill: stretched joins them.") from None
        out["note"] = f"Made as Surface Filling (smooth through the edges): FreeCAD's {ft.lower()} fill refused these curves."
        return out

    def surface_extend(a):
        ref = a.get("face")
        label, sub, _ = picks.resolve(s, ref) if isinstance(ref, str) else (None, None, None)
        if not sub or not sub.startswith("Face"):
            raise bad("face: \"Body.Face2\".")
        u, v = picks.num(a.get("u", 0.05), "u"), picks.num(a.get("v", 0.05), "v")
        if not (-0.5 <= u <= 10 and -0.5 <= v <= 10):
            raise bad("u, v: how far past each pair of opposite edges, as a share of the face's size that way: -0.5 (shrunk to nothing) … 10 (0.05 = 5% at each end).")
        o = new("Surface::Extend", a.get("name") or "Extended")
        o.Face = (picks.find(doc(), label), [sub])
        o.ExtendUSymetric = o.ExtendVSymetric = True  # the same at both ends: FreeCAD copies Neg to Pos
        o.ExtendUNeg, o.ExtendVNeg = u, v
        return done(o, "surface_extend", {"u": u, "v": v, "note": "A new four-sided B-spline surface over the face's whole u and v range, run on by u and v of that range at each end and fitted to within 0.1 mm of the face (property Tolerance): holes and a trimmed outline are not kept."})

    def surface_sew(a):
        refs = a.get("faces") or []
        links = {}
        for r in refs:
            if not isinstance(r, str):
                raise bad("faces: surfaces' names, or faces as \"Body.Face3\".")
            label, sub, _ = picks.resolve(s, r)
            x = picks.find(doc(), label)
            # The feature sews only the faces listed: a whole object brings all of its own.
            subs = [sub] if sub else [f"Face{i + 1}" for i in range(len(x.Shape.Faces))]
            if not subs:
                raise bad(f"faces: {x.Label} has no faces.")
            links.setdefault(x, []).extend(subs)
        if sum(len(v) for v in links.values()) < 2:
            raise bad("faces: two or more faces (surfaces, or \"Body.Face3\") whose edges meet.")
        tol = picks.num(a.get("tolerance", 0.01), "tolerance")
        if tol <= 0:
            raise bad("tolerance: mm, over 0 — edges closer than this are joined (0.01).")
        o = new("Surface::Sewing", a.get("name") or "Sewn")
        o.ShapeList = list(links.items())
        o.Tolerance = tol
        out = done(o, "surface_sew")
        if not out.get("shells"):
            out["warning"] = "No face was joined to another (no shell): their edges are further apart than tolerance, or do not match along their length."
        if a.get("solid"):
            sh = o.Shape
            if not (sh.Shells and sh.Shells[0].isClosed()):
                free = [e for e in sh.Edges if len(sh.ancestorsOfType(e, Part.Face)) < 2] if sh.Shells else []
                out["solid"] = "not made: the shell is open — a gap wider than tolerance, or a face missing" + (f" ({len(free)} edge(s) with a face on one side only)" if free else "")
            else:
                sol = doc().addObject("Part::Feature", "Body")
                sol.Label = s.unique(a.get("name") and a["name"] + " solid" or f"{o.Label} solid")
                sol.Shape = geo.clean(Part.makeSolid(sh.Shells[0]))
                doc().recompute()
                out["solid"] = {"body": sol.Label, "volume": round(sol.Shape.Volume, 3)}
        return out

    def surface_cut(a):
        x, y = picks.shaped(doc(), a.get("surface"), "surface"), picks.shaped(doc(), a.get("by"), "by")
        if x is y:
            raise bad("surface, by: two different objects.")
        before = len(x.Shape.Faces), x.Shape.Area
        o = new("Surface::Cut", a.get("name") or "Surface cut")
        o.ShapeList = [x, y]
        out = done(o, "surface_cut", {"of": x.Label, "by": y.Label})
        if out.get("faces") == before[0] and abs(out.get("area", 0) - before[1]) < 1e-6 * max(1.0, before[1]):
            out["note"] = f"Nothing was cut: {y.Label} does not cross {x.Label}."
        elif abs(out.get("area", 0) - before[1]) < 1e-6 * max(1.0, before[1]):
            out["note"] = f"{y.Label} is a surface, not a solid: nothing was removed, {x.Label} came back split along where they cross. part_extract takes the piece to keep."
        return out

    def surface_blend(a):
        ends = {}
        for side in ("start", "end"):
            e = a.get(side)
            if not isinstance(e, dict):
                raise bad(f"{side}: {{ edge: \"Body.Edge3\", at: 0 … 1, continuity: 0 … 4, size }}.")
            ob, subs = edge_ref(e.get("edge"), f"{side}.edge")
            c = e.get("continuity", 2)
            if isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 4:
                raise bad(f"{side}.continuity: 0 (touching) … 4; 1 tangent, 2 curvature.")
            at = picks.num(e.get("at", 0 if side == "start" else 1), f"{side}.at")
            if not 0 <= at <= 1:
                raise bad(f"{side}.at: 0 (the edge's start) … 1 (its end).")
            size = picks.num(e.get("size", 1), f"{side}.size")
            if not -100 <= size <= 100 or size == 0:
                raise bad(f"{side}.size: -100 … 100, not 0 — how strongly the blend follows the edge's direction there; negative leaves against the edge's direction.")
            ends[side] = ((ob, [subs[0]]), c, at, size)
        o = new("Surface::FeatureBlendCurve", a.get("name") or "Blend curve")
        # Both edges first: changing any other property recomputes the curve at once.
        o.StartEdge, o.EndEdge = ends["start"][0], ends["end"][0]
        for side, (_, c, at, size) in ends.items():
            p = side.capitalize()
            setattr(o, f"{p}Continuity", c)
            setattr(o, f"{p}Parameter", at)
            setattr(o, f"{p}Size", size)
        return done(o, "surface_blend", {"note": "at: where on each edge, 0 (its start) … 1 (its end); size: how far the blend follows each edge's direction (negative: against it — the usual fix for a blend that loops back)."})

    return [
        Tool("surface_sections", "A surface through curves in order (Surface Sections, parametric: it follows them): sections [\"Body.Edge3\" | a wire or sketch's name …], two or more, each one open curve, all running the same way; every edge of a named wire is a section of its own. Reply: object, sections, faces, area, closed.",
             obj({"sections": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}}, ["sections"]), surface_sections, changes=True),
        Tool("surface_boundary", "A surface bounded by 2–4 curves meeting end to end, given going round (Surface GeomFillSurface, parametric): edges, fill stretched (default, flattest) | coons | curved (rounder). Lines and arcs are taken as B-splines. When coons or curved is refused for curves that do not match, a Surface Filling through the same edges is made instead (reply: note). Reply: object, fill, sides, area.",
             obj({"edges": {"type": "array", "items": {"type": "string"}}, "fill": {"type": "string"}, "name": {"type": "string"}}, ["edges"]), surface_boundary, changes=True),
        Tool("surface_extend", "Run a face on past its edges (Surface Extend, parametric): face \"Body.Face2\"; u and v, how far past each pair of opposite edges as a share of its size that way (0.05 = 5% at each end; -0.5 … 10). The result is a new four-sided B-spline surface within 0.1 mm of the face; holes and a trimmed outline are not kept. Reply: object, area.",
             obj({"face": {"type": "string"}, "u": {"type": "number"}, "v": {"type": "number"}, "name": {"type": "string"}}, ["face"]), surface_extend, changes=True),
        Tool("surface_sew", "Sew surfaces into one shell (Surface Sewing, parametric): faces [surface objects (all their faces), or \"Body.Face3\"], two or more whose edges meet within tolerance mm (0.01). solid: true also makes a closed shell a solid body (a plain copy). Reply: faces, shells, closed, area; solid { body, volume }, or why not (the shell is open); warning when nothing joined.",
             obj({"faces": {"type": "array", "items": {"type": "string"}}, "tolerance": {"type": "number"}, "solid": {"type": "boolean"}, "name": {"type": "string"}}, ["faces"]), surface_sew, changes=True),
        Tool("surface_cut", "Cut a surface by another object (Surface Cut, a boolean cut that follows both): surface, by. By a solid: what lies inside it is removed. By a surface: nothing is removed, the surface comes back split along where they cross (reply: note; part_extract takes a piece). Reply: object, of, by, faces, area.", obj({"surface": {"type": "string"}, "by": {"type": "string"}, "name": {"type": "string"}}, ["surface", "by"]), surface_cut, changes=True),
        Tool("surface_blend", "A blend curve joining two edges smoothly (Surface BlendCurve, parametric): start / end { edge \"Body.Edge3\", at 0…1 along it (default: start 0, end 1), continuity 0…4 (1 tangent, 2 curvature, default), size (1; the tangent there is size × the distance between the two points, so 5 swings wide; negative leaves against the edge's direction) }. Reply: object, edges 1, length. Use it as a boundary for the next surface.",
             obj({"start": {"type": "object"}, "end": {"type": "object"}, "name": {"type": "string"}}, ["start", "end"]), surface_blend, changes=True),
    ]
