# SPDX-License-Identifier: LGPL-2.1-or-later
# One way to name faces and edges, shared by every tool that takes them
# (pd_fillet, pd_chamfer, pd_draft, pd_thickness, fea_hold, fea_load and the
# rest of the study, sketch_external …): what shape_query answers can be
# handed straight on. A spec is
#
#   "Face8" / "Body.Face8" / "Edge3"        a reference as shape_query gives it
#   { ref: "Face8", … }                     one of shape_query's items as it came
#   { type, radius, axis, normal, near,     shape_query's filters, on this body
#     inside, x, y, z, tol, area, length,
#     within, of, outside, sort, limit }
#   [ any of these, … ]                     every one of them, in order
#
# and each tool keeps its own older forms ({ near } the nearest edge,
# { face: { at, normal } }, { all: true }; { near, radius } faces that close,
# { normal, z } flat faces at a plane, { faces: [..] }), passed in as legacy.
# Not a family (it is not in NAMES).

import re

from ..protocol import ToolError

REF = re.compile(r"^(?:(?P<owner>.+)[.:])?(?P<sub>(?P<kind>Face|Edge|Vertex)(?P<n>\d+))$")
ATTR = {"face": "Faces", "edge": "Edges", "vertex": "Vertexes"}
# The keys only shape_query's filters have: a dict with any of them is a filter.
FILTER_ONLY = {"type", "axis", "within", "area", "length", "inside", "outside", "of", "sort", "limit", "ref"}
FILTER_KEYS = FILTER_ONLY | {"normal", "radius", "near", "x", "y", "z", "tol", "kind"}
# Edge kinds a tool's older { kind: line } meant: shape_query's type.
EDGE_TYPES = {"line", "circle", "ellipse", "bspline", "bezier"}
HELP = ("a reference as shape_query gives it (\"Face8\", \"Body.Face8\"), a list of them, or shape_query's filters "
        "({ type, radius, axis, normal, near, inside, x, y, z, … } on this body)")


def parse(ref):
    """("Body" or None, "Face", 8) for "Body.Face8" / "Face8", else None."""
    if not isinstance(ref, str):
        return None
    m = REF.match(ref.strip())
    if not m:
        return None
    return m.group("owner"), m.group("kind"), int(m.group("n"))


def is_filter(q, legacy_keys=()):
    """Whether a dict is shape_query's filters rather than a tool's own
    older form: it has a key only the filters have, or keys the older
    form does not know."""
    if not isinstance(q, dict) or not q:
        return False
    keys = set(q)
    if keys & FILTER_ONLY:
        return True
    return not keys <= set(legacy_keys) and keys <= FILTER_KEYS


def _owner_ok(owner, names):
    if owner is None or not names:
        return True
    return owner in {n for n in names if n}


def _by_ref(shape, ref, kind, what, names):
    p = parse(ref)
    if p is None:
        raise ToolError("invalid_input", f"{what}: {ref!r} is not a reference — {HELP}.")
    owner, sub, n = p
    if not _owner_ok(owner, names):
        raise ToolError("invalid_input", f"{what}: {ref} is on {owner}, not on {names[0]} — give this body's references (shape_query {{ body: \"{names[0]}\" }}).")
    have = getattr(shape, f"{sub}s" if sub != "Vertex" else "Vertexes")
    if not 1 <= n <= len(have):
        raise ToolError("not_found", f"{what}: {sub}{n} is not on {names[0] if names else 'this body'} ({sub}1 … {sub}{len(have)}) — numbers change after every edit: shape_query again.")
    el = have[n - 1]
    want = kind.capitalize()
    if sub == want:
        return [(f"{sub}{n}", el)]
    if kind == "edge" and sub == "Face":
        # A face given for edges: every edge of it (the older { face } form).
        out = []
        for i, e in enumerate(shape.Edges, 1):
            if any(e.isSame(fe) for fe in el.Edges):
                out.append((f"Edge{i}", e))
        return out
    raise ToolError("invalid_input", f"{what}: {sub}{n} is a {sub.lower()}; this takes {kind}s — {HELP}.")


