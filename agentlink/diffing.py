# SPDX-License-Identifier: LGPL-2.1-or-later
"""What history_diff compares beyond a body's numbers: where each body's box
sits, the features and sketches by name with the values that make them, and
which checks a change makes stale.

Plain Python: nothing of FreeCAD is imported. The readers take FreeCAD's
objects as they are (PropertiesList, getTypeIdOfProperty, a sketch's
Constraints) and anything that cannot be read is left out, never raised.
"""
import re
import time

# Objects read as features: PartDesign's (a Body is a part, not a feature),
# sketches, and Part's parametric objects (a Part::Box's Length is an edit
# like a Pad's). A plain Part::Feature holds a shape and has nothing to edit.
FEATURE_PREFIXES = ("PartDesign::", "Sketcher::SketchObject", "Part::")
NOT_FEATURES = ("PartDesign::Body", "Part::Feature")
MAX_FEATURES = 600     # objects read per step; past it features are not compared (said)
MAX_SECONDS = 0.25     # a step's reading taking longer turns the next ones off (said)
MAX_NAMES = 30         # names per list in the answer
MAX_PROPS = 12         # changed values named per feature
MAX_TEXT = 120

# Properties that are results, looks or bookkeeping, not what a person edits.
SKIP_PROPS = {"Shape", "AddSubShape", "SuppressedShape", "PreviewShape", "Proxy", "Label", "Label2", "Visibility", "_Body",
              "ExpressionEngine", "Constraints", "Geometry", "ExternalGeo", "ExternalTypes", "FullyConstrained", "Group",
              "InternalShape", "ExposeInternalGeometry", "_ElementMapVersion", "VisualLayerList"}
SKIP_TYPE_WORDS = ("Shape", "PythonObject", "GeometryList", "ConstraintList", "Material", "Color", "Map", "PersistentObject", "FileIncluded")
# Sketcher's dimensional constraints: their Value is the dimension.
DIMENSIONAL = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle", "Weight", "SnellsLaw")


def is_feature(type_id):
    t = str(type_id or "")
    return t.startswith(FEATURE_PREFIXES) and t not in NOT_FEATURES


def _num(x):
    return round(float(x), 6)


def value(v):
    """A property's value as something small that compares: a number, text,
    a list of numbers, an object's name. None: not a kind compared here."""
    try:
        if v is None or isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return _num(v)
        if isinstance(v, str):
            return v[:MAX_TEXT]
        if hasattr(v, "Value") and hasattr(v, "Unit"):  # a quantity: millimetres, degrees
            return _num(v.Value)
        if hasattr(v, "TypeId") and hasattr(v, "Name"):  # a linked object
            return str(v.Name)
        if hasattr(v, "Base") and hasattr(v, "Rotation"):  # a placement
            b, r = v.Base, v.Rotation
            ax = r.Axis
            return [_num(b.x), _num(b.y), _num(b.z), _num(ax.x), _num(ax.y), _num(ax.z), round(float(r.Angle) * 57.29577951308232, 4)]
        if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
            return [_num(v.x), _num(v.y), _num(v.z)]
        if isinstance(v, (list, tuple)):
            if len(v) > 40:
                return f"{len(v)} items"
            out = [value(x) for x in v]
            return None if any(x is None for x in out) and not all(x is None for x in out) else out
    except Exception:
        return None
    return None


def _constraints(sk):
    """A sketch's constraints as rows that compare: (type, name, value, the
    geometry it is on). An angle's value in degrees."""
    rows = []
    for c in sk.Constraints:
        t = str(c.Type)
        val = None
        if t in DIMENSIONAL:
            try:
                val = float(c.Value)
                val = round(val * 57.29577951308232, 4) if t == "Angle" else _num(val)
            except Exception:
                val = None
        rows.append((t, str(getattr(c, "Name", "") or ""), val,
                     (getattr(c, "First", None), getattr(c, "FirstPos", None), getattr(c, "Second", None), getattr(c, "SecondPos", None),
                      getattr(c, "Third", None), getattr(c, "ThirdPos", None)), bool(getattr(c, "Driving", True))))
    return rows


def _geometry(sk):
    """A sketch's drawn geometry as (count, total length, box): changes when
    an edge is added, removed or dragged."""
    try:
        n = int(sk.GeometryCount)
    except Exception:
        n = None
    try:
        sh = sk.Shape
        if sh.isNull():
            return (n, 0.0, None)
        b = sh.BoundBox
        return (n, round(float(sh.Length), 4), (round(b.XLength, 4), round(b.YLength, 4), round(b.ZLength, 4)))
    except Exception:
        return (n, None, None)


def _body_of(o):
    try:
        g = o.getParentGeoFeatureGroup()
        return str(g.Label) if g is not None else None
    except Exception:
        return None


