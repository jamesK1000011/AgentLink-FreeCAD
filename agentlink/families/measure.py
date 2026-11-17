# SPDX-License-Identifier: LGPL-2.1-or-later
# Reading the geometry: faces and edges found by what they are (the
# references the modelling tools take), measurements between them, a
# section through a body, mass properties and the clearance between two
# bodies. Nothing here changes the document.

import math

import Part

from .. import geometry as geo
from .. import store
from ..materials import MASS_DENSITY
from .. import runners
from ..protocol import ToolError
from . import picks


def _deferred(session, name, args):
    """The answer of an add-on's service for this job (hooks), marked with
    where it came from; None when no add-on offers it or it failed for a
    reason of its own (this tool's own answer is given instead). A refusal
    it gives (a code and a message) is the answer."""
    from .. import hooks

    fn = hooks.service(name)
    if fn is None:
        return None
    try:
        out = fn(session, dict(args))
    except Exception as e:  # noqa: BLE001 - an add-on's refusal, or its failure
        code, msg = getattr(e, "code", None), getattr(e, "message", None)
        if code and msg:
            raise ToolError(code, msg) from None
        return None
    if not isinstance(out, dict):
        return None
    return {**out, "from": f"the {name} service of an installed add-on"}

GROUP = "measure"
INFO = "Find faces and edges (the references other tools take), measure between them, sections, mass properties, clearance."

SURFACES = {"Plane": "plane", "Cylinder": "cylinder", "Cone": "cone", "Sphere": "sphere", "Toroid": "torus", "BSplineSurface": "bspline", "BezierSurface": "bezier", "SurfaceOfRevolution": "revolution", "SurfaceOfExtrusion": "extrusion", "OffsetSurface": "offset"}
CURVES = {"Line": "line", "LineSegment": "line", "Circle": "circle", "Ellipse": "ellipse", "BSplineCurve": "bspline", "BezierCurve": "bezier", "Hyperbola": "hyperbola", "Parabola": "parabola", "OffsetCurve": "offset"}
KIND_ATTR = {"face": "Faces", "edge": "Edges", "vertex": "Vertexes"}


def r(x, n=3):
    """x rounded to n places, a float; never -0.0."""
    return round(float(x), n) + 0.0


def surface_type(f):
    """A face's surface in these tools' words (plane, cylinder, cone …); "unknown" when it has none to read."""
    try:
        return SURFACES.get(type(f.Surface).__name__, type(f.Surface).__name__.lower())
    except Exception:
        return "unknown"


def curve_type(e):
    """An edge's curve in these tools' words (line, circle, ellipse …); "unknown" when it has none to read."""
    try:
        return CURVES.get(type(e.Curve).__name__, type(e.Curve).__name__.lower())
    except Exception:
        return "unknown"


def face_normal(f, at=None):
    """The outward normal (the face's orientation counted) at the point of
    the face nearest `at`, its centroid by default."""
    p = at if at is not None else f.CenterOfMass
    try:
        u, v = f.Surface.parameter(p)
        n = f.normalAt(u, v)
    except Exception:
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    return n.normalize() if n.Length > 1e-12 else n


def line_dir(e):
    """A straight edge's direction, from its first vertex to its last (its tangent at the start when it has one vertex)."""
    d = e.Vertexes[-1].Point - e.Vertexes[0].Point if len(e.Vertexes) > 1 else e.tangentAt(e.FirstParameter)
    return d.normalize() if d.Length > 1e-12 else d


def describe_face(f, i):
    """What a face is, as shape_query and measure answer it: ref, type, area, centroid, and what its surface has (normal; radius, axis, centre …)."""
    t = surface_type(f)
    out = {"ref": f"Face{i}", "type": t, "area": r(f.Area, 2), "centroid": geo.vec(f.CenterOfMass)}
    s = f.Surface
    if t == "plane":
        out["normal"] = geo.vec(face_normal(f))
    elif t == "cylinder":
        out.update(radius=r(s.Radius), axis=geo.vec(s.Axis), center=geo.vec(s.Center))
    elif t == "cone":
        out.update(semiAngle=r(math.degrees(s.SemiAngle), 3), axis=geo.vec(s.Axis), apex=geo.vec(s.Apex))
    elif t == "sphere":
        out.update(radius=r(s.Radius), center=geo.vec(s.Center))
    elif t == "torus":
        out.update(radius=r(s.MajorRadius), minorRadius=r(s.MinorRadius), axis=geo.vec(s.Axis), center=geo.vec(s.Center))
    return out


