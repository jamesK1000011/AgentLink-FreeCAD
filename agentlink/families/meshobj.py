# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's Mesh and MeshPart workbenches on the document's mesh objects
# (an add-on's scan tools work on the scan in its own session instead):
# a body meshed three ways, a mesh evaluated and repaired as the Mesh
# workbench's Evaluate & Repair does, decimated, refined, smoothed, offset,
# trimmed by a plane, transformed, joined by booleans, cut into
# cross-sections, split into its pieces and into planar or curved segments,
# its curvature measured (and drawn), and a shape projected onto it.

import math
import os

import FreeCAD
import Mesh  # noqa: F401 — the family stands on the Mesh module; left out without it
import Part

import numpy as np

from .. import geometry as geo
from .. import meshbool
from .. import meshdist
from .. import render
from .. import store
from .. import runners
from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "mesh"
INFO = ("FreeCAD's Mesh workbench on document meshes: mesh a body, evaluate and repair, decimate, refine, smooth, offset, trim, transform, "
        "booleans, cross-sections, split, planar and curvature segments, curvature, projection onto a mesh.")

V = FreeCAD.Vector


def meshes(doc):
    return [o for o in doc.Objects if o.isDerivedFrom("Mesh::Feature")]


def reading(m):
    out = {"points": m.CountPoints, "facets": m.CountFacets, "solid": bool(m.isSolid()), "components": int(m.countComponents()),
           "area": round(m.Area, 3), "box": geo.box_json(m, 3)["size"]}
    if out["solid"]:
        out["volume"] = round(m.Volume, 3)
    return out


def arrays(m):
    """A Mesh's points (where they stand, its Placement applied) and facets."""
    pts, tris = m.Topology
    V = np.array([[p.x, p.y, p.z] for p in pts], dtype=float).reshape(-1, 3)
    return V, np.array(tris, dtype=np.int64).reshape(-1, 3)


def from_arrays(V, F):
    """A Mesh of points V and facets F as they are: given as (points,
    facets), so no point is merged with a near one; as triangles of points
    where this FreeCAD does not take that form."""
    F = np.asarray(F, dtype=np.int64).reshape(-1, 3)
    try:
        m = Mesh.Mesh()
        m.addFacets(([FreeCAD.Vector(*p) for p in np.asarray(V, dtype=float).tolist()], [tuple(t) for t in F.tolist()]))
        if m.CountFacets == len(F):
            return m
    except Exception:
        pass
    m = Mesh.Mesh()
    m.addFacets([[tuple(V[i]) for i in t] for t in F.tolist()])
    return m


def in_place(m):
    """A copy of a Mesh with its points where they stand and no placement
    of its own (addMesh and transform work on the stored points and pass a
    placement by)."""
    g = m.copy()
    pl = g.Placement
    if not pl.isIdentity():
        g.Placement = FreeCAD.Placement()
        g.transform(pl.toMatrix())
    return g


def vec(v, name, default=None):
    """[x, y, z] numbers as a Vector, refused by name."""
    if v is None and default is not None:
        v = list(default)
    if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        raise bad(f"{name}: [x, y, z] numbers.")
    return V(*[float(x) for x in v])


def edges_state(m):
    """open: edges one facet has; bad: edges more than two share."""
    F = np.array(m.Topology[1], dtype=np.int64).reshape(-1, 3)
    if len(F) == 0:
        return {"open": 0, "bad": 0, "facets": 0}
    a, b = F.reshape(-1), F[:, [1, 2, 0]].reshape(-1)
    n = int(F.max()) + 1
    _, c = np.unique(np.minimum(a, b) * n + np.maximum(a, b), return_counts=True)
    return {"open": int((c == 1).sum()), "bad": int((c > 2).sum()), "facets": int(len(F))}


def worse(after, before):
    """Whether a repair step left the mesh worse than it found it: more open
    or overloaded edges, or nothing left."""
    return after["facets"] == 0 or after["open"] > before["open"] or after["bad"] > before["bad"]


def evaluation(m):
    """The Mesh workbench's Evaluate & Repair checks, read."""
    e = {}
    checks = (("nonManifolds", "hasNonManifolds"), ("selfIntersections", "hasSelfIntersections"), ("flippedNormals", "hasNonUniformOrientedFacets"),
              ("corruptedFacets", "hasCorruptedFacets"), ("invalidPoints", "hasInvalidPoints"), ("pointsOnEdges", "hasPointsOnEdge"),
              ("indicesOutOfRange", "hasFacetsOutOfRange"), ("invalidNeighbours", "hasInvalidNeighbourhood"))
    for k, f in checks:
        try:
            e[k] = bool(getattr(m, f)())
        except Exception:
            pass
    try:
        e["flippedCount"] = int(m.countNonUniformOrientedFacets())
    except Exception:
        pass
    try:
        # the pairs are found a second time to be listed: only when there are any
        e["selfIntersectionPairs"] = len(m.getSelfIntersections()) if e.get("selfIntersections") else 0
    except Exception:
        pass
    e["open"] = not m.isSolid()
    problems = [k for k, v in e.items() if v is True and k != "open"] + (["open (holes)"] if e["open"] else [])
    return e, problems


def _curv_map(s, a):
    ref = a.get("mesh") or (a.get("objects") or [None])[0]
    ms = meshes(s.doc)
    o = next((x for x in ms if ref in (x.Label, x.Name)), None) if ref else (ms[-1] if ms else None)
    if o is None:
        raise ToolError("not_found", "No mesh to show: meshobj_from_shape or import_file one.")
    m = o.Mesh
    V_ = np.array([[p.x, p.y, p.z] for p in m.Points], dtype=float)
    F_ = np.array([list(f.PointIndices) for f in m.Facets], dtype=int)
    c = np.array([(k[0], k[1]) for k in m.getCurvaturePerVertex()], dtype=float)  # k1, k2 (and their directions) per point
    kind = a.get("curvature", "mean")
    vals = {"mean": (c[:, 0] + c[:, 1]) / 2, "gauss": c[:, 0] * c[:, 1], "max": np.max(np.abs(c), axis=1)}.get(kind, (c[:, 0] + c[:, 1]) / 2)
    lo5, hi95 = float(np.percentile(vals, 5)), float(np.percentile(vals, 95))
    if lo5 < 0 < hi95:  # concave and convex: zero in the middle
        m_ = max(-lo5, hi95) or 1.0
        rng = [-m_, m_]
    else:  # all one way: the colours spent on its own spread
        rng = [lo5, hi95] if hi95 > lo5 else [lo5 - 1e-6, hi95 + 1e-6]
    return {"layers": [{"name": o.Label, "V": V_, "F": F_, "values": vals, "creases": True}], "unit": "1/mm", "cmap": "jet", "range": rng,
            "worst": "abs", "label": f"CURVATURE ({kind.upper()})", "note": f"{o.Label}: {kind} curvature at each point (1 / radius); 5% beyond the colours' ends."}