def read_feature(o):
    """One feature or sketch as { label, type, body, props, constraints,
    geometry }: what makes it, in values that compare."""
    t = str(o.TypeId)
    fp = {"label": str(o.Label), "type": t.split("::")[-1], "body": _body_of(o), "props": {}}
    derived = t.startswith("PartDesign::")  # a feature's Placement follows its sketch
    try:
        attached = str(getattr(o, "MapMode", "Deactivated")) != "Deactivated"
    except Exception:
        attached = False
    for p in o.PropertiesList:
        if p in SKIP_PROPS or (p == "Placement" and (derived or attached)):
            continue
        try:
            pt = o.getTypeIdOfProperty(p)
            if any(w in pt for w in SKIP_TYPE_WORDS):
                continue
            v = value(getattr(o, p))
        except Exception:
            continue
        if v is not None and v != [] and v != "":
            fp["props"][p] = v
    try:
        for path, expr in (getattr(o, "ExpressionEngine", None) or []):
            fp["props"][f"{path} (expression)"] = str(expr)[:MAX_TEXT]
    except Exception:
        pass
    if t == "Sketcher::SketchObject":
        try:
            fp["constraints"] = _constraints(o)
        except Exception:
            pass
        fp["geometry"] = _geometry(o)
    return fp


def fingerprint(doc, previous=None, clock=time.time):
    """{object name: read_feature} for the document's features and sketches,
    or { "_unchecked": why } when there are too many or reading them took
    too long. previous: the step before's — an unchanged feature keeps the
    same record (a long session's steps then share them), and a previous
    "_unchecked" for slowness stays."""
    if isinstance(previous, dict) and previous.get("_unchecked") and previous.get("_slow"):
        return previous
    try:
        objs = [o for o in doc.Objects if is_feature(getattr(o, "TypeId", ""))]
    except Exception:
        return {"_unchecked": "the document's objects could not be read"}
    if len(objs) > MAX_FEATURES:
        return {"_unchecked": f"{len(objs)} features and sketches, over {MAX_FEATURES}: not compared by value"}
    t0 = clock()
    out = {}
    prev = previous if isinstance(previous, dict) and not previous.get("_unchecked") else {}
    for o in objs:
        try:
            fp = read_feature(o)
            name = str(o.Name)
        except Exception:
            continue
        old = prev.get(name)
        out[name] = old if old == fp else fp
    if clock() - t0 > MAX_SECONDS:
        return {"_unchecked": f"reading {len(objs)} features took over {MAX_SECONDS:g} s a step: not compared by value in this session", "_slow": True}
    return out


def _feature_changes(b, n):
    """What differs between two records of one feature: { property: { from,
    to } }, a sketch's constraints by index and its geometry."""
    out = {}
    if b.get("label") != n.get("label"):
        out["Label"] = {"from": b.get("label"), "to": n.get("label")}
    bp, np_ = b.get("props") or {}, n.get("props") or {}
    keys = [k for k in list(np_) + [k for k in bp if k not in np_] if bp.get(k) != np_.get(k)]
    for k in keys[:MAX_PROPS]:
        out[k] = {"from": bp.get(k), "to": np_.get(k)}
    if len(keys) > MAX_PROPS:
        out["more"] = f"{len(keys) - MAX_PROPS} more properties"
    bc, nc = b.get("constraints"), n.get("constraints")
    if bc is not None and nc is not None and bc != nc:
        if len(bc) != len(nc):
            out["constraints"] = {"from": len(bc), "to": len(nc)}
        rows = []
        for i, (x, y) in enumerate(zip(bc, nc)):
            if x == y:
                continue
            row = {"index": i, "type": y[0]}
            if y[1]:
                row["name"] = y[1]
            if x[0] == y[0] and x[3] == y[3] and x[2] != y[2]:
                row.update({"from": x[2], "to": y[2]})
            elif x[0] == y[0] and x[3] == y[3] and x[4] != y[4]:
                row["driving"] = {"from": x[4], "to": y[4]}
            elif x[0] == y[0] and x[3] == y[3]:
                row["renamed"] = {"from": x[1], "to": y[1]}
            else:
                row["replaced"] = f"was {x[0]}" + (f" {x[2]:g}" if isinstance(x[2], float) else "")
            rows.append(row)
        if rows:
            out["constraintValues"] = rows[:MAX_PROPS] + ([{"more": len(rows) - MAX_PROPS}] if len(rows) > MAX_PROPS else [])
    bg, ng = b.get("geometry"), n.get("geometry")
    if bg is not None and ng is not None and bg != ng:
        g = {}
        if bg[0] != ng[0]:
            g["count"] = {"from": bg[0], "to": ng[0]}
        if bg[1] != ng[1]:
            g["length"] = {"from": bg[1], "to": ng[1]}
        if bg[2] != ng[2] and bg[2] is not None and ng[2] is not None:
            g["size"] = {"from": list(bg[2]), "to": list(ng[2])}
        if g:
            out["geometry"] = g
    return out


