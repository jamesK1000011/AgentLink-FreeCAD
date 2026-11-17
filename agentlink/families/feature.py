# SPDX-License-Identifier: LGPL-2.1-or-later
# PartDesign features, one call each: pad, pocket, revolution, groove,
# hole, fillet, chamfer, draft, thickness, mirror and patterns, loft, pipe,
# datum planes; and the body's history — list, edit, remove, suppress.
# Faces and edges are named by where they are, not by index. A feature
# that fails is refused with FreeCAD's own error and nothing is kept.

import re

import FreeCAD

from .. import runners
from . import pd_common as pc
from . import picks

GROUP = "feature"
INFO = "PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, datum planes) and the body's feature history."

# The tools themselves are data (agentlink/data/tools.json, run by
# agentlink/runners.py's steps runner): each entry has the tool's words, its
# checks with their refusals, the order of its steps and its answer. What is
# here is what those entries call by name: the family's finishing code and
# the small functions that are FreeCAD's API (docs/data-tools.md).

V = FreeCAD.Vector
KEYS = ("SideType", "Type", "Type2", "Length", "Length2", "Offset", "TaperAngle", "Midplane", "Reversed", "Angle", "Angle2", "Radius", "ChamferType", "Size", "Size2", "Value", "Join",
        "Occurrences", "TransformMode", "Factor", "Diameter", "Depth", "DepthType", "Threaded", "ModelThread", "ThreadType", "ThreadSize", "HoleCutType", "HoleCutDiameter", "HoleCutDepth",
        "Ruled", "Closed", "Mode", "Pitch", "Height", "Turns", "Suppressed", "Refine")


def has(o, p):
    return p in o.PropertiesList


def set_sides(f, side, length2=None):
    """A pad's or pocket's one | two | symmetric, after its Type is set.
    FreeCAD 1.1: SideType ("One side", "Two sides", "Symmetric") with a
    Type2 / Length2 for the second side; before it, Midplane and Type
    TwoLengths (1.1 warns when Midplane is set, and keeps "?TwoLengths" only
    to read old files). False where this FreeCAD has no two sides for the
    feature's Type (the entry refuses), True otherwise."""
    if side in (None, "one"):
        return True
    if has(f, "SideType"):
        f.SideType = {"two": "Two sides", "symmetric": "Symmetric"}[side]
        if side == "two" and length2 is None and has(f, "Type2") and f.Type == "ThroughAll":
            f.Type2 = "ThroughAll"  # through all, both ways: the second side is a 5 mm length otherwise
    elif side == "symmetric":
        f.Midplane = True
    elif f.Type != "Length":
        return False
    else:
        f.Type = "TwoLengths"
    if side == "two" and length2 is not None:
        f.Length2 = float(length2)
    return True


def thread_key(name):
    """(8.0, 1.0) of "M8x1", "M8x1.0" or "m8 x 1"; (5.0, None) of "M5";
    None of what is not a metric designation."""
    m = re.match(r"^\s*[Mm]\s*(\d+(?:\.\d+)?)(?:\s*[xX×]\s*(\d+(?:\.\d+)?))?\s*$", str(name))
    return (float(m.group(1)), float(m.group(2)) if m.group(2) else None) if m else None


def thread_pick(sizes, thread, coarse):
    """The designation in sizes that thread names: the same text, else the
    same diameter and pitch (FreeCAD 1.1 writes "M5x0.8", "M8x1.0"); a
    diameter alone picks the coarse one."""
    if thread in sizes:
        return thread
    want = thread_key(thread)
    if want is None:
        return None
    for z in sizes:
        k = thread_key(z)
        if k is None or abs(k[0] - want[0]) > 1e-9:
            continue
        if want[1] is None:
            if coarse:
                return z
        elif k[1] is not None and abs(k[1] - want[1]) <= 1e-9:
            return z
    return None


def hole_spots(sk, f):
    """How many holes the sketch gives: FreeCAD drills at every circle and
    arc that is not construction geometry, and (1.1, by the Hole's
    BaseProfileType: 1 points, 2 circles, 4 arcs) at every sketch point."""
    mask = int(getattr(f, "BaseProfileType", 6))
    n = 0
    for i, g in enumerate(sk.Geometry):
        try:
            if sk.getConstruction(i):
                continue
        except Exception:
            pass
        t = type(g).__name__
        if (t == "Circle" and mask & 2) or (t == "ArcOfCircle" and mask & 4) or (t == "Point" and mask & 1):
            n += 1
    return n, bool(mask & 1)


def key_values(f):
    """A feature's key values as feature_list shows them: each of KEYS it
    has, left out where it says nothing (a false flag, a second length of a
    one-sided pad, a pattern's step outside Spacing mode), its profile, its
    originals, a dress-up's edges or faces, and what is bound to what."""
    out = {}
    for k in KEYS:
        if has(f, k):
            try:
                v = getattr(f, k)
            except Exception:
                continue
            v = picks.num_json(v)
            if k in ("Suppressed", "Refine", "Midplane", "Reversed", "Threaded", "ModelThread", "Ruled", "Closed", "TaperAngle") and not v:
                continue
            if k in ("Length2", "Type2") and not (has(f, "SideType") and f.SideType == "Two sides"):
                continue
            if k == "Angle2" and not (has(f, "Type") and f.Type == "TwoAngles"):
                continue
            if k == "Size2" and not (has(f, "ChamferType") and f.ChamferType == "Two distances"):
                continue
            if k == "Offset" and (not v if not has(f, "Occurrences") else getattr(f, "Mode", None) != "Spacing"):
                # a pad's offset from its up-to face (0: none); a pattern's step, used in Spacing mode only
                continue
            if k == "TransformMode" and v == "Features":
                continue
            out[k[0].lower() + k[1:]] = v
    for k in ("Profile",):
        if has(f, k) and getattr(f, k):
            p = getattr(f, k)
            out["profile"] = (p[0] if isinstance(p, tuple) else p).Label
    if has(f, "Originals") and f.Originals:
        out["originals"] = [o.Label for o in f.Originals]
    if has(f, "Base") and f.isDerivedFrom("PartDesign::DressUp") and f.Base:
        out["on"] = list(f.Base[1])
    bound = {p.lstrip("."): e for p, e in getattr(f, "ExpressionEngine", [])}
    if bound:
        out["bound"] = bound
    return out


