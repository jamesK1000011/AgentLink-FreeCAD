# SPDX-License-Identifier: LGPL-2.1-or-later
# Inspection: FreeCAD's own Inspection feature — an actual (a mesh, points,
# or a body meshed for the purpose, or a scan read from a file) measured
# against nominals (bodies, meshes, points) point by point, signed where
# the nominal is a solid — run, read back as numbers a person can act on
# (RMS, spread, how much is in tolerance, where the worst spots are),
# coloured, and written out. The feature stays in the document, so the
# person sees the same colours in FreeCAD's Inspection workbench.

import csv
import json
import math
import os

import Inspection  # noqa: F401 — the family stands on the module; left out without it
import Mesh

import numpy as np

from .. import render
from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks
from .picks import r4

GROUP = "inspection"
INFO = "FreeCAD's Inspection: an actual (mesh, points, body or scan file) against nominals, point by point, with tolerance, statistics, worst spots, a colour map and a report."

TOL_PROP = ("ToleranceLow", "ToleranceHigh")
BIG = 1e30  # Inspection marks a point out of reach with ±FLT_MAX


def kind_of(o):
    if o.isDerivedFrom("Mesh::Feature"):
        return "mesh"
    if o.isDerivedFrom("Points::Feature"):
        return "points"
    if o.isDerivedFrom("Part::Feature"):
        return "shape"
    return None


def points_of(o):
    """The actual's points in the order Inspection measures them."""
    k = kind_of(o)
    if k == "mesh":
        return np.array([[p.x, p.y, p.z] for p in o.Mesh.Points], dtype=float)
    if k == "points":
        return np.array([[p.x, p.y, p.z] for p in o.Points.Points], dtype=float)
    return None


def stats(d, lo=None, hi=None, bins=10):
    """Numbers from Inspection's distances (a numpy array)."""
    d = np.asarray(d, dtype=float)
    reach = np.abs(d) < BIG
    m = d[reach]
    out = {"points": int(d.size), "measured": int(m.size), "outOfReach": int(d.size - m.size)}
    if d.size:
        out["outOfReachPercent"] = r4(100.0 * (d.size - m.size) / d.size)
    if not m.size:
        return out
    out.update({"min": r4(m.min()), "max": r4(m.max()), "mean": r4(m.mean()), "rms": r4(math.sqrt(float(np.mean(m * m)))),
                "stdDev": r4(m.std()), "p95abs": r4(np.percentile(np.abs(m), 95))})
    if lo is not None and hi is not None:
        inside = (m >= lo) & (m <= hi)
        out["tolerance"] = [r4(lo), r4(hi)]
        out["inTolerancePercent"] = r4(100.0 * inside.sum() / m.size)
        out["over"] = int((m > hi).sum())
        out["under"] = int((m < lo).sum())
        out["verdict"] = "pass" if inside.all() and not out["outOfReach"] else "fail" if not inside.all() else "unknown"
    edges = np.linspace(m.min(), m.max(), bins + 1) if m.max() > m.min() else np.array([m.min() - 1e-6, m.max() + 1e-6])
    counts, edges = np.histogram(m, edges)
    out["histogram"] = [{"from": r4(edges[i]), "to": r4(edges[i + 1]), "count": int(c)} for i, c in enumerate(counts)]
    return out


def worst(P, d, n=5, lo=None, hi=None, spacing=None):
    """The worst spots: the largest |distance| (or furthest outside the
    band), spread so the same bump is not named five times."""
    d = np.asarray(d, dtype=float)
    ok = np.abs(d) < BIG
    if P is None or not ok.any():
        return []
    idx = np.where(ok)[0]
    if lo is not None and hi is not None:
        score = np.maximum(d[idx] - hi, lo - d[idx])
    else:
        score = np.abs(d[idx])
    order = idx[np.argsort(-score)]
    span = float(np.linalg.norm(P.max(0) - P.min(0))) if len(P) else 1.0
    gap = spacing if spacing else max(span * 0.05, 1e-6)
    out = []
    for i in order:
        p = P[i]
        if any(np.linalg.norm(p - np.array(o["at"])) < gap for o in out):
            continue
        out.append({"at": [r4(p[0]), r4(p[1]), r4(p[2])], "distance": r4(d[i])})
        if len(out) >= n:
            break
    return out


