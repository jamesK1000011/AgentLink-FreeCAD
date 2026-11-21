# SPDX-License-Identifier: LGPL-2.1-or-later
# What the doc, model and measure tools share: finding an object by name or
# label, reading a reference to its geometry ("Face12", "Box.Edge3", a
# point), placements from JSON, and values made JSON-safe. Not a family of
# its own (it is not in NAMES).

import math
import re

import FreeCAD
import Part

from .. import geometry as geo
from ..protocol import ToolError

V = FreeCAD.Vector
SUB = re.compile(r"^(Face|Edge|Vertex)(\d+)$")

def num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ToolError("invalid_input", f"{name}: a number.")
    return float(v)


def num_json(v, nd=4):
    """A property's value as JSON (output; num checks input): Quantities as
    their number (mm, degrees), floats rounded to nd places."""
    if hasattr(v, "Value") and not isinstance(v, (int, float)):
        return round(float(v.Value), nd) + 0.0
    if isinstance(v, float):
        return round(v, nd) + 0.0
    return v


def choice(a, key, options, msg, default=None):
    """a[key] (default when it is absent), one of options; else the site's
    refusal msg (invalid_input)."""
    v = a.get(key, default)
    if v not in options:
        raise ToolError("invalid_input", msg)
    return v


def ref_list(v, msg=None):
    """One name or a list of them, as a list. msg: the refusal
    (invalid_input) when there is none; without it, none passes through."""
    if isinstance(v, str):
        v = [v]
    if msg is not None and not v:
        raise ToolError("invalid_input", msg)
    return v


def r4(v):
    return round(float(v), 4) + 0.0


def number(a, key, default=None, *, gt=None, ge=None, le=None, msg=None, what=None):
    """a[key] (default when it is absent) as a number (num, named what or
    key), then a range: outside gt/ge/le it refuses invalid_input with msg,
    the site's own words."""
    v = num(a.get(key, default), what or key)
    if (gt is not None and v <= gt) or (ge is not None and v < ge) or (le is not None and v > le):
        raise ToolError("invalid_input", msg or f"{what or key}: out of range.")
    return v


def vec3(v, name, default=None):
    if v is None:
        if default is None:
            raise ToolError("invalid_input", f"{name}: [x, y, z], mm.")
        return V(*default)
    if isinstance(v, str):
        axes = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1), "x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}
        if v.lower() in axes:
            return V(*axes[v.lower()])
    if isinstance(v, list) and len(v) == 2:
        v = list(v) + [0]
    if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        raise ToolError("invalid_input", f"{name}: [x, y, z] (or +x, -z …).")
    return V(*[float(x) for x in v])


def direction(v, name, default=None):
    d = vec3(v, name, default)
    if d.Length < 1e-12:
        raise ToolError("invalid_input", f"{name}: not [0, 0, 0] — a direction.")
    return d.normalize()


def placement(a):
    """at [x,y,z] and a rotation — rotate { axis, angle } or axis and angle
    beside at (degrees) — into a Placement. Tools list one or the other;
    either is taken, so a rotation given is never dropped."""
    pos = vec3(a.get("at"), "at", (0, 0, 0))
    rot = FreeCAD.Rotation()
    r = a.get("rotate")
    if r is None and (a.get("axis") is not None or a.get("angle") is not None):
        r = {"axis": a.get("axis"), "angle": a.get("angle", 0)}
    if r:
        if not isinstance(r, dict):
            raise ToolError("invalid_input", "rotate: { axis: [x,y,z], angle: degrees }.")
        rot = FreeCAD.Rotation(direction(r.get("axis"), "rotate.axis", (0, 0, 1)), num(r.get("angle", 0), "rotate.angle"))
    return FreeCAD.Placement(pos, rot)


def placed(a):
    """Whether a placement was asked for at all: at, axis, angle or rotate."""
    return any(a.get(k) is not None for k in ("at", "axis", "angle", "rotate"))


def placement_json(p):
    ax = p.Rotation.Axis
    return {"at": geo.vec(p.Base), "axis": geo.vec(ax), "angle": round(math.degrees(p.Rotation.Angle), 4)}


