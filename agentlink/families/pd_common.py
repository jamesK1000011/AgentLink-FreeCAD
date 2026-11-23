# SPDX-License-Identifier: LGPL-2.1-or-later
# What the sketch, feature and param families share: finding a PartDesign
# body, its origin planes and axes, its features and sketches; faces and
# edges found by where they are (a point, a normal) rather than by index;
# and one reading of a body after a change. Written for FreeCAD's public
# Python API, tolerant of the property renames between releases
# (Support -> AttachmentSupport, Midplane -> SideType).

import math
import re

import FreeCAD
import Part

from .. import geometry as geo
from ..protocol import ToolError
from . import picks

V = FreeCAD.Vector
PLANES = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
AXES = {"X": "X_Axis", "Y": "Y_Axis", "Z": "Z_Axis"}


def short(o):
    return o.TypeId.split("::", 1)[-1]


def vec3(a, what):
    if not (isinstance(a, (list, tuple)) and len(a) == 3 and all(isinstance(x, (int, float)) for x in a)):
        raise ToolError("invalid_input", f"{what}: [x, y, z] in mm.")
    return V(float(a[0]), float(a[1]), float(a[2]))


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def vec2(a, what):
    """A sketch point [x, y]. Any other form is refused, with what was
    given and the form (owner, 22 Nov: no guessing in a change)."""
    if not (isinstance(a, (list, tuple)) and len(a) == 2 and all(_num(x) for x in a)):
        got = ""
        if isinstance(a, (list, tuple)) and len(a) == 3 and all(_num(x) for x in a):
            got = " You gave [x, y, z]: a sketch is flat, so give [x, y]; sketch_new's offset or plane sets its height."
        elif isinstance(a, dict):
            got = f" You gave an object ({', '.join(map(str, a))}): give a list, [x, y]."
        elif a is not None:
            got = f" You gave {str(a)[:60]}."
        raise ToolError("invalid_input", f"{what}: [x, y] in mm, in the sketch's own coordinates.{got} Example: \"{what.split('.')[-1]}\": [10, 0].")
    return V(float(a[0]), float(a[1]), 0)


def support_prop(o):
    return "AttachmentSupport" if "AttachmentSupport" in o.PropertiesList else "Support"


# ---- bodies, features, sketches ------------------------------------------------------------

def pd_bodies(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]


def pd_body(doc, ref):
    return picks.one_of(pd_bodies(doc), ref, "body: say which — {labels}.", "body {ref}: no such PartDesign body — they are: {labels}.",
                        none="No PartDesign body in the document: pd_body_new makes one.", nocase=True)


def body_of(o):
    try:
        g = o.getParentGeoFeatureGroup()
    except Exception:
        g = None
    if g is not None and g.TypeId == "PartDesign::Body":
        return g
    for b in pd_bodies(o.Document):
        if b.hasObject(o):
            return b
    return None


def in_body(body, ref, kinds=None, what="feature"):
    """An object of the body by label or name; kinds: TypeId prefixes allowed."""
    items = [o for o in body.Group if kinds is None or any(o.TypeId.startswith(k) for k in kinds)]
    for o in items:
        if ref in (o.Label, o.Name) or o.Label.lower() == str(ref).lower():
            return o
    raise ToolError("not_found", f"{what} {ref!r}: not in {body.Label} — there: {', '.join(o.Label for o in items) or 'none'}.")


def sketch_of(doc, ref, body=None):
    sk = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
    if ref is None:
        if body is not None:
            sk = [o for o in sk if body.hasObject(o)]
        if len(sk) == 1:
            return sk[0]
        raise ToolError("invalid_input", f"sketch: say which — {', '.join(o.Label for o in sk) or 'none yet: sketch_new makes one'}.")
    for o in sk:
        if ref in (o.Label, o.Name) or o.Label.lower() == str(ref).lower():
            return o
    raise ToolError("not_found", f"sketch {ref!r}: no such sketch — they are: {', '.join(o.Label for o in sk) or 'none: sketch_new makes one'}.")


def tip_shape(body, need=True):
    tip = body.Tip
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        if need:
            raise ToolError("invalid_state", f"{body.Label} has no solid yet: pd_pad a closed sketch (or pd_primitive) first.")
        return None, None
    return tip, tip.Shape


def ref_shape(body, shape):
    """The shape to find faces and edges on: the Body's own (where
    shape_query and session_state read them: the Body's placement in it),
    the tip's when the Body has not caught up. The numbering is the
    same."""
    try:
        bs = body.Shape
        if not bs.isNull() and len(bs.Edges) == len(shape.Edges) and len(bs.Faces) == len(shape.Faces):
            return bs
    except Exception:
        pass
    return shape


def ref_names(body, *objs):
    """The names a reference may carry for this body: "Body.Face8",
    "Pad.Face8" (its tip)."""
    out = []
    for o in (body,) + objs:
        if o is not None:
            out += [o.Label, o.Name]
    return tuple(out)


# ---- the body's origin ---------------------------------------------------------------------

def origin_feature(body, role):
    org = body.Origin
    feats = list(getattr(org, "OriginFeatures", None) or getattr(org, "Group", None) or org.OutList)
    for f in feats:
        if getattr(f, "Role", "") == role:
            return f
    for f in feats:
        if f.Name.startswith(role) or f.Label.startswith(role):
            return f
    raise ToolError("failed", f"{body.Label}'s origin has no {role}.")


