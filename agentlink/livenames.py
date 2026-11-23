# SPDX-License-Identifier: LGPL-2.1-or-later
"""The live names of the agent's document, in one short line (plain Python;
used by protocol.py).

Small models lose track of names after a refusal (local-model runs, 23 Nov:
every sketch was called "Sketch" while the answers said "Sketch 2" and
"Sketch 3"). So every answer of a call that changes the document, a batch's
answer and a refusal end with "now": the names as they are, by label (the
name every tool takes):

    "now": {"Body": ["Sketch→Pad", "Sketch 2→Pad 2", "Sketch 3 (not used)"]}

A body gives its features in order, each with the sketch it uses; a sketch
that no feature uses yet is named alone, with "(not used)". What is not in
a body (a Part solid, a free sketch) is under "(no body)". Short by design:
at most MAX_ITEMS names a body (the last ones, after "… N before") and
MAX_BODIES bodies (the last ones). Cheap reads only; any error gives None,
and a call never fails for it.
"""

MAX_BODIES = 4
MAX_ITEMS = 8
NO_BODY = "(no body)"
NOT_USED = " (not used)"
# What is no feature of the agent's: a body's origin and its axes and planes.
HELPERS = ("App::Origin", "App::Line", "App::Plane", "App::Point")
# Top-level objects worth naming outside a body.
SHOWN_PREFIXES = ("Part::", "Sketcher::", "PartDesign::", "Mesh::")


def _type(o):
    return str(getattr(o, "TypeId", "") or "")


def _is_sketch(o):
    try:
        return bool(o.isDerivedFrom("Sketcher::SketchObject"))
    except Exception:  # noqa: BLE001 - a stand-in without isDerivedFrom
        return _type(o).startswith("Sketcher::")


def _profile(f):
    """The sketch a feature is built from (its Profile; a Part feature's
    Base), or None."""
    p = getattr(f, "Profile", None)
    if p is None or p == () or p == []:
        p = getattr(f, "Base", None)
    if isinstance(p, (tuple, list)):
        p = p[0] if p else None
    if isinstance(p, (tuple, list)):  # [(obj, subs)] as some features keep it
        p = p[0] if p else None
    return p if p is not None and _is_sketch(p) else None


def _used(sk):
    """Whether a feature (anything but a group or the body) uses the sketch."""
    try:
        return any(not _type(p).startswith(("PartDesign::Body", "App::")) for p in sk.InList)
    except Exception:  # noqa: BLE001
        return False


def _cap(items, n=MAX_ITEMS):
    if len(items) <= n:
        return items
    return [f"… {len(items) - n} before"] + items[-n:]


def _label(o):
    return str(getattr(o, "Label", None) or getattr(o, "Name", ""))


def names(doc):
    """{ body label: [names in order], "(no body)": [...] } of doc, or None
    (no document, nothing in it, or a read that failed)."""
    if doc is None:
        return None
    try:
        objs = list(doc.Objects)
    except Exception:  # noqa: BLE001 - a closed document
        return None
    try:
        bodies = [o for o in objs if _type(o) == "PartDesign::Body"]
        in_body = set()
        out = {}
        for b in bodies:
            group = list(getattr(b, "Group", None) or ())
            in_body.update(id(o) for o in group)
            try:
                origin = getattr(b, "Origin", None)
                if origin is not None:
                    in_body.add(id(origin))
                    in_body.update(id(o) for o in (getattr(origin, "OriginFeatures", None) or ()))
            except Exception:  # noqa: BLE001
                pass
            items = []
            for f in group:
                if _type(f) in HELPERS:
                    continue
                if _is_sketch(f):
                    if not _used(f):
                        items.append(_label(f) + NOT_USED)
                    continue
                sk = _profile(f)
                items.append(f"{_label(sk)}→{_label(f)}" if sk is not None else _label(f))
            out[_label(b)] = _cap(items)
        if len(out) > MAX_BODIES:
            keep = list(out)[-MAX_BODIES:]
            out = {k: out[k] for k in keep}
            out["…"] = f"{len(bodies) - MAX_BODIES} bodies before"
        free = []
        for o in objs:
            t = _type(o)
            if id(o) in in_body or t == "PartDesign::Body" or t in HELPERS or not t.startswith(SHOWN_PREFIXES):
                continue
            try:
                consumed = any(_type(p) not in ("App::DocumentObjectGroup",) for p in o.InList)
            except Exception:  # noqa: BLE001
                consumed = False
            if _is_sketch(o):
                if not _used(o):
                    free.append(_label(o) + NOT_USED)
            elif not consumed:
                sk = _profile(o)
                free.append(f"{_label(sk)}→{_label(o)}" if sk is not None else _label(o))
        if free:
            out[NO_BODY] = _cap(free)
        return out or None
    except Exception:  # noqa: BLE001 - never fails the call it ends
        return None