# ---- finishing a change ------------------------------------------------------------------

def _invalid(o):
    return hasattr(o, "isValid") and not o.isValid()


def recompute_scoped(doc, objs):
    """Recompute objs and what is built from them (FreeCAD adds what they are
    built from, when that needs it) — not the rest of the document. A whole
    recompute after a call also re-ran objects the call never touched (one
    left touched, a heavy mesh), so a small change took as long as they did.
    The count recomputed; the whole document when objs is empty or this
    FreeCAD takes no list."""
    todo = {}
    for o in objs or ():
        try:
            todo.setdefault(o.Name, o)
            for p in o.InListRecursive:
                todo.setdefault(p.Name, p)
        except Exception:
            continue
    if not todo:
        return doc.recompute()
    try:
        return doc.recompute(list(todo.values()))
    except TypeError:
        return doc.recompute()


def finish(session, tool, read=None, *, objs=(), refuse=None, broken=_invalid, check=None, doc=None, recompute=True, extra=None, step=True):
    """The tail every changing tool shares. Recompute (doc, the session's by
    default), refuse a broken result with nothing kept, one snapshot, then
    the answer and the step. read: the answer, a dict or a callable run after
    the snapshot so it reads the recomputed model. refuse: when broken(o) for
    any of objs, each of objs is removed and the refusal is refuse with {msg}
    the first broken one's status and {kind} its type. check: a callable run
    after the recompute that refuses by itself."""
    d = session.doc if doc is None else doc
    if recompute:
        d.recompute()
    if refuse is not None:
        bad_ = [o for o in objs if broken(o)]
        if bad_:
            msg, kind = bad_[0].getStatusString(), bad_[0].TypeId.split("::")[-1]
            for o in objs:
                try:
                    d.removeObject(o.Name)
                except Exception:
                    pass
            raise ToolError("failed", refuse.replace("{kind}", kind).replace("{msg}", msg))
    if check is not None:
        check()
    session.snapshot(tool)
    out = read() if callable(read) else ({} if read is None else read)
    if extra:
        out.update(extra)
    if step:
        out["step"] = len(session.steps)
    return out


def one_of(pool, ref, which, missing, none=None, nocase=False):
    """The one of pool that ref names (its label or name; nocase: the label in
    any case too), or the only one when ref is None. Each site keeps its own
    words: none (not_found) when pool is empty, which (invalid_input) when
    ref is None and there are several, missing (not_found) when ref names
    none of them; {labels} in them is the labels, {ref} ref's repr."""
    if none is not None and not pool:
        raise ToolError("not_found", none)
    labels = ", ".join(o.Label for o in pool)
    if ref is None:
        if len(pool) == 1:
            return pool[0]
        raise ToolError("invalid_input", which.replace("{labels}", labels))
    # The internal Name before the Label (a Name never changes; a label can be
    # another object's name), then the label in any case, then a label the
    # object had before object_rename (bicycle runs of 20 Nov: "FrameW" was
    # not found after the body got the label "Frame").
    for o in pool:
        if o.Name == ref:
            return o
    for o in pool:
        if o.Label == ref:
            return o
    if nocase:
        for o in pool:
            if o.Label.lower() == str(ref).lower():
                return o
    try:
        was = former(getattr(pool[0], "Document", None) if pool else None, ref)
    except Exception:  # noqa: BLE001
        was = None
    if was is not None and was in pool:
        return was
    raise ToolError("not_found", re.sub(r"\{(ref|labels)\}", lambda m: repr(ref) if m[1] == "ref" else labels, missing))


# ---- objects ----------------------------------------------------------------------------

BODY = "PartDesign::Body"