def inspections(doc):
    return [o for o in doc.Objects if o.TypeId == "Inspection::Feature"]


def tol_props(o):
    """The tolerance band's two properties, added when the inspection has
    none (one made in FreeCAD's own Inspection workbench)."""
    for p in TOL_PROP:
        if p not in o.PropertiesList:
            o.addProperty("App::PropertyFloat", p, "Tolerance", "The band a distance must fall in, mm (set by Agent Link)")


def band(o):
    if all(p in o.PropertiesList for p in TOL_PROP):
        lo, hi = float(o.ToleranceLow), float(o.ToleranceHigh)
        if hi > lo:
            return lo, hi
    return None, None


def _map(s, a):
    """view_render's "inspection" map: the actual coloured by its distances."""
    doc = s.doc
    ins = inspections(doc)
    ref = a.get("inspection") or (a.get("objects") or [None])[0]
    o = next((x for x in ins if ref in (x.Label, x.Name)), None) if ref else (ins[-1] if ins else None)
    if o is None:
        raise ToolError("not_found", "No inspection to show: insp_run first" + (f" ({ref!r} is not one)" if ref else "") + ".")
    d = np.asarray(o.Distances, dtype=float)
    vals = np.where(np.abs(d) < BIG, d, np.nan)
    act = o.Actual
    lo, hi = band(o)
    r = float(o.SearchRadius)
    rng = [lo, hi] if lo is not None else [-r, r]
    if kind_of(act) == "mesh":
        m = act.Mesh
        V = np.array([[p.x, p.y, p.z] for p in m.Points], dtype=float)
        F = np.array([list(f.PointIndices) for f in m.Facets], dtype=int)
        layer = {"name": act.Label, "V": V, "F": F, "values": vals, "creases": True}
    else:
        # points: shown on the first nominal's surface, each spot the nearest point's value
        nom = (o.Nominals or [None])[0]
        if nom is None or not hasattr(nom, "Shape") and kind_of(nom) != "mesh":
            raise ToolError("unavailable", "Points are coloured on a nominal body or mesh, and this inspection has none.")
        L = render.body_layer(nom, 0) if kind_of(nom) == "shape" else {"V": np.array([[p.x, p.y, p.z] for p in nom.Mesh.Points]), "F": np.array([list(f.PointIndices) for f in nom.Mesh.Facets])}
        V, F = L["V"], L["F"]
        P = points_of(act)
        good = np.isfinite(vals)
        layer = {"name": nom.Label, "V": V, "F": F, "values": render.nearest_values(V, P[good], vals[good]), "creases": True}
    return {"layers": [layer], "unit": "mm", "cmap": "jet", "symmetric": lo is None, "range": rng, "worst": "abs", "label": "DEVIATION",
            "note": f"{o.Label}: distance to the nominal at each point ({'tolerance' if lo is not None else '± the search radius'} spans the colours; grey is out of reach)."}