# Coordinate systems and the planes in them (FreeCAD 1.1, src/App/Datums.h): an
# App::LocalCoordinateSystem (Part::LocalCoordinateSystem is one) keeps its
# axes and planes in OriginFeatures, each with its Role ("XY_Plane" …), as a
# Body's origin does. PartDesign::CoordinateSystem is a Part::Datum with no
# planes of its own: a sketch takes its XY, XZ or YZ by the ObjectXY, ObjectXZ
# or ObjectYZ mode. Part::DatumPlane is an App::Plane.
CSYS_TYPES = ("App::LocalCoordinateSystem", "Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem")
PLANE_TYPES = ("PartDesign::Plane", "Part::DatumPlane", "App::Plane")
_CSYS_PLANE = re.compile(r"\.(XY|XZ|YZ)_Plane \(.* has no planes")


def _is(o, types):
    if getattr(o, "TypeId", "") in types:
        return True
    try:
        return any(o.isDerivedFrom(t) for t in types)
    except Exception:
        return False


def _role_feature(holder, role):
    """The axis or plane of a body's origin or of a coordinate system by its
    Role (its name's start where an older file has no Role), or None."""
    feats = list(getattr(holder, "OriginFeatures", None) or [])
    for f in feats:
        if getattr(f, "Role", "") == role:
            return f
    for f in feats:
        if f.Name.startswith(role) or f.Label.startswith(role):
            return f
    return None


def _plane_key(word):
    key = str(word).upper().replace("-PLANE", "").replace("_PLANE", "").replace(" PLANE", "")
    return key if key in PLANES else None


def _holder_of(plane):
    """The coordinate system or origin that holds an App::Plane, or None."""
    for o in getattr(plane, "InList", None) or []:
        if plane in list(getattr(o, "OriginFeatures", None) or []):
            return o
    return None


def _plane_objects(body, ref, kinds):
    """The objects of kinds that ref names: the body's own first, then the
    document's; an exact name, an exact label, then a label in any case."""
    doc = body.Document
    pool = [o for o in doc.Objects if _is(o, kinds)]
    own = [o for o in pool if body.hasObject(o) or any(body.hasObject(h) for h in [_holder_of(o)] if h is not None)]
    low = str(ref).lower()
    for group in (own, pool):
        for how in ("name", "label", "case"):
            hits = [o for o in group if (o.Name == ref if how == "name" else o.Label == ref if how == "label" else o.Label.lower() == low)]
            if hits:
                return hits
    return []


def _csys_plane(body, cs, key, what):
    """A coordinate system's XY, XZ or YZ plane as a link, and its words."""
    out = "" if body.hasObject(cs) else f" (outside {body.Label}: a cross-reference)"
    pl = _role_feature(cs, PLANES[key])
    if pl is not None:
        return (pl, [""]), f"{cs.Label}.{PLANES[key]}{out}"
    if cs.TypeId == "PartDesign::CoordinateSystem" or not _is(cs, ("App::LocalCoordinateSystem",)):
        # no planes of its own: the sketch takes the system by ObjectXY | ObjectXZ | ObjectYZ (plane_mode)
        return (cs, [""]), f"{cs.Label}.{PLANES[key]} ({cs.Label} has no planes: Object{key}){out}"
    raise ToolError("failed", f"{what}: {cs.Label} has no {PLANES[key]}.")


def plane_mode(link, words=""):
    """The MapMode for a sketch on what plane_ref gave (link, words): FlatFace, or
    Object<XY|XZ|YZ> on a coordinate system with no planes of its own
    (PartDesign::CoordinateSystem)."""
    m = _CSYS_PLANE.search(words or "")
    if m and _is(link[0], CSYS_TYPES):
        return "Object" + m.group(1)
    return "FlatFace"


