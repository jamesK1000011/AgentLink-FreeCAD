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
from ..protocol import ToolError, describe
from . import picks
from .. import facesel

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
            got = f" You gave {describe(a)}."
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


# Which sketch a tool takes when none is named (local fixes, 23 Nov,
# decision 4; rule R2: no other guess): (1) the sketch open in edit in the
# window, else (2) the sketch this session's agent made last (its last
# sketch_new), else (3) the only sketch there is, else a refusal that lists
# the sketches: unused first, newest first, each marked "(not used)" or
# "(used by Pad)". A sketch taken by this rule is said in the answer's
# filled (agentlink/protocol.py): took() puts it on the session.

def sketch_users(sk):
    """Labels of what uses a sketch (a feature, not the body or a group)."""
    out = []
    for p in getattr(sk, "InList", None) or []:
        t = str(getattr(p, "TypeId", "") or "")
        if t.startswith(("PartDesign::Body", "App::")):
            continue
        out.append(str(p.Label))
    return out


def sketch_list(sketches):
    """The sketches in words: unused first, newest first, each marked."""
    order = list(reversed(list(sketches)))
    unused = [o for o in order if not sketch_users(o)]
    used = [o for o in order if sketch_users(o)]
    return ", ".join([f"{o.Label} (not used)" for o in unused] + [f"{o.Label} (used by {', '.join(sketch_users(o))})" for o in used])


def sketch_in_edit(doc):
    """The sketch of doc open in edit in the window, or None (no GUI too)."""
    try:
        if not getattr(FreeCAD, "GuiUp", False):
            return None
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        o = getattr(gd.getInEdit(), "Object", None) if gd is not None else None
    except Exception:
        return None
    if o is None or getattr(o, "TypeId", "") != "Sketcher::SketchObject" or getattr(o, "Document", None) is not doc:
        return None
    return o


def note_made_sketch(session, sk, asked=None):
    """Record sk as the sketch this session's agent made last (sketch_new).
    asked: the name the call gave. When another object had it, sk got
    "asked 2" (Session.unique, as every tool that makes an object does): the
    answer's filled says so, and the later calls of the same batch that
    name asked get sk (26 Nov QA: they drew into the old sketch)."""
    if session is None or sk is None:
        return
    if isinstance(asked, str) and asked and sk.Label != asked and not _dry():
        got = getattr(session, "filled_now", None)
        if isinstance(got, list):
            got.append(f"name={sk.Label} (the name {asked} was taken; this sketch is {sk.Label})")
        alias = session.__dict__.get("_batch_aliases") if hasattr(session, "__dict__") else None
        if isinstance(alias, dict):
            try:
                alias[(sk.Document.Name, asked)] = sk.Name
            except Exception:  # noqa: BLE001
                pass
    if getattr(session, "by", "agent") != "agent":
        return
    try:
        rec = getattr(session, "made_sketch", None)
        if not isinstance(rec, dict):
            rec = session.made_sketch = {}
        rec[sk.Document.Name] = sk.Name
    except Exception:
        pass


def renamed_sketch(session, doc, ref):
    """The sketch that sketch_new made in this batch in place of the taken
    name ref, or None."""
    try:
        alias = session.__dict__.get("_batch_aliases") if session is not None else None
        name = alias.get((doc.Name, ref)) if isinstance(alias, dict) else None
        return doc.getObject(name) if name else None
    except Exception:  # noqa: BLE001
        return None


def made_sketch(session, doc):
    """The sketch this session's agent made last in doc, if it is still there."""
    try:
        name = (getattr(session, "made_sketch", None) or {}).get(doc.Name)
        return doc.getObject(name) if name else None
    except Exception:
        return None


def _dry():
    try:
        from .. import needs

        return needs.dry()
    except Exception:
        return False


def took(session, sk, why):
    """Say in the answer's filled which sketch a left-out sketch took. Only
    the call's own answer notes; nothing in a dry reading (needs.py)."""
    got = getattr(session, "filled_now", None) if session is not None else None
    if isinstance(got, list) and not _dry():
        got.append(f"sketch={sk.Label} ({why})")


def note_named(session, sk):
    """Keep the first sketch a call works on: the used-sketch note reads it.
    Only the call's own answer notes; nothing in a dry reading (needs.py)."""
    if session is None or _dry():
        return
    try:
        if getattr(session, "sketch_now", None) is None and isinstance(getattr(session, "filled_now", None), list):
            session.sketch_now = sk
    except Exception:
        pass


def sketch_of(doc, ref, body=None, session=None):
    sk = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
    if ref is None:
        if body is not None:
            sk = [o for o in sk if body.hasObject(o)]
        if session is not None:
            for o, why in ((sketch_in_edit(doc), "open in edit in the window"), (made_sketch(session, doc), "you made it last")):
                if o is not None and any(o is x for x in sk):
                    took(session, o, why)
                    note_named(session, o)
                    return o
        if len(sk) == 1:
            if session is not None:
                took(session, sk[0], "the only sketch" + (f" in {body.Label}" if body is not None else ""))
                note_named(session, sk[0])
            return sk[0]
        where = f" in {body.Label}" if body is not None else ""
        if not sk:
            raise ToolError("invalid_input", f"sketch: there is no sketch{where} yet. sketch_new makes one.")
        why = "No sketch is open in edit, and you made none here. " if session is not None else ""
        raise ToolError("invalid_input", f"sketch: say which. {why}The sketches{where}, unused first and newest first: {sketch_list(sk)}.")
    o = renamed_sketch(session, doc, ref)
    if o is not None and any(o is x for x in sk):
        note_named(session, o)
        return o
    for o in sk:
        if ref in (o.Label, o.Name) or o.Label.lower() == str(ref).lower():
            note_named(session, o)
            return o
    # 24 Nov (Gemma: "Sketch1" for "Sketch 2"): the same ordered, marked
    # list as say-which, and where the names come from.
    if not sk:
        raise ToolError("not_found", f"sketch {ref!r}: no such sketch — there is none yet: sketch_new makes one.")
    raise ToolError("not_found", f"sketch {ref!r}: no such sketch. The sketches, unused first and newest first: {sketch_list(sk)}. "
                                 "Use a name exactly as sketch_new's answer gives it (sketch) or as now lists it.")


