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
from .. import runners
from ..protocol import ToolError, bad
from . import picks
from .picks import r4

GROUP = "inspection"
INFO = "FreeCAD's Inspection: an actual (mesh, points, body or scan file) against nominals, point by point, with tolerance, statistics, worst spots, a colour map and a report."

TOL_PROP = ("ToleranceLow", "ToleranceHigh")
BIG = 1e30  # Inspection marks a point out of reach with ±FLT_MAX


def kind_of(o):
    """What an object is to Inspection: a mesh, points, a shape, or None when it is none of them."""
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
    """The document's Inspection features, in order."""
    return [o for o in doc.Objects if o.TypeId == "Inspection::Feature"]


def tol_props(o):
    """The tolerance band's two properties, added when the inspection has
    none (one made in FreeCAD's own Inspection workbench)."""
    for p in TOL_PROP:
        if p not in o.PropertiesList:
            o.addProperty("App::PropertyFloat", p, "Tolerance", "The band a distance must fall in, mm (set by Agent Link)")


def band(o):
    """An inspection's tolerance band (low, high) in mm; (None, None) when it has none set."""
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


def has_faces(o):
    """Whether an object is a body with faces to split an inspection by (a mesh or a cloud has none)."""
    import Part

    return isinstance(getattr(o, "Shape", None), Part.Shape) and bool(o.Shape.Faces)


def faces_mesh(bodies, deflection):
    """The bodies' faces tessellated into one triangle mesh: (vertices,
    triangles, the face each triangle is of, as "Body.Face4")."""
    V, F, owner = [], [], []
    for nb in bodies:
        for k, fc in enumerate(nb.Shape.Faces, start=1):
            vs, ts = fc.tessellate(float(deflection))
            base = len(V)
            V += [(p.x, p.y, p.z) for p in vs]
            F += [(base + i, base + j, base + m) for i, j, m in ts]
            owner += [f"{nb.Label}.Face{k}"] * len(ts)
    return V, F, owner


def by_face(o, mesh, reach, lo, hi):
    """An inspection's measured points sorted to the face each lies nearest
    (within reach mm), a row a face: its points, mean, min, max, rms and,
    with a band, outOfTolerance and verdict — the faces that are off first."""
    from .. import meshdist

    V, F, owner = mesh
    d = np.asarray(o.Distances, dtype=float)
    P = points_of(o.Actual)
    ok = np.abs(d) < BIG
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
    return out


def lined_up(o):
    """Whether an inspection's distances are one to a point of its actual (they are not after the actual changed)."""
    P = points_of(o.Actual)
    return P is not None and len(P) == len(np.asarray(o.Distances, dtype=float))


def point_rows(o):
    """A row a measured point for the report: x, y, z, the distance, and its
    status — out_of_reach, or with a tolerance band ok, over or under."""
    d = np.asarray(o.Distances, dtype=float)
    P = points_of(o.Actual)
    lo, hi = band(o)
    rows = []
    for i, v in enumerate(d):
        x, y, z = (P[i] if P is not None and i < len(P) else (float("nan"),) * 3)
        if abs(v) >= BIG:
            st, val = "out_of_reach", ""
        elif lo is not None:
            st, val = ("over" if v > hi else "under" if v < lo else "ok"), f"{v:.5f}"
        else:
            st, val = "", f"{v:.5f}"
        rows.append([f"{x:.5f}", f"{y:.5f}", f"{z:.5f}", val, st])
    return rows


def write_csv(path, header, rows):
    """header and rows written as a CSV file; answers how many rows."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for row in rows:
            w.writerow(row)
    return len(rows)


def write_json(path, data):
    """data written as a JSON file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def read_points(module, path):
    """A point cloud read from a file by FreeCAD's Points module (its Points class, or read on a build without it)."""
    return module.Points(path) if hasattr(module, "Points") else module.read(path)


def points_module():
    """FreeCAD's Points module, loaded when a scan of points is read."""
    import Points

    return Points


def tools(session):
    """The inspection tools are data (agentlink/data/tools.json, group
    "inspection"; run by agentlink/runners.py's steps runner): each entry
    has the tool's words, its checks with their refusals, the order of its
    steps and its answer. What is here is what those entries call by name
    (docs/data-tools.md)."""
    s = session
    doc = lambda: s.doc  # noqa: E731

    def find(ref, what="object"):
        """An object by its label or name (the label in any case too)."""
        for o in doc().Objects:
            if ref in (o.Label, o.Name):
                return o
        for o in doc().Objects:
            if o.Label.lower() == str(ref).lower():
                return o
        raise ToolError("not_found", f"{what} {ref!r}: not here — session_state and object_list name what there is.")

    def ins_of(ref):
        """The inspection ref names, or the only one when ref is None."""
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
        """The call's tolerance as a band (low, high): ±t from a number, [low, high] as given; (None, None) when left out."""
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
        """A body as a hidden mesh in the document, to be measured at its
        vertices: tessellated, then split until no edge is over spacing (a
        flat face is measured across it, not only at its corners)."""
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
        """An inspection's numbers as every tool here answers them: its
        label, name, actual, nominals, search radius and thickness, the
        statistics of its distances (stats), the worst spots, and a note
        when over 5% of the points are out of reach."""
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

    # What the tools' entries (agentlink/data/tools.json, group "inspection") call by name.
    # Mesh's and Points' own are reached when called, not here.
    helpers = {"doc": doc, "unique": lambda label, own=None: s.unique(label, own), "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps),
               "finish": lambda tool, read: picks.finish(s, tool, read), "num": picks.num,
               "in_file": lambda tool, p, key: paths.in_file(s, tool, p, key), "made": lambda name: paths.made(s, os.path.join(s.out_dir, name)),
               "isfile": lambda p: os.path.isfile(p), "file_ext": lambda p: os.path.splitext(p)[1].lower(), "file_stem": lambda p: os.path.splitext(os.path.basename(p))[0],
               # FreeCAD's own
               "read_mesh": lambda p: Mesh.Mesh(p), "points_module": points_module, "read_points": read_points,
               # the family's
               "find": find, "ins_of": ins_of, "tol_of": tol_of, "mesh_of_body": mesh_of_body, "reading": reading, "inspections": lambda: inspections(doc()),
               "kind_of": kind_of, "band": band, "tol_props": tol_props, "has_faces": has_faces, "faces_mesh": faces_mesh, "by_face": by_face, "lined_up": lined_up,
               "point_rows": point_rows, "write_csv": write_csv, "write_json": write_json}
    return runners.tools(GROUP, s, helpers)