def plane_ref(body, ref, what="plane"):
    """XY | XZ | YZ, a datum plane's name (PartDesign or Part), a coordinate
    system's plane ("LCS.XZ_Plane", or the plane's own name), a whole
    coordinate system (its XY plane), or a face query {at, normal}: the
    (object, [sub]) a property links to, and what it is."""
    if isinstance(ref, str):
        key = _plane_key(ref)
        if key:
            return (origin_feature(body, PLANES[key]), [""]), key
        if "." in ref and ref.rsplit(".", 1)[1].startswith("Face"):
            # "Pad.Face3": that feature's face, as the reference names it.
            name, sub = ref.rsplit(".", 1)
            o = in_body(body, name, None, "feature")
            try:
                o.Shape.getElement(sub)
            except Exception:
                raise ToolError("invalid_input", f"{what}: {o.Label} has no {sub}.")
            return (o, [sub]), f"{o.Label}.{sub}"
        if "." in ref and _plane_key(ref.rsplit(".", 1)[1]):
            # "LCS.XZ_Plane", "Part.LCS.XY", "Body.YZ_Plane": the plane of that system or origin.
            head, tail = ref.rsplit(".", 1)
            key = _plane_key(tail)
            name = head.rsplit(".", 1)[-1]
            hits = _plane_objects(body, name, CSYS_TYPES + ("PartDesign::Body",))
            if not hits:
                raise ToolError("not_found", f"{what} {ref!r}: no coordinate system or body {name!r} — {_planes_there(body)}.")
            if len(hits) > 1:
                raise ToolError("invalid_input", f"{what} {ref!r}: {len(hits)} objects are labelled {name!r} ({', '.join(o.Name for o in hits)}) — give the name.")
            h = hits[0]
            if h.TypeId == "PartDesign::Body":
                return (origin_feature(h, PLANES[key]), [""]), f"{h.Label}.{PLANES[key]}"
            return _csys_plane(body, h, key, what)
        hits = _plane_objects(body, ref, PLANE_TYPES + CSYS_TYPES)
        if len(hits) > 1:
            def said(o):
                h = _holder_of(o)
                return f"{h.Label}.{o.Label}" if h is not None else o.Label
            raise ToolError("invalid_input", f"{what} {ref!r}: {len(hits)} planes have that label ({', '.join(said(o) for o in hits)}) — "
                                             "give \"LCS.XZ_Plane\" or the plane's name.")
        if not hits:
            raise ToolError("not_found", f"{what} {ref!r}: no datum plane, coordinate system or plane of that name — {_planes_there(body)}.")
        o = hits[0]
        if _is(o, CSYS_TYPES):
            # a whole coordinate system: its XY plane
            return _csys_plane(body, o, "XY", what)
        out = "" if body.hasObject(o) else f" (outside {body.Label}: a cross-reference)"
        h = _holder_of(o)
        if h is not None and getattr(h, "TypeId", "") != "App::Origin":
            role = getattr(o, "Role", "") or o.Label
            return (o, [""]), f"{h.Label}.{role}{'' if body.hasObject(h) else out}"
        return (o, [""]), f"{o.Label}{out}"
    if isinstance(ref, dict):
        tip, shape = tip_shape(body)
        i, f = find_face(shape, ref)
        own, j = face_owner(body, ref, tip, f)
        return (own, [f"Face{j + 1}"]), f"face at {geo.vec(f.CenterOfMass)}" + ("" if own is tip else f" ({own.Label}'s)")
    raise ToolError("invalid_input", f"{what}: XY, XZ, YZ, a datum plane's name (pd_datum_plane makes one), an LCS or its plane (\"LCS.XZ_Plane\"), "
                                     f"\"Pad.Face3\" as shape_query names it, or a face {{ at: [x,y,z], normal: [x,y,z] }}.")


def _planes_there(body):
    """The planes a sketch of this body can take, for a refusal."""
    doc = body.Document
    names = [o.Label for o in body.Group if _is(o, ("PartDesign::Plane", "Part::DatumPlane"))]
    names += [f"{o.Label}.XY_Plane" for o in doc.Objects if _is(o, CSYS_TYPES)]
    names += [o.Label for o in doc.Objects if _is(o, ("Part::DatumPlane",)) and o.Label not in names]
    return "there: XY, XZ, YZ" + (", " + ", ".join(names[:12]) if names else "")


def solid_features(body, upto=None):
    """The body's features with a solid, in the body's order, up to and
    including upto (the tip when left out)."""
    upto = upto if upto is not None else getattr(body, "Tip", None)
    out = []
    for o in list(body.Group):
        try:
            if o.isDerivedFrom("PartDesign::Feature") and not o.Shape.isNull() and o.Shape.Solids:
                out.append(o)
        except Exception:
            pass
        if o is upto:
            break
    return out


def same_face(a, b, tol=1e-4):
    """Two faces that are the same face: the same area, centre and edge
    count (a face a later feature left as it was)."""
    try:
        return (abs(a.Area - b.Area) <= tol * max(1.0, b.Area) and (a.CenterOfMass - b.CenterOfMass).Length <= tol
                and len(a.Edges) == len(b.Edges))
    except Exception:
        return False


def face_owner(body, ref, tip, face):
    """The feature that owns a face of the body: the one the reference names
    (feature: "Pad"), else the earliest feature in the body whose shape has
    that same face; the tip when no earlier one has it. Bound to the tip, a
    sketch's support pointed at a feature built after it (or at itself once
    the sketch's own feature became the tip), and FreeCAD warned on every
    recompute. (feature, face index)."""
    named = ref.get("feature") if isinstance(ref, dict) else None
    if named:
        o = in_body(body, named, None, "feature")
        i, _ = find_face(o.Shape, ref)
        return o, i
    for o in solid_features(body, tip):
        if o is tip:
            break
        try:
            i, g = find_face(o.Shape, ref)
        except ToolError:
            continue
        if same_face(g, face):
            return o, i
    i, _ = find_face(tip.Shape, ref)
    return tip, i


def _construction(sketch, i):
    try:
        return bool(sketch.getConstruction(i))
    except Exception:
        return False