def profile_users(sk):
    """Labels of the features whose profile is sketch sk (their Profile
    link: a Pad, Pocket, Revolution, Groove, Hole …)."""
    out = []
    for p in getattr(sk, "InList", None) or []:
        prof = getattr(p, "Profile", None)
        if isinstance(prof, (tuple, list)):
            prof = prof[0] if prof else None
        if prof is sk:
            out.append(str(p.Label))
    return out


def used_sketch_note(sk, body=None, tool=None):
    """For a change to the geometry of a sketch that a feature uses (decision
    4, D-b): words that name the feature, and the body's unused sketch when
    it has one; else None. Blind QA, 24 Nov: holes were added to the sketch
    of a Pad, then that sketch was pocketed, and the pocket cut nothing."""
    users = sketch_users(sk)
    if not users:
        return None
    body = body if body is not None else body_of(sk)
    if body is None:
        return None
    free = [o for o in reversed(list(getattr(body, "Group", None) or [])) if getattr(o, "TypeId", "") == "Sketcher::SketchObject"
            and o is not sk and not sketch_users(o)]
    if not free:
        prof = profile_users(sk)
        doing = "adding to it" if tool == "sketch_add" else "this change"
        if prof:
            return f"Note: {sk.Label} is the profile of {', '.join(prof)}; {doing} changes {', '.join(prof)}."
        return f"Note: {sk.Label} is used by {', '.join(users)}; {doing} changes {', '.join(users)}."
    names = ", ".join(o.Label for o in free[:3])
    return (f"{sk.Label} is used by {', '.join(users)}, so this change also changes {', '.join(users)}. "
            f"{body.Label} also has a sketch that is not used: {names}. "
            f"If you meant {free[0].Label}, use history_undo, then give sketch: \"{free[0].Label}\".")


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
            _owner_ok(o, sub, what)
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
        i, f = find_face(shape, ref, body=body)
        own, j = face_owner(body, ref, tip, f)
        # Checked before the sketch is bound to it (decision 5, 23 Nov): a
        # broken feature, or a face that is not there, gives a lost face.
        _owner_ok(own, f"Face{j + 1}", what)
        try:
            there = own.Shape.getElement(f"Face{j + 1}") is not None
        except AttributeError:
            there = True  # a shape with no getElement: nothing to check
        except Exception:
            there = False
        if not there:
            raise ToolError("invalid_state", f"{what}: {own.Label} has no Face{j + 1} now. Its faces changed. "
                                             f"Find the face again: {facesel.FORMS}.")
        return (own, [f"Face{j + 1}"]), f"face at {geo.vec(f.CenterOfMass)}" + ("" if own is tip else f" ({own.Label}'s)")
    raise ToolError("invalid_input", f"{what}: XY, XZ, YZ, a datum plane's name (pd_datum_plane makes one), an LCS or its plane (\"LCS.XZ_Plane\"), "
                                     f"\"Pad.Face3\" as shape_query names it, or a face {{ side: \"+z\" }} or {{ at: [x,y,z], normal: [x,y,z] }}.")


def _owner_ok(own, sub, what):
    """Refuse a face of a feature that failed its recompute."""
    try:
        ok = own.isValid()
    except Exception:
        ok = True
    if not ok:
        raise ToolError("invalid_state", f"{what}: {own.Label} is broken now (it failed to recompute). "
                                         f"So its {sub} cannot hold a sketch. Repair {own.Label} first, or use a plane: XY, XZ or YZ.")


def status_words(o):
    """FreeCAD's status of a failed object, in plain words where known."""
    try:
        raw = o.getStatusString()
    except Exception:
        raw = "invalid"
    from .. import fusehint

    return fusehint.plain_error(o, raw)


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
        i, _ = find_face(o.Shape, ref, body=body)
        return o, i
    for o in solid_features(body, tip):
        if o is tip:
            break
        try:
            i, g = find_face(o.Shape, ref, body=body)
        except ToolError:
            continue
        if same_face(g, face):
            return o, i
    i, _ = find_face(tip.Shape, ref, body=body)
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


def face_descs(shape, pl=None):
    """The shape's faces as facesel describes them (center, a point on the
    face, outward normal there, area, type); pl: a placement to carry them
    into another shape's frame."""
    out = []
    for f in shape.Faces:
        c = f.CenterOfMass
        at = c
        try:
            d, pts, _ = f.distToShape(Part.Vertex(c))
            if d > 1e-6:
                at = pts[0][0]
        except Exception:
            pass
        n = _normal_at(f, at)
        if pl is not None:
            c, at = pl.multVec(c), pl.multVec(at)
            n = pl.Rotation.multVec(n) if n is not None else None
        out.append({"center": [c.x, c.y, c.z], "at": [at.x, at.y, at.z], "normal": [n.x, n.y, n.z] if n is not None else None,
                    "area": f.Area, "type": facesel.surface_type(type(f.Surface).__name__)})
    return out


def _body_named(names):
    doc = FreeCAD.ActiveDocument
    for b in (pd_bodies(doc) if doc is not None else []):
        if b.Label in names or b.Name in names:
            return b
    return None


def _mark_of(shape, descs, of, body=None, names=()):
    """descs again, with of among the owners of the faces it made: those on
    its AddSubShape (a PartDesign feature), else on its shape; the body:
    all of them."""
    body = body if body is not None else _body_named(names)
    if of in names or (body is not None and of in (body.Label, body.Name)):
        return facesel.with_owner(descs, set(range(len(descs))), of)
    if body is not None:
        o = in_body(body, of, None, "face.of")
    else:
        doc = FreeCAD.ActiveDocument
        o = None
        if doc is not None:
            o = doc.getObject(of) or next(iter(doc.getObjectsByLabel(of)), None)
        if o is None:
            raise ToolError("not_found", f"face.of {of!r}: no feature or body of that name.")
    # A PartDesign feature's Shape is the whole body up to it: the faces it
    # made are those on its AddSubShape (the solid it added or cut).
    theirs = None
    for prop in ("AddSubShape", "Shape"):
        t = getattr(o, prop, None)
        if t is not None and not t.isNull() and t.Faces:
            theirs = t
            break
    if theirs is None:
        # A sketch's name for of (live s1126e: of: "Base", the sketch the pad
        # was made from): name the feature that uses it.
        users = [u for u in (getattr(o, "InList", None) or [])
                 if getattr(getattr(u, "Profile", None), "__iter__", None) and o in list(u.Profile or [])[:1]]
        if getattr(o, "TypeId", "") == "Sketcher::SketchObject":
            made = f' Its feature is {users[0].Label}: of: "{users[0].Label}".' if users else ""
            raise ToolError("invalid_input", f"face.of {of!r}: {o.Label} is a sketch; of takes the feature made from it, or leave of out.{made}")
        raise ToolError("invalid_input", f"face.of {of!r}: {o.Label} has no faces — a feature with a solid, or the body.")
    pl = shape.Placement * theirs.Placement.inverse()
    back = pl.inverse()
    owned = set()
    for i, j in facesel.owner_pairs(descs, face_descs(theirs, pl)):
        if i not in owned and theirs.Faces[j].distToShape(Part.Vertex(back.multVec(FreeCAD.Vector(*descs[i]["at"]))))[0] <= 1e-4:
            owned.add(i)
    return facesel.with_owner(descs, owned, of)