def own_keys(f):
    """The key properties f has, as a refusal lists them."""
    return ", ".join(k for k in KEYS if has(f, k))


def version():
    """This FreeCAD's version, "1.1.3"."""
    return ".".join(FreeCAD.Version()[:3])


def solid_tip(b):
    """The body's tip when it has a solid (None for an empty body, or one
    whose tip has no shape yet)."""
    tip = b.Tip
    return tip if (tip is not None and not tip.Shape.isNull() and tip.Shape.Solids) else None


def profile_sketch(f):
    """The sketch a feature is built on: its Profile, which FreeCAD keeps as
    the sketch or as (sketch, [sub-elements]). None when it has none."""
    prof = getattr(f, "Profile", None)
    return (prof[0] if isinstance(prof, tuple) else prof) if prof else None


def users_of(f, b):
    """The labels of what refers to f by a property of its own: a sketch on
    its face, a fillet of its edges, a pattern of it. The feature after it
    (whose BaseFeature it is) does not: the body re-links that itself. Each
    once: InList repeats an object per link."""
    return list(dict.fromkeys(o.Label for o in f.InList if o != b and o.TypeId != "PartDesign::Body" and pc.uses(o, f)))


def multi_steps(b):
    """{ step's name: its MultiTransform's label }: a MultiTransform's steps
    sit in the body after it, as FreeCAD keeps them."""
    out = {}
    for o in b.Group:
        if o.TypeId == "PartDesign::MultiTransform":
            out.update({t.Name: o.Label for t in o.Transformations})
    return out


def whole_mode(f):
    """FreeCAD 1.1's own whole-body mode of a Transformed feature
    (TransformMode: "Features" | "Whole shape"; "body" for a release that
    words it so), or None where it has none."""
    if "TransformMode" not in f.PropertiesList:
        return None
    try:
        modes = list(f.getEnumerationsOfProperty("TransformMode") or [])
    except Exception:
        modes = []
    return next((m for m in modes if "whole" in m.lower()), None) or next((m for m in modes if "body" in m.lower()), None)


def whole_body(f, b, prior):
    """The whole body transformed by the new feature f: FreeCAD's own mode
    where it has it, else every additive and subtractive feature up to
    prior (the tip before f, which the body is read up to: the tip is put
    back on f whatever happens) as the originals. What was used, in words;
    None when the body has no such feature."""
    b.Tip = prior
    try:
        pick = whole_mode(f)
        if pick:
            f.TransformMode = pick
            return f"the whole body (FreeCAD's TransformMode \"{pick}\")"
        feats = [o for o in pc.solid_features(b, upto=None) if o is not f and o.isDerivedFrom("PartDesign::FeatureAddSub")]
        if not feats:
            return None
        f.Originals = feats
        return f"every additive and subtractive feature ({', '.join(o.Label for o in feats)}); fillets and chamfers are not repeated this way"
    finally:
        b.Tip = f


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def new(b, kind, label):
        """A new feature of the body, labelled (uniquely) and made the tip:
        some releases leave the tip where it was for a pattern, and the body
        is the new feature's shape from here on. A datum plane is no tip."""
        label = s.unique(label)
        f = b.newObject(kind, kind.split("::")[-1])
        f.Label = label
        if kind != "PartDesign::Plane" and b.Tip != f:
            b.Tip = f
        return f

    def settle(b, f, tool, before=None, must_change=None, hint=""):
        """Recompute, refuse a feature (or a later one) that failed or changed
        nothing where it must, else the body's reading (pd_common.settle)."""
        return pc.settle(s, b, f, tool, before, must_change, hint=hint)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "settle": settle, "new": new, "snapshot": lambda tool: s.snapshot(tool), "steps": lambda: len(s.steps),
               "body": lambda ref: pc.pd_body(doc(), ref), "sketch_of": lambda ref, b=None: pc.sketch_of(doc(), ref, b), "in_body": pc.in_body,
               "volume": pc.volume, "tip_shape": pc.tip_shape, "solid_tip": solid_tip, "body_reading": pc.body_reading, "short": pc.short, "version": version,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "setprop": setattr, "xyz": pc.geo.vec, "vec3": pc.vec3, "num_json": picks.num_json,
               # faces, edges, planes and axes by where they are (pd_common)
               "find_faces": lambda *x: pc.find_faces(*x), "find_edges": lambda *x: pc.find_edges(*x), "ref_shape": pc.ref_shape, "ref_names": pc.ref_names,
               "plane_ref": lambda *x: pc.plane_ref(*x), "axis_ref": lambda *x: pc.axis_ref(*x), "support_prop": pc.support_prop,
               "ref_snapshot": pc.ref_snapshot, "repair_refs": pc.repair_refs, "broken": pc.broken,
               # the family's
               "has_prop": has, "own_keys": own_keys, "set_sides": set_sides, "thread_key": thread_key, "thread_pick": thread_pick, "hole_spots": hole_spots,
               "key_values": key_values, "profile_sketch": profile_sketch, "users_of": users_of, "multi_steps": multi_steps, "whole_body": whole_body}
    return runners.tools(GROUP, s, helpers)