def axis_ref(body, ref, sketch=None, what="axis"):
    """x | y | z (the body's origin axes), H_Axis | V_Axis of the sketch, or a
    sketch geometry id (a line, often construction)."""
    if isinstance(ref, str):
        key = ref.upper().replace("_AXIS", "")
        if key in AXES:
            return (origin_feature(body, AXES[key]), [""]), key.lower()
        if key in ("H", "V") and sketch is not None:
            return (sketch, [f"{key}_Axis"]), f"{sketch.Label} {key}_Axis"
        line = next((o for o in body.Group if o.TypeId == "PartDesign::Line" and ref in (o.Label, o.Name)), None)
        if line is not None:
            return (line, [""]), line.Label
    if isinstance(ref, int) and not isinstance(ref, bool) and sketch is not None:
        geo_ = sketch.Geometry
        if not (0 <= ref < len(geo_)):
            raise ToolError("invalid_input", f"{what}: geometry {ref} is not in {sketch.Label} (0 to {len(geo_) - 1}).")
        g = geo_[ref]
        if type(g).__name__ != "LineSegment":
            raise ToolError("invalid_input", f"{what}: geometry {ref} of {sketch.Label} is a {type(g).__name__}, not a line — a straight line's id (sketch_state lists them), or x | y | z | V_Axis | H_Axis.")
        # FreeCAD names a sketch's construction lines "Axis0", "Axis1" … in
        # their own count (SketchObject::getAxis), and reads "Edge3" on the
        # sketch's shape, which holds the profile's edges only: a geometry id
        # is neither (FeatureSketchBased.cpp, ProfileBased::getAxis).
        if _construction(sketch, ref):
            k = sum(1 for i in range(ref) if type(geo_[i]).__name__ == "LineSegment" and _construction(sketch, i))
            return (sketch, [f"Axis{k}"]), f"{sketch.Label} geometry {ref} (construction line {k})"
        pl = sketch.Placement
        a0, a1 = pl.multVec(g.StartPoint), pl.multVec(g.EndPoint)
        for i, e in enumerate(sketch.Shape.Edges):
            if len(e.Vertexes) == 2 and type(e.Curve).__name__ == "Line":
                p0, p1 = e.Vertexes[0].Point, e.Vertexes[1].Point
                if ((p0 - a0).Length < 1e-6 and (p1 - a1).Length < 1e-6) or ((p0 - a1).Length < 1e-6 and (p1 - a0).Length < 1e-6):
                    return (sketch, [f"Edge{i + 1}"]), f"{sketch.Label} geometry {ref}"
        raise ToolError("invalid_input", f"{what}: geometry {ref} of {sketch.Label} was not found among its profile's edges — make the axis a construction line (sketch_add {{ kind: line, construction: true }}).")
    raise ToolError("invalid_input", f"{what}: x, y, z (the body's axes)" + (", H_Axis or V_Axis (the sketch's), a line's geometry id in the sketch (a number, from 0)" if sketch is not None else "") + ", or a datum line's name (pd_datum { kind: line } makes one).")


# ---- faces and edges by where they are -----------------------------------------------------

def _normal_at(face, p):
    try:
        u, v = face.Surface.parameter(p)
        n = face.normalAt(u, v)
        return n if n.Length > 1e-12 else None
    except Exception:
        return None


def _angle(a, b):
    if a is None or a.Length < 1e-12 or b.Length < 1e-12:
        return 180.0
    c = max(-1.0, min(1.0, a.dot(b) / (a.Length * b.Length)))
    return math.degrees(math.acos(c))


def find_face(shape, q, tol=0.5):
    """The face a query names: at [x,y,z] on it (within tol mm), normal
    [x,y,z] outward there (within 15°). Returns (index, face)."""
    if not isinstance(q, dict) or "at" not in q:
        raise ToolError("invalid_input", "face: { at: [x,y,z] on the face, normal: [x,y,z] outward } — a point on it, not its index (indices change after edits).")
    p = vec3(q["at"], "face.at")
    n = vec3(q["normal"], "face.normal") if q.get("normal") is not None else None
    tol = float(q.get("tol", tol))
    vx = Part.Vertex(p)
    cands = []
    for i, f in enumerate(shape.Faces):
        d = f.distToShape(vx)[0]
        if d > max(tol, 5.0) * 4:
            continue
        nn = _normal_at(f, f.distToShape(vx)[1][0][0]) if d > 1e-9 else _normal_at(f, p)
        cands.append((d, i, f, nn))
    cands.sort(key=lambda c: c[0])
    for d, i, f, nn in cands:
        if d <= tol and (n is None or _angle(nn, n) <= 15.0):
            return i, f
    near = [{"center": geo.vec(f.CenterOfMass), "normal": geo.vec(nn) if nn is not None else None, "distance": round(d, 3)} for d, i, f, nn in cands[:5]]
    raise ToolError("not_found", f"No face within {tol} mm of {geo.vec(p)}" + (f" facing {geo.vec(n)}" if n is not None else "") + f". Nearest faces: {near or 'none'} — give a point on the face and its outward normal.")


EDGE_KEYS = ("near", "face", "all", "kind", "tol")
FACE_KEYS = ("at", "normal", "tol")


def _edges_legacy(shape, q):
    """The older edge forms: { near } the edge nearest a point (within 1
    mm), { face: { at, normal } } every edge of a face, { all: true };
    kind: line | circle filters any of them."""
    edges = shape.Edges
    if q.get("all"):
        idx = list(range(len(edges)))
    elif "near" in q:
        p = Part.Vertex(vec3(q["near"], "edges.near"))
        ds = sorted((e.distToShape(p)[0], i) for i, e in enumerate(edges))
        tol = float(q.get("tol", 1.0))
        if not ds or ds[0][0] > tol:
            close = [{"edge": geo.vec(edges[i].CenterOfMass), "distance": round(d, 3)} for d, i in ds[:4]]
            raise ToolError("not_found", f"No edge within {tol} mm of {q['near']}: nearest edges (their mid-points) {close} — give a point on the edge.")
        idx = [ds[0][1]]
    elif "face" in q:
        _, f = find_face(shape, q["face"])
        idx = [i for i, e in enumerate(edges) if any(e.isSame(fe) for fe in f.Edges)]
    else:
        raise ToolError("invalid_input", "edges: each one { near } | { face } | { all: true }, a reference (\"Edge3\", \"Body.Edge3\") or shape_query's filters.")
    kind = q.get("kind")
    if kind:
        want = {"line": "Line", "circle": "Circle"}.get(kind)
        if not want:
            raise ToolError("invalid_input", "edges.kind: line or circle.")
        idx = [i for i in idx if type(edges[i].Curve).__name__ == want]
    return [(f"Edge{i + 1}", edges[i]) for i in idx]