def _by_selector(shape, q, body=None, names=()):
    """(index, descs) of the one face a selector names on the shape."""
    descs = face_descs(shape)
    _, of, _ = facesel.check(q)
    if of is not None:
        descs = _mark_of(shape, descs, of, body, names)
    return facesel.select(descs, q), descs


def find_face(shape, q, tol=0.5, body=None, names=()):
    """The face a query names: at [x,y,z] on it (within tol mm), normal
    [x,y,z] outward there (within 15°); or a selector { side: "+z", of,
    largest } (facesel.py) that must match one face. Returns (index, face).
    body / names: the body, to read a selector's of."""
    if facesel.is_selector(q):
        i, _ = _by_selector(shape, q, body, names)
        return i, shape.Faces[i]
    if not isinstance(q, dict) or "at" not in q:
        raise ToolError("invalid_input", f"{facesel.FORMS} — not its index or name (they change after edits).")
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


def face_pick(body, ref):
    """The form that picks the face ref names on the body's solid, for an
    answer the next call can copy: { side, … } when one picks it alone,
    else { at, normal }."""
    _, shape = tip_shape(body)
    sel = facesel.is_selector(ref)
    if sel:
        i, descs = _by_selector(shape, ref, body)
    else:
        i, _ = find_face(shape, ref, body=body)
        descs = face_descs(shape)
    return facesel.copyable(descs, i, ref if sel else None)


def face_pick_said(body, ref):
    """face_pick's form, and with it which face a { side } selector took
    when it had a choice, in words (facesel.pick_words; None when it had
    none, or for { at, normal })."""
    _, shape = tip_shape(body)
    if not facesel.is_selector(ref):
        return face_pick(body, ref), None
    i, descs = _by_selector(shape, ref, body)
    return facesel.copyable(descs, i, ref), facesel.pick_words(descs, i, ref)


EDGE_KEYS = ("near", "face", "all", "kind", "tol")
FACE_KEYS = ("at", "normal", "tol")


def _edges_legacy(shape, q, names=()):
    """The older edge forms: { near } the edge nearest a point (within 1
    mm), { face: { at, normal } } every edge of a face, { all: true };
    kind: line | circle filters any of them."""
    unknown = sorted(k for k in q if k not in EDGE_KEYS) if isinstance(q, dict) else []
    if unknown:
        # 24 Nov QA: an unknown key (position) was dropped without a word,
        # and the wrong edges were rounded. No key is guessed or left out.
        from .refs import FILTER_KEYS

        raise ToolError("invalid_input", f"edges: {', '.join(unknown)} is not a key of an edge query. Keys: {', '.join(EDGE_KEYS)}; "
                                         f"or shape_query's filters ({', '.join(sorted(FILTER_KEYS))}). Nothing was changed.")
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
        _, f = find_face(shape, q["face"], names=names)
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
        raise ToolError("invalid_input", "edges: [{ near: [x,y,z] } | { face: { side: \"+z\" } or { at, normal } } | { all: true } | \"Edge3\" | shape_query's filters { type, radius, axis, … }, …], kind: line | circle to filter.")
    try:
        got = refs.pick(shape, queries, "edge", "edges", legacy=lambda q: _edges_legacy(shape, q, names), is_legacy=refs.legacy_of(EDGE_KEYS), names=names)
    except ToolError as e:
        if e.message == "edges: nothing matched.":
            raise ToolError("not_found", "The queries matched no edge (kind filtered them all out?).") from None
        raise
    return [n for n, _ in got]


EDGES_SHOWN = 12  # edges an answer describes one by one; the rest are counted
EDGES_SIDED = 200  # edges sorted into outside and inside; past this, not


def _num_word(x):
    x = round(float(x), 2)
    return str(int(x)) if x == int(x) else f"{x:g}"


def _dir_word(d):
    """"x", "-z" … for a direction along an axis (within 1°), else [x, y, z]."""
    for i, ax in enumerate("xyz"):
        if abs(d[i]) >= math.cos(math.radians(1.0)):
            return ax
    return "[" + ", ".join(_num_word(c) for c in d) + "]"


def edge_words(shape, names, cap=EDGES_SHOWN):
    """Each edge of names on shape in a short line: "Edge9: line along y,
    60 mm, mid [40, 0, 0]" (24 Nov QA: an answer that named the edges only
    let a wrong choice of edges pass unseen). At most cap lines, then how
    many more there are. Each line ends with outside or inside when it is
    known (26 Nov QA), and the first line counts them: "8 edges: 4 outside
    (lose material), 4 inside (gain material)"."""
    from .measure import describe_edge

    edges = shape.Edges
    sides = edge_sides(shape, names)
    out = []
    for k, n in enumerate(names[:cap]):
        try:
            i = int(str(n)[4:])
            d = describe_edge(edges[i - 1], i)
        except Exception:  # noqa: BLE001 - a name that is not an edge stays as it is
            out.append(str(n))
            continue
        t = d.get("type", "edge")
        if t == "line" and d.get("dir"):
            what = f"line along {_dir_word(d['dir'])}"
        elif "radius" in d:
            what = f"{'circle' if d.get('closed') else 'arc'} r {_num_word(d['radius'])} mm about {_dir_word(d['axis'])}"
        else:
            what = t
        side = f", {sides[k]}" if sides and sides[k] else ""
        out.append(f"{n}: {what}, {_num_word(d['length'])} mm, mid [{', '.join(_num_word(c) for c in d['mid'])}]{side}")
    if len(names) > cap:
        out.append(f"… and {len(names) - cap} more edges ({len(names)} in all)")
    head = sides_line(sides)
    return ([head] if head else []) + out