def named(doc, ref, prefer=(BODY,)):
    """The object that ref names in doc, shown or hidden, or None. An exact
    Name first, then an exact Label, then a Label or Name that differs only
    in case. Among the Label matches, an object of a type in prefer (a
    PartDesign Body) comes first: a hidden body is found by its label even
    when its tip feature or a sketch has a near label (test drive of 20
    Nov, finding 13: hidden sprocket bodies were not found)."""
    if not isinstance(ref, str) or not ref:
        return None
    try:
        o = doc.getObject(ref)
    except Exception:
        o = None
    if o is not None:
        return o
    objs = list(getattr(doc, "Objects", None) or [])
    low = ref.lower()
    for exact in (True, False):
        hits = [x for x in objs if (str(getattr(x, "Label", "")) == ref if exact
                                    else str(getattr(x, "Label", "")).lower() == low or str(getattr(x, "Name", "")).lower() == low)]
        if hits:
            return next((x for x in hits if getattr(x, "TypeId", "") in prefer), hits[0])
    return None


# Labels that objects had before object_rename: {(document name, old label):
# object Name}. A tool given the old label still finds the object, when no
# object has that label or name now. Kept for the session only.
FORMER = {}


def keep_former(o, old):
    """Note that o had the label old (object_rename)."""
    try:
        if old and old != o.Label:
            FORMER[(o.Document.Name, old)] = o.Name
    except Exception:  # noqa: BLE001 - a note only
        pass


def former(doc, ref):
    """The object that had the label ref before object_rename, or None."""
    if doc is None or not isinstance(ref, str):
        return None
    try:
        name = FORMER.get((doc.Name, ref))
        return doc.getObject(name) if name else None
    except Exception:  # noqa: BLE001
        return None


def find(doc, ref, what="object"):
    if not isinstance(ref, str) or not ref:
        raise ToolError("invalid_input", f"{what}: an object's name or label.")
    o = doc.getObject(ref)
    if o is not None:
        return o
    hits = doc.getObjectsByLabel(ref) or [x for x in doc.Objects if x.Label.lower() == ref.lower()]
    if hits:
        return hits[0]
    o = former(doc, ref)
    if o is not None:
        return o
    names = ", ".join(x.Label for x in doc.Objects[:30]) or "none"
    raise ToolError("not_found", f"{what} {ref!r}: not here — the objects: {names}.")


def shaped(doc, ref, what="body"):
    o = find(doc, ref, what)
    sh = getattr(o, "Shape", None)
    if sh is None or sh.isNull():
        raise ToolError("invalid_state", f"{o.Label} has no shape ({o.TypeId}): a mesh becomes a body with import_file {{ solid: true }}.")
    return o


def solid_body(session, ref):
    """A body with solids: session.body() for its refusals, by name too."""
    if ref is not None:
        o = shaped(session.doc, ref)
        if not o.Shape.Solids:
            raise ToolError("invalid_state", f"{o.Label} has no solid: close it first (part_extrude a closed profile).")
        return o
    return session.body(None)


def split_ref(ref):
    """"Box.Face3" -> ("Box", "Face3"); "Face3" -> (None, "Face3"); a label -> (label, None)."""
    if SUB.match(ref):
        return None, ref
    if "." in ref:
        head, tail = ref.rsplit(".", 1)
        if SUB.match(tail):
            return head, tail
    return ref, None


def element(shape, sub, owner):
    m = SUB.match(sub)
    kind, i = m.group(1), int(m.group(2))
    have = {"Face": len(shape.Faces), "Edge": len(shape.Edges), "Vertex": len(shape.Vertexes)}[kind]
    if not 1 <= i <= have:
        raise ToolError("not_found", f"{owner}.{sub}: {owner} has {have} {kind.lower()}{'s' if have != 1 else ''} — shape_query finds them again after a change renumbers them.")
    return shape.getElement(sub)


def resolve(session, ref, body=None):
    """A reference into (label, sub or None, shape): a point [x,y,z], an
    object ("Box"), or its element ("Box.Face3", or "Face3" with body)."""
    if isinstance(ref, list):
        p = vec3(ref, "point")
        return "point", None, Part.Vertex(p)
    if isinstance(ref, dict) and "body" in ref and "ref" in ref:
        body, ref = ref["body"], ref["ref"]
    if not isinstance(ref, str):
        raise ToolError("invalid_input", "A reference: \"Face12\" (with body), \"Box.Face12\", an object's name, or a point [x, y, z].")
    head, sub = split_ref(ref)
    if head is None:
        o = shaped(session.doc, body) if body else session.body(None)
    else:
        o = shaped(session.doc, head)
    if sub is None:
        return o.Label, None, o.Shape
    return o.Label, sub, element(o.Shape, sub, o.Label)