def find_edges(shape, queries, names=()):
    """Edge names (Edge1 …) for queries (families/refs.py): a reference
    "Edge3" / "Body.Edge3" (a face's reference: its edges), shape_query's
    filters, or the older { near: [x,y,z] } the edge nearest a point (within
    1 mm), { face: { at, normal } } every edge of a face, { all: true } every
    edge, kind: line | circle filtering any of them; one or a list."""
    from . import refs

    if not queries:
        raise ToolError("invalid_input", "edges: [{ near: [x,y,z] } | { face: { at, normal } } | { all: true } | \"Edge3\" | shape_query's filters { type, radius, axis, … }, …], kind: line | circle to filter.")
    try:
        got = refs.pick(shape, queries, "edge", "edges", legacy=lambda q: _edges_legacy(shape, q), is_legacy=refs.legacy_of(EDGE_KEYS), names=names)
    except ToolError as e:
        if e.message == "edges: nothing matched.":
            raise ToolError("not_found", "The queries matched no edge (kind filtered them all out?).") from None
        raise
    return [n for n, _ in got]


def find_faces(shape, queries, names=()):
    """Face names for queries (families/refs.py): a reference "Face8" /
    "Body.Face8", shape_query's filters, or the older { at: [x,y,z],
    normal: [x,y,z] } — by where they are; one or a list."""
    from . import refs

    if not queries:
        raise ToolError("invalid_input", "faces: [{ at: [x,y,z], normal: [x,y,z] } | \"Face8\" | shape_query's filters { type, normal, near, … }, …] — by where they are, not by index.")

    def legacy(q):
        i, f = find_face(shape, q)
        return [(f"Face{i + 1}", f)]

    return [n for n, _ in refs.pick(shape, queries, "face", "faces", legacy=legacy,
                                    is_legacy=refs.legacy_of(FACE_KEYS, lambda q: "at" in q), names=names)]


# ---- after a change ------------------------------------------------------------------------

def broken(doc):
    out = []
    for o in doc.Objects:
        try:
            ok = o.isValid()
        except Exception:
            ok = "Invalid" not in o.State
        if not ok:
            out.append({"object": o.Label, "type": short(o), "error": (o.getStatusString() if hasattr(o, "getStatusString") else "invalid")})
    return out


def newly_broken(doc):
    """broken(doc) less the objects that were already failing when the call
    in hand began (the hub's health check knows them: health.failing_before).
    What a guard refuses a change for: a change is not to blame for what
    was red before it, and a document with one old failure in it refused
    every guarded change (a cell set in a new, empty sheet, live)."""
    try:
        from .. import health

        was = health.failing_before(doc)
    except Exception:
        was = set()
    if not was:
        return broken(doc)
    labels = set()
    for o in doc.Objects:
        if o.Name in was:
            labels.add(o.Label)
    return [b for b in broken(doc) if b["object"] not in labels]


def body_reading(body):
    s = body.Shape
    if s is None or s.isNull() or not s.Solids:
        return {"body": body.Label, "solid": False}
    return {"body": body.Label, **geo.stats(s)}


def profile_words(feat):
    """Why a feature's sketch makes no face, or "": no geometry, an open
    outline, or outlines that cross or touch each other."""
    try:
        prof = getattr(feat, "Profile", None)
        sk = prof[0] if isinstance(prof, (list, tuple)) else prof
        if sk is None or not hasattr(sk, "Shape"):
            return ""
        name = sk.Label
        geo = [g for i, g in enumerate(getattr(sk, "Geometry", ()) or ()) if not sk.getConstruction(i)] if hasattr(sk, "getConstruction") else list(getattr(sk, "Geometry", ()) or ())
        if not geo:
            return f"The sketch {name} has no geometry (construction lines do not count): add the outline with sketch_add first."
        wires = list(sk.Shape.Wires)
        opened = [i for i, w in enumerate(wires) if not w.isClosed()]
        if opened:
            return f"The sketch {name} has {len(opened)} open outline{'s' if len(opened) > 1 else ''}: close each one (sketch_state names the open ends)."
        for i in range(len(wires)):
            for j in range(i + 1, len(wires)):
                if wires[i].distToShape(wires[j])[0] < 1e-6:
                    return (f"In the sketch {name}, two outlines cross or touch (outline {i + 1} and {j + 1}): a hole circle on the outer edge does this. "
                            "Move it inside the outline, or make it smaller.")
    except Exception:  # noqa: BLE001 - advice only
        return ""
    return ""