def edge_sides(shape, names):
    """"outside", "inside" or None for each edge of names on shape
    (measure.edge_side); [] when there are too many to look at."""
    if len(names) > EDGES_SIDED:
        return []
    from .measure import edge_side

    edges = shape.Edges
    out = []
    for n in names:
        try:
            out.append(edge_side(shape, edges[int(str(n)[4:]) - 1]))
        except Exception:  # noqa: BLE001 - not an edge: not known
            out.append(None)
    return out


def sides_line(sides):
    """"8 edges: 4 outside (lose material), 4 inside (gain material)", or
    "" when no edge's side is known."""
    o, i = sides.count("outside"), sides.count("inside")
    if not o and not i:
        return ""
    parts = []
    if o:
        parts.append(f"{o} outside (lose material)")
    if i:
        parts.append(f"{i} inside (gain material)")
    rest = len(sides) - o - i
    if rest:
        parts.append(f"{rest} smooth or not known")
    return f"{len(sides)} edge{'s' if len(sides) != 1 else ''}: " + ", ".join(parts)


def find_faces(shape, queries, names=()):
    """Face names for queries (families/refs.py): a reference "Face8" /
    "Body.Face8", shape_query's filters, or the older { at: [x,y,z],
    normal: [x,y,z] } — by where they are; one or a list."""
    from . import refs

    if not queries:
        raise ToolError("invalid_input", "faces: [{ side: \"+z\" } | { at: [x,y,z], normal: [x,y,z] } | \"Face8\" | shape_query's filters { type, normal, near, … }, …] — by where they are, not by index.")

    def legacy(q):
        i, f = find_face(shape, q, names=names)
        return [(f"Face{i + 1}", f)]

    old = refs.legacy_of(FACE_KEYS, lambda q: "at" in q)
    return [n for n, _ in refs.pick(shape, queries, "face", "faces", legacy=legacy,
                                    is_legacy=lambda q: facesel.is_selector(q) or old(q), names=names)]


# ---- after a change ------------------------------------------------------------------------

def broken(doc):
    out = []
    for o in doc.Objects:
        try:
            ok = o.isValid()
        except Exception:
            ok = "Invalid" not in o.State
        if not ok:
            out.append({"object": o.Label, "type": short(o), "error": (status_words(o) if hasattr(o, "getStatusString") else "invalid")})
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


def dressup_valid(body):
    """False only when the body's shape is there and FreeCAD's check says it
    is not valid; a shape too large to check in time counts as valid."""
    try:
        sh = body.Shape
        if sh is None or sh.isNull():
            return True
        from ..health import FACES_VALID

        if len(sh.Faces) > FACES_VALID:
            return True
        return bool(sh.isValid())
    except Exception:  # noqa: BLE001 - not known: not refused
        return True


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


# A card's hint to check the sketch fits an error about the sketch or its
# profile only (24 Nov QA: it came after "Up to face: Must not intersect
# sketch" and "BRep_API: command not done", which are not).
SKETCH_CHECK = "Check the sketch with sketch_state"
SKETCH_ERROR = re.compile(r"not closed|open (?:wire|edge|vert)|shape object is empty|(?:sketch|profile) is empty|empty (?:sketch|profile)"
                          r"|self.?intersect|face from (?:the )?(?:sketch|profile)|(?:sketch|profile) has no face|no faces? (?:in|from) (?:the )?(?:sketch|profile)"
                          r"|(?:make|create|creating) (?:a )?face", re.I)
# FreeCAD's up-to-face checks (FeatureSketchBased): what each one means.
UP_TO_WORDS = (
    (re.compile(r"up to face: must not intersect sketch", re.I),
     "The face to go up to touches the sketch (often it is the face that the sketch is on). "
     "Choose a face away from the sketch, in the direction of the feature, or use extent length."),
    (re.compile(r"up to face: must not be parallel", re.I),
     "The face to go up to is parallel to the direction of the feature, so the feature never meets it. Choose a face across that direction."),
)


def sketch_error(error):
    """Whether FreeCAD's error is about the sketch or its profile."""
    return bool(SKETCH_ERROR.search(str(error or "")))


def fit_hint(hint, error=""):
    """hint without its sentence to check the sketch when the error is not
    about the sketch; the rest as it was."""
    if not hint or SKETCH_CHECK not in hint or sketch_error(error):
        return hint
    parts = [p for p in re.split(r"(?<=[;.])\s+", hint) if SKETCH_CHECK not in p]
    return re.sub(r";$", ".", " ".join(parts).strip())


_CONNECTOR_END = re.compile(r"(?:\s*(?:[,;:]|\b(?:or|and|then|with)\b))+\s*$", re.I)


def drop_phrase(text, phrase):
    """text without the clauses that say phrase (the refusal said it once
    already). Clauses are the parts of a sentence between semicolons. A
    clause keeps its words before phrase, less a last "or", "and", comma or
    colon; a sentence with nothing left goes. So no sentence is cut mid-way
    (26 Nov run: "put the sketch on the face it enters, or." from "…, or
    reversed: true.")."""
    if not text or phrase not in text:
        return text
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text.strip()):
        if phrase not in s:
            out.append(s)
            continue
        end = s[-1] if s[-1] in ".!?" else "."
        kept = []
        for c in re.split(r"\s*;\s*", s[:-1] if s[-1] in ".!?" else s):
            if phrase in c:
                c = _CONNECTOR_END.sub("", c[:c.find(phrase)]).strip()
            if c:
                kept.append(c)
        if kept:
            out.append("; ".join(kept) + end)
    return " ".join(out)