render.register_map("inspection", _map, "An Inspection feature's distances on its actual (insp_run): objects [the inspection], else the last.")


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def find(ref, what="object"):
        for o in doc().Objects:
            if ref in (o.Label, o.Name):
                return o
        for o in doc().Objects:
            if o.Label.lower() == str(ref).lower():
                return o
        raise ToolError("not_found", f"{what} {ref!r}: not here — session_state and object_list name what there is.")

    def ins_of(ref):
        all_ = inspections(doc())
        if ref is None:
            if len(all_) == 1:
                return all_[0]
            raise (ToolError("not_found", "No inspection: insp_run makes one.") if not all_ else bad(f"inspection: say which — {', '.join(o.Label for o in all_)}."))
        o = next((x for x in all_ if ref in (x.Label, x.Name)), None)
        if o is None:
            raise ToolError("not_found", f"inspection {ref!r}: there are {', '.join(x.Label for x in all_) or 'none'}.")
        return o

    def tol_of(a):
        t = a.get("tolerance")
        if t is None:
            return None, None
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            if t <= 0:
                raise bad("tolerance: a band [low, high] in mm, or ±t as a number over 0.")
            return -float(t), float(t)
        if isinstance(t, list) and len(t) == 2 and all(isinstance(x, (int, float)) for x in t) and t[0] < t[1]:
            return float(t[0]), float(t[1])
        raise bad("tolerance: ±t (a number) or [low, high] mm, low < high.")

    def mesh_of_body(o, deflection, spacing, cap):
        # Tessellated, then split until no edge is over spacing: a flat face
        # is measured across it, not only at its corners.
        L = render.body_layer(o, 0, tol=deflection)
        T, F = render.subdivide(L["V"], L["F"], spacing, cap=cap)
        m = Mesh.Mesh([[tuple(T[i]) for i in tri] for tri in F])
        f = doc().addObject("Mesh::Feature", "Inspected")
        f.Label = s.unique(f"{o.Label} as inspected")
        f.Mesh = m
        try:
            f.Visibility = False
        except Exception:
            pass
        return f

    def reading(o, n_worst=5):
        lo, hi = band(o)
        d = np.asarray(o.Distances, dtype=float)
        out = {"inspection": o.Label, "name": o.Name, "actual": o.Actual.Label if o.Actual else None, "nominals": [x.Label for x in o.Nominals],
               "searchRadius": r4(o.SearchRadius), "thickness": r4(o.Thickness), **stats(d, lo, hi)}
        P = points_of(o.Actual) if o.Actual is not None else None
        if P is not None and len(P) == len(d):
            out["worst"] = worst(P, d, n_worst, lo, hi)
        if out.get("outOfReachPercent", 0) > 5:
            out["note"] = (f"{out['outOfReachPercent']:g}% of the points are further than the search radius ({r4(o.SearchRadius)} mm) from every nominal: "
                           "a larger search_radius, or align the actual first (object_align, or an add-on's alignment).")
        return out

    def insp_run(a):
        if a.get("file"):
            p = paths.in_file(s, "insp_run", a["file"], "file")
            if not os.path.isfile(p):
                raise ToolError("not_found", f"{p}: no such file.")
            ext = os.path.splitext(p)[1].lower()
            if ext in (".stl", ".obj", ".ply", ".off", ".3mf", ".amf"):
                act = doc().addObject("Mesh::Feature", "Actual")
                act.Mesh = Mesh.Mesh(p)
            elif ext in (".asc", ".pcd", ".xyz", ".txt", ".e57"):
                import Points

                act = doc().addObject("Points::Feature", "Actual")
                act.Points = Points.Points(p) if hasattr(Points, "Points") else Points.read(p)
            else:
                raise bad(f"file: {ext or 'no extension'} is not read here — a mesh (stl, obj, ply, off, 3mf, amf) or points (asc, pcd, xyz, txt, e57). import_file brings other formats in; then actual names the object.")
            act.Label = s.unique(os.path.splitext(os.path.basename(p))[0])
        elif a.get("actual"):
            act = find(a["actual"], "actual")
        else:
            raise bad("actual: the measured thing (a mesh, points or a body), or file: a scan to read.")
        k = kind_of(act)
        if k is None:
            raise bad(f"actual: {act.Label} is a {act.TypeId} — the actual is a mesh, a point cloud or an object with a shape (object_list names them).")
        meshed = None
        if k == "shape":
            # A body is measured at the vertices of a mesh of it, kept in the
            # document (hidden): each distance then has its point.
            defl = float(a.get("deflection", 0.1))
            if not 0.001 <= defl <= 5:
                raise bad("deflection: how closely the body's mesh follows it, 0.001 … 5 mm.")
            diag = act.Shape.BoundBox.DiagonalLength
            spacing = float(a.get("spacing") or max(diag / 100.0, 0.2))
            if spacing <= 0:
                raise bad("spacing: mm between measured points on the body, over 0.")
            cap = int(a.get("cap", 60000))
            meshed = mesh_of_body(act, defl, spacing, max(1000, min(cap, 400000)))
            act_used = meshed
        else:
            act_used = act
        noms = [find(n, "nominal") for n in (a.get("nominals") or [])]
        if not noms:
            raise bad("nominals: what it should be — bodies, meshes or points (a list of names).")
        for n in noms:
            if kind_of(n) is None:
                raise bad(f"nominals: {n.Label} is a {n.TypeId} — each is a body (an object with a shape), a mesh or a point cloud.")
            if n is act:
                raise bad(f"nominals: {n.Label} is the actual itself — the nominal is what it should be (the design), the actual what was measured or made.")
        r = picks.num(a.get("search_radius", 1.0), "search_radius")
        if r <= 0:
            raise bad("search_radius: mm, over 0 — points further than this from every nominal are out of reach.")
        lo, hi = tol_of(a)
        if lo is not None and max(abs(lo), abs(hi)) > r:
            raise bad(f"tolerance reaches past search_radius ({r:g} mm): points out of tolerance would read as out of reach. Raise search_radius.")
        f = doc().addObject("Inspection::Feature", "Inspection")
        f.Label = s.unique(a.get("name") or f"Inspection of {act.Label}")
        f.Actual = act_used
        f.Nominals = noms
        f.SearchRadius = r
        if a.get("thickness") is not None:
            f.Thickness = picks.num(a["thickness"], "thickness")
        tol_props(f)
        if lo is not None:
            f.ToleranceLow, f.ToleranceHigh = lo, hi
        doc().recompute()
        if not len(f.Distances):
            raise ToolError("failed", f"Inspection measured no points: {act.Label} holds none" + (" (the file read as empty — is it a mesh FreeCAD reads?)" if a.get("file") else "") + " — nothing was kept.")
        s.snapshot("insp_run")
        out = reading(f, int(a.get("worst", 5)))
        if meshed is not None:
            out["measuredOn"] = f"{meshed.Label}: {len(meshed.Mesh.Points)} points about {spacing:.3g} mm apart (spacing), hidden"
            out["how"] = (f"{act.Label} was tessellated first (a mesh at deflection {defl:g} mm, split to spacing {spacing:.3g} mm, {len(meshed.Mesh.Points)} points) "
                          "and FreeCAD's Inspection read each point's distance to the nominals — the body's faces are not sampled directly. "
                          "Timed against the body's B-spline poles: a large free-form body is given a longer deadline (and a coarser deflection or larger spacing is quicker).")
        if a.get("thickness") is not None:
            out["thicknessNote"] = "Thickness is stored on the feature, but FreeCAD 1.1's Inspection does not use it when measuring: the distances are the same with or without it."
        out["next"] = "view_render { map: \"inspection\" } to see it; insp_faces says which faces are off; insp_export for a report."
        out["step"] = len(s.steps)
        return out

    def insp_update(a):
        o = ins_of(a.get("inspection"))
        if not any(k in a for k in ("search_radius", "thickness", "tolerance", "nominals")):
            raise bad("Nothing to change: search_radius, thickness, tolerance (±t, [low, high] or null to clear) or nominals — insp_read reads it as it is.")
        # Checked before anything is set, so a refusal changes nothing.
        r = float(o.SearchRadius)
        if a.get("search_radius") is not None:
            r = picks.num(a["search_radius"], "search_radius")
            if r <= 0:
                raise bad("search_radius: mm, over 0 — points further than this from every nominal are out of reach.")
        lo, hi = band(o)
        if a.get("tolerance") is not None:
            lo, hi = tol_of(a)
        elif "tolerance" in a:
            lo = hi = None
        if lo is not None and max(abs(lo), abs(hi)) > r:
            raise bad(f"tolerance reaches past search_radius ({r:g} mm): points out of tolerance would read as out of reach. Raise search_radius in the same call.")
        noms = None
        if a.get("nominals"):
            noms = [find(n, "nominal") for n in a["nominals"]]
            for n in noms:
                if kind_of(n) is None:
                    raise bad(f"nominals: {n.Label} is a {n.TypeId} — each is a body (an object with a shape), a mesh or a point cloud.")
                if n is o.Actual:
                    raise bad(f"nominals: {n.Label} is this inspection's actual.")
        if a.get("search_radius") is not None:
            o.SearchRadius = r
        if a.get("thickness") is not None:
            o.Thickness = picks.num(a["thickness"], "thickness")
        if "tolerance" in a:
            tol_props(o)
            o.ToleranceLow, o.ToleranceHigh = (0.0, 0.0) if lo is None else (lo, hi)
        if noms is not None:
            o.Nominals = noms
        o.touch()
        return picks.finish(s, "insp_update", lambda: reading(o, int(a.get("worst", 5))))

    def insp_list(a):
        out = []
        for o in inspections(doc()):
            r = reading(o, 0)
            out.append({k: r[k] for k in ("inspection", "actual", "nominals", "points", "rms", "inTolerancePercent", "verdict", "outOfReachPercent") if k in r})
        return {"inspections": out} if out else {"inspections": [], "note": "None yet: insp_run { actual, nominals }."}

    def insp_read(a):
        return reading(ins_of(a.get("inspection")), int(a.get("worst", 10)))

    def insp_faces(a):
        """An inspection split by the nominal body's faces: which faces are off, and by how much."""
        from .. import meshdist

        o = ins_of(a.get("inspection"))
        d = np.asarray(o.Distances, dtype=float)
        P = points_of(o.Actual)
        if P is None or len(P) != len(d):
            raise ToolError("invalid_state", f"{o.Label}: its points and distances do not line up — insp_update to measure again.")
        noms = [x for x in (o.Nominals or []) if isinstance(getattr(x, "Shape", None), __import__("Part").Shape) and x.Shape.Faces]
        if a.get("body"):
            nb = find(a["body"], "body")
            if not isinstance(getattr(nb, "Shape", None), __import__("Part").Shape) or not nb.Shape.Faces:
                raise bad(f"body: {nb.Label} ({nb.TypeId}) has no faces to split the inspection by.")
            noms = [nb]
        if not noms:
            raise ToolError("invalid_input", "This inspection's nominals hold no body with faces (meshes and points have none): body names a body whose faces to split by.")
        lo, hi = band(o)
        V, F, owner = [], [], []
        for nb in noms:
            for k, fc in enumerate(nb.Shape.Faces, start=1):
                vs, ts = fc.tessellate(float(a.get("deflection", 0.05)))
                base = len(V)
                V += [(p.x, p.y, p.z) for p in vs]
                F += [(base + i, base + j, base + m) for i, j, m in ts]
                owner += [f"{nb.Label}.Face{k}"] * len(ts)
        ok = np.abs(d) < BIG
        reach = float(a.get("reach", max(1.0, float(getattr(o, "SearchRadius", 1.0) or 1.0))))
        tri, _dist, _sg = meshdist.nearest(P[ok], np.array(V), np.array(F), reach)
        rows = {}
        for pi, ti in zip(np.nonzero(ok)[0], tri):
            if ti < 0:
                continue
            r = rows.setdefault(owner[ti], [])
            r.append(d[pi])
        out = []
        for face, vals in rows.items():
            v = np.array(vals)
            row = {"face": face, "points": int(v.size), "mean": r4(v.mean()), "min": r4(v.min()), "max": r4(v.max()), "rms": r4(np.sqrt((v * v).mean()))}
            if lo is not None:
                bad_ = int(((v < lo) | (v > hi)).sum())
                row["outOfTolerance"] = bad_
                row["verdict"] = "pass" if bad_ == 0 else "fail"
            out.append(row)
        key = (lambda r: -r.get("outOfTolerance", 0) * 1e9 - abs(r["mean"])) if lo is not None else (lambda r: -abs(r["mean"]))
        out.sort(key=key)
        if not out:
            raise ToolError("not_found", f"{o.Label}: no measured point lies within {reach:g} mm of a face of {', '.join(x.Label for x in noms)} — a larger reach, or the body is not where the actual is.")
        res = {"inspection": o.Label, "faces": out[: int(a.get("limit", 30))], "facesMeasured": len(out)}
        if lo is not None:
            res["failing"] = [r["face"] for r in out if r.get("verdict") == "fail"]
        res["note"] = "mean is how far the face sits off (+ outside the nominal, - inside); a spread between min and max is its form error."
        return res

    def insp_export(a):
        o = ins_of(a.get("inspection"))
        base = (a.get("name") or o.Label).replace(" ", "-")
        d = np.asarray(o.Distances, dtype=float)
        P = points_of(o.Actual)
        lo, hi = band(o)
        rep = reading(o, int(a.get("worst", 10)))
        csv_path = paths.made(s, os.path.join(s.out_dir, base + ".csv"))
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["x", "y", "z", "distance_mm", "status"])
            for i, v in enumerate(d):
                x, y, z = (P[i] if P is not None and i < len(P) else (float("nan"),) * 3)
                if abs(v) >= BIG:
                    st, val = "out_of_reach", ""
                elif lo is not None:
                    st, val = ("over" if v > hi else "under" if v < lo else "ok"), f"{v:.5f}"
                else:
                    st, val = "", f"{v:.5f}"
                w.writerow([f"{x:.5f}", f"{y:.5f}", f"{z:.5f}", val, st])
        json_path = paths.made(s, os.path.join(s.out_dir, base + ".json"))
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        return {"inspection": o.Label, "files": {"csv": {"path": csv_path, "rows": int(d.size)}, "json": {"path": json_path}},
                "summary": {k: rep[k] for k in ("rms", "min", "max", "inTolerancePercent", "verdict") if k in rep}}

    return [
        Tool("insp_run", "Inspect with FreeCAD's own Inspection feature (left in the document): actual — a mesh, points or a body — or file (a scan: stl, obj, ply, off, 3mf, amf, asc, pcd, xyz) against nominals [bodies, meshes, points]. Nothing is aligned: put the actual where the nominal is first (object_align). search_radius mm (1; FreeCAD's own default is 0.05): a point further than that from every nominal reads out of reach, so it must reach past the tolerance. tolerance ±t or [low, high] mm gives the verdict. Distances are signed: + outside a solid nominal (material added), − inside. A mesh or scan is measured at its vertices; a body is meshed first (deflection 0.1 mm, points every spacing mm, default 1% of its size, at most cap 60000) and that hidden mesh measured (how says so). thickness is stored but FreeCAD 1.1 does not use it. Cost grows with points × nominal faces: a free-form body against a big scan takes minutes — raise spacing first. Reply: points, measured, outOfReach, min, max, mean, rms, stdDev, inTolerancePercent, verdict (pass only when all are in tolerance and none out of reach), worst [{ at, distance }], health.",
             obj({"actual": {"type": "string"}, "file": {"type": "string"}, "nominals": {"type": "array", "items": {"type": "string"}}, "search_radius": {"type": "number"}, "thickness": {"type": "number"},
                  "tolerance": {"type": ["number", "array"]}, "deflection": {"type": "number"}, "spacing": {"type": "number"}, "cap": {"type": "integer"}, "name": {"type": "string"}, "worst": {"type": "integer"}}, ["nominals"]), insp_run, changes=True),
        Tool("insp_update", "Change an inspection and measure again: search_radius, thickness, tolerance (±t or [low, high]; null clears), nominals — at least one; inspection may be left out when there is one. Checked before anything is set (a tolerance past the search radius is refused). Reply: as insp_run.",
             obj({"inspection": {"type": "string"}, "search_radius": {"type": "number"}, "thickness": {"type": "number"}, "tolerance": {"type": ["number", "array", "null"]}, "nominals": {"type": "array", "items": {"type": "string"}}, "worst": {"type": "integer"}}), insp_update, changes=True),
        Tool("insp_read", "One inspection's numbers (the one there is when inspection is left out): points, measured, outOfReach, min, max, mean, rms, stdDev, p95abs, histogram, tolerance, inTolerancePercent, over, under, verdict, worst spots (worst: how many, 10). Distances in mm, + outside the nominal. Changes nothing.",
             obj({"inspection": {"type": "string"}, "worst": {"type": "integer"}}), insp_read),
        Tool("insp_list", "The inspections in the document, a line each: inspection, actual, nominals, points, rms, inTolerancePercent, verdict, outOfReachPercent. Changes nothing.", obj({}), insp_list),
        Tool("insp_faces", "An inspection split by the nominal body's faces: each face (\"Body.Face4\") with its points, mean offset (+ the actual sits outside there), min, max, rms and, with a tolerance, outOfTolerance and verdict — the faces that are off first; failing lists them. A face off evenly is displaced; one with min and max far apart is out of form. body: which body when the nominals hold several or none; reach mm (the search radius): how near a face a point must be to count for it; limit (30). Changes nothing.",
             obj({"inspection": {"type": "string"}, "body": {"type": "string"}, "reach": {"type": "number"}, "deflection": {"type": "number"}, "limit": {"type": "integer"}}), insp_faces),
        Tool("insp_export", "Write an inspection out to the session's folder: <name>.csv with a row a point (x, y, z, distance_mm, status ok | over | under | out_of_reach) and <name>.json with insp_read's numbers. name: the files' base name (the inspection's label by default). Reply: files { csv { path, rows }, json { path } }, summary. The document is not changed.",
             obj({"inspection": {"type": "string"}, "name": {"type": "string"}, "worst": {"type": "integer"}}), insp_export),
    ]