def settle(session, body, feat, tool, before=None, must_change=None, hint=""):
    """Recompute; refuse (the call's transaction is rolled back) if the
    feature or anything after it failed; else the body's reading."""
    doc = session.doc
    doc.recompute()
    bad = newly_broken(doc)  # not what was failing before the call
    if bad:
        mine = [b for b in bad if feat is not None and b["object"] == feat.Label]
        first = (mine or bad)[0]
        if not hint and ("edge link" in first["error"].lower() or "face link" in first["error"].lower() or "invalid link" in first["error"].lower()):
            # FreeCAD names a feature's edges and faces by the model before
            # it; a change upstream can leave a later feature's references
            # pointing at what is no longer there (worst in 1.0).
            hint = (f"{first['object']} refers to edges or faces of the model as it was, which the change renamed or removed. "
                    f"feature_remove {first['object']}, make the change, then add it again on the new edges (shape_query finds them; pd_fillet, pd_chamfer, pd_draft or pd_thickness).")
        if "shape object is empty" in first["error"].lower() or "wire is not closed" in first["error"].lower():
            # The profile makes no face (live, 22 Nov: a circle across the
            # outline's edge, twice): say why, from the sketch itself.
            why = profile_words(feat)
            if why:
                hint = (why + " " + hint).strip()
        if "multiple solids" in first["error"].lower():
            # FreeCAD 1.1: a body takes several solids only while its
            # AllowCompound is true (the default); with it off, a feature
            # that leaves two pieces is an error.
            hint = (f"The result would be more than one solid and {body.Label}'s AllowCompound is off: make the feature touch the rest of the body, "
                    f"or object_set {{ object: \"{body.Label}\", values: {{ AllowCompound: true }} }} first.")
        raise ToolError("failed", f"{first['object']} ({first['type']}) failed: {first['error']}" + (f"; also broken: {[b['object'] for b in bad if b is not first]}" if len(bad) > 1 else "") + f" — nothing was kept.{(' ' + hint) if hint else ''}")
    out = {**({"feature": feat.Label, "type": short(feat)} if feat is not None else {}), "valid": True, **body_reading(body)}
    if before is not None and "volume" in out:
        delta = out["volume"] - before
        out["volumeChange"] = round(delta, 2)
        if must_change == "add" and delta <= 1e-6:
            raise ToolError("failed", f"{feat.Label} added no material — it lies inside the body already. Nothing was kept. {hint}".strip())
        dress = feat is not None and getattr(feat, "TypeId", "") in DRESSUPS
        if must_change == "cut" and delta >= -1e-6:
            what = ("removed no material — the wall did not hollow the body" if dress
                    else "cut nothing — the profile does not meet the body that way")
            side = "" if dress else cut_side_words(feat, body)
            raise ToolError("failed", f"{feat.Label} {what}.{(' ' + side) if side else ''} Nothing was kept. {hint}".strip())
        if must_change == "changed" and abs(delta) <= 1e-6:
            # A fillet or chamfer may add material (an inside corner, concave)
            # or take it away (an outside one): only no change at all is wrong.
            raise ToolError("failed", f"{feat.Label} left the body as it was — the edges it was given round or bevel nothing. Nothing was kept. {hint}".strip())
    return picks.finish(session, tool, out, recompute=False)


