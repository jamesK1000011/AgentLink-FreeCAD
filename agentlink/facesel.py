# SPDX-License-Identifier: LGPL-2.1-or-later
# A face by what it is, not by where a point is: { side: "+z" } the flat face
# of the body farthest along +z whose outward normal points that way;
# of: "<feature>" keeps the faces that feature made (on its AddSubShape),
# of: "<body>" keeps all;
# largest: true takes the largest face facing that way (not the farthest).
# Owner, 22 Nov: no guessing. A selector must match exactly one face, or the
# call is refused with the faces that are there, each with the selector (or
# { at, normal }) that picks it, so the agent can copy one. Local models
# chose faces worst of all (face: "Pad1", refused four times); CADIR found
# index references rebuild 0.32-0.47 of the nodes, semantic ones 1.00, and
# listing the admissible choices gave 8-14B models +42-44 points.
#
# Plain Python over plain face descriptions, so it runs and tests without
# FreeCAD; families/pd_common.py makes the descriptions from a shape:
#
#   { "center": [x,y,z], "at": [x,y,z] a point on the face (default center),
#     "normal": [x,y,z] outward at "at" (None when unknown), "area": mm²,
#     "type": "plane" | "cylinder" | …, "owners": names of the features or
#     bodies whose shape has this face (only when of is asked) }

import json
import math

from .protocol import ToolError

SIDES = {"+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0), "+y": (0.0, 1.0, 0.0),
         "-y": (0.0, -1.0, 0.0), "+z": (0.0, 0.0, 1.0), "-z": (0.0, 0.0, -1.0)}
KEYS = ("side", "of", "largest", "feature")  # feature: sketch_attach's, read by its caller
TIE = 1e-6        # mm (and mm² for largest): closer than this is the same
PARALLEL = 1 - 1e-6  # cosine: a normal this close to an axis points along it
LIST = 8          # faces a refusal lists
FORMS = "face: { side: +z } (also -z, +x, -x, +y, -y; of: \"Pad\" or the body; largest: true) or { at: [x,y,z], normal: [x,y,z] }"


# FreeCAD's surface classes by the names shape_query uses (families/measure.py).
SURFACES = {"Plane": "plane", "Cylinder": "cylinder", "Cone": "cone", "Sphere": "sphere", "Toroid": "torus",
            "BSplineSurface": "bspline", "BezierSurface": "bezier", "SurfaceOfRevolution": "revolution",
            "SurfaceOfExtrusion": "extrusion", "OffsetSurface": "offset"}


def surface_type(cls_name):
    return SURFACES.get(cls_name, cls_name.lower())


def is_selector(q):
    """Whether a face query is this form (and not { at, normal })."""
    return isinstance(q, dict) and "at" not in q and ("side" in q or "largest" in q)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


def side_word(normal):
    """"+z" … for a normal along an axis, else None."""
    if normal is None:
        return None
    n = _len(normal)
    if n < 1e-12:
        return None
    for w, a in SIDES.items():
        if _dot(normal, a) >= PARALLEL * n:
            return w
    return None


def _r(v, nd):
    return [round(float(x), nd) + 0.0 for x in v]


def words(q):
    """The selector as the agent wrote it, in one line."""
    return "{ " + ", ".join(f"{k}: {json.dumps(v)}" for k, v in q.items() if k != "feature") + " }"


def check(q):
    """The selector's own fields, checked: (side, of, largest)."""
    bad = [k for k in q if k not in KEYS]
    if bad:
        raise ToolError("invalid_input", f"face.{bad[0]}: not a field of this form — {FORMS}. Give side or at, not both.")
    s = q.get("side")
    if s is None:
        raise ToolError("invalid_input", f"face: give side with largest — {FORMS}.")
    side = s.strip().lower() if isinstance(s, str) else None
    if side not in SIDES:
        raise ToolError("invalid_input", f"face.side: one of +x, -x, +y, -y, +z, -z (with the sign) — not {s!r}.")
    of = q.get("of")
    if of is not None and (not isinstance(of, str) or not of.strip()):
        raise ToolError("invalid_input", "face.of: a feature's or the body's name, as text.")
    largest = q.get("largest", False)
    if not isinstance(largest, bool):
        raise ToolError("invalid_input", "face.largest: true or false.")
    return side, of, largest


def _facing(faces, side, of):
    out = []
    for i, f in enumerate(faces):
        if f.get("type") != "plane" or side_word(f.get("normal")) != side:
            continue
        if of is not None and of not in (f.get("owners") or ()):
            continue
        out.append(i)
    return out