def settle(session, body, feat, tool, before=None, must_change=None, hint=""):
    """Recompute; refuse (the call's transaction is rolled back) if the
    feature or anything after it failed; else the body's reading."""
    from ..protocol import NAMES_NOTHING

    doc = session.doc
    doc.recompute()
    bad = newly_broken(doc)  # not what was failing before the call
    if bad:
        mine = [b for b in bad if feat is not None and b["object"] == feat.Label]
        first = (mine or bad)[0]
        hint = fit_hint(hint, first["error"])
        known = sketch_error(first["error"])  # the sketch hint says what to change
        for pat, words in UP_TO_WORDS:
            if pat.search(first["error"]):
                hint, known = words, True
        later = feat is None or first["object"] != feat.Label  # a feature after this one broke
        if (not hint or later) and ("edge link" in first["error"].lower() or "face link" in first["error"].lower() or "invalid link" in first["error"].lower()):
            # FreeCAD names a feature's edges and faces by the model before
            # it; a change upstream can leave a later feature's references
            # pointing at what is no longer there (worst in 1.0).
            hint = (f"{first['object']} refers to edges or faces of the model as it was, which the change renamed or removed. "
                    f"feature_remove {first['object']}, make the change, then add it again on the new edges (shape_query finds them; pd_fillet, pd_chamfer, pd_draft or pd_thickness).")
            known = True
        if "shape object is empty" in first["error"].lower() or "wire is not closed" in first["error"].lower():
            # The profile makes no face (live, 22 Nov: a circle across the
            # outline's edge, twice): say why, from the sketch itself.
            why = profile_words(feat)
            if why:
                hint = (why + " " + hint).strip()
            known = True
        if "multiple solids" in first["error"].lower():
            # FreeCAD 1.1: a body takes several solids only while its
            # AllowCompound is true (the default); with it off, a feature
            # that leaves two pieces is an error.
            hint = (f"The result would be more than one solid and {body.Label}'s AllowCompound is off: make the feature touch the rest of the body, "
                    f"or object_set {{ object: \"{body.Label}\", values: {{ AllowCompound: true }} }} first.")
            known = True
        if not known:
            hint = (hint + " " + NAMES_NOTHING).strip()
        raise ToolError("failed", f"{first['object']} ({first['type']}) failed: {first['error']}" + (f"; also broken: {[b['object'] for b in bad if b is not first]}" if len(bad) > 1 else "") + f" — nothing was kept.{(' ' + hint) if hint else ''}")
    hint = fit_hint(hint)
    if feat is not None and getattr(feat, "TypeId", "") in DRESSUPS and not dressup_valid(body):
        # 24 Nov QA: a fillet that FreeCAD computed without an error left a
        # shape that is not valid (2 solids, NOT valid), and the answer said
        # ok; the health line said broken only after it.
        raise ToolError("failed", f"{feat.Label} ({short(feat)}) made a shape that is not valid (FreeCAD's shape check), though it gave no error — nothing was kept. "
                                  f"{hint or 'Try a smaller size, or fewer edges.'}".strip())
    out = {**({"feature": feat.Label, "type": short(feat)} if feat is not None else {}), "valid": True, **body_reading(body)}
    if "box" in out:
        # Where the body is, not only its size (24 Nov QA: a centred
        # sketch on XZ gave the right size 40 as z -20..20, in 7 of 9 runs).
        try:
            out["bounds"] = span_text(body.Shape.BoundBox)
        except Exception:  # noqa: BLE001 - a reading only
            pass
    if before is not None and "volume" in out:
        delta = out["volume"] - before
        out["volumeChange"] = round(delta, 2)
        # No change within the noise of FreeCAD's volume on a curved body
        # (24 Nov QA: five cuts that removed nothing came back ok with
        # volumeChange -0.0, as the test of 1e-6 let the noise through).
        tol = max(0.01, 1e-7 * max(abs(before), abs(out["volume"])))
        if must_change == "add" and delta <= tol:
            raise ToolError("failed", f"{feat.Label} added no material — it lies inside the body already. Nothing was kept. {hint}".strip())
        dress = feat is not None and getattr(feat, "TypeId", "") in DRESSUPS
        if must_change == "cut" and delta >= -tol:
            what = ("removed no material — the wall did not hollow the body" if dress
                    else "cut nothing — the profile does not meet the body that way")
            side = "" if dress else cut_side_words(feat, body)
            if side:
                # The side words say which way (or that the outline is beside
                # the body): the card's own reversed words would say it twice,
                # or point away from the fix (26 Nov QA).
                hint = drop_phrase(hint, "reversed: true")
            raise ToolError("failed", f"{feat.Label} {what}.{(' ' + side) if side else ''} Nothing was kept. {hint}".strip())
        if must_change == "changed" and abs(delta) <= tol:
            # A fillet or chamfer may add material (an inside corner, concave)
            # or take it away (an outside one): only no change at all is wrong.
            raise ToolError("failed", f"{feat.Label} left the body as it was — the edges it was given round or bevel nothing. Nothing was kept. {hint}".strip())
        if feat is not None:
            out.update(where_went(feat, body, delta, tol))
            if "where" in out:
                # The one plain sentence first (owner, 25 Nov: a small model reads
                # the top of an ok answer and moves on; the numbers follow it).
                head = {k: out[k] for k in ("feature", "type") if k in out}
                out = {**head, "where": out["where"], **{k: v for k, v in out.items() if k not in head and k != "where"}}
    out = with_changed(session, body, out, before)
    if out.get("volume") is not None:
        note_answered(session, body)
    return picks.finish(session, tool, out, recompute=False)


def note_answered(session, body):
    """This answer gives body's reading (volume, box, solids) after the
    recompute: the session counts it as a measure of that body once the
    change is kept (Session.note_answered; agentlink/measured.py)."""
    try:
        got = session.__dict__.get("_answered")
        if isinstance(got, list):
            got.append(body.Label)
    except Exception:  # noqa: BLE001 - a stand-in session
        pass


# ---- what changed since the body's last reading (owner, 25 Nov) ----------------------------
# Each feature's answer gives the whole body again (volume, area, faces,
# solids, box, bounds); a small model read the same numbers each step and
# missed the one that moved. changed says only what moved, from the last
# reading of the same body in this conversation.

CHANGED_KEYS = ("volume", "faces", "solids", "box", "bounds")


def _num(x):
    return f"{round(x, 2):g}"