def index_of(shape, sub_shape, kind):
    for i, s in enumerate(getattr(shape, kind), 1):
        if s.isSame(sub_shape):
            return i
    return None


# ---- the document -------------------------------------------------------------------------

MADE_PROP, HID_PROP, LABEL_PROP = "AgentLinkMade", "AgentLinkHid", "AgentLinkRelabelled"


def remember_made(out, made=(), hid=(), relabelled=None):
    """On a result: the helper objects made for it alone, the inputs it hid
    and the labels it changed (name=old label), kept with the document, so
    object_delete of the result takes the helpers too and shows and
    renames the inputs back."""
    for prop, vals in ((MADE_PROP, [o.Name for o in made if o is not None]), (HID_PROP, [o.Name for o in hid if o is not None]),
                       (LABEL_PROP, [f"{k}={v}" for k, v in (relabelled or {}).items()])):
        if not vals:
            continue
        try:
            if prop not in out.PropertiesList:
                out.addProperty("App::PropertyStringList", prop, "Agent Link", "Set by Agent Link: what object_delete of this result undoes")
                try:
                    out.setEditorMode(prop, 2)  # hidden in the property view
                except Exception:
                    pass
            setattr(out, prop, list(getattr(out, prop) or []) + vals)
        except Exception:
            pass


def made_record(o):
    """(helper names, hidden input names, {name: old label}) remember_made kept."""
    def get(p):
        try:
            return list(getattr(o, p) or []) if p in o.PropertiesList else []
        except Exception:
            return []

    labels = {}
    for x in get(LABEL_PROP):
        k, _, v = x.partition("=")
        if k:
            labels[k] = v
    return get(MADE_PROP), get(HID_PROP), labels


def bake(session, base, shape, name=None, consumed=(), keep=False):
    """Put a modelling result in the document as a plain shape: into the base
    when it is one (a Part::Feature) and no new name is asked, else as a new
    Part::Feature under the base's label or the name; a PartDesign Body
    gives a new Body on the shape, the old one kept hidden. The inputs are
    then removed, or hidden with keep. Returns the result's object."""
    doc = session.doc
    shape = geo.clean(shape)
    gone = [o for o in consumed if o is not None]
    if base is not None and base.TypeId == "PartDesign::Body":
        # A PartDesign Body is never replaced by a plain shape (nor deleted
        # with its history): the result is a new Body built on the shape
        # (its base feature), so modelling goes on in PartDesign, and the
        # old Body stays, hidden, as the input.
        label = name or base.Label
        relabelled = {}
        if name is None:
            relabelled[base.Name] = base.Label
            base.Label = base.Label + " (input)"
        before = {x.Name for x in doc.Objects}
        holder = doc.addObject("Part::Feature", "BaseShape")
        holder.Shape = shape
        holder.Label = session.unique(f"{label} base shape")
        out = doc.addObject("PartDesign::Body", "Body")
        out.BaseFeature = holder
        out.Label = label if name is None else session.unique(label)
        hid = [base]
        for o in (holder, base):
            if hasattr(o, "Visibility"):
                o.Visibility = False
        for o in gone:
            if o is base:
                continue
            if keep or o.InList:
                if hasattr(o, "Visibility"):
                    o.Visibility = False
                    hid.append(o)
            else:
                doc.removeObject(o.Name)
        doc.recompute()
        # The holder and what FreeCAD made with the Body for it (its
        # FeatureBase "BaseFeature", its Origin): object_delete of the
        # result takes them along, and shows the inputs again.
        made = [x for x in doc.Objects if x.Name not in before and x is not out]
        remember_made(out, made, hid, relabelled)
        session.last_hidden = [o.Label for o in hid]
        return out
    if name is None and base is not None and base.TypeId == "Part::Feature":
        base.Shape = shape
        out = base
        gone = [o for o in gone if o is not base]
    else:
        label = name or (base.Label if base is not None else "Body")
        if name is None and base is not None:
            gone = [base] + [o for o in gone if o is not base]
            base.Label = base.Label + " (input)"  # frees the label
        out = doc.addObject("Part::Feature", "Body")
        out.Shape = shape
        out.Label = label if name is None else session.unique(label)
    hid = []
    for o in gone:
        if keep or o.InList:
            if hasattr(o, "Visibility"):
                o.Visibility = False
                hid.append(o)
        else:
            doc.removeObject(o.Name)
    doc.recompute()
    if out is not base:
        relabelled = {base.Name: base.Label[:-len(" (input)")]} if (name is None and base is not None and base.Label.endswith(" (input)") and base in hid) else {}
        remember_made(out, (), hid, relabelled)
    session.last_hidden = [o.Label for o in hid]
    return out