def matches(faces, q):
    """The indices of the faces the selector names: one when it is good,
    none or several when it is not. (The pool facing that way comes too.)"""
    side, of, largest = check(q)
    pool = _facing(faces, side, of)
    if not pool:
        return [], pool
    if largest:
        top = max(faces[i]["area"] for i in pool)
        hits = [i for i in pool if faces[i]["area"] >= top - TIE]
    else:
        ax = SIDES[side]
        top = max(_dot(faces[i]["center"], ax) for i in pool)
        hits = [i for i in pool if _dot(faces[i]["center"], ax) >= top - TIE]
    return hits, pool


def copyable(faces, i, q=None):
    """The shortest form that picks face i alone: { side } (with the
    asked of, or largest, when that is needed), else { at, normal }."""
    f = faces[i]
    w = side_word(f.get("normal")) if f.get("type") == "plane" else None
    if w:
        of = q.get("of") if isinstance(q, dict) else None
        tries = [{"side": w}]
        if isinstance(of, str) and of in (f.get("owners") or ()):
            tries.append({"side": w, "of": of})
        tries.append({"side": w, "largest": True})
        for t in tries:
            hits, _ = matches(faces, t)
            if hits == [i]:
                return t
    at = f.get("at") or f["center"]
    out = {"at": _r(at, 2)}
    if f.get("normal") is not None:
        n = f["normal"]
        k = _len(n) or 1.0
        out["normal"] = _r([x / k for x in n], 3)
    return out


def entry(faces, i, q=None):
    """One face as a refusal lists it."""
    f = faces[i]
    d = {}
    w = side_word(f.get("normal")) if f.get("type") == "plane" else None
    if w:
        d["side"] = w
    d["center"] = _r(f["center"], 2)
    if f.get("normal") is not None:
        k = _len(f["normal"]) or 1.0
        d["normal"] = _r([x / k for x in f["normal"]], 3)
    d["area"] = round(float(f["area"]), 2)
    d["type"] = f.get("type") or "other"
    d["pick"] = copyable(faces, i, q)
    return d


def listing(faces, q=None, first=()):
    """Up to LIST faces of the body: first (the tied ones) first, then those
    facing the asked side (farthest first), then the rest, largest first."""
    order = list(dict.fromkeys(first))
    side = None
    if isinstance(q, dict) and isinstance(q.get("side"), str) and q["side"].strip().lower() in SIDES:
        side = q["side"].strip().lower()
    if side:
        ax = SIDES[side]
        facing = sorted(_facing(faces, side, None), key=lambda j: -_dot(faces[j]["center"], ax))
        order += [j for j in facing if j not in order]
    rest = sorted(range(len(faces)), key=lambda j: -faces[j]["area"])
    order += [j for j in rest if j not in order]
    return [entry(faces, j, q) for j in order[:LIST]]


def _list_words(items, total):
    more = f" ({total - len(items)} more not shown)" if total > len(items) else ""
    return json.dumps(items, separators=(", ", ": ")) + more


def select(faces, q):
    """The index of the one face the selector names; refused (with the faces
    there and how to pick each) when none or several match."""
    hits, _ = matches(faces, q)
    if len(hits) == 1:
        return hits[0]
    if not faces:
        raise ToolError("not_found", f"No face matches {words(q)}: the shape has no faces.")
    items = listing(faces, q, hits)
    if not hits:
        raise ToolError("not_found", f"No face matches {words(q)}. The faces there (copy a pick): {_list_words(items, len(faces))}")
    raise ToolError("invalid_input", f"{len(hits)} faces match {words(q)}: a face selector must match one face. "
                                     f"The faces there (copy a pick): {_list_words(items, len(faces))}")


def same_whole(f, g, tol=1e-4):
    """Two descriptions of one whole face: the same area and center."""
    return (abs(f["area"] - g["area"]) <= tol * max(1.0, g["area"])
            and _len([a - b for a, b in zip(f["center"], g["center"])]) <= tol * max(1.0, _len(g["center"])))


def owner_pairs(faces, theirs, tol=1e-4):
    """(i, j): face i may lie on their face j (theirs: the faces a feature
    made, described the same way and in the same frame). The same type,
    normals along one line (a pocket's faces face the other way), and a flat
    face in their plane; whether it lies inside is FreeCAD's distance (the
    glue), or same_whole without FreeCAD."""
    out = []
    for i, f in enumerate(faces):
        n = f.get("normal")
        p = f.get("at") or f["center"]
        for j, g in enumerate(theirs):
            if f.get("type") != g.get("type"):
                continue
            m = g.get("normal")
            if n is not None and m is not None:
                if abs(_dot(n, m)) < 0.999 * _len(n) * _len(m):
                    continue
                if f.get("type") == "plane" and abs(_dot(m, [a - b for a, b in zip(p, g["center"])])) > tol * max(1.0, _len(m)):
                    continue
            out.append((i, j))
    return out


def with_owner(faces, owned, name):
    """New descriptions: name added to the owners of the faces in owned."""
    return [dict(f, owners=set(f.get("owners") or ()) | ({name} if i in owned else set())) for i, f in enumerate(faces)]
