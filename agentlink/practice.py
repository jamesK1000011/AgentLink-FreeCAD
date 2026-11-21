# SPDX-License-Identifier: LGPL-2.1-or-later
"""Modelling-practice warnings (plain Python; read by health.py and body_check).

Test builds (21 Nov) showed the agent model like a script runner: many
bodies in one file, primitives put at world coordinates, long boolean
chains, Refine on weldments, modelled threads. These readings name such a
pattern at the moment the agent acts. They are advice only: they never
refuse a call and never make a health reading red.

Each warning is said once a conversation for each document, object and
kind (news), and again only when it goes away and comes back, or when its
kind changes (a modelled thread that then is not made). Nothing is added to
an answer when no warning fires, so the base token cost stays the same.

The limits are named constants here (no data file of the hub holds such
values; fusehint.py keeps its own the same way). Sources: the test builds of
20 and 21 Nov (claude/bicycle-a-l5-report-2026-11-21.md, test-drive notes).
"""
import re

from . import fusehint

# 1. A Body of mostly primitives: at least this many primitive features, and
#    more than this share of its solid features (bicycle and desk-lamp builds).
PRIMITIVES_MIN = 3
PRIMITIVES_SHARE = 0.5
# 2. A boolean chain longer than this: parametric Part booleans in a row, the
#    PartDesign Booleans of one body, or part_boolean results on one label.
BOOLEAN_CHAIN = 3
# 3. Refine on in a body that fuses at least this many tube members (pipes,
#    and the bodies a PartDesign Boolean fuses). fusehint.REFINE_PIPES (8) is
#    the count past which the todo on an invalid shape names Refine.
WELD_MEMBERS = 4
# 4. More solid bodies than this in one document (with an assembly in it, or
#    no other document open).
BODIES_MAX = 8
# At most this many warning lines in one health reading; the rest are counted.
MAX_LINES = 3

PRIMITIVE = re.compile(r"^PartDesign::(Additive|Subtractive)(Box|Cylinder|Sphere|Cone|Ellipsoid|Torus|Prism|Wedge)$")
NOT_SOLID = {"PartDesign::Plane", "PartDesign::Line", "PartDesign::Point", "PartDesign::CoordinateSystem",
             "PartDesign::ShapeBinder", "PartDesign::SubShapeBinder", "PartDesign::FeatureBase", "PartDesign::Body"}
PART_BOOLEANS = {"Part::Cut", "Part::Fuse", "Part::Common", "Part::MultiFuse", "Part::MultiCommon"}
ASSEMBLY = "Assembly::AssemblyObject"


def _t(o):
    return getattr(o, "TypeId", "") or ""


def _label(o):
    return getattr(o, "Label", None) or getattr(o, "Name", "?")


def _features(body):
    return [f for f in (getattr(body, "Group", None) or []) if _t(f).startswith("PartDesign::") and _t(f) not in NOT_SOLID]


def primitives(body):
    """(primitives, solid features) of a PartDesign Body when the primitives
    are at least PRIMITIVES_MIN and more than PRIMITIVES_SHARE of them, else None."""
    feats = _features(body)
    n = sum(1 for f in feats if PRIMITIVE.match(_t(f)))
    if n >= PRIMITIVES_MIN and n > PRIMITIVES_SHARE * len(feats):
        return n, len(feats)
    return None


def _inputs(o):
    out = []
    for p in ("Base", "Tool"):
        x = getattr(o, p, None)
        if x is not None:
            out.append(x)
    out += list(getattr(o, "Shapes", None) or [])
    return out


def chains(objs):
    """[(result, depth)] of parametric Part boolean chains deeper than
    BOOLEAN_CHAIN, read from the Base, Tool and Shapes links (only the end
    of each chain)."""
    depth = {}

    def d(o, seen=()):
        k = id(o)
        if k in depth:
            return depth[k]
        if _t(o) not in PART_BOOLEANS or k in seen:
            return 0
        v = 1 + max([d(x, seen + (k,)) for x in _inputs(o)] or [0])
        depth[k] = v
        return v

    bools = [o for o in objs if _t(o) in PART_BOOLEANS]
    used = {id(x) for o in bools for x in _inputs(o)}
    return [(o, d(o)) for o in bools if id(o) not in used and d(o) > BOOLEAN_CHAIN]


def pd_booleans(body):
    return sum(1 for f in (getattr(body, "Group", None) or []) if _t(f) == "PartDesign::Boolean")


def weldment(body):
    """(refined features, tube members) when Refine is on in a body that
    fuses several tube members, or on a PartDesign Boolean that fuses
    bodies; else None. The same rule as fusehint.refine_todo (one count)."""
    on = fusehint.refined(body)
    if not on:
        return None
    members = fusehint.members(body)
    fused = [f for f in (getattr(body, "Group", None) or []) if _t(f) == "PartDesign::Boolean"
             and str(getattr(f, "Type", "Fuse")) == "Fuse" and _label(f) in on]
    if members >= WELD_MEMBERS or fused:
        return on, members
    return None


def _num(v):
    try:
        return float(getattr(v, "Value", v))
    except Exception:
        return None