def repoint(doc, old, new):
    """Every link to old (links, link lists, sub-element links, groups,
    expressions) pointed at new instead, so replacing an object leaves
    nothing dangling. Returns the labels of the objects that changed."""
    if old is None or new is None or old is new:
        return []

    def swap(v):
        if v is old:
            return new, True
        if isinstance(v, (list, tuple)):
            out, hit = [], False
            for x in v:
                y, h = swap(x)
                out.append(y)
                hit = hit or h
            return (type(v)(out) if isinstance(v, tuple) else out), hit
        return v, False

    changed = []
    for p in list(old.InList):
        if p is new:
            continue
        hit_any = False
        for prop in p.PropertiesList:
            try:
                t = p.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not (t.startswith("App::PropertyLink") or t.startswith("App::PropertyXLink")):
                continue
            try:
                v = p.getPropertyByName(prop)
            except Exception:
                continue
            nv, hit = swap(v)
            if hit:
                try:
                    setattr(p, prop, nv)
                    hit_any = True
                except Exception:
                    pass
        for path, expr in list(getattr(p, "ExpressionEngine", []) or []):
            if re.search(r"(?<![\w<])" + re.escape(old.Name) + r"\.", expr) or ("<<" + old.Label + ">>") in expr:
                e2 = re.sub(r"(?<![\w<])" + re.escape(old.Name) + r"\.", new.Name + ".", expr).replace("<<" + old.Label + ">>", new.Name)
                e2 = doc_refs(doc, p, e2)
                try:
                    p.setExpression(path, e2)
                    hit_any = True
                except Exception:
                    pass
        if hit_any:
            changed.append(p.Label)
    return changed


# Objects whose own sub-objects FreeCAD looks for under a name in an
# expression on them, and which log an exception when that name is not one
# of them: a LocalCoordinateSystem (Part::LocalCoordinateSystem, FreeCAD 1.1's
# PartDesign::CoordinateSystem) and an Origin (roles X_Axis, XY_Plane, ...).
SUB_OWNERS = ("App::LocalCoordinateSystem", "App::Origin", "Part::LocalCoordinateSystem", "PartDesign::CoordinateSystem")


def sub_owner(o):
    """Whether o is a LocalCoordinateSystem or an Origin (SUB_OWNERS)."""
    try:
        if any(o.isDerivedFrom(t) for t in SUB_OWNERS):
            return True
    except Exception:  # noqa: BLE001
        pass
    return str(getattr(o, "TypeId", "")) in SUB_OWNERS or "OriginFeatures" in (getattr(o, "PropertiesList", None) or ())


def sub_names(o):
    """The names FreeCAD can read as o's own sub-objects in an expression on
    o: the roles, names and labels of its origin features (X_Axis,
    XY_Plane …) and the names and labels of what its Group holds."""
    out = set()
    for f in list(getattr(o, "OriginFeatures", None) or []) + list(getattr(o, "Group", None) or []):
        for k in ("Role", "Name", "Label"):
            v = getattr(f, k, None)
            if isinstance(v, str) and v:
                out.add(v)
    return out