render.register_map("curvature", _curv_map, "A document mesh's curvature (mesh names which; curvature mean | gauss | max).")


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    EDIT = "meshEdit"
    HEAVY = 200000  # triangles past which the slower tools say so

    def editing():
        """{original label: its edit copy's label} for meshes being edited."""
        return store.read(doc(), EDIT, {})

    def mesh_of(ref):
        ms = meshes(doc())
        ed = editing()
        if ref is not None and ref in ed:
            # Being edited: the tools work on its copy (meshobj_edit).
            cp = next((x for x in ms if x.Label == ed[ref]), None)
            if cp is not None:
                return cp
        if ref is None:
            ms = [x for x in ms if x.Label not in ed]  # an original being edited is not a choice

            if len(ms) == 1:
                return ms[0]
            raise (ToolError("not_found", "No mesh in the document: meshobj_from_shape makes one, import_file reads one.") if not ms else bad(f"mesh: say which — {', '.join(o.Label for o in ms)}."))
        o = next((x for x in ms if ref in (x.Label, x.Name)), None)
        if o is None:
            raise ToolError("not_found", f"mesh {ref!r}: the meshes are {', '.join(x.Label for x in ms) or 'none'}.")
        return o

    def keep(o, m, tool, a, extra=None, before=None):
        """The changed mesh: into the object, or a new one with copy: true."""
        if a.get("copy"):
            n = doc().addObject("Mesh::Feature", "Mesh")
            n.Label = s.unique(a.get("name") or f"{o.Label} ({tool.split('_', 1)[1]})")
            n.Mesh = m
            target = n
        else:
            o.Mesh = m
            target = o
        doc().recompute()
        s.snapshot(tool)
        out = {"mesh": target.Label, **reading(target.Mesh), **(extra or {}), "step": len(s.steps)}
        if before is not None:
            out["before"] = before
        return out

    def meshobj_edit(a):
        act = a.get("action", "state")
        ed = editing()
        if act == "state":
            return {"editing": [{"mesh": k, "copy": v} for k, v in ed.items()]}
        ref = a.get("mesh")
        if act == "begin":
            o = mesh_of(ref)
            if o.Label in ed or o.Label in ed.values():
                raise ToolError("invalid_state", f"{o.Label} is being edited already: use or discard first.")
            c = new_mesh(o.Mesh.copy(), f"{o.Label} (editing)")
            if getattr(o, "ViewObject", None) is not None:
                o.ViewObject.Visibility = False
            ed[o.Label] = c.Label
            store.write(doc(), EDIT, ed)
            doc().recompute()
            return {"editing": o.Label, "copy": c.Label, **reading(c.Mesh), "note": f"Every meshobj tool given {o.Label} now changes the copy (each step undoable); use puts it in place of the original, discard drops it."}
        orig = next((k for k, v in ed.items() if ref in (k, v)), None) if ref else (next(iter(ed)) if len(ed) == 1 else None)
        if orig is None:
            raise ToolError("invalid_state", "No edit of that mesh: meshobj_edit { action: begin, mesh } starts one." if ref else f"mesh: which edit — {', '.join(ed) or 'none'}.")
        o = next((x for x in meshes(doc()) if x.Label == orig), None)
        c = next((x for x in meshes(doc()) if x.Label == ed[orig]), None)
        if act == "use":
            if o is None or c is None:
                raise ToolError("not_found", "The original or its copy is gone: discard.")
            before = reading(o.Mesh)
            o.Mesh = c.Mesh.copy()
            doc().removeObject(c.Name)
        elif act == "discard":
            if c is not None:
                doc().removeObject(c.Name)
            before = None
        else:
            raise bad("action: begin, use, discard or state.")
        if o is not None and getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = True
        del ed[orig]
        store.write(doc(), EDIT, ed)
        doc().recompute()
        s.snapshot("meshobj_edit")
        return {"mesh": orig, ("used" if act == "use" else "discarded"): True, **({"now": reading(o.Mesh), "before": before} if act == "use" and o is not None else {})}

    def new_mesh(m, label):
        n = doc().addObject("Mesh::Feature", "Mesh")
        n.Label = s.unique(label)
        n.Mesh = m
        return n

    # ---- making and reading ----

    def meshobj_from_shape(a):
        import MeshPart

        src = next((o for o in doc().Objects if a.get("body") in (o.Label, o.Name) and hasattr(o, "Shape")), None) if a.get("body") else (s.bodies()[0] if len(s.bodies()) == 1 else None)
        if src is None:
            have = ", ".join(o.Label for o in s.bodies()[:20]) or "none"
            raise bad(f"body: the shape to mesh, by label — the bodies: {have}.")
        if src.Shape.isNull() or not src.Shape.Faces:
            raise bad(f"body: {src.Label} has no faces to mesh.")
        how = a.get("method", "standard")
        kw = {"Shape": src.Shape}
        if how == "standard":
            defl, ang = picks.num(a.get("deflection", 0.05), "deflection"), picks.num(a.get("angle", 15), "angle")
            if defl <= 0 or not 0 < ang <= 90:
                raise bad("deflection: mm the triangles may stand off the surface, over 0 (0.05); angle: degrees between neighbouring triangles on a curve, over 0 to 90 (15).")
            kw.update(LinearDeflection=defl, AngularDeflection=math.radians(ang), Relative=False)
        elif how == "mefisto":
            ml = picks.num(a.get("maxLength", 2.0), "maxLength")
            if ml <= 0:
                raise bad("maxLength: mm, the longest triangle edge, over 0 (2).")
            kw.update(MaxLength=ml)
        elif how == "netgen":
            fine = {"verycoarse": 0, "coarse": 1, "moderate": 2, "fine": 3, "veryfine": 4}
            if a.get("fineness", "moderate") not in fine:
                raise bad(f"fineness: {', '.join(fine)}.")
            kw.update(Fineness=fine[a.get("fineness", "moderate")], SecondOrder=0, Optimize=1, AllowQuad=0)
        else:
            raise bad("method: standard (deflection, angle), mefisto (maxLength: even triangles) or netgen (fineness).")
        try:
            m = MeshPart.meshFromShape(**kw)
        except Exception as e:
            raise ToolError("unavailable" if how == "netgen" else "failed", f"{how} meshing failed: {e}" + (" — this FreeCAD may lack Netgen; mefisto gives even triangles too." if how == "netgen" else ""))
        n = new_mesh(m, a.get("name") or f"{src.Label} mesh")
        doc().recompute()
        s.snapshot("meshobj_from_shape")
        out = {"mesh": n.Label, "from": src.Label, "method": how, **reading(m), "step": len(s.steps)}
        # Mefisto can leave a face with small holes (a screw boss's pilot)
        # half-meshed: open and non-manifold from a sound solid. Say so rather
        # than hand back a broken mesh as if it were the part.
        if src.Shape.Solids and src.Shape.isClosed() and (not m.isSolid() or m.hasNonManifolds()):
            out["warning"] = f"The solid meshed open or non-manifold with {how} ({out.get('components', '?')} components): method standard (or netgen) meshes it closed; meshobj_info shows the problems."
        if m.CountFacets > HEAVY:
            out["heavy"] = f"{m.CountFacets} triangles: the repair, boolean, segment and section tools slow down past about {HEAVY} — a coarser deflection / maxLength, or meshobj_decimate."
        return out

    def meshobj_info(a):
        o = mesh_of(a.get("mesh"))
        e, problems = evaluation(o.Mesh)
        return {"mesh": o.Label, **reading(o.Mesh), "evaluation": e, "problems": problems, **({"next": "meshobj_repair fixes them."} if problems else {"verdict": "clean"})}

    # ---- repair ----

    # What Mesh.write tells from a file's extension (MeshCore's MeshOutput::GetFormat, FreeCAD 1.1).
    WRITES = ("stl", "ast", "obj", "off", "ply", "3mf", "amf", "smf", "iv", "x3d", "x3dz", "xhtml", "wrl", "vrml", "wrz", "nas", "bdf", "py", "asy", "bms", "idtf", "mgl")

    REPAIRS = ("normals", "duplicates", "nonmanifolds", "selfintersections", "degenerate", "folds", "indices", "pointsonedges", "holes", "islands")

    def meshobj_repair(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        e0, p0 = evaluation(m)
        want = a.get("fix") or [r for r in REPAIRS if r not in ("holes", "islands")]
        unknown = [w for w in want if w not in REPAIRS] if isinstance(want, list) else [want]
        if unknown:
            raise bad(f"fix: a list of any of {', '.join(REPAIRS)} — not {', '.join(str(u) for u in unknown)}.")
        did, undone = [], []
        state = edges_state(m)
        start = dict(state)
        for w in want:
            # Each step on its own, kept only if it leaves the mesh no worse:
            # FreeCAD's removeNeedles, fixSelfIntersections and
            # removeFoldsOnSurface delete facets, and on a closed mesh that
            # opens holes (a closed solid came back open).
            prev = m.copy()
            try:
                if w == "indices":
                    m.fixIndices()
                    m.rebuildNeighbourHood()
                elif w == "duplicates":
                    m.removeDuplicatedPoints()
                    m.removeDuplicatedFacets()
                elif w == "degenerate":
                    m.fixDegenerations(float(a.get("tolerance", 1e-6)))
                    m.removeNeedles(float(a.get("tolerance", 1e-6)) * 1000)
                elif w == "nonmanifolds":
                    m.removeNonManifolds()
                    m.removeNonManifoldPoints()
                elif w == "selfintersections":
                    m.fixSelfIntersections()
                elif w == "folds":
                    m.removeFoldsOnSurface()
                elif w == "normals":
                    m.harmonizeNormals()
                    if m.isSolid() and m.Volume < 0:
                        m.flipNormals()
                elif w == "holes":
                    m.fillupHoles(int(a.get("maxHoleEdges", 50)))
                elif w == "islands":
                    m.removeComponents(int(a.get("minFacets", 10)))
                elif w == "pointsonedges":
                    m.removePointsOnEdge(False)
            except Exception as ex:
                m = prev
                undone.append(f"{w}: failed ({ex})")
                continue
            now = edges_state(m)
            if worse(now, state):
                m = prev
                undone.append(f"{w}: undone — it left {now['open']} open and {now['bad']} overloaded edges, {now['facets']} facets (before: {state['open']}, {state['bad']}, {state['facets']})")
                continue
            state = now
            did.append(w)
        e1, p1 = evaluation(m)
        out = {"did": did, "problems": p1, "fixed": [p for p in p0 if p not in p1], "edges": {"open": state["open"], "overloaded": state["bad"]}}
        if undone:
            out["undone"] = undone
        if not did:
            return {"mesh": o.Label, **reading(o.Mesh), **out, "changed": False, "note": "No step left the mesh better without making it worse; it is unchanged."}
        return keep(o, m, "meshobj_repair", a, out, before={"problems": p0, "facets": o.Mesh.CountFacets, "edges": {"open": start["open"], "overloaded": start["bad"]}})

    # ---- reshape ----

    def meshobj_decimate(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        n0 = m.CountFacets
        if a.get("facets"):
            target = int(a["facets"])
            if not 4 <= target < n0:
                raise bad(f"facets: fewer than now ({n0}), 4 or more.")
            red = 1 - target / n0
        else:
            red = picks.num(a.get("reduction", 0.5), "reduction")
            if not 0 < red < 1:
                raise bad("reduction: the share of triangles to remove, 0 … 1 (or facets: how many to keep).")
        tol = picks.num(a.get("tolerance", 0.1), "tolerance")
        if tol <= 0:
            raise bad("tolerance: over 0 — the error one collapse may add (0.1); a larger one lets more triangles go.")
        m.decimate(tol, red)
        extra = {"reduced": f"{n0} → {m.CountFacets} triangles"}
        want = n0 * (1 - red)
        if m.CountFacets > want * 1.1 + 4:
            # FreeCAD stops collapsing where the next collapse would add more error than tolerance
            extra["note"] = f"Stopped at {m.CountFacets}, short of the {int(want)} asked: tolerance {tol:g} holds the rest (flat regions go first). A larger tolerance removes more, at the cost of shape."
        return keep(o, m, "meshobj_decimate", a, extra, before={"facets": n0})

    def meshobj_refine(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        n0 = m.CountFacets
        rounds = a.get("rounds", 1)
        if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 3:
            raise bad("rounds: 1 … 3 (each puts a point in the middle of every triangle: about three times as many).")
        if n0 * 3 ** rounds > 2000000:
            raise ToolError("invalid_state", f"{o.Label} has {n0} triangles: {rounds} round(s) would make about {n0 * 3 ** rounds} (over 2,000,000). Fewer rounds, or meshobj_decimate first.")
        for _ in range(rounds):
            m.refine()
        if a.get("optimize"):
            m.optimizeTopology(-1.0)
        return keep(o, m, "meshobj_refine", a, {"refined": f"{n0} → {m.CountFacets} triangles"})

    def meshobj_smooth(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        meth = a.get("method", "taubin")
        it = a.get("iterations", 3)
        if isinstance(it, bool) or not isinstance(it, int) or not 1 <= it <= 200:
            raise bad("iterations: a whole number, 1 … 200 (3).")
        if meth == "laplace":
            m.smooth(Method="Laplace", Iteration=it, Lambda=float(a.get("lambda", 0.6307)))
        elif meth == "taubin":
            m.smooth(Method="Taubin", Iteration=it, Lambda=float(a.get("lambda", 0.6307)), Micro=float(a.get("mu", 0.0424)))
        else:
            raise bad("method: taubin (shrinks far less) or laplace (shrinks).")
        vol0 = o.Mesh.Volume if o.Mesh.isSolid() else None
        extra = {"method": meth, "iterations": it}
        if vol0:
            extra["volumeChange"] = round(m.Volume - vol0, 3)
            # FreeCAD's Taubin moves each point towards its neighbours' mean and
            # back out, point after point: on a coarse mesh the two do not cancel
            # (a 150-point sphere lost a fifth of its volume in 5 iterations).
            if abs(m.Volume - vol0) > 0.02 * abs(vol0):
                extra["warning"] = (f"The volume changed by {100 * (m.Volume - vol0) / vol0:.1f}%: smoothing pulls a coarse mesh in (taubin less than laplace). "
                                    "Fewer iterations, or meshobj_refine first; history_undo takes it back.")
        return keep(o, m, "meshobj_smooth", a, extra)

    def meshobj_trim(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        p = vec(a.get("at"), "at", (0, 0, 0))
        n = vec(a.get("normal"), "normal", (0, 0, 1))
        if n.Length < 1e-9:
            raise bad("normal: not zero — the side it points to is removed.")
        # Triangles wholly on the side taken away, and those the plane crosses
        # (each cut one comes back as one or two: the count after is no measure
        # of what went — a cube cut in half has 14 triangles where it had 12).
        P0, F0 = arrays(m)
        side = ((P0 - np.array([p.x, p.y, p.z])) @ np.array([n.x, n.y, n.z]) / n.Length)[F0] if len(F0) else np.zeros((0, 3))
        gone = int(np.sum((side >= -1e-7).all(axis=1) & (side > 1e-7).any(axis=1)))
        crossed = int(np.sum((side > 1e-7).any(axis=1) & (side < -1e-7).any(axis=1)))
        m.trimByPlane(p, n)
        # trimByPlane adds the split triangles with points of their own, so the
        # strip along the cut came back as a second component, its seam as two
        # extra open loops, and close then capped all three (self-intersecting,
        # three caps of area). Merging the points first leaves the one cut loop.
        m.removeDuplicatedPoints()
        m.removeDuplicatedFacets()
        m.fixIndices()
        if m.CountFacets == 0:
            raise ToolError("failed", f"The plane leaves nothing of {o.Label}: all of it lies on the side normal points to. Turn normal round, or move at. Nothing was changed.")
        if a.get("preview"):
            bb = m.BoundBox
            return {"mesh": o.Label, "preview": True, "wouldRemove": gone, "wouldCut": crossed, "wouldKeep": m.CountFacets,
                    "keptBox": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)], "note": "Nothing changed: the same call without preview cuts."}
        extra = {"removed": gone, "cut": crossed}
        if a.get("close") and not m.isSolid():
            m.fillupHoles(int(a.get("maxHoleEdges", 1000)))
            m.harmonizeNormals()
            if m.isSolid() and m.Volume < 0:
                m.flipNormals()
            if not m.isSolid():
                extra["warning"] = "The cut is not fully closed: a loop longer than maxHoleEdges, or the mesh was open before the cut. meshobj_boundary shows the loops left."
        extra["note"] = "Capped flat where the plane passed." if a.get("close") else "Cut open where the plane passed; close: true fills the cut."
        return keep(o, m, "meshobj_trim", a, extra)

    def meshobj_transform(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh.copy()
        mat = FreeCAD.Matrix()
        flips = 0
        if not any(a.get(k) is not None for k in ("scale", "rotate", "move", "mirror")):
            raise bad("One or more of scale (a factor or [x, y, z]), rotate { axis, angle }, move [x, y, z], mirror \"x\" | \"y\" | \"z\".")
        if a.get("scale") is not None:
            f = a["scale"]
            f = [f, f, f] if isinstance(f, (int, float)) and not isinstance(f, bool) else f
            if not (isinstance(f, list) and len(f) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x != 0 for x in f)):
                raise bad("scale: a factor, or [x, y, z] — none of them 0. About the origin: move it back after, or scale a mesh centred there.")
            fx, fy, fz = (float(x) for x in f)
            mat.scale(fx, fy, fz)
            flips += sum(1 for x in (fx, fy, fz) if x < 0)
        if a.get("rotate"):
            r = a["rotate"]
            if not isinstance(r, dict) or isinstance(r.get("angle", 0), bool) or not isinstance(r.get("angle", 0), (int, float)):
                raise bad("rotate: { axis: [x, y, z] (default z), angle: degrees } — about the origin.")
            ax = vec(r.get("axis"), "rotate.axis", (0, 0, 1))
            if ax.Length < 1e-9:
                raise bad("rotate.axis: not [0, 0, 0].")
            rot = FreeCAD.Rotation(ax, float(r.get("angle", 0)))
            mat = rot.toMatrix().multiply(mat)
        if a.get("move"):
            t = FreeCAD.Matrix()
            t.move(vec(a["move"], "move"))
            mat = t.multiply(mat)
        if a.get("mirror"):
            if a["mirror"] not in ("x", "y", "z"):
                raise bad("mirror: \"x\", \"y\" or \"z\" — the axis whose sign flips (x mirrors across the YZ plane through the origin).")
            mm = FreeCAD.Matrix()
            ax = {"x": (0, 0), "y": (1, 1), "z": (2, 2)}[a["mirror"]]
            setattr(mm, f"A{ax[0] + 1}{ax[1] + 1}", -1.0)
            mat = mm.multiply(mat)
            flips += 1
        # Mesh.transform moves the stored points, before the object's own
        # placement is applied: carried through it, so a mesh that has been
        # placed turns and moves in the document's axes like any other.
        pl = m.Placement
        if not pl.isIdentity():
            pm = pl.toMatrix()
            mat = pm.inverse().multiply(mat).multiply(pm)
        m.transform(mat)
        if flips % 2:
            m.flipNormals()  # a mirror (or an odd count of negative scales) turns every triangle inside out
        return keep(o, m, "meshobj_transform", a)

    BOOL_OPS = {"union": "add", "intersection": "intersect", "difference": "subtract"}

    def meshobj_boolean(a):
        x, y = mesh_of(a.get("a")), mesh_of(a.get("b"))
        op = a.get("op", "union")
        if not (x.Mesh.isSolid() and y.Mesh.isSolid()):
            raise ToolError("invalid_state", "Mesh booleans need closed meshes: meshobj_repair { fix: [\"holes\"] } first.")
        if op not in BOOL_OPS:
            raise bad("op: union, intersection or difference.")
        # Agent Link's own boolean first (numpy, any density): only the
        # triangles the other mesh crosses are cut, the rest kept as they
        # are, the result closed or refused. FreeCAD's Mesh booleans come
        # back open on dense meshes (a 140,698-triangle scan minus a
        # 5,212-triangle cutter: 2,607 open edges), so they and the trip
        # through solids are only what is left when it refuses.
        res, how, why = None, "mesh (Agent Link's boolean: only the triangles the other mesh crosses are cut)", None
        try:
            V, F, _, _ = meshbool.boolean(*arrays(x.Mesh), *arrays(y.Mesh), BOOL_OPS[op])
            if len(F) == 0:
                raise ToolError("failed", f"The {op} left nothing: the meshes do not overlap that way.")
            res = from_arrays(V, F)
            if not res.isSolid():
                why, res = "its result did not read back closed", None
        except meshbool.BooleanError as e:
            why = str(e)
        if res is None:
            mx = x.Mesh.copy()
            how = f"FreeCAD's mesh boolean (Agent Link's refused: {why})"
            try:
                res = {"union": mx.unite, "intersection": mx.intersect, "difference": mx.difference}[op](y.Mesh)
            except Exception:
                res = None
            if res is None or res.CountFacets == 0 or not res.isSolid() or evaluation(res)[1]:
                if max(x.Mesh.CountFacets, y.Mesh.CountFacets) > int(a.get("maxFacets", 60000)):
                    raise ToolError("failed", f"The mesh {op} came out broken ({why}), and the meshes are too dense to go through solids (maxFacets).")
                import MeshPart

                def solid(m):
                    sh = Part.Shape()
                    sh.makeShapeFromMesh(m.Topology, 0.01)
                    return Part.makeSolid(Part.makeShell(sh.Faces))

                try:
                    sa, sb = solid(x.Mesh), solid(y.Mesh)
                    r = {"union": sa.fuse, "intersection": sa.common, "difference": sa.cut}[op](sb)
                except Exception as e:
                    raise ToolError("failed", f"The {op} failed both as meshes and as solids: {e}")
                if r.isNull() or not r.Solids or r.Volume < 1e-9:
                    raise ToolError("failed", f"The {op} left nothing: the meshes do not overlap that way.")
                res = MeshPart.meshFromShape(Shape=r, LinearDeflection=float(a.get("deflection", 0.05)), AngularDeflection=0.3, Relative=False)
                how = f"through solids (Agent Link's boolean refused: {why}; FreeCAD's mesh boolean came out broken)"
        n = new_mesh(res, a.get("name") or f"{x.Label} {op} {y.Label}")
        return picks.finish(s, "meshobj_boolean", lambda: {"mesh": n.Label, "op": op, "how": how, **reading(res)})

    # ---- sections, pieces, segments, curvature ----

    def meshobj_sections(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh
        n = vec(a.get("normal"), "normal", (0, 0, 1))
        if n.Length < 1e-9:
            raise bad("normal: not [0, 0, 0] — the direction the slices are stacked along.")
        n.normalize()
        bb = m.BoundBox
        # the box's reach along n: each axis gives its low or its high end, by n's sign there
        ends = [(bb.XMin * n.x, bb.XMax * n.x), (bb.YMin * n.y, bb.YMax * n.y), (bb.ZMin * n.z, bb.ZMax * n.z)]
        lo, hi = sum(min(e) for e in ends), sum(max(e) for e in ends)
        if a.get("at") is not None:
            ds = a["at"]
            if not (isinstance(ds, list) and 1 <= len(ds) <= 500 and all(isinstance(d, (int, float)) and not isinstance(d, bool) for d in ds)):
                raise bad(f"at: [distances] mm from the origin along normal, 1 … 500 of them — {o.Label} reaches from {lo:.4g} to {hi:.4g}.")
            ds = [float(d) for d in ds]
        else:
            k = a.get("count", 5)
            if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 500:
                raise bad("count: 1 … 500 slices, evenly spaced between the mesh's ends (or at: [distances]).")
            ds = [lo + (hi - lo) * (i + 1) / (k + 1) for i in range(k)]
        tol = picks.num(a.get("tolerance", 0.01), "tolerance")
        if tol <= 0:
            raise bad("tolerance: mm within which cut ends are joined into one loop, over 0 (0.01, FreeCAD's own).")
        planes = [(n * d, n) for d in ds]
        polys = m.crossSections(planes, tol, True)
        wires, rows = [], []
        for d, sec in zip(ds, polys):
            ws = []
            # a plane through a row of the mesh's own edges is answered twice over
            sec, _twice = meshdist.once_each([[(q.x, q.y, q.z) for q in map(V, pl)] for pl in sec])
            for pl in sec:
                pts = [V(*p) for p in pl]
                if len(pts) >= 2:
                    try:
                        ws.append(Part.makePolygon(pts))
                    except Exception:
                        pass
            wires += ws
            rows.append({"at": round(d, 4), "loops": len(ws), "length": round(sum(w.Length for w in ws), 3)})
        if not wires:
            raise ToolError("failed", f"No section met {o.Label} at those distances ({lo:.3g} … {hi:.3g} along {geo.vec(n)}).")
        c = doc().addObject("Part::Feature", "Sections")
        c.Label = s.unique(a.get("name") or f"{o.Label} sections")
        c.Shape = Part.Compound(wires)
        return picks.finish(s, "meshobj_sections", lambda: {"sections": c.Label, "normal": geo.vec(n), "slices": rows, "use": "export writes them as DXF; part_face makes one a face."})

    def meshobj_split(a):
        o = mesh_of(a.get("mesh"))
        parts = o.Mesh.getSeparateComponents()
        if len(parts) < 2:
            raise bad(f"{o.Label} is one piece.")
        least = a.get("minFacets", 1)
        if isinstance(least, bool) or not isinstance(least, int) or least < 1:
            raise bad("minFacets: a whole number, 1 or more — pieces with fewer triangles are left out.")
        parts = sorted([p for p in parts if p.CountFacets >= least], key=lambda x: -x.CountFacets)
        if not parts:
            raise bad(f"minFacets: no piece of {o.Label} has {least} triangles or more.")
        if len(parts) > 100:
            # a noisy scan: thousands of crumbs would each become an object
            raise ToolError("invalid_state", f"{o.Label} has {len(parts)} pieces of {least} or more triangles (the 100th has {parts[99].CountFacets}): over 100 objects. Give minFacets above that to keep the real parts, or meshobj_repair {{ fix: [\"islands\"], minFacets }} to drop the crumbs first. Nothing was made.")
        made = []
        for i, p in enumerate(parts, 1):
            made.append(new_mesh(p, f"{o.Label} {i}").Label)
        if hasattr(o, "Visibility"):
            o.Visibility = False
        return picks.finish(s, "meshobj_split", lambda: {"from": o.Label, "pieces": made, "facets": [p.CountFacets for p in parts][:20],
                                                         "note": f"{o.Label} is hidden, not removed; the pieces are largest first."})

    def meshobj_segments(a):
        o = mesh_of(a.get("mesh"))
        m = o.Mesh
        kind = a.get("kind", "planar")
        least, top = a.get("minFacets", 20), a.get("top", 12)
        for k_, v_ in (("minFacets", least), ("top", top)):
            if isinstance(v_, bool) or not isinstance(v_, int) or v_ < 1:
                raise bad(f"{k_}: a whole number, 1 or more.")
        if kind == "planar":
            dev = picks.num(a.get("deviation", 0.01), "deviation")
            if dev <= 0:
                raise bad("deviation: mm a triangle may stand off its region's plane, over 0 (0.01; a scan needs about its noise, 0.05 … 0.3).")
            segs = m.getPlanarSegments(dev, least)
        elif kind == "curvature":
            tol = picks.num(a.get("tolerance", 0.01), "tolerance")
            if tol <= 0:
                raise bad("tolerance: 1/mm either principal curvature may be off zero, over 0 (0.01: flatter than a 100 mm radius).")
            try:
                # (wanted max curvature, wanted min curvature, tolerance of each, least facets): 0, 0 is flat
                segs = m.getSegmentsByCurvature([(0.0, 0.0, tol, tol, least)])
            except Exception as e:
                raise ToolError("failed", f"Curvature segmentation failed here: {e} — kind planar finds flat regions.")
        else:
            raise bad("kind: planar (flat regions by distance from a fitted plane: deviation mm) or curvature (flat regions by curvature: tolerance 1/mm).")
        found = []
        for seg in segs:
            sub = m.meshFromSegment(list(seg))
            nrm = V()
            for f in sub.Facets:
                nrm += V(f.Normal) * f.Area
            if nrm.Length > 1e-12:
                nrm.normalize()
            found.append(({"facets": len(seg), "area": round(sub.Area, 3), "center": geo.vec(sub.BoundBox.Center), "normal": geo.vec(nrm)}, sub))
        found.sort(key=lambda r: -r[0]["area"])
        rows = [r for r, _ in found]
        out = {"mesh": o.Label, "kind": kind, "segments": len(rows), "largest": rows[:top]}
        if not rows:
            out["note"] = ("No flat region of that size: a larger deviation (a scan's noise), or a smaller minFacets." if kind == "planar"
                           else "No flat region of that size: a larger tolerance, or a smaller minFacets.")
        if a.get("keep") and rows:
            made = []
            for i, (_, sub) in enumerate(found[:top], 1):  # in the order of largest
                made.append(new_mesh(sub, f"{o.Label} segment {i}").Label)
            out["kept"] = made
            picks.finish(s, "meshobj_segments", out)
        out["use"] = "A flat segment's normal and centre place a sketch (sketch_new { face }) or a datum plane on a scan."
        return out

    def meshobj_curvature(a):
        o = mesh_of(a.get("mesh"))
        if o.Mesh.CountFacets == 0:
            raise ToolError("invalid_state", f"{o.Label} has no triangles.")
        c = np.array([(k[0], k[1]) for k in o.Mesh.getCurvaturePerVertex()], dtype=float).reshape(-1, 2)
        k1, k2 = c[:, 0], c[:, 1]
        mean = (k1 + k2) / 2
        kmax = np.max(np.abs(c), axis=1)
        flat = float(np.mean(kmax < float(a.get("flat", 1e-3))) * 100)
        r = 1 / np.maximum(kmax, 1e-12)
        return {"mesh": o.Label, "points": int(len(c)), "flatPercent": round(flat, 2),
                "tightestRadius": round(float(np.min(r)), 4), "medianRadius": round(float(np.median(r[kmax > 1e-6])) if (kmax > 1e-6).any() else math.inf, 3),
                "meanCurvature": {"min": round(float(mean.min()), 5), "max": round(float(mean.max()), 5)},
                "next": "view_render { map: \"curvature\", objects: [the mesh] } colours it."}

    def meshobj_project(a):
        import MeshPart

        o = mesh_of(a.get("mesh"))
        src = next((x for x in doc().Objects if a.get("shape") in (x.Label, x.Name) and hasattr(x, "Shape")), None)
        if src is None or not src.Shape.Edges:
            raise bad("shape: a wire, sketch or body with edges to project, by label.")
        d = vec(a.get("direction"), "direction", (0, 0, -1))
        if d.Length < 1e-9:
            raise bad("direction: not [0, 0, 0] — the way the edges are thrown onto the mesh (default down, [0, 0, -1]).")
        try:
            polys = MeshPart.projectShapeOnMesh(src.Shape, o.Mesh, d)
        except Exception as e:
            raise ToolError("failed", f"The projection failed: {e}")
        # FreeCAD's polyline repeats the points where its stretches join, and
        # runs out and back along a triangle's chord where a sample lands on a mesh edge.
        clean = [meshdist.no_spurs([(q.x, q.y, q.z) for q in map(V, pl)]) for pl in polys]
        wires = [Part.makePolygon([V(*q) for q in pl]) for pl in clean if len(pl) >= 2]
        if not wires:
            raise ToolError("failed", f"Nothing of {src.Label} landed on {o.Label} along {geo.vec(d)}: the shape must lie over the mesh seen along direction (turn direction round if it is on the other side).")
        c = doc().addObject("Part::Feature", "Projection")
        c.Label = s.unique(a.get("name") or f"{src.Label} on {o.Label}")
        c.Shape = Part.Compound(wires)
        return picks.finish(s, "meshobj_project", lambda: {"projection": c.Label, "wires": len(wires), "length": round(sum(w.Length for w in wires), 3)})

    def meshobj_export(a):
        o = mesh_of(a.get("mesh"))
        want = a.get("path") or f"{o.Label}.stl"
        ext = os.path.splitext(str(want))[1].lower().lstrip(".")
        if ext not in WRITES:
            raise bad(f"path: its extension picks the format — one of {', '.join(WRITES)} (stl is binary, ast its text form). Not .{ext or '(none)'}.")
        if o.Mesh.CountFacets == 0:
            raise ToolError("invalid_state", f"{o.Label} has no triangles to write.")
        p = paths.out_file(s, "meshobj_export", want)
        try:
            o.Mesh.write(p)
        except Exception as e:
            raise ToolError("failed", f"Not written: {e} — formats by extension: {', '.join(WRITES)}.")
        if not os.path.isfile(p):
            raise ToolError("failed", f"FreeCAD wrote no file at {p} (.{ext}): try stl, obj, ply or 3mf.")
        return {"mesh": o.Label, "file": p, "format": ext, "bytes": os.path.getsize(p), "facets": o.Mesh.CountFacets,
                "note": "Written where the mesh stands (its placement applied), in mm. import_file reads it back."}

    mref = {"type": "string", "description": "The mesh's label; may be left out when there is one."}
    cp = {"copy": {"type": "boolean"}, "name": {"type": "string"}}
    def unroll_exact(face, ref, label, a):
        """A cylinder's or cone's side (and a flat face) rolled out exactly: no stretch."""
        import math

        from .. import flat2d

        srf = face.Surface
        kind = type(srf).__name__

        def flat(p):
            u, v = srf.parameter(p)
            if kind == "Cylinder":
                return (srf.Radius * u, v)
            if kind == "Cone":
                sa = math.sin(srf.SemiAngle)
                rho = (srf.Radius + v * sa) / abs(sa)
                th = u * abs(sa)
                return (rho * math.cos(th), rho * math.sin(th))
            return (u, v)

        u0, u1, v0, v1 = face.ParameterRange
        if kind == "Plane":
            items = [{"kind": "line", "points": [list(flat(p)) for p in w.discretize(Deflection=float(a.get("tolerance", 0.05)))], "closed": True, "layer": "cut"}
                     for w in face.Wires]
        elif kind == "Cylinder":
            # the side rolled out: its turn's length by its height
            w_, h_ = srf.Radius * (u1 - u0), v1 - v0
            items = [{"kind": "line", "points": [[0, 0], [w_, 0], [w_, h_], [0, h_]], "closed": True, "layer": "cut"}]
        else:
            # a cone's side (a frustum): two arcs between two straight edges
            sa = math.sin(srf.SemiAngle)
            r0, r1 = sorted([(srf.Radius + v0 * sa) / abs(sa), (srf.Radius + v1 * sa) / abs(sa)])
            span = (u1 - u0) * abs(sa)
            n = max(16, int(math.degrees(span) / 3))
            outer = [(r1 * math.cos(span * i / n), r1 * math.sin(span * i / n)) for i in range(n + 1)]
            inner = [(r0 * math.cos(span * (n - i) / n), r0 * math.sin(span * (n - i) / n)) for i in range(n + 1)]
            items = [{"kind": "line", "points": [list(q) for q in outer + inner], "closed": True, "layer": "cut"}]
        x0, y0, x1, y1 = flat2d.bounds(items)
        poly = items[0]["points"]
        fa = abs(sum(x0_ * y1_ - x1_ * y0_ for (x0_, y0_), (x1_, y1_) in zip(poly, poly[1:] + poly[:1]))) / 2
        out = {"of": ref, "surface": kind.lower(), "exact": True, "area3d": round(face.Area, 3), "areaFlat": round(fa, 3),
               "stretch": {"mean": 0.0, "max": round(abs(fa / face.Area - 1) * 100, 3), "unit": "%"}, "outlines": len(items),
               "size": [round(x1 - x0, 3), round(y1 - y0, 3)]}
        if kind == "Cone":
            out["radii"] = [round(r0, 3), round(r1, 3)]
            out["angle"] = round(math.degrees(span), 3)
        if a.get("path"):
            pth = paths.made(s, a["path"] if os.path.isabs(a["path"]) else os.path.join(s.out_dir, a["path"]))
            os.makedirs(os.path.dirname(pth), exist_ok=True)
            if pth.lower().endswith(".dxf"):
                out["writer"] = flat2d.write_dxf(items, pth)[1]
            else:
                with open(pth, "w", encoding="utf-8") as f:
                    f.write(flat2d.svg(items))
            out["path"] = pth
        if a.get("make", True):
            o = doc().addObject("Part::Feature", "Pattern")
            o.Label = s.unique(a.get("name") or f"{label} flat")
            o.Shape = Part.makeCompound([Part.makePolygon([FreeCAD.Vector(x, y, 0) for x, y in it["points"]] + [FreeCAD.Vector(*it["points"][0], 0)]) for it in items])
            doc().recompute()
            s.snapshot("meshobj_unwrap")
            out["pattern"] = o.Label
        return out

    def unwrap_apart(P, F, iters, weight):
        import subprocess
        import sys
        import tempfile

        d = tempfile.mkdtemp(prefix="agentlink-unwrap-")
        src, dst = os.path.join(d, "in.npz"), os.path.join(d, "out.npz")
        np.savez(src, P=P, F=F)
        code = (
            "import sys, numpy as np\n"
            "import FreeCAD, Part, Mesh  # flatmesh stands on them: loaded first\n"
            "import flatmesh\n"
            "z = np.load(sys.argv[1])\n"
            "fl = flatmesh.FaceUnwrapper(np.ascontiguousarray(z['P'], dtype=np.float64), np.ascontiguousarray(z['F'], dtype=np.int64))\n"
            f"fl.findFlatNodes({iters}, {weight})\n"
            "b = fl.getFlatBoundaryNodes()\n"
            "np.savez(sys.argv[2], Q=np.asarray(fl.ze_nodes, float), n=np.array([len(x) for x in b]), B=np.concatenate([np.asarray(x, float) for x in b]) if b else np.zeros((0, 3)))\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([x for x in sys.path if x])
        exe = sys.executable if sys.executable and "python" in os.path.basename(sys.executable).lower() else None
        if exe is None:
            # FreeCAD's window is its own program, not a Python: the one shipped
            # with it (beside it, or in the Mac bundle's Resources/bin) runs it.
            from .. import testrun
            from .app import _bundle_python

            exe = testrun.real_python(sys.executable) or _bundle_python()
        if exe is None:
            raise ToolError("unavailable", "No Python to run the unwrapping in apart from FreeCAD here (none beside FreeCAD's program or in its bundle): unwrap a cylinder, cone or flat face (\"Body.Face3\") instead — those are laid flat exactly, without it.")
        try:
            r = subprocess.run([exe, "-c", code, src, dst], env=env, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise ToolError("failed", "The unwrapping ran over 5 minutes: a coarser tolerance, or a smaller surface.") from None
        if r.returncode != 0 or not os.path.isfile(dst):
            why = (r.stderr or "").strip().splitlines()[-1:] or [f"it stopped (code {r.returncode})"]
            raise ToolError("failed", f"FreeCAD's unwrapping could not lay this surface flat: {why[0]} — split it into simpler faces (a cone or cylinder side unwraps; a whole sphere does not).")
        z = np.load(dst)
        Q = np.asarray(z["Q"], float)[:, :2]
        n, B = list(z["n"]), np.asarray(z["B"], float)
        bounds, k = [], 0
        for c in n:
            bounds.append(B[k:k + int(c), :2])
            k += int(c)
        return Q, bounds

    def meshobj_unwrap(a):
        """A curved surface laid flat (MeshPart's unwrap): its outline as a flat
        pattern to cut from sheet, with how much it had to stretch."""
        import importlib.util

        if importlib.util.find_spec("flatmesh") is None:
            raise ToolError("unavailable", "This FreeCAD has no flatmesh (MeshPart's unwrapping): it was built without it.")
        from .. import flat2d
        from . import picks as _p

        ref = a.get("of")
        if not isinstance(ref, str):
            raise bad("of: a mesh's name, or a body's face \"Body.Face3\".")
        # A mesh by its name first: resolving it as a shape refuses an object with no Shape.
        mo = next((x for x in meshes(doc()) if ref in (x.Label, x.Name)), None)
        if mo is not None:
            label, sub, el = mo.Label, None, None
        else:
            label, sub, el = _p.resolve(s, ref)
            if not (sub and sub.startswith("Face")):
                raise bad(f"of: {ref} is a whole body — name one of its faces (\"{label}.Face3\"; shape_query lists them), or a mesh.")
        if el is not None and type(el.Surface).__name__ in ("Cylinder", "Cone", "Plane"):
            return unroll_exact(el, ref, label, a)
        if el is not None:
            vs, ts = el.tessellate(float(a.get("tolerance", 0.1)))
            P = np.array([(v.x, v.y, v.z) for v in vs], float)
            F = np.array(ts, int)
        else:
            m = mesh_of(label).Mesh
            if m.isSolid():
                raise ToolError("invalid_state", f"{label} is a closed mesh, which cannot be laid flat in one piece: meshobj_trim or meshobj_segments {{ keep: true }} gives an open patch of it to unwrap.")
            if m.countComponents() != 1:
                raise ToolError("invalid_state", f"{label} is {m.countComponents()} separate pieces: meshobj_split, then unwrap one.")
            if m.CountFacets > 50000:
                raise ToolError("invalid_state", f"{label} has {m.CountFacets} triangles: the unwrapping is given up to 50,000 (it runs apart from FreeCAD with a 5 minute limit) — meshobj_decimate {{ copy: true }} first.")
            P, F = arrays(m)
        if len(F) < 2:
            raise bad("of: a surface with area.")
        # flatmesh can bring FreeCAD down on a surface it cannot handle:
        # it runs in a Python of its own, and a crash there is only a refusal
        Q, bounds = unwrap_apart(P, F, int(a.get("iterations", 5)), float(a.get("weight", 0.95)))
        def area(X, T):
            A, B, C = X[T[:, 0]], X[T[:, 1]], X[T[:, 2]]
            if X.shape[1] == 2:
                return 0.5 * np.abs((B[:, 0] - A[:, 0]) * (C[:, 1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (C[:, 0] - A[:, 0]))
            return 0.5 * np.linalg.norm(np.cross(B - A, C - A), axis=1)
        a3, a2 = area(P, F), area(Q, F)
        stretch = np.where(a3 > 1e-12, a2 / np.maximum(a3, 1e-12) - 1, 0.0)
        items = [{"kind": "line", "points": b.tolist(), "closed": True, "layer": "cut"} for b in bounds if len(b) >= 3]
        out = {"of": ref, "area3d": round(float(a3.sum()), 3), "areaFlat": round(float(a2.sum()), 3),
               "stretch": {"mean": round(float(np.abs(stretch).mean()) * 100, 3), "max": round(float(np.abs(stretch).max()) * 100, 3), "unit": "%"},
               "outlines": len(items)}
        x0, y0, x1, y1 = flat2d.bounds(items)
        out["size"] = [round(x1 - x0, 3), round(y1 - y0, 3)]
        if a.get("path"):
            pth = paths.made(s, a["path"] if os.path.isabs(a["path"]) else os.path.join(s.out_dir, a["path"]))
            os.makedirs(os.path.dirname(pth), exist_ok=True)
            if pth.lower().endswith(".dxf"):
                out["writer"] = flat2d.write_dxf(items, pth)[1]
            else:
                with open(pth, "w", encoding="utf-8") as f:
                    f.write(flat2d.svg(items))
            out["path"] = pth
        if a.get("make", True):
            o = doc().addObject("Part::Feature", "Pattern")
            o.Label = s.unique(a.get("name") or f"{label} flat")
            o.Shape = Part.makeCompound([Part.makePolygon([FreeCAD.Vector(x, y, 0) for x, y in b.tolist()] + [FreeCAD.Vector(*b[0].tolist(), 0)]) for b in bounds if len(b) >= 3])
            doc().recompute()
            s.snapshot("meshobj_unwrap")
            out["pattern"] = o.Label
        if out["stretch"]["max"] > 5:
            out["note"] = "Doubly curved: it cannot lie flat without stretching — the most stretched spots are where a cut or dart would help."
        return out

    def meshobj_primitive(a):
        kind = a.get("kind", "box")
        at = vec(a.get("at"), "at", (0, 0, 0))
        n = a.get("segments", 48)
        if isinstance(n, bool) or not isinstance(n, int) or not 3 <= n <= 720:
            raise bad("segments: how many steps round, 3 … 720 (48).")

        def over0(key, default, what):
            v = picks.num(a.get(key, default), key)
            if v <= 0:
                raise bad(f"{key}: {what}, mm, over 0.")
            return v

        try:
            if kind == "box":
                size = a.get("size", [10, 10, 10])
                if not (isinstance(size, list) and len(size) == 3 and all(isinstance(c, (int, float)) and not isinstance(c, bool) and c > 0 for c in size)):
                    raise bad("size: [x, y, z] mm, each over 0.")
                x, y, z = [float(c) for c in size]
                m = Mesh.createBox(x, y, z)
                m.translate(x / 2, y / 2, z / 2)  # a corner at at, as part_primitive
            elif kind == "sphere":
                m = Mesh.createSphere(over0("radius", 5, "the radius"), n)
            elif kind in ("cylinder", "cone"):
                r1, h = over0("radius", 5, "the radius at the base"), over0("height", 10, "the height")
                r2 = r1 if kind == "cylinder" else picks.num(a.get("radius2", 0), "radius2")
                if r2 < 0:
                    raise bad("radius2: the radius at the top, 0 (a point) or more.")
                # Rings 0.5 mm apart on a small one, as before; on a large one
                # no more than 40 along its longest size (a 1 m cylinder at
                # 0.5 mm was some 380,000 triangles, built one by one in Python).
                edge = max(0.5, max(h, r1, r2) / 40.0)
                m = Mesh.createCylinder(r1, h, 1, edge, n) if kind == "cylinder" else Mesh.createCone(r1, r2, h, 1, edge, n)
                m.rotate(0, -math.pi / 2, 0)  # FreeCAD builds it along x: up z
            elif kind == "torus":
                r1, r2 = over0("radius", 10, "the ring's radius"), over0("radius2", 2, "the tube's radius")
                if r2 >= r1:
                    raise bad("radius2: the tube's radius, under radius (the ring's).")
                m = Mesh.createTorus(r1, r2, n)
                if m.BoundBox.ZLength > m.BoundBox.XLength + 1e-6 or m.BoundBox.XLength < m.BoundBox.YLength - 1e-6:
                    m.rotate(0, math.pi / 2, 0)  # its axis up z
                # FreeCAD's builder (BuildRegularGeoms.Toroid) stands the ring
                # off the origin by its radius along its axis: centred here.
                c = m.BoundBox.Center
                m.translate(-c.x, -c.y, -c.z)
            else:
                raise bad("kind: box | sphere | cylinder | cone | torus.")
        except ToolError:
            raise
        except Exception as e:
            raise bad(f"{kind}: {e}")
        m.translate(at.x, at.y, at.z)
        o = new_mesh(m, a.get("name") or f"Mesh {kind}")
        return picks.finish(s, "meshobj_primitive", lambda: {"mesh": o.Label, "kind": kind, **reading(m)})

    def meshobj_merge(a):
        refs = a.get("meshes")
        if not isinstance(refs, list) or len(refs) < 2:
            raise bad("meshes: two or more to put into one (not fused: meshobj_boolean union for that).")
        objs = [mesh_of(r) for r in refs]
        if len({o.Name for o in objs}) < len(objs):
            raise bad("meshes: each one once.")
        # addMesh joins the stored points and passes placements by: each mesh is brought to where it stands first
        m = in_place(objs[0].Mesh)
        for o in objs[1:]:
            m.addMesh(in_place(o.Mesh))
        n = new_mesh(m, a.get("name") or "Merged mesh")
        if a.get("remove"):
            for o in objs:
                doc().removeObject(o.Name)
        return picks.finish(s, "meshobj_merge", lambda: {"mesh": n.Label, **reading(m)})

    def meshobj_boundary(a):
        o = mesh_of(a.get("mesh"))
        pts, facets = o.Mesh.Topology
        # edges one triangle has, counted in numpy (a dict of every edge took seconds on a dense scan)
        F = np.array(facets, dtype=np.int64).reshape(-1, 3)
        if len(F) == 0:
            raise ToolError("invalid_state", f"{o.Label} has no triangles.")
        e0, e1 = F.reshape(-1), F[:, [1, 2, 0]].reshape(-1)
        lo_, hi_ = np.minimum(e0, e1), np.maximum(e0, e1)
        nn = int(F.max()) + 1
        keys, cnt = np.unique(lo_ * nn + hi_, return_counts=True)
        open_edges = [(int(k // nn), int(k % nn)) for k in keys[cnt == 1]]
        if not open_edges:
            return {"mesh": o.Label, "loops": 0, "note": "No open edges: the mesh is closed."}
        nbr = {}
        for p0, p1 in open_edges:
            nbr.setdefault(p0, []).append(p1)
            nbr.setdefault(p1, []).append(p0)
        seen = set()
        loops = []
        for p0, p1 in open_edges:
            if (p0, p1) in seen:
                continue
            chain = [p0, p1]
            seen.add((p0, p1))
            while True:
                last, prev = chain[-1], chain[-2]
                nxt = next((q for q in nbr[last] if q != prev and (min(last, q), max(last, q)) not in seen), None)
                if nxt is None:
                    break
                seen.add((min(last, nxt), max(last, nxt)))
                chain.append(nxt)
                if nxt == chain[0]:
                    break
            loops.append(chain)
        wires, info = [], []
        for c in loops:
            P = [V(pts[i]) for i in c]
            w = Part.makePolygon(P)
            wires.append(w)
            closed = c[0] == c[-1]
            item = {"edges": len(c) - 1, "length": round(w.Length, 3), "closed": closed, "centre": [round(x, 3) for x in w.BoundBox.Center]}
            if closed:
                try:
                    item["area"] = round(Part.Face(w).Area, 3)
                except Exception:
                    pass
            info.append(item)
        order = sorted(range(len(info)), key=lambda i: -info[i]["length"])
        info = [info[i] for i in order]
        out = {"mesh": o.Label, "loops": len(loops), "openEdges": len(open_edges), "boundaries": info[:20]}
        if a.get("keep", True):
            b = doc().addObject("Part::Feature", "Boundary")
            b.Shape = Part.makeCompound(wires)
            b.Label = s.unique(a.get("name") or f"{o.Label} boundary")
            doc().recompute()
            s.snapshot("meshobj_boundary")
            out["wires"] = b.Label
        return out

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": doc, "mesh_of": mesh_of, "keep": keep}
    return runners.tools(GROUP, s, helpers) + [
        Tool("meshobj_unwrap", "Lay a surface flat as a cutting pattern (sheet, fabric, leather): of a body's face \"Body.Face3\" or an open mesh in one piece. A plane, cylinder or cone face rolls out exactly; other faces and meshes go through FreeCAD's flatmesh (up to 50,000 triangles, run apart with a 5 minute limit; a closed mesh is refused). Reply: area3d, areaFlat, stretch { mean, max % }, outlines, size, pattern (the wire object; make: false keeps none); path .svg or .dxf writes it. tolerance mm tessellates a face (0.1).",
             obj({"of": {"type": "string"}, "path": {"type": "string"}, "make": {"type": "boolean"}, "tolerance": {"type": "number"}, "iterations": {"type": "integer"}, "weight": {"type": "number"}, "name": {"type": "string"}}, ["of"]), meshobj_unwrap, changes=True),
        Tool("meshobj_from_shape", "Mesh a body (MeshPart) into a new mesh object: method standard (deflection mm off the surface, 0.05; angle deg, 15) | mefisto (maxLength mm: even triangles, but it can leave faces with small holes open: the reply warns) | netgen (fineness verycoarse … veryfine; unavailable where FreeCAD lacks it). A flat-sided body meshes to two triangles a face (a box: 12); a small deflection on a large curved body makes hundreds of thousands (reply: heavy). Reply: mesh, points, facets, solid, components, area, volume, box.",
             obj({"body": {"type": "string"}, "method": {"type": "string"}, "deflection": {"type": "number"}, "angle": {"type": "number"}, "maxLength": {"type": "number"}, "fineness": {"type": "string"}, "name": {"type": "string"}}), meshobj_from_shape, changes=True),
        Tool("meshobj_info", "A mesh's size and the Mesh workbench's evaluation: points, facets, solid (closed), components, area, volume, box; evaluation { nonManifolds, selfIntersections, flippedNormals, corruptedFacets, … }, problems, verdict clean or next. Changes nothing. The self-intersection test is slow on a dense mesh (not measured): background: true runs it as a job.", obj({"mesh": mref}), meshobj_info),
        Tool("meshobj_repair", "Repair a mesh as Evaluate & Repair does: fix any of normals, duplicates, nonmanifolds, selfintersections, degenerate, folds, indices, pointsonedges (default: those), holes (loops up to maxHoleEdges, 50, filled flat), islands (pieces of minFacets, 10, or fewer triangles dropped). Each step is kept only if it leaves no more open or overloaded edges (undone says which). Reply: did, fixed, problems (left), edges { open, overloaded }, before. In place; copy: true leaves the original. Evaluates twice: slow on a dense mesh, and a change cannot run as a job.",
             obj({"mesh": mref, "fix": {"type": "array", "items": {"type": "string"}}, "tolerance": {"type": "number"}, "maxHoleEdges": {"type": "integer"}, "minFacets": {"type": "integer"}, **cp}), meshobj_repair, changes=True),
        Tool("meshobj_decimate", "Fewer triangles: reduction (share to remove, 0.5) or facets (how many to keep); tolerance (0.1) caps the error one collapse may add, so it can stop short of the count (the reply's note says so: raise tolerance). Reply: reduced \"n → m triangles\", the mesh's reading, before.",
             obj({"mesh": mref, "reduction": {"type": "number"}, "facets": {"type": "integer"}, "tolerance": {"type": "number"}, **cp}), meshobj_decimate, changes=True),
        Tool("meshobj_refine", "More triangles: rounds 1 … 3, each putting a point in the middle of every triangle (about three times as many; refused past 2,000,000); optimize: true swaps edges to even their shapes. The surface does not change. Reply: refined \"n → m triangles\".", obj({"mesh": mref, "rounds": {"type": "integer"}, "optimize": {"type": "boolean"}, **cp}), meshobj_refine, changes=True),
        Tool("meshobj_smooth", "Smooth a mesh: method taubin (default; shrinks far less than laplace, but a coarse mesh still loses volume; lambda 0.6307, mu 0.0424) | laplace (lambda; shrinks), iterations (3). Reply: volumeChange mm³ on a closed mesh, warning past 2%.",
             obj({"mesh": mref, "method": {"type": "string"}, "iterations": {"type": "integer"}, "lambda": {"type": "number"}, "mu": {"type": "number"}, **cp}), meshobj_smooth, changes=True),
        Tool("meshobj_edit", "Edit a mesh on a copy, as ScanRuler's Mesh Tools do: action begin { mesh } (a copy made, the original hidden; every meshobj tool given the original's name then changes the copy) | use (the copy put in place of the original) | discard (the copy dropped) | state (default: what is being edited).",
             obj({"action": {"type": "string", "enum": ["begin", "use", "discard", "state"]}, "mesh": mref}), meshobj_edit, changes=True),
        Tool("meshobj_trim", "Cut a mesh with a plane: at [x,y,z] on it, normal (the side it points to is removed); close: true caps the cut flat (loops up to maxHoleEdges, 1000); preview: true answers wouldRemove / wouldCut / wouldKeep and changes nothing. Refused when nothing would be left. Reply: removed (triangles wholly on that side), cut (triangles the plane crossed, each kept in part), solid, warning when the cap did not close it.",
             obj({"mesh": mref, "at": {"type": "array", "items": {}}, "normal": {"type": "array", "items": {}}, "close": {"type": "boolean"}, "maxHoleEdges": {"type": "integer"}, "preview": {"type": "boolean"}, **cp}), meshobj_trim, changes=True),
        Tool("meshobj_transform", "Scale (a factor or [x,y,z]), rotate { axis, angle degrees }, move [x,y,z], mirror \"x\" | \"y\" | \"z\" a mesh's points, in that order, about the document's origin and axes. A mirror keeps the triangles facing out. In place; copy: true makes a new mesh.",
             obj({"mesh": mref, "scale": {"type": ["number", "array"]}, "rotate": {"type": "object"}, "move": {"type": "array", "items": {}}, "mirror": {"type": "string"}, **cp}), meshobj_transform, changes=True),
        Tool("meshobj_boolean", "A boolean of two closed meshes (meshobj_info: solid true): a, b, op union | intersection | difference (a minus b); a new mesh, a and b kept. Dense scans as they are: only the triangles the other mesh crosses are cut (built for scans of 100,000 triangles and more; time not measured, and a change cannot run as a job). Reply: how (which engine made it), solid, volume.",
             obj({"a": {"type": "string"}, "b": {"type": "string"}, "op": {"type": "string"}, "name": {"type": "string"}}, ["a", "b"]), meshobj_boolean, changes=True),
        Tool("meshobj_sections", "Cross-sections of a mesh as wires: normal (default z), count evenly spaced (5) or at [distances from the origin along normal], up to 500; tolerance mm joins cut ends (0.01). Reply: slices [{ at, loops, length }], sections (the wire compound; export writes DXF, part_face makes a face).",
             obj({"mesh": mref, "normal": {"type": "array", "items": {}}, "count": {"type": "integer"}, "at": {"type": "array", "items": {}}, "tolerance": {"type": "number"}, "name": {"type": "string"}}), meshobj_sections, changes=True),
        Tool("meshobj_split", "Split a mesh into its separate pieces, a mesh object each, largest first (minFacets leaves out smaller ones; over 100 pieces is refused: raise minFacets). The original is hidden, not removed. Reply: pieces, facets.", obj({"mesh": mref, "minFacets": {"type": "integer"}}), meshobj_split, changes=True),
        Tool("meshobj_segments", "Find a mesh's flat regions: kind planar (deviation mm off a fitted plane, 0.01; about the noise on a scan) | curvature (both curvatures within tolerance 1/mm of 0); minFacets (20). Reply: segments (count), largest [{ facets, area, center, normal }] up to top (12); keep: true makes those meshes. On a scan: where to put a sketch. Slow on a dense mesh (every region is walked; not measured).",
             obj({"mesh": mref, "kind": {"type": "string"}, "deviation": {"type": "number"}, "tolerance": {"type": "number"}, "minFacets": {"type": "integer"}, "top": {"type": "integer"}, "keep": {"type": "boolean"}}), meshobj_segments, changes=True),
        Tool("meshobj_curvature", "A mesh's curvature: flatPercent (points under flat, 0.001 1/mm), tightestRadius and medianRadius mm, meanCurvature { min, max }. view_render { map: \"curvature\" } colours it. Changes nothing; on a dense mesh background: true runs it as a job.",
             obj({"mesh": mref, "flat": {"type": "number"}}), meshobj_curvature),
        Tool("meshobj_project", "Project a wire, sketch or body's edges onto a mesh along direction [x,y,z] (default down, [0,0,-1]); kept as wires on its surface. Reply: projection, wires, length.",
             obj({"mesh": mref, "shape": {"type": "string"}, "direction": {"type": "array", "items": {}}, "name": {"type": "string"}}, ["shape"]), meshobj_project, changes=True),
        Tool("meshobj_primitive", "A mesh primitive (the Mesh workbench's regular solids): kind box (size [x,y,z], a corner at at) | sphere (radius, centred) | cylinder | cone (radius at the base, radius2 at the top, height; base centre at at, up +z) | torus (radius, radius2 the tube; centred, axis z); segments round (48). Reply: mesh, facets, solid, volume, box.",
             obj({"kind": {"type": "string", "enum": ["box", "sphere", "cylinder", "cone", "torus"]}, "size": {"type": "array", "items": {}}, "radius": {"type": "number"}, "radius2": {"type": "number"},
                  "height": {"type": "number"}, "at": {"type": "array", "items": {}}, "segments": {"type": "integer"}, "name": {"type": "string"}}), meshobj_primitive, changes=True),
        Tool("meshobj_merge", "Put meshes into one mesh object where they stand (not fused: components stay apart; meshobj_boolean union fuses): meshes [names]; remove: true drops the originals. Reply: components, facets.",
             obj({"meshes": {"type": "array", "items": {"type": "string"}}, "remove": {"type": "boolean"}, "name": {"type": "string"}}, ["meshes"]), meshobj_merge, changes=True),
        Tool("meshobj_boundary", "A mesh's open edges as wires (Reverse Engineering's mesh boundary): loops, openEdges, boundaries [{ edges, length, closed, centre, area }] longest first (20); keep (default) makes them a wire compound to fill, sweep or fit. A closed mesh answers loops 0.",
             obj({"mesh": mref, "keep": {"type": "boolean"}, "name": {"type": "string"}}), meshobj_boundary, changes=True),
        Tool("meshobj_export", "Write a document mesh to a file, the format by path's extension: stl (binary), ast, obj, ply, off, 3mf, amf, smf, wrl, x3d, iv, nas … (default <label>.stl in the out folder), where it stands, in mm. Reply: file, format, bytes, facets. Changes nothing; background: true runs a big one as a job.",
             obj({"mesh": mref, "path": {"type": "string"}}), meshobj_export),
    ]