def thread(hole, body=None):
    """None, "modelled", or "not made" for a PartDesign Hole. FreeCAD
    issue #19254 and the PartDesign Hole wiki: a modelled thread with
    Reversed on, or in a blind hole (DepthType Dimension) shorter than the
    part, can be left out of the shape. The part's size is read from the
    body's box (its smallest side): a hole shorter than that is blind."""
    if _t(hole) != "PartDesign::Hole" or not bool(getattr(hole, "ModelThread", False)):
        return None
    if bool(getattr(hole, "Reversed", False)):
        return "not made"
    if str(getattr(hole, "DepthType", "")) == "Dimension":
        depth = _num(getattr(hole, "Depth", None))
        try:
            bb = body.Shape.BoundBox
            side = min(bb.XLength, bb.YLength, bb.ZLength)
        except Exception:
            side = None
        if depth is not None and side and depth < side - 1e-6:
            return "not made"
    return "modelled"


def _body_findings(b):
    out = []
    lb = _label(b)
    p = primitives(b)
    if p:
        out.append(("primitives", lb, "", f"Body {lb}: {p[0]} of {p[1]} features are primitives. "
                    "A sketch with a pad, pocket or revolution keeps sizes as constraints."))
    n = pd_booleans(b)
    if n > BOOLEAN_CHAIN:
        out.append(("booleans", lb, "", f"Body {lb}: {n} Booleans in a row. "
                    "Sketch-based features in one body keep each step small and editable."))
    w = weldment(b)
    if w:
        out.append(("refine", lb, "", f"Body {lb}: Refine is on in a weldment of {w[1]} members. "
                    "Set Refine off on its features, or the body can become unorientable."))
    for f in getattr(b, "Group", None) or []:
        k = thread(f, b)
        if k == "modelled":
            out.append(("thread", _label(f), k, f"Hole {_label(f)} has a modelled thread. "
                        "A thread as data (threaded, no modelThread) is enough unless the part is printed."))
        elif k == "not made":
            out.append(("thread", _label(f), k, f"Hole {_label(f)}: the thread is not made with Reversed or a blind depth. "
                        "Turn off modelThread, or make the hole through all."))
    return out


def findings(objs, parts=None, others=0, booleans=None, body=None):
    """[(kind, object, state, line)] for the document's objects. parts: the
    solid parts (health's Session.bodies_in), else read here. others: the
    count of other open documents. booleans: { label: part_boolean results
    on that label } (session counts, see note). body: only that body's
    findings, and the document's own."""
    objs = list(objs or [])
    bodies = [o for o in objs if _t(o) == "PartDesign::Body"]
    out = []
    for b in bodies:
        if body is None or b is body:
            out += _body_findings(b)
    for o, d in chains(objs):
        if body is None or o is body:
            out.append(("booleans", _label(o), "", f"{_label(o)}: {d} booleans in a chain. "
                        "Sketch-based features in one PartDesign body keep each step small and editable."))
    for lb, n in (booleans or {}).items():
        if n > BOOLEAN_CHAIN and (body is None or _label(body) == lb):
            out.append(("booleans", lb, "", f"{lb}: {n} part_boolean steps. "
                        "Sketch-based features in one PartDesign body keep each step small and editable."))
    if parts is None or not parts:
        # Without the hub's reading: Bodies, and Part shapes that nothing is made from.
        parts = bodies + [o for o in objs if _t(o).startswith("Part::") and not (getattr(o, "InList", None) or [])
                          and not _t(o).startswith("Part::Part2D") and getattr(o, "Visibility", True)]
    n = len(parts)
    if n > BODIES_MAX and (others == 0 or any(_t(o) == ASSEMBLY for o in objs)):
        out.append(("bodies", "", "", f"{n} bodies in one file. "
                    "One file for each part, linked into an assembly file, keeps rebuilds small."))
    return out


def news(session, doc_name, found):
    """The lines of found that were not said before in this conversation for
    this document (same kind, object and state). A finding that is gone is
    forgotten, so it is said again when it comes back."""
    from .once import state

    st = state(session).setdefault("practice", {})
    now = {(doc_name, k, o): s for k, o, s, _ in found}
    for key in [k for k in st if k[0] == doc_name and k not in now]:
        del st[key]
    out = []
    for k, o, s, line in found:
        key = (doc_name, k, o)
        if key not in st or st[key] != s:
            out.append(line)
        st[key] = s
    return out


def count_booleans(session, doc_name, made):
    """part_boolean results counted by label for this conversation. A
    part_boolean result is a plain shape with no link to its inputs (the
    inputs are removed or hidden), so the chain depth cannot be read from
    the document. This counts the part_boolean calls whose result kept a
    label: the same base cut again and again. It does not see a chain made
    before the conversation, or one whose steps took new names."""
    from .once import state

    st = state(session).setdefault("booleans", {})
    d = st.setdefault(doc_name, {})
    for lb in made:
        d[lb] = d.get(lb, 0) + 1
    return d


def booleans_of(session, doc_name):
    from .once import state

    return dict(state(session).get("booleans", {}).get(doc_name, {}))
