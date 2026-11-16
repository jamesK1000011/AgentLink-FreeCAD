# SPDX-License-Identifier: LGPL-2.1-or-later
# Faces picked by a query rather than by name, so a pick still finds its
# faces after an edit renumbers them: { faces: ["Face3"] }, { near: [x,y,z],
# radius }, { normal: [nx,ny,nz], x|y|z: plane, tol: degrees }, and
# { cylinder: true } to keep cylindrical faces only. Also what every other
# tool takes (families/refs.py): "Face8" / "Body.Face8", a list of them,
# shape_query's items and its filters ({ type: cylinder, radius: 3 } …).

import math

import FreeCAD
import Part

from .protocol import ToolError

V = FreeCAD.Vector
KEYS = ("faces", "near", "radius", "normal", "x", "y", "z", "tol", "cylinder", "largest")
HELP = "a query: { near: [x,y,z] } (the nearest face; radius: mm takes every face that close), { normal: [0,0,1], z: 0 } (flat faces facing that way, at that plane), { faces: [\"Face3\"] }, a reference shape_query gives (\"Face8\", \"Body.Face8\") or a list of them, or shape_query's filters ({ type: cylinder, radius, axis, near, … })"


def _vec(v, what):
    if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)):
        raise ToolError("invalid_input", f"{what}: [x, y, z], numbers.")
    return V(*[float(x) for x in v])


def outward_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)


def describe(name, face):
    c = face.CenterOfMass
    d = {"face": name, "area": round(face.Area, 2), "centre": [round(c.x, 3), round(c.y, 3), round(c.z, 3)]}
    s = face.Surface
    if isinstance(s, Part.Plane):
        n = outward_normal(face)
        d["normal"] = [round(n.x, 3), round(n.y, 3), round(n.z, 3)]
    elif isinstance(s, Part.Cylinder):
        d["cylinder"] = round(2 * s.Radius, 3)
    return d


def _legacy(q):
    """Whether a dict is this module's own query (not shape_query's
    filters): only its keys, and radius only with near (radius alone is
    shape_query's, the faces' own radius)."""
    from .families import refs

    return refs.legacy_of(KEYS, lambda d: "radius" not in d or "near" in d)(q)


def pick(shape, q, what="faces", names=()):
    """[(name, face)] the query picks on the shape; refused when none.
    A reference, a list, or shape_query's filters go through the shared
    resolver (families/refs.py); this module's own dicts as they were."""
    if isinstance(q, (str, list)) or (isinstance(q, dict) and q and not _legacy(q)):
        from .families import refs

        return refs.pick(shape, q, "face", what, legacy=lambda d: _pick(shape, d, what), is_legacy=_legacy, names=names)
    return _pick(shape, q, what)


def _pick(shape, q, what):
    if not isinstance(q, dict) or not q:
        raise ToolError("invalid_input", f"{what}: {HELP}.")
    bad = [k for k in q if k not in KEYS]
    if bad:
        raise ToolError("invalid_input", f"{what}.{bad[0]}: not a query key — {HELP}.")
    faces = [(f"Face{i + 1}", f) for i, f in enumerate(shape.Faces)]
    if q.get("cylinder"):
        faces = [(n, f) for n, f in faces if isinstance(f.Surface, Part.Cylinder)]
    if "faces" in q:
        names = q["faces"] if isinstance(q["faces"], list) else [q["faces"]]
        have = dict(faces)
        miss = [n for n in names if n not in have]
        if miss:
            raise ToolError("not_found", f"{what}: {miss[0]} is not a face here (Face1 … Face{len(shape.Faces)}) — a near or normal query survives edits better.")
        return [(n, have[n]) for n in names]
    if "normal" in q:
        n = _vec(q["normal"], f"{what}.normal")
        if n.Length < 1e-9:
            raise ToolError("invalid_input", f"{what}.normal: not zero.")
        n.normalize()
        tol = math.radians(float(q.get("tol", 5)))
        out = []
        for name, f in faces:
            if not isinstance(f.Surface, Part.Plane):
                continue
            fn = outward_normal(f)
            if fn.getAngle(n) > tol:
                continue
            bb = f.BoundBox
            ok = True
            for ax, lo, hi in (("x", bb.XMin, bb.XMax), ("y", bb.YMin, bb.YMax), ("z", bb.ZMin, bb.ZMax)):
                if ax in q and not (lo - 0.05 <= float(q[ax]) <= hi + 0.05):
                    ok = False
            if ok:
                out.append((name, f))
        if q.get("largest") and out:
            out = [max(out, key=lambda t: t[1].Area)]
        # normal with near: the faces that way, the nearest of them (or those
        # within radius) — near was ignored once normal had picked, so an
        # outside wall came with the inside one facing the same way.
        if "near" in q and out:
            vx = Part.Vertex(_vec(q["near"], f"{what}.near"))
            dd = sorted(((vx.distToShape(f)[0], n, f) for n, f in out), key=lambda t: t[0])
            if "radius" in q:
                out = [(n, f) for d, n, f in dd if d <= float(q["radius"])]
            else:
                out = [(n, f) for d, n, f in dd if d <= dd[0][0] + 1e-6]
        if not out:
            raise ToolError("not_found", f"{what}: no flat face faces {list(q['normal'])}" + (" at that plane" if any(a in q for a in "xyz") else "") + " — session_state gives the box; or pick with near.")
        return out
    if "near" in q:
        p = _vec(q["near"], f"{what}.near")
        vx = Part.Vertex(p)
        dists = [(vx.distToShape(f)[0], name, f) for name, f in faces]
        if not dists:
            raise ToolError("not_found", f"{what}: no {'cylindrical ' if q.get('cylinder') else ''}face on this body.")
        dists.sort(key=lambda t: t[0])
        if "radius" in q:
            out = [(n, f) for d, n, f in dists if d <= float(q["radius"])]
        else:
            out = [(n, f) for d, n, f in dists if d <= dists[0][0] + 1e-6]
        if not out:
            raise ToolError("not_found", f"{what}: no face within {q['radius']} mm of {list(q['near'])} — the nearest is {dists[0][0]:.2f} mm away.")
        return out
    raise ToolError("invalid_input", f"{what}: {HELP}.")