def attached(o):
    """Whether FreeCAD computes o's Placement from its attachment: an
    AttachExtension object with a MapMode other than Deactivated and a
    support. Its own offset is AttachmentOffset."""
    try:
        props = list(getattr(o, "PropertiesList", None) or [])
        if "AttachmentOffset" not in props or "MapMode" not in props:
            return False
        if str(getattr(o, "MapMode", "Deactivated")) in ("Deactivated", "", "None"):
            return False
        sup = getattr(o, "AttachmentSupport", None) if "AttachmentSupport" in props else getattr(o, "Support", None)
        return bool(sup)
    except Exception:  # noqa: BLE001
        return False


def doc_refs_said(doc, o, expr):
    """(expression, {word: <<label>>}, [words left]) for an expression to
    put on o. When o is a SUB_OWNERS object, or a word before a "." is one
    of o's own sub-object names (sub_names), each other object it names is
    written by its label, <<Dims>>.lift (exprs.by_label): by its name or by
    its label as given. Only objects whose label is their own (no other
    object has it): a label two objects share would not resolve; those
    words are the third item. Else expr as it is."""
    if not isinstance(expr, str):
        return expr, {}, []
    from .. import exprs

    words = [w for w, _m in exprs.owners(expr)]
    if not sub_owner(o) and not (set(words) & sub_names(o)):
        return expr, {}, []
    objs = list(getattr(doc, "Objects", []) or [])
    count, names = {}, {x.Name for x in objs}
    for x in objs:
        count[x.Label] = count.get(x.Label, 0) + 1
    labels = {x.Name: x.Label for x in objs if x is not o and count.get(x.Label) == 1 and x.Label}
    # an object named by its label, where no object has that word as its name
    labels.update({x.Label: x.Label for x in objs if x is not o and count.get(x.Label) == 1 and x.Label not in names and exprs.IDENT.fullmatch(x.Label or "")})
    out, done = exprs.by_label(expr, labels)
    left = [w for w in words if w not in done and w not in labels and (w in names or count.get(w)) and w != o.Name and w != o.Label]
    return out, done, left


def doc_refs(doc, o, expr):
    """doc_refs_said's expression only."""
    return doc_refs_said(doc, o, expr)[0]


def json_safe(v, depth=0):
    """A property's value as JSON: vectors as lists, placements, quantities
    as numbers in the document's units, objects by label, shapes as stats."""
    if depth > 3:
        return str(v)
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 6) if math.isfinite(v) else str(v)
    if isinstance(v, FreeCAD.Vector):
        return geo.vec(v)
    if isinstance(v, FreeCAD.Placement):
        return placement_json(v)
    if isinstance(v, FreeCAD.Rotation):
        return {"axis": geo.vec(v.Axis), "angle": round(math.degrees(v.Angle), 4)}
    if hasattr(FreeCAD, "Units") and isinstance(v, FreeCAD.Units.Quantity):
        return round(v.Value, 6)
    if isinstance(v, Part.Shape):
        return geo.stats(v) if v.Solids else {"null": v.isNull(), "faces": len(v.Faces), "edges": len(v.Edges)} if not v.isNull() else None
    if hasattr(v, "TypeId") and hasattr(v, "Label") and hasattr(v, "Document"):
        return v.Label
    if isinstance(v, (list, tuple)):
        out = [json_safe(x, depth + 1) for x in list(v)[:50]]
        if len(v) > 50:
            out.append(f"… {len(v) - 50} more")
        return out
    if isinstance(v, dict):
        return {str(k): json_safe(x, depth + 1) for k, x in list(v.items())[:50]}
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    return str(v)


def carry_material(s, src, copies):
    """A copy keeps the material of what it was copied from
    (material.carry); the labels given it. A copy is never refused for
    this: an error leaves the copy without a record, as before."""
    try:
        from . import material

        return material.carry(s.doc, src, copies)
    except Exception:  # noqa: BLE001
        return []