def cut_side_words(feat, body):
    """Where a cut that cut nothing went, against where the body is: the
    sketch's normal, and the side of the sketch the body lies on (live,
    22 Nov: an agent found a pocket's side by trial, twice)."""
    try:
        prof = getattr(feat, "Profile", None)
        sk = prof[0] if isinstance(prof, (list, tuple)) else prof
        pl = sk.getGlobalPlacement() if hasattr(sk, "getGlobalPlacement") else sk.Placement
        import FreeCAD

        n = pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        bb = body.Shape.BoundBox
        c = FreeCAD.Vector((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, (bb.ZMin + bb.ZMax) / 2)
        side = (c - pl.Base).dot(n)
        axis = max(("x", abs(n.x), n.x), ("y", abs(n.y), n.y), ("z", abs(n.z), n.z), key=lambda t: t[1])
        normal = f"{'+' if axis[2] > 0 else '-'}{axis[0]}"
        rev = bool(getattr(feat, "Reversed", False))
        if abs(side) < 1e-6:
            return f"The sketch {sk.Label}'s normal is {normal}; the body's centre is in the sketch's plane."
        where = "on the side its normal points to" if side > 0 else "on the side opposite its normal"
        # A pocket goes against the normal, reversed along it.
        fix = (f" reversed: {'false' if rev else 'true'} sends the cut that way." if (side > 0) != rev else
               " The cut went toward the body: check that the sketch overlaps it (its position, not its side).")
        return f"The sketch {sk.Label}'s normal is {normal}, and the body is {where}." + fix
    except Exception:  # noqa: BLE001 - advice only
        return ""


def uses(o, f):
    """Whether object o refers to feature f by a property of its own (a
    profile, a base and its edges, originals, a support, an axis): the
    body's own bookkeeping (BaseFeature, the feature before it; _Body) does
    not count."""
    def has(v):
        if v is f:
            return True
        if isinstance(v, (list, tuple)):
            return any(has(x) for x in v)
        return False

    for p in o.PropertiesList:
        if p in ("BaseFeature", "_Body", "Group", "Tip"):
            continue
        try:
            if o.getTypeIdOfProperty(p).startswith(("App::PropertyLink", "App::PropertyXLink")) and has(getattr(o, p)):
                return True
        except Exception:
            continue
    # an expression that reads it (<<Pad>>.Length, Pad.Length)
    try:
        if any(f.Name in str(e) or f.Label in str(e) for _, e in (getattr(o, "ExpressionEngine", None) or [])):
            return True
    except Exception:
        pass
    return False


def volume(body):
    s = body.Shape
    return s.Volume if s is not None and not s.isNull() and s.Solids else 0.0


# ---- references that a change upstream renames ------------------------------------------
# A dress-up feature (fillet, chamfer, draft, thickness) names the edges or
# faces of the model before it as Edge8, Face3. Change a pad or a sketch
# and those names can land on other edges or none at all (FreeCAD 1.0
# especially). Before such a change each reference is read as what it is —
# kind, curve or surface, size, middle, direction — and if the change breaks
# the feature, every reference is found again by that, on the new model.

DRESSUPS = ("PartDesign::Fillet", "PartDesign::Chamfer", "PartDesign::Draft", "PartDesign::Thickness")


def _sig(shape, sub):
    name = sub.split(".")[-1]
    try:
        el = shape.getElement(name)
    except Exception:
        return None
    kind = "Edge" if name.startswith("Edge") else "Face" if name.startswith("Face") else None
    if kind is None:
        return None
    c = el.CenterOfMass if hasattr(el, "CenterOfMass") else el.BoundBox.Center
    if kind == "Edge":
        t = type(el.Curve).__name__
        d = None
        if t == "Line":
            v = el.Vertexes[-1].Point - el.Vertexes[0].Point
            d = v.normalize() if v.Length > 1e-9 else None
        elif hasattr(el.Curve, "Axis"):
            d = FreeCAD.Vector(el.Curve.Axis)
        return {"kind": kind, "type": t, "size": el.Length, "at": c, "dir": d}
    t = type(el.Surface).__name__
    try:
        u0, u1, v0, v1 = el.ParameterRange
        d = el.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    except Exception:
        d = None
    return {"kind": kind, "type": t, "size": el.Area, "at": c, "dir": d}


def ref_snapshot(body):
    """Each dress-up feature of the body, with what each of its references
    is, read on the model it is built on."""
    snap = []
    for f in getattr(body, "Group", []):
        if f.TypeId not in DRESSUPS or not getattr(f, "Base", None):
            continue
        base, subs = f.Base
        if base is None or base.Shape.isNull():
            continue
        sigs = [_sig(base.Shape, s) for s in subs]
        if all(sigs):
            snap.append({"feature": f, "base": base, "subs": list(subs), "sigs": sigs})
    return snap


def _match(shape, sig, taken, scale):
    cands = shape.Edges if sig["kind"] == "Edge" else shape.Faces
    best, best_score = None, None
    for i, el in enumerate(cands):
        name = f"{sig['kind']}{i + 1}"
        if name in taken:
            continue
        s = _sig(shape, name)
        if s is None or s["type"] != sig["type"]:
            continue
        if sig["dir"] is not None and s["dir"] is not None and abs(sig["dir"].dot(s["dir"])) < 0.995:
            continue
        score = (s["at"] - sig["at"]).Length + 0.25 * abs(s["size"] - sig["size"]) ** (0.5 if sig["kind"] == "Face" else 1)
        if best_score is None or score < best_score:
            best, best_score = name, score
    if best is None or best_score > 0.25 * scale:
        return None
    return best


def repair_refs(doc, snap):
    """Find each snapshotted feature's references again on its base's new
    model, where the old names broke. Returns what was moved, by feature:
    { feature: [[old, new], …] }, or None when a reference could not be
    found (nothing is changed then)."""
    moved = {}
    plans = []
    for e in snap:
        f, base = e["feature"], e["base"]
        shape = base.Shape
        if shape.isNull():
            return None
        scale = max(shape.BoundBox.DiagonalLength, 1e-6)
        taken, new = set(), []
        for old, sig in zip(e["subs"], e["sigs"]):
            m = _match(shape, sig, taken, scale)
            if m is None:
                return None
            taken.add(m)
            new.append(m)
        # Set again even where the name is the same: the link FreeCAD keeps
        # behind a name (1.0's element map) can be stale while the name is not.
        plans.append((f, base, new))
        moved[f.Label] = [[o.split(".")[-1], n] for o, n in zip(e["subs"], new) if o.split(".")[-1] != n] or "relinked"
    for f, base, new in plans:
        f.Base = (base, new)
    doc.recompute()
    return moved


# ---- datums attached to several references (the skeleton workflow) -------------------------
#
# A datum (point, line, plane, coordinate system) attached to one or more
# references of any object: a sketch, a SubShapeBinder, a datum, an LCS, a
# feature. FreeCAD's attacher (src/Mod/Part/App/Attacher.cpp, 1.1) reads the
# references in order; the default mode for a combination comes from its
# table of reference types per mode:
#   coordinate system / plane (AttachEngine3D)
#     vertex              Translate     origin at the vertex, axes as the global ones
#     vertex + edge       OZX           origin at the vertex, Z along the edge (start to end)
#     vertex + vertex     OZX           origin at the first, Z toward the second
#     vertex + 2 more     OZX           Z by the second, X by the third
#     vertex + circle     Concentric    origin at the circle's centre, Z on its axis
#     straight edge       NormalToEdge  Z along the edge, at its start
#     circle or arc       Concentric
#     flat face           FlatFace
#     face + vertex       TangentPlane
#     whole object        ObjectXY      the object's own placement
#   line (AttachEngineLine): straight edge or two vertices TwoPointLine, circle
#     AxisOfCurvature, two faces IntersectionLine, whole object ObjectZ
#   point (AttachEnginePoint): vertex Vertex, circle CenterOfCurvature, whole
#     object ObjectOrigin, other edges, faces and several vertices CenterOfMass

MODE_KIND = {"lcs": "csys"}


def _elem_kind(o, sub):
    """V vertex, E straight edge, C circle or arc, K other curve, F face, O whole object or a datum's own element."""
    if not sub:
        return "O"
    m = picks.SUB.match(sub)
    if not m:
        return "O"  # an LCS's own Origin, X_Axis, XY_Plane …
    sh = getattr(o, "Shape", None)
    if sh is None or sh.isNull():
        raise ToolError("invalid_state", f"{o.Label}.{sub}: {o.Label} has no shape to take {sub} from — give the whole object, or a binder, sketch or feature with a shape.")
    el = picks.element(sh, sub, o.Label)
    kind = m.group(1)
    if kind == "Vertex":
        return "V"
    if kind == "Face":
        return "F"
    try:
        c = el.Curve
        name = type(c).__name__
    except Exception:
        name = ""
    if name in ("Line", "LineSegment"):
        return "E"
    if name == "Circle":
        return "C"
    return "K"


def default_mode(kind, sig):
    """The attacher's mode for a datum kind and the references' kinds in
    order (a string of V E C K F O), and the order to give them in: a list of
    indexes. (None, None) when there is no plain choice: then mode is needed."""
    k = MODE_KIND.get(kind, kind)
    n = len(sig)
    order = list(range(n))
    if k in ("csys", "plane"):
        one = {"V": "Translate", "E": "NormalToEdge", "C": "Concentric", "K": "NormalToEdge", "F": "FlatFace", "O": "ObjectXY"}
        if n == 1:
            return one[sig], order
        if sorted(sig) in (["C", "V"],):
            return "Concentric", order
        if "V" in sig and 2 <= n <= 3 and all(c in "VE" for c in sig):
            v = sig.index("V")  # the origin first: the O-modes take it so
            return "OZX", [v] + [i for i in order if i != v]
        if sorted(sig) == ["F", "V"]:
            return "TangentPlane", order
        return None, None
    if k == "line":
        if sig in ("E", "VV"):
            return "TwoPointLine", order
        if sig == "C":
            return "AxisOfCurvature", order
        if sig == "FF":
            return "IntersectionLine", order
        if sig == "O":
            return "ObjectZ", order
        return None, None
    if k == "point":
        if sig == "V":
            return "Vertex", order
        if sig == "C":
            return "CenterOfCurvature", order
        if sig == "O":
            return "ObjectOrigin", order
        if all(c != "O" for c in sig) and n <= 4:
            return "CenterOfMass", order
        return None, None
    return None, None


def ref_object(doc, name, body=None):
    """The object a reference names, any kind, shown or hidden; one of the
    body's own first when two have that label."""
    if body is not None:
        for o in getattr(body, "Group", None) or []:
            if name in (o.Label, o.Name):
                return o
    return picks.named(doc, name, prefer=())


def attach_refs(doc, o, refs, mode=None, kind="csys", offset=None, body=None):
    """Attach the datum o to refs ["Obj.Vertex1", "Obj.Edge2", "Obj"] by
    mode (a FreeCAD MapMode), or by the default for the references (the
    table above). offset: the AttachmentOffset Placement. Returns
    { refs: [as kept, in order], mode }."""
    if not isinstance(refs, list) or not refs or len(refs) > 4 or not all(isinstance(r, str) and r for r in refs):
        raise ToolError("invalid_input", "refs: one to four references, \"Binder.Vertex3\", \"Skeleton.Edge2\" or a whole object \"Skeleton\" — a sketch, binder, datum, LCS or feature.")
    pairs, sig = [], ""
    for r in refs:
        head, sub = picks.split_ref(r)
        if head is None:
            raise ToolError("invalid_input", f"refs {r!r}: name the object too, \"Binder.{sub}\".")
        t = ref_object(doc, head, body)
        if t is None:
            raise ToolError("not_found", f"refs {r!r}: no object {head!r} — session_state names them; a binder or sketch by its label.")
        if t is o:
            raise ToolError("invalid_input", f"refs {r!r}: the datum cannot attach to itself.")
        sig += _elem_kind(t, sub)
        pairs.append((t, sub or ""))
    if mode:
        order, chosen = list(range(len(pairs))), str(mode)
    else:
        chosen, order = default_mode(kind, sig)
        if chosen is None:
            raise ToolError("invalid_input", f"refs: no plain mode for these references ({', '.join(refs)}) — give mode, a FreeCAD MapMode: "
                            "OZX (origin at a vertex, Z along an edge), ObjectXY, FlatFace, NormalToEdge, Concentric, Translate, TwoPointLine, CenterOfMass …")
    pairs = [pairs[i] for i in order]
    try:
        allowed = o.getEnumerationsOfProperty("MapMode") or []
    except Exception:
        allowed = []
    if allowed and chosen not in allowed:
        raise ToolError("invalid_input", f"mode {chosen!r}: not a FreeCAD attachment mode of this datum — its modes: {', '.join(allowed)}.")
    setattr(o, support_prop(o), pairs)
    o.MapMode = chosen
    if offset is not None:
        o.AttachmentOffset = offset
    return {"refs": [f"{t.Label}.{s}" if s else t.Label for t, s in pairs], "mode": chosen}


def world_json(o):
    """Where o is in the document's coordinates (its body or part's placement applied)."""
    try:
        p = o.getGlobalPlacement()
    except Exception:
        p = o.Placement
    return picks.placement_json(p)