def _by_filter(shape, q, kind, what, names):
    from . import measure

    q = dict(q)
    if q.get("ref") is not None:
        # One of shape_query's own items handed on: its reference.
        return _by_ref(shape, q["ref"], kind, what, names)
    bad = sorted(k for k in q if k not in FILTER_KEYS | {"body"})
    if bad:
        raise ToolError("invalid_input", f"{what}.{bad[0]}: not a filter — {HELP}.")
    k = q.pop("kind", None)
    if k in EDGE_TYPES and kind == "edge":
        q.setdefault("type", k)  # the older { kind: line } is shape_query's type
    elif k not in (None, kind):
        raise ToolError("invalid_input", f"{what}.kind: {kind} here (this takes {kind}s).")
    limit = q.pop("limit", None)
    q.pop("body", None)
    of = q.pop("of", None)
    of_el = None
    if of is not None:
        got = _by_ref(shape, of, "face", f"{what}.of", names)
        of_el = got[0][1]
    _, hits = measure.filter_shape(shape, q, kind, of_el=of_el)
    near = q.get("near")
    if limit is None and near is not None and not isinstance(near, dict) and hits:
        # A point and no limit: the element nearest it (as the older
        # { near } forms took), not every one sorted by distance.
        limit = 1
    if limit is not None:
        hits = hits[: max(1, int(limit))]
    if not hits:
        raise ToolError("not_found", f"{what}: no {kind} on {names[0] if names else 'the body'} matches {_words(q)} — shape_query with the same filters lists what is there.")
    return [(d["ref"], el) for _, el, d in hits]


def _words(q):
    return "{ " + ", ".join(f"{k}: {v}" for k, v in q.items()) + " }"


def legacy_of(keys, also=None):
    """is_legacy for pick: a dict of only these keys (and not a filter);
    also(q), when given, must hold too."""
    return lambda q: not is_filter(q, keys) and (also is None or also(q))


# A direction in words where a kind or a type goes (24 Nov QA: { kind:
# "vertical" } for the vertical edges of a box): shape_query's filters take
# a direction as axis (an edge) or normal (a face).
DIRECTION_WORDS = {"vertical", "horizontal"}


def direction_word(q, kind, what):
    """Refuse kind or type given as a direction word, with the filter that
    gives the direction."""
    for key in ("kind", "type"):
        v = q.get(key)
        if isinstance(v, str) and v.strip().lower() in DIRECTION_WORDS:
            if kind == "edge":
                fix = ('For a direction, use axis: { type: "line", axis: "z" } is every straight edge along z (the vertical edges). '
                       'axis: "x" or "y" gives the horizontal edges along that axis.')
            else:
                fix = ('For a direction, use normal: { type: "plane", normal: "+z" } is every flat face that points up. '
                       'A vertical face has its normal along x or y.')
            raise ToolError("invalid_input", f"{what}: {key} {v.strip()!r} is not a {key} of a{'n' if kind == 'edge' else ''} {kind}. {fix} Nothing was changed.")


def pick(shape, spec, kind, what, legacy=None, is_legacy=None, names=()):
    """[(name, element)] for a spec (above) on shape, each once, in order.
    kind: "face" or "edge" — what the tool takes. legacy(q) -> [(name,
    element)]: the tool's own older dict forms, those is_legacy(q) says are
    (legacy_of(keys)). names: the body's label and name, so "Other.Face3"
    is refused here."""
    if spec is None or spec == [] or spec == {}:
        raise ToolError("invalid_input", f"{what}: {HELP}.")
    items = spec if isinstance(spec, list) else [spec]
    for q in items:
        if isinstance(q, dict):
            direction_word(q, kind, what)
    out, seen = [], set()
    for q in items:
        if isinstance(q, str):
            got = _by_ref(shape, q, kind, what, names)
        elif isinstance(q, dict) and q.get("ref") is None and legacy is not None and (is_legacy is None or is_legacy(q)):
            got = legacy(q)
        elif isinstance(q, dict):
            got = _by_filter(shape, q, kind, what, names)
        else:
            raise ToolError("invalid_input", f"{what}: each one {HELP} — not {q!r}.")
        for n, el in got:
            if n not in seen:
                seen.add(n)
                out.append((n, el))
    if not out:
        raise ToolError("not_found", f"{what}: nothing matched.")
    return out