def changed_words(old, new):
    """What moved from one body reading to the next, in one short line:
    "volume +5250, box z 5→40, faces 6→14"; "" when nothing did."""
    parts = []
    try:
        if isinstance(old.get("volume"), (int, float)) and isinstance(new.get("volume"), (int, float)):
            d = new["volume"] - old["volume"]
            if abs(d) > max(0.01, 1e-7 * max(abs(old["volume"]), abs(new["volume"]))):
                parts.append(f"volume {'+' if d > 0 else '-'}{_num(abs(d))}")
        ob, nb = old.get("box"), new.get("box")
        if isinstance(ob, (list, tuple)) and isinstance(nb, (list, tuple)) and len(ob) == len(nb) == 3:
            moved = [f"{ax} {_num(a)}→{_num(b)}" for ax, a, b in zip("xyz", ob, nb) if abs(b - a) > 1e-3]
            if moved:
                parts.append("box " + ", ".join(moved))
        for k in ("faces", "solids"):
            if isinstance(old.get(k), int) and isinstance(new.get(k), int) and old[k] != new[k]:
                parts.append(f"{k} {old[k]}→{new[k]}")
        if old.get("bounds") and new.get("bounds") and old["bounds"] != new["bounds"] and not any(p.startswith("box ") for p in parts):
            parts.append(f"bounds now {new['bounds']}")  # moved, the same size
    except Exception:  # noqa: BLE001 - a reading only
        return ""
    return ", ".join(parts)


def with_changed(session, body, out, before):
    """out with changed right after where (or after feature and type),
    from the last reading of this body kept in the session; the reading
    kept for the next one. No line on the body's first reading, or when the
    body changed since it by another way (before, the volume when this
    call began, is not the kept one): the line would compare with the
    wrong shape. Never raises."""
    try:
        from .. import once

        kept = once.state(session).setdefault("bodies", {})
        key = (getattr(getattr(body, "Document", None), "Name", ""), body.Name)
        last = kept.get(key)
        kept[key] = {k: out[k] for k in CHANGED_KEYS if k in out}
        if not last or before is None or not isinstance(last.get("volume"), (int, float)):
            return out
        if abs(last["volume"] - before) > max(0.01, 1e-6 * max(abs(before), 1.0)):
            return out
        words = changed_words(last, out)
        if not words:
            return out
        lead = [k for k in ("feature", "type", "where") if k in out]
        return {**{k: out[k] for k in lead}, "changed": words, **{k: v for k, v in out.items() if k not in lead}}
    except Exception:  # noqa: BLE001 - a reading only
        return out


# ---- where a feature's material went (24 Nov QA) -------------------------------------------
# A feature's answer gave the body's size and volume change, never where the
# change was: an upright padded across the middle of a base, holes cut below
# it, a hollow made from the top and the wrong edges rounded all answered as
# if right. One boolean (after less before, or before less after) says where.

WHERE_FACES = 4000  # faces of the two shapes together: past this, not worked out
WHERE_LIDS = 40  # faces of the removed region looked at for where it opens


def _r(x):
    v = round(x, 2)
    return 0.0 if v == 0 else v


def span_text(bb):
    """A bounding box as one short line: "x -30..30, y -15..15, z 0..5"."""
    return f"x {_r(bb.XMin):g}..{_r(bb.XMax):g}, y {_r(bb.YMin):g}..{_r(bb.YMax):g}, z {_r(bb.ZMin):g}..{_r(bb.ZMax):g}"


def beyond_sides(new, old, tol=1e-3):
    """The sides of the old box the new box goes past, as ["-z", "+z"]
    (boxes as xmin, xmax, ymin, ymax, zmin, zmax)."""
    out = []
    for i, ax in enumerate("xyz"):
        if new[2 * i] < old[2 * i] - tol:
            out.append(f"-{ax}")
        if new[2 * i + 1] > old[2 * i + 1] + tol:
            out.append(f"+{ax}")
    return out


def side_word(normal, point):
    """"+z at z 10" for a face whose normal runs along an axis; else
    "normal [0.71, 0, 0.71] at [x, y, z]"."""
    ax = max(range(3), key=lambda i: abs(normal[i]))
    if abs(normal[ax]) > 0.999:
        name = "xyz"[ax]
        return f"{'+' if normal[ax] > 0 else '-'}{name} at {name} {_r(point[ax]):g}"
    return f"normal [{', '.join(f'{_r(c):g}' for c in normal)}] at [{', '.join(f'{_r(c):g}' for c in point)}]"


def _bbt(bb):
    return (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)


def where_went(feat, body, delta, tol=0.01):
    """{added: "x .., y .., z ..", beyond: [sides]} or {removed: …, opens:
    [faces of the body it breaks through]}, from the body before the
    feature (its BaseFeature) and after, and where: the same in one
    sentence, against the body before (26 Nov QA: no model read the terse
    fields). A sketch of several profiles adds profiles: what each one did.
    {} when there was no body before (the first feature: bounds says it
    all). Large bodies: {where: why not}."""
    try:
        base = getattr(feat, "BaseFeature", None)
        old = getattr(base, "Shape", None) if base is not None else None
        new = body.Shape
        if old is None or old.isNull() or not old.Solids or new is None or new.isNull():
            return {}
        if getattr(feat, "TypeId", "") in ("PartDesign::Fillet", "PartDesign::Chamfer"):
            # A round or a bevel says its edges (on); its region is slivers
            # along them, whose box is the whole body: noise.
            return {}
        if len(old.Faces) + len(new.Faces) > WHERE_FACES:
            return {"where": f"not worked out: the body has more than {WHERE_FACES // 2} faces"}
        if delta > 0:
            reg = new.cut(old)
            if reg.isNull() or reg.Volume <= tol:
                return {}
            nb, ob = _bbt(reg.BoundBox), _bbt(old.BoundBox)
            out = {"added": span_text(reg.BoundBox), "beyond": beyond_sides(nb, ob), "where": added_sentence(nb, ob)}
            apart = loose_sentence(old, new)
            if apart:
                out["where"] = apart + " " + out["where"]
            out.update(profile_results(feat, reg, old, tol, cut=False))
            return out
        reg = old.cut(new)
        if reg.isNull() or reg.Volume <= tol:
            return {}
        out = {"removed": span_text(reg.BoundBox)}
        diag = max(old.BoundBox.DiagonalLength, 1.0)
        # The old body's surface, not its solid: a point inside a solid is at
        # distance 0 from it (live, 25 Nov: a hollow's inner walls were listed).
        skin = Part.Compound(list(old.Faces))
        lids, sides = _lids(reg, skin, diag)
        out["opens"] = lids or ["nothing: the cut is closed inside the body"]
        out["where"] = removed_sentence(sides, _bbt(reg.BoundBox))
        pieces = [x for x in reg.Solids if x.Volume > tol]
        if len(pieces) > 1:
            # 26 Nov QA: two notches in one pocket came back as one box that
            # "goes all the way through along x". Each piece apart.
            out["where"] = pieces_sentence(pieces, skin, diag)
        out.update(profile_results(feat, reg, old, tol, cut=True))
        return out
    except Exception as e:  # noqa: BLE001 - a reading only
        return {"where": f"not worked out ({type(e).__name__})"}


