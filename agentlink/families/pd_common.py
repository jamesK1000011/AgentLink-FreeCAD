# SPDX-License-Identifier: LGPL-2.1-or-later
# What the sketch, feature and param families share: finding a PartDesign
# body, its origin planes and axes, its features and sketches; faces and
# edges found by where they are (a point, a normal) rather than by index;
# and one reading of a body after a change. Written for FreeCAD's public
# Python API, tolerant of the property renames between releases
# (Support -> AttachmentSupport, Midplane -> SideType).

import math

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


def vec2(a, what):
    if not (isinstance(a, (list, tuple)) and len(a) == 2 and all(isinstance(x, (int, float)) for x in a)):
        raise ToolError("invalid_input", f"{what}: [x, y] in mm, in the sketch's own coordinates.")
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


def plane_ref(body, ref, what="plane"):
    """XY | XZ | YZ, a datum plane's name, or a face query {at, normal}: the
    (object, [sub]) a property links to, and what it is."""
    if isinstance(ref, str):
        key = ref.upper().replace("_PLANE", "")
        if key in PLANES:
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
        o = in_body(body, ref, ["PartDesign::Plane"], "datum plane")
        return (o, [""]), o.Label
    if isinstance(ref, dict):
        tip, shape = tip_shape(body)
        i, f = find_face(shape, ref)
        own, j = face_owner(body, ref, tip, f)
        return (own, [f"Face{j + 1}"]), f"face at {geo.vec(f.CenterOfMass)}" + ("" if own is tip else f" ({own.Label}'s)")
    raise ToolError("invalid_input", f"{what}: XY, XZ, YZ, a datum plane's name (pd_datum_plane makes one), \"Pad.Face3\" as shape_query names it, or a face {{ at: [x,y,z], normal: [x,y,z] }}.")


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
            raise ToolError("failed", f"{feat.Label} {what}. Nothing was kept. {hint}".strip())
        if must_change == "changed" and abs(delta) <= 1e-6:
            # A fillet or chamfer may add material (an inside corner, concave)
            # or take it away (an outside one): only no change at all is wrong.
            raise ToolError("failed", f"{feat.Label} left the body as it was — the edges it was given round or bevel nothing. Nothing was kept. {hint}".strip())
    return picks.finish(session, tool, out, recompute=False)


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