def _named(fp):
    return fp["label"] + (f" ({fp['body']})" if fp.get("body") and fp["body"] != fp["label"] else "")


def features_diff(before, now):
    """{ added: [names], removed: [names], edited: { name: changes } } with
    only the keys that have something, {} when nothing differs, or
    { unchecked: why } when either side was not read."""
    before, now = before or {}, now or {}
    for side in (now, before):
        if side.get("_unchecked"):
            return {"unchecked": side["_unchecked"]}
    out = {}
    added = [_named(now[k]) for k in now if k not in before]
    removed = [_named(before[k]) for k in before if k not in now]
    edited = {}
    for k in now:
        b, n = before.get(k), now[k]
        if b is None or b is n or b == n:
            continue
        ch = _feature_changes(b, n)
        if ch:
            edited[_named(n)] = ch
    if added:
        out["added"] = added[:MAX_NAMES] + ([f"… {len(added) - MAX_NAMES} more"] if len(added) > MAX_NAMES else [])
    if removed:
        out["removed"] = removed[:MAX_NAMES] + ([f"… {len(removed) - MAX_NAMES} more"] if len(removed) > MAX_NAMES else [])
    if edited:
        keep = dict(list(edited.items())[:MAX_NAMES])
        if len(edited) > MAX_NAMES:
            keep["more"] = f"{len(edited) - MAX_NAMES} more edited"
        out["edited"] = keep
    return out


def moved(before, now, eps=1e-6):
    """{ body: { by: [dx, dy, dz], distance } } for each body whose box's
    lowest corner (x, y and z at their least) is somewhere else. before,
    now: { body: [xmin, ymin, zmin] }."""
    out = {}
    for name in sorted(set(before or {}) & set(now or {})):
        b, n = before[name], now[name]
        try:
            d = [float(n[i]) - float(b[i]) for i in range(3)]
        except Exception:
            continue
        dist = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
        if dist > eps:
            out[name] = {"by": [round(x, 3) for x in d], "distance": round(dist, 3)}
    return out


# ---- which checks a change makes stale ----------------------------------------------------

# A read whose answer is a verdict on a body or the document, by the words
# in its name: body_check, an assembly's check, a review, a fit, a clearance.
CHECK_WORDS = re.compile(r"(^|_)(check|review|fit|clearance|interference|results|probe|wall|thickness|mass|dfm|strength|qa)(_|$)")
BODY_KEYS = ("body", "bodies", "a", "b", "part", "parts", "object", "objects", "target", "moving", "fixed", "hole", "shaft")
MAX_CHECKS = 200


def is_check(name):
    return bool(CHECK_WORDS.search(str(name or "")))


def bodies_named(args, labels):
    """The bodies a call's arguments name (by the usual keys), as labels."""
    low = {str(x).lower(): x for x in labels}
    out = []
    for k in BODY_KEYS:
        v = (args or {}).get(k)
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if isinstance(x, str) and x.lower() in low and low[x.lower()] not in out:
                out.append(low[x.lower()])
    return out


def note_check(log, tool, args, labels, step):
    """A check that ran: kept as log[(tool, body or "")] = step. A call that
    names no body is the one body's when there is one, else the document's
    ("")."""
    if not is_check(tool):
        return
    named = bodies_named(args, labels) or ([labels[0]] if len(labels) == 1 else [""])
    for b in named:
        log.pop((tool, b), None)  # the newest last
        log[(tool, b)] = step
    while len(log) > MAX_CHECKS:
        log.pop(next(iter(log)))


def recheck(changed, log, last, differs, known=None, extra=()):
    """The checks to run again after a change: [{ tool, body, ranAt }] for
    each check in log that ran before the newest step on a body among
    changed (or on the document, body "") and whose body is not as it was
    then, then extra rows ({ tool, … , why }) that are not there already.

    changed: the bodies the diff found changed, moved, added or removed;
    differs(body, step) -> whether that body (or, for "", any body) differs
    now from how it was at that step; known: tool names this server has
    (others are dropped)."""
    out, seen = [], set()
    changed = set(changed or ())
    for (tool, body), step in (log or {}).items():
        if known is not None and tool not in known:
            continue
        if step >= last or (body and body not in changed) or (not body and not changed):
            continue
        try:
            if not differs(body, step):
                continue
        except Exception:
            continue
        row = {"tool": tool, **({"body": body} if body else {}), "ranAt": step}
        out.append(row)
        seen.add((tool, body))
    for row in extra or ():
        key = (row.get("tool"), row.get("body") or "")
        if known is not None and row.get("tool") not in known:
            continue
        if key in seen or ((row.get("tool"), "") in seen and not row.get("page")):
            continue
        seen.add(key)
        out.append(row)
    return out