PIECES_SHOWN = 4  # separate pieces of one cut said one by one


def _lids(reg, skin, diag):
    """(the side words, side_key's) of the faces of the removed region reg
    that lie on the old body's surface skin: where the cut opens the body."""
    lids, sides = [], []
    for f in list(reg.Faces)[:WHERE_LIDS]:
        # A face of the removed region that lies on the body's old
        # surface is where the cut opens the body; the others are the
        # new walls inside it.
        try:
            u0, u1, v0, v1 = f.ParameterRange
            p = f.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
            if not f.isInside(p, 1e-6, True):
                p = f.CenterOfMass
            if skin.distToShape(Part.Vertex(p))[0] > 1e-4 * diag:
                continue
            n = f.normalAt(*f.Surface.parameter(p))
            # Outward from the removed region (and so from the old body)
            # whatever the face's orientation: a step along it is outside.
            step = 1e-3 * diag
            if reg.isInside(p + n * step, 1e-7, False):
                n = -n
            w = side_word((n.x, n.y, n.z), (p.x, p.y, p.z))
        except Exception:  # noqa: BLE001 - one face not read
            continue
        if w not in lids:
            lids.append(w)
            sides.append(side_key((n.x, n.y, n.z), (p.x, p.y, p.z)))
    return lids, sides


def pieces_sentence(pieces, skin, diag):
    """"2 separate cuts: x -15..-10, y …: the cut opens on +y …; …" for a
    removed region in several solids."""
    words = []
    for x in pieces[:PIECES_SHOWN]:
        _w, sides = _lids(x, skin, diag)
        said = removed_sentence(sides, _bbt(x.BoundBox))
        words.append(f"{span_text(x.BoundBox)}: {said[0].lower()}{said[1:].rstrip('.')}")
    more = f"; and {len(pieces) - PIECES_SHOWN} more" if len(pieces) > PIECES_SHOWN else ""
    return f"{len(pieces)} separate cuts: " + "; ".join(words) + more + "."


def _g(x):
    return f"{_r(x):g}"


OWNER = "the body's"


def loose_sentence(old, new):
    """The words when added material does not join the body: the body has
    more solids after the feature than before. With AllowCompound true (the
    default in FreeCAD 1.1) the feature is still valid, and health says
    "valid" (live, 25 Nov: an upright drawn beside a plate, not on it, and
    the model went on). None when the count did not go up."""
    try:
        before, after = len(old.Solids), len(new.Solids)
    except Exception:  # noqa: BLE001
        return None
    if after <= before:
        return None
    return (f"It does not touch the body: it is a separate solid, and the body is now {after} pieces. "
            "To join it, start the shape inside bodyExtent of the sketch, or move it until it meets the body.")


def added_sentence(new, old, tol=1e-3):
    """Where added material goes against the body before it, in one
    sentence: "The new material goes 20 mm below the body's bottom (z 0)
    and 15 mm above its top (z 5)." (boxes as xmin, xmax, ymin, ymax,
    zmin, zmax)."""
    words = []
    for i, ax in enumerate("xyz"):
        lo, hi = old[2 * i], old[2 * i + 1]
        if new[2 * i] < lo - tol:
            how, what = ("below", "bottom") if ax == "z" else ("past", f"-{ax} side")
            words.append((lo - new[2 * i], how, what, ax, lo))
        if new[2 * i + 1] > hi + tol:
            how, what = ("above", "top") if ax == "z" else ("past", f"+{ax} side")
            words.append((new[2 * i + 1] - hi, how, what, ax, hi))
    if not words:
        return "The new material is inside the body's box before."
    said = [f"{_g(d)} mm {how} {'its' if k else OWNER} {what} ({ax} {_g(at)})"
            for k, (d, how, what, ax, at) in enumerate(words)]
    return "The new material goes " + _and(said) + "."