def describe_edge(e, i):
    """What an edge is: ref, type, length, mid, and a line's direction or a circle's centre, axis, radius and whether it closes."""
    t = curve_type(e)
    mid = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
    out = {"ref": f"Edge{i}", "type": t, "length": r(e.Length), "mid": geo.vec(mid)}
    if t == "line":
        out["dir"] = geo.vec(line_dir(e))
    elif t in ("circle", "ellipse"):
        c = e.Curve
        out.update(center=geo.vec(c.Location), axis=geo.vec(c.Axis))
        if t == "circle":
            out["radius"] = r(c.Radius)
            out["closed"] = e.isClosed()
    return out


def rng(v, name):
    """A filter's range from a number (± a small tolerance) or [least, most]; None when not asked."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        tol = max(1e-3, abs(v) * 1e-4)
        return (v - tol, v + tol)
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return (min(v), max(v))
    raise ToolError("invalid_input", f"{name}: a number or [least, most].")


def query(session, a, default_kind="face"):
    """The elements of a body that pass every filter asked: [(index, element, description)], and the body."""
    o = picks.solid_body(session, a.get("body")) if a.get("body") or not a.get("of") else None
    of = a.get("of")
    el = None
    if of:
        label, sub, el = picks.resolve(session, of, a.get("body"))
        if not sub or not sub.startswith("Face"):
            raise ToolError("invalid_input", "of: a face (\"Face6\" or \"Box.Face6\") whose edges or vertices to take.")
        o = picks.shaped(session.doc, label)
    kind, out = filter_shape(o.Shape, a, default_kind, of_el=el)
    return o, kind, out


def filter_shape(shape, a, default_kind="face", of_el=None):
    """The elements of a shape that pass every filter in a (shape_query's:
    kind, type, normal, axis, within, radius, area, length, near, inside,
    x/y/z with tol, sort): (kind, [(index, element, description)]). of_el:
    a face whose edges or vertices only are taken. The one filter every
    tool that takes faces or edges shares (families/refs.py)."""
    kind = (a.get("kind") or default_kind).lower()
    if kind not in KIND_ATTR:
        raise ToolError("invalid_input", "kind: face, edge or vertex.")
    types = a.get("type")
    types = picks.ref_list(types)
    within = picks.num(a.get("within", 1.0), "within")
    normal = picks.direction(a["normal"], "normal") if a.get("normal") is not None else None
    axis = picks.direction(a["axis"], "axis") if a.get("axis") is not None else None
    radius = rng(a.get("radius"), "radius")
    area = rng(a.get("area"), "area")
    length = rng(a.get("length"), "length")
    near = a.get("near")
    near_p, near_d = None, None
    if near is not None:
        if isinstance(near, dict):
            near_p, near_d = picks.vec3(near.get("point"), "near.point"), picks.num(near.get("within", 1e9), "near.within")
        else:
            near_p, near_d = picks.vec3(near, "near"), 1e9
    box = a.get("inside")
    if box is not None:
        if not (isinstance(box, dict) and "min" in box and "max" in box):
            raise ToolError("invalid_input", "inside: { min: [x,y,z], max: [x,y,z] } — the element's centre in that box.")
        lo, hi = picks.vec3(box["min"], "inside.min"), picks.vec3(box["max"], "inside.max")
    # x / y / z: the element's centre at that coordinate (a face's plane, say), within tol mm.
    at_xyz = {k: picks.num(a[k], k) for k in ("x", "y", "z") if a.get(k) is not None}
    tol = picks.num(a.get("tol", 0.01), "tol")
    cos_w = math.cos(math.radians(within))
    pool = getattr(shape, KIND_ATTR[kind])
    if of_el is not None:
        pool_of = getattr(of_el, KIND_ATTR[kind])
        pool = [x for x in pool if any(x.isSame(y) for y in pool_of)]
    out = []
    for x in pool:
        i = picks.index_of(shape, x, KIND_ATTR[kind])
        if kind == "face":
            d = describe_face(x, i)
            centre = x.CenterOfMass
        elif kind == "edge":
            d = describe_edge(x, i)
            centre = picks.V(*d["mid"])
        else:
            d = {"ref": f"Vertex{i}", "at": geo.vec(x.Point)}
            centre = x.Point
        if types and d.get("type") not in types:
            continue
        if normal is not None:
            if kind != "face":
                raise ToolError("invalid_input", "normal: faces only — for edges, axis gives a line's direction or a circle's axis.")
            n = face_normal(x)
            if n.Length < 1e-9 or n.dot(normal) < cos_w:
                continue
            d.setdefault("normal", geo.vec(n))
        if axis is not None:
            ax = d.get("axis") or d.get("dir")
            if ax is None or abs(picks.V(*ax).normalize().dot(axis)) < cos_w:
                continue
        if radius and not ("radius" in d and radius[0] <= d["radius"] <= radius[1]):
            continue
        if area and not ("area" in d and area[0] <= d["area"] <= area[1]):
            continue
        if length and not ("length" in d and length[0] <= d["length"] <= length[1]):
            continue
        if at_xyz and any(abs(getattr(centre, k) - v) > tol for k, v in at_xyz.items()):
            continue
        if box is not None and not (lo.x <= centre.x <= hi.x and lo.y <= centre.y <= hi.y and lo.z <= centre.z <= hi.z):
            continue
        if near_p is not None:
            dist = x.distToShape(Part.Vertex(near_p))[0]
            if dist > near_d:
                continue
            d["distance"] = r(dist)
        out.append((i, x, d))
    sort = a.get("sort")
    if sort is None and near_p is not None:
        sort = "distance"
    if sort:
        key, rev = sort.lstrip("-"), sort.startswith("-")
        if key in ("x", "y", "z"):
            out.sort(key=lambda t: (t[2].get("centroid") or t[2].get("mid") or t[2].get("at"))["xyz".index(key)], reverse=rev)
        elif key in ("area", "radius", "length", "distance"):
            out.sort(key=lambda t: t[2].get(key, math.inf if not rev else -math.inf), reverse=rev)
        else:
            raise ToolError("invalid_input", "sort: area, radius, length, distance, x, y or z; a leading - for the largest first.")
    return kind, out


def describe(label, sub, sh):
    """What measure reads of one reference: a point, a whole body (volume, area, box) or an element (describe_face, describe_edge, a vertex's place), a round one with its diameter."""
    if label == "point":
        return {"point": geo.vec(sh.Point)}
    if sub is None:
        return {"body": label, "volume": r(sh.Volume, 2), "area": r(sh.Area, 2), **geo.box_of(sh)}
    if sub.startswith("Face"):
        d = describe_face(sh, int(sub[4:]))
    elif sub.startswith("Edge"):
        d = describe_edge(sh, int(sub[4:]))
    else:
        d = {"ref": sub, "at": geo.vec(sh.Point)}
    d["ref"] = f"{label}.{sub}"
    if "radius" in d:
        d["diameter"] = r(2 * d["radius"])
    return d


def angle_between(u, v, undirected=False):
    """The angle between two unit vectors in degrees (0–180); undirected: between two lines, 0–90."""
    c = max(-1.0, min(1.0, u.dot(v)))
    deg = math.degrees(math.acos(c))
    if undirected:
        deg = min(deg, 180 - deg)
    return round(deg, 3)


def inertia(shape, rho):
    """Mass, centre and inertia (g, mm, g·mm²) of every solid together, about the centre of mass."""
    solids = shape.Solids
    if not solids:
        raise ToolError("invalid_state", "No solid: mass properties need a closed body.")
    k = rho / 1000.0  # g/cm³ -> g/mm³
    m = sum(s.Volume for s in solids) * k
    c = picks.V()
    for s in solids:
        c += s.CenterOfMass * (s.Volume * k)
    c = c * (1.0 / m)
    I = [[0.0] * 3 for _ in range(3)]
    for s in solids:
        M = s.MatrixOfInertia
        rows = [[M.A11, M.A12, M.A13], [M.A21, M.A22, M.A23], [M.A31, M.A32, M.A33]]
        ms = s.Volume * k
        d = s.CenterOfMass - c
        dv = [d.x, d.y, d.z]
        dd = d.dot(d)
        for i in range(3):
            for j in range(3):
                I[i][j] += rows[i][j] * k + ms * ((dd if i == j else 0.0) - dv[i] * dv[j])
    return m, c, I


# FreeCAD's Measure objects by kind: the type, how many elements it takes (0: one or more) and the property that holds the result.
KEEP = {"distance": ("Measure::MeasureDistance", 2, "Distance"), "angle": ("Measure::MeasureAngle", 2, "Angle"),
        "length": ("Measure::MeasureLength", 0, "Length"), "area": ("Measure::MeasureArea", 0, "Area"),
        "radius": ("Measure::MeasureRadius", 1, "Radius"), "diameter": ("Measure::MeasureDiameter", 1, "Diameter"),
        "position": ("Measure::MeasurePosition", 1, "Position")}

# What each of FreeCAD's Measure objects accepts (its isValidSelection).
TAKES = {"distance": "two of: a vertex, an edge, a flat or cylindrical face", "angle": "two straight edges or flat faces",
         "length": "edges", "area": "faces", "radius": "one circular edge (a circle or arc, not a cylindrical face)",
         "diameter": "one circular edge (a circle or arc, not a cylindrical face)", "position": "one vertex"}


def wrong(kind, sub, el):
    """Why FreeCAD's Measure object of this kind does not take the element, or None."""
    what = "a face" if sub.startswith("Face") else "an edge" if sub.startswith("Edge") else "a vertex"
    if sub.startswith("Face"):
        t = surface_type(el)
        if kind == "area" or (kind == "angle" and t == "plane") or (kind == "distance" and t in ("plane", "cylinder")):
            return None
        return f"{what} ({t})"
    if sub.startswith("Edge"):
        t = curve_type(el)
        if kind in ("length", "distance") or (kind == "angle" and t == "line") or (kind in ("radius", "diameter") and t == "circle"):
            return None
        return f"{what} ({t})"
    return None if kind in ("position", "distance") else what


def tools(session):
    """The measuring tools are data (agentlink/data/tools.json, group
    "measure"; run by agentlink/runners.py's steps runner): each entry has
    the tool's words, its checks with their refusals, the order of its steps
    and its answer. What is here is what those entries call by name
    (docs/data-tools.md)."""
    s = session

    def recorded(label):
        """The material material_set recorded for a body, or None."""
        return store.materials(s.doc).get(label)

    def printed(label):
        """The body's print setup, when it has one (a printed part with no material is taken as PLA)."""
        return store.setup_of(s.doc, label, "print")

    def card(ref):
        """A FreeCAD library card (its id or name) or a custom material of
        this document, as material_set records them; None when it is neither."""
        from . import material as _material

        return _material.card(s.doc, ref)

    def addon_mass(label):
        """The answer of the add-on that owns mass for this body (its
        "mass_properties" service: as printed, inserts included), or None
        when none is installed or it failed for a reason of its own."""
        return _deferred(s, "mass_properties", {"body": label})

    def prop(o, name):
        """A property by a name worked out in the call (a Measure object's result)."""
        return getattr(o, name)

    # What the tools' entries call by name. Part's own is reached when called, not here.
    helpers = {"doc": lambda: s.doc, "unique": lambda label, own=None: s.unique(label, own), "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps),
               "find": lambda ref: picks.find(s.doc, ref), "resolve": lambda ref, body=None: picks.resolve(s, ref, body), "solid_body": lambda ref: picks.solid_body(s, ref),
               "num": picks.num, "vec3": picks.vec3, "direction": picks.direction, "ref_list": picks.ref_list,
               # FreeCAD's own, and the readings every answer is given in
               "vector": lambda xyz: picks.V(*xyz), "plane_through": lambda p, n: Part.Plane(p, n), "vec": geo.vec, "box_of": geo.box_of, "r": r,
               # the family's
               "query": lambda a: query(s, a), "describe": describe, "angle_between": angle_between, "inertia": inertia, "wrong": wrong, "prop": prop,
               "addon_mass": addon_mass, "recorded": recorded, "printed": printed, "card": card,
               "KEEP": KEEP, "TAKES": TAKES, "MASS_DENSITY": MASS_DENSITY}
    return runners.tools(GROUP, s, helpers)