def _and(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def side_key(normal, point):
    """(axis index, +1 or -1, coordinate) for a face whose normal runs along
    an axis; None for a slanted or curved one."""
    ax = max(range(3), key=lambda i: abs(normal[i]))
    if abs(normal[ax]) > 0.999:
        return (ax, 1 if normal[ax] > 0 else -1, point[ax])
    return None


def removed_sentence(sides, reg):
    """Where a cut opens the body, in one sentence, from side_key's of the
    faces it opens and the removed region's box (xmin, xmax, …): "The cut
    goes all the way through along z.", "The cut opens on +z (z 10) and
    goes 7 mm deep.", "The cut is closed inside the body."."""
    if not sides:
        return "The cut is closed inside the body."
    keyed = [k for k in sides if k is not None]
    slant = len(sides) - len(keyed)
    signs = {}
    for ax, sg, at in keyed:
        signs.setdefault(ax, {})[sg] = at
    through = [ax for ax in sorted(signs) if len(signs[ax]) == 2]
    ends = [(ax, sg, at) for ax in sorted(signs) if ax not in through for sg, at in sorted(signs[ax].items(), reverse=True)]
    deep = [(f"{'+' if sg > 0 else '-'}{'xyz'[ax]} ({'xyz'[ax]} {_g(at)})", _g(reg[2 * ax + 1] - reg[2 * ax])) for ax, sg, at in ends]
    parts = []
    if through:
        parts.append("goes all the way through along " + _and(["xyz"[ax] for ax in through]))
    if len(deep) == 1 and not through and not slant:
        parts.append(f"opens on {deep[0][0]} and goes {deep[0][1]} mm deep")
    elif deep:
        parts.append("opens on " + ", and on ".join(f"{w}, {d} mm deep" for w, d in deep))
    if slant:
        parts.append(f"opens on {'a' if slant == 1 else slant} slanted or curved face{'s' if slant > 1 else ''}")
    return "The cut " + _and(parts) + "."


PROFILES_SHOWN = 12  # profiles of one sketch looked at one by one
NOT_CUT = "holesNotCut"  # profile_results' count for pd_hole's answer, taken out by holes_cut
PROFILE_FEATURES = ("PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Hole")


def profile_faces(feat):
    """[(words, face)] for each profile (outline with its holes) of a pad's,
    pocket's or hole's sketch, when it has more than one; else []."""
    if getattr(feat, "TypeId", "") not in PROFILE_FEATURES:
        return []
    sk = _profile_of(feat)
    if sk is None or "Sketch" not in getattr(sk, "TypeId", ""):
        return []
    wires = [w for w in sk.Shape.Wires if w.isClosed()]
    if len(wires) < 2:
        return []
    try:
        faces = list(Part.makeFace(wires, "Part::FaceMakerBullseye").Faces)
    except Exception:  # noqa: BLE001 - older FreeCAD
        faces = list(Part.Face(wires, "Part::FaceMakerBullseye").Faces)
    if len(faces) < 2:
        return []
    inv = sk.Placement.inverse()
    out = []
    for f in faces:
        edges = f.OuterWire.Edges
        c = inv.multVec(f.CenterOfMass)
        at = f"({_g(c.x)}, {_g(c.y)})"
        if len(edges) == 1 and type(edges[0].Curve).__name__ == "Circle":
            out.append((f"the circle r {_g(edges[0].Curve.Radius)} at {at}", f))
        else:
            out.append((f"the outline at {at}", f))
    return out


def profile_results(feat, reg, old, tol, cut=True):
    """{profiles: "2 profiles: the circle r 2.5 at (45, 0) is off the body;
    1 cut."} for a sketch of several profiles (26 Nov QA: one hole of two
    was off the part, and nothing said so); {} for one profile, or on any
    error. A profile did something when its prism along the sketch's
    normal meets the region the feature added or removed."""
    try:
        got = profile_faces(feat)
        if not got:
            return {}
        n_all = len(got)
        got = got[:PROFILES_SHOWN]
        bb = old.BoundBox
        span = 2 * max(bb.DiagonalLength, reg.BoundBox.DiagonalLength, 1.0) + bb.Center.Length + reg.BoundBox.Center.Length
        verb = "cut" if cut else "added"
        idle, idle_circles = [], 0
        for words, f in got:
            n = f.normalAt(0, 0)
            prism = f.translated(n * -span).extrude(n * (2 * span))
            if prism.common(reg).Volume > tol:
                continue
            idle_circles += words.startswith("the circle")
            if not cut:
                idle.append(f"{words} adds nothing (inside the body already)")
            elif prism.common(old).Volume > tol:
                idle.append(f"{words} cut nothing")
            else:
                idle.append(f"{words} is off the body")
        did = len(got) - len(idle)
        head = f"{n_all} profiles" + (f" ({len(got)} looked at)" if n_all > len(got) else "")
        if not idle:
            return {"profiles": f"{head}: {'both' if did == 2 else 'all ' + str(did)} {verb}."}
        out = {"profiles": f"{head}: " + "; ".join(idle) + f"; {did} {verb}."}
        if getattr(feat, "TypeId", "") == "PartDesign::Hole":
            # The holes not drilled (26 Nov QA: "holes: 2" when one circle of
            # two was off the body): pd_hole's answer counts only those cut
            # (holes_cut). FreeCAD keeps such a hole feature, so no refusal.
            out[NOT_CUT] = idle_circles
        return out
    except Exception:  # noqa: BLE001 - a reading only: left out
        return {}


def holes_cut(spots, out):
    """pd_hole's holes: the spots the sketch gives, less the circles that
    cut nothing (profile_results); that count is taken out of the answer."""
    try:
        return max(int(spots) - int(out.pop(NOT_CUT, 0) or 0), 0)
    except Exception:  # noqa: BLE001
        return spots


def _profile_of(o):
    prof = getattr(o, "Profile", None)
    return prof[0] if isinstance(prof, (list, tuple)) and prof else prof


def outside_words(sk, bb, n):
    """Words when the sketch's outline lies beside the body along an axis
    of the sketch's plane (world axes, the normal's axis left out), or ""."""
    try:
        pb = sk.Shape.BoundBox
    except Exception:  # noqa: BLE001
        return ""
    return outside_text(sk.Label, (pb.XMin, pb.XMax, pb.YMin, pb.YMax, pb.ZMin, pb.ZMax),
                        (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), (n.x, n.y, n.z))


def outside_text(label, prof, body, normal, tol=1e-6):
    """Plain-number form of outside_words (profile and body boxes as
    xmin, xmax, ymin, ymax, zmin, zmax; normal x, y, z)."""
    words = []
    for i, ax in enumerate("xyz"):
        if abs(normal[i]) > 0.9:  # the axis the cut goes along
            continue
        plo, phi, blo, bhi = prof[2 * i], prof[2 * i + 1], body[2 * i], body[2 * i + 1]
        if phi < blo - tol or plo > bhi + tol:
            words.append(f"the outline lies at {ax} {plo:g} to {phi:g}; the body spans {ax} {blo:g} to {bhi:g}")
    if not words:
        return ""
    return (f"The sketch {label}'s outline is beside the body, not over it: " + "; ".join(words) +
            ". Move the outline over the body (its position, not its direction).")


def cut_side_words(feat, body):
    """Where a cut that cut nothing went, against where the body is: the
    sketch's normal, and the side of the sketch the body lies on (live,
    22 Nov: an agent found a pocket's side by trial, twice)."""
    try:
        prof = getattr(feat, "Profile", None)
        sk = prof[0] if isinstance(prof, (list, tuple)) else prof
        pl = sk.getGlobalPlacement() if hasattr(sk, "getGlobalPlacement") else sk.Placement
        import FreeCAD

        # The sketch is another feature's profile already (live, 22 Nov: holes
        # drilled from the pad's own sketch, 14 times): it needs its own.
        others = [o for o in (getattr(sk, "InList", None) or ()) if o is not feat and _profile_of(o) is sk]
        if others:
            return (f"The sketch {sk.Label} is the profile of {others[0].Label} already, so it lies on the body's own face. "
                    "A hole or pocket needs a sketch of its own, on the face it goes into: sketch_new { face: { at, normal } }, then sketch_add.")
        n = pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        bb = body.Shape.BoundBox
        # First: does the outline lie over the body at all, across the
        # sketch's plane? (live, 23 Nov: holes at y +15 beside a plate at
        # y -30..0 got the direction words three times.)
        off = outside_words(sk, bb, n)
        if off:
            return off
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
