# SPDX-License-Identifier: LGPL-2.1-or-later
# PartDesign features, one call each: pad, pocket, revolution, groove,
# hole, fillet, chamfer, draft, thickness, mirror and patterns, loft, pipe,
# datum planes; and the body's history — list, edit, remove, suppress.
# Faces and edges are named by where they are, not by index. A feature
# that fails is refused with FreeCAD's own error and nothing is kept.

import re

import FreeCAD

from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import pd_common as pc
from . import picks

GROUP = "feature"
INFO = "PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, datum planes) and the body's feature history."

V = FreeCAD.Vector
KEYS = ("SideType", "Type", "Type2", "Length", "Length2", "Offset", "TaperAngle", "Midplane", "Reversed", "Angle", "Angle2", "Radius", "ChamferType", "Size", "Size2", "Value", "Join",
        "Occurrences", "TransformMode", "Factor", "Diameter", "Depth", "DepthType", "Threaded", "ModelThread", "ThreadType", "ThreadSize", "HoleCutType", "HoleCutDiameter", "HoleCutDepth",
        "Ruled", "Closed", "Mode", "Pitch", "Height", "Turns", "Suppressed", "Refine")
SIDES = ("one", "two", "symmetric")


def has(o, p):
    return p in o.PropertiesList


def set_sides(f, side, length2=None):
    """A pad's or pocket's one | two | symmetric, after its Type is set.
    FreeCAD 1.1: SideType ("One side", "Two sides", "Symmetric") with a
    Type2 / Length2 for the second side; before it, Midplane and Type
    TwoLengths (1.1 warns when Midplane is set, and keeps "?TwoLengths" only
    to read old files)."""
    if side in (None, "one"):
        return
    if has(f, "SideType"):
        f.SideType = {"two": "Two sides", "symmetric": "Symmetric"}[side]
        if side == "two" and length2 is None and has(f, "Type2") and f.Type == "ThroughAll":
            f.Type2 = "ThroughAll"  # through all, both ways: the second side is a 5 mm length otherwise
    elif side == "symmetric":
        f.Midplane = True
    elif f.Type != "Length":
        raise ToolError("unavailable", f"sides two with type {f.Type}: this FreeCAD ({'.'.join(FreeCAD.Version()[:3])}) has two sides for type length only — sides symmetric, or two features.")
    else:
        f.Type = "TwoLengths"
    if side == "two" and length2 is not None:
        f.Length2 = float(length2)


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


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def body_sketch(a, key="sketch"):
        b = pc.pd_body(doc(), a.get("body"))
        sk = pc.sketch_of(doc(), a.get(key), b)
        if not b.hasObject(sk):
            raise ToolError("invalid_input", f"{sk.Label} is not in {b.Label}: a feature takes a sketch of its own body.")
        return b, sk

    def sketch_note(sk):
        dof = getattr(sk, "DoF", None)
        return {"sketchDof": dof} if dof else {}

    def new(b, kind, label):
        label = s.unique(label)
        f = b.newObject(kind, kind.split("::")[-1])
        f.Label = label
        # Some releases leave the tip where it was for a pattern: the body
        # is the new feature's shape from here on.
        if kind != "PartDesign::Plane" and b.Tip != f:
            b.Tip = f
        return f

    def sketched(kind, additive):
        tool = {"Pad": "pd_pad", "Pocket": "pd_pocket"}[kind]

        def run(a):
            b, sk = body_sketch(a)
            before = pc.volume(b)
            tip = b.Tip if (b.Tip is not None and not b.Tip.Shape.isNull() and b.Tip.Shape.Solids) else None
            if not additive and tip is None:
                raise ToolError("invalid_state", f"{b.Label} has no solid to pocket: pd_pad (or pd_primitive) first.")
            # FreeCAD's Type strings (FeaturePad.cpp, FeaturePocket.cpp): a pad
            # has UpToLast where a pocket has ThroughAll.
            types = {"length": "Length", "up_to_face": "UpToFace", "up_to_first": "UpToFirst", **({"up_to_last": "UpToLast"} if additive else {"through_all": "ThroughAll"})}
            typ = a.get("type") or ("up_to_face" if a.get("upToFace") is not None else "length")
            if typ not in types:
                raise bad(f"type {typ!r}: one of {', '.join(types)}"
                          + (" — a pad has no through_all: up_to_last goes to the body's far side." if additive and typ == "through_all"
                             else " — a pocket has no up_to_last: through_all." if typ == "up_to_last" else "."))
            side = a.get("sides") or "one"
            if side not in SIDES:
                raise bad(f"sides {side!r}: one, two (with length2) or symmetric.")
            if typ != "length" and tip is None:
                raise ToolError("invalid_state", f"type {typ}: {b.Label} has no solid to go up to yet — the first pad takes type length.")
            L = a.get("length")
            if typ == "length" and (not isinstance(L, (int, float)) or isinstance(L, bool) or L <= 0):
                raise bad(f"length: mm, over 0 — or type {' | '.join(t for t in types if t != 'length')}.")
            L2 = a.get("length2")
            if side == "two" and typ == "length" and (not isinstance(L2, (int, float)) or isinstance(L2, bool) or L2 <= 0):
                raise bad("sides two: give length2, the mm on the other side of the sketch (length is this side's) — or sides symmetric to share length both ways.")
            taper = a.get("taper")
            if taper and (not isinstance(taper, (int, float)) or abs(taper) >= 90):
                raise bad("taper: degrees, under 90 (positive widens it away from the sketch; type length only).")
            up_face = None
            if typ == "up_to_face":
                if a.get("upToFace") is None:
                    raise bad("type up_to_face: give upToFace — { at: [x,y,z], normal: [x,y,z] } on the body, or \"Face8\" as shape_query names it.")
                up_face = pc.find_faces(pc.ref_shape(b, tip.Shape), [a["upToFace"]], pc.ref_names(b, tip))[0]
            f = new(b, f"PartDesign::{kind}", kind)
            f.Profile = sk
            if typ == "up_to_face":
                f.Type = "UpToFace"
                f.UpToFace = (tip, [up_face])
            elif typ != "length":
                f.Type = types[typ]
            else:
                f.Length = float(L)
            set_sides(f, side, L2 if typ == "length" else None)
            if a.get("reversed"):
                f.Reversed = True
            if taper and has(f, "TaperAngle"):
                f.TaperAngle = float(taper)
            out = pc.settle(s, b, f, tool, before, "add" if additive else "cut",
                            hint=("Check the sketch with sketch_state (closed wires, no open vertices)" + ("; reversed: true goes the other way into the body." if not additive else "; reversed: true goes the other way.")))
            out.update(sketch_note(sk))
            return out

        return run

    def revolved(kind):
        def run(a):
            b, sk = body_sketch(a)
            before = pc.volume(b)
            if kind == "Groove" and before <= 0:
                raise ToolError("invalid_state", f"{b.Label} has no solid to groove: pd_pad or pd_revolution first.")
            angle = a.get("angle", 360)
            if not isinstance(angle, (int, float)) or isinstance(angle, bool) or not (0 < angle <= 360):
                raise bad("angle: degrees, over 0 up to 360.")
            # A revolution has no SideType: Midplane shares the angle both
            # ways; two angles are its Type "TwoAngles" with Angle2
            # (FeatureRevolution.cpp, FeatureGroove.cpp).
            side = a.get("sides") or "one"
            if side not in ("one", "symmetric"):
                raise bad(f"sides {side!r}: one or symmetric (the angle shared both ways). Two different angles: make it one-sided, then "
                          "feature_edit { feature, set: { Type: \"TwoAngles\", Angle2: … } }.")
            f = new(b, f"PartDesign::{kind}", kind)
            f.Profile = sk
            f.ReferenceAxis = pc.axis_ref(b, a.get("axis", "V_Axis"), sk)[0]
            f.Angle = float(angle)
            if side == "symmetric":
                f.Midplane = True
            if a.get("reversed"):
                f.Reversed = True
            out = pc.settle(s, b, f, "pd_" + kind.lower(), before, "add" if kind == "Revolution" else "cut",
                            hint="The profile must be closed and lie wholly on one side of the axis (sketch_state)" + (": reversed: true turns a part-turn groove the other way." if kind == "Groove" else "."))
            out.update(sketch_note(sk))
            return out

        return run

    def pd_hole(a):
        b, sk = body_sketch(a)
        tip, _ = pc.tip_shape(b)
        before = pc.volume(b)
        thread = a.get("thread")
        d = a.get("diameter")
        if not thread and (not isinstance(d, (int, float)) or isinstance(d, bool) or d <= 0):
            raise bad("diameter: mm, over 0 — or thread: \"M5\" for a standard size.")
        depth = a.get("depth", "through")
        if depth != "through" and (not isinstance(depth, (int, float)) or isinstance(depth, bool) or depth <= 0):
            raise bad("depth: mm, over 0, or \"through\".")
        point = a.get("drillPoint", "flat")
        if point not in ("flat", "angled"):
            raise bad("drillPoint: flat or angled (118°).")
        fit = a.get("fit")
        fit_names = {"close": ("Fine", "Close"), "normal": ("Medium", "Normal"), "loose": ("Coarse", "Loose", "Wide")}
        if fit is not None and fit not in fit_names:
            raise bad("fit: close, normal or loose (a clearance hole's: with thread and threaded: false).")
        f = new(b, "PartDesign::Hole", "Hole")
        f.Profile = sk
        spots, points = hole_spots(sk, f)
        if not spots:
            raise bad(f"{sk.Label} has no circles" + (" or points" if points else "") + ": a hole is drilled at each circle's centre"
                      + (" and at each point" if points else "") + " — sketch_add them (not as construction) on the face the holes enter.")
        if thread:
            # FreeCAD 1.1 names them "M5x0.8" (coarse) and "M8x1.0" (fine).
            f.ThreadType = "ISOMetricProfile"
            sizes = list(f.getEnumerationsOfProperty("ThreadSize"))
            pick = thread_pick(sizes, thread, True)
            if pick is None:
                f.ThreadType = "ISOMetricFineProfile"
                fine = list(f.getEnumerationsOfProperty("ThreadSize"))
                pick = thread_pick(fine, thread, False)
                if pick is None:
                    key = thread_key(thread)
                    same = [z for z in fine if key and (thread_key(z) or (None,))[0] == key[0]]
                    raise bad(f"thread {thread!r}: not an ISO metric size FreeCAD has — coarse by diameter (\"M5\"): {', '.join(sizes[6:16])} …; "
                              + (f"fine pitches for M{key[0]:g}: {', '.join(same)}." if same else f"fine with its pitch: {', '.join(fine[10:14])} …")
                              + " Other standards (UNC, UNF, BSP …): make the hole by diameter, then feature_edit its ThreadType and ThreadSize.")
            f.ThreadSize = pick
            f.Threaded = bool(a.get("threaded", True))
            if f.Threaded and has(f, "ModelThread"):
                f.ModelThread = bool(a.get("modelThread", False))
            if not f.Threaded and fit and has(f, "ThreadFit"):
                fits = list(f.getEnumerationsOfProperty("ThreadFit"))
                got = next((x for x in fit_names[fit] if x in fits), None)
                if got:
                    f.ThreadFit = got
        else:
            f.Diameter = float(d)
        if depth == "through":
            f.DepthType = "ThroughAll"
        else:
            f.DepthType = "Dimension"
            f.Depth = float(depth)
        f.DrillPoint = "Angled" if point == "angled" else "Flat"
        cut = a.get("cut")
        if cut:
            opts = list(f.getEnumerationsOfProperty("HoleCutType"))
            want = next((o for o in opts if o.lower() == str(cut).lower() and o != "None"), None)
            if want is None:
                raise bad(f"cut {cut!r}: one of {', '.join(o if ' ' in o else o.lower() for o in opts if o != 'None')}"
                          + ("." if thread else " (a thread size adds the screw standards FreeCAD has)."))
            f.HoleCutType = want
            if any(k in a for k in ("cutDiameter", "cutDepth", "countersinkAngle")) or not thread:
                if has(f, "HoleCutCustomValues"):
                    f.HoleCutCustomValues = True
                if "cutDiameter" in a:
                    f.HoleCutDiameter = float(a["cutDiameter"])
                elif not thread:
                    raise bad("cutDiameter: mm — needed for a counterbore or countersink on a plain diameter (a thread size gives its own).")
                if "cutDepth" in a:
                    f.HoleCutDepth = float(a["cutDepth"])
                if "countersinkAngle" in a:
                    f.HoleCutCountersinkAngle = float(a["countersinkAngle"])
        if a.get("reversed"):
            f.Reversed = True
        out = pc.settle(s, b, f, "pd_hole", before, "cut", hint="The hole goes against the sketch's normal: put the sketch on the face it enters, or reversed: true.")
        out["holes"] = spots
        out["diameter"] = picks.num_json(f.Diameter)
        if thread:
            out["thread"] = f.ThreadSize + (" (cosmetic)" if f.Threaded and not getattr(f, "ModelThread", False) else "" if f.Threaded else " clearance")
        if cut:
            out["cut"] = {"type": f.HoleCutType, "diameter": picks.num_json(f.HoleCutDiameter), "depth": picks.num_json(f.HoleCutDepth)}
        return out

    def dressup(kind):
        def run(a):
            b = pc.pd_body(doc(), a.get("body"))
            tip, shape = pc.tip_shape(b)
            before = pc.volume(b)
            size_key = {"Fillet": "radius", "Chamfer": "size", "Draft": "angle", "Thickness": "thickness"}[kind]
            v = a.get(size_key, 1.5 if kind == "Draft" else 1)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or (v <= 0 and kind != "Draft") or (kind == "Draft" and not (0 < abs(v) < 90)):
                raise bad(f"{size_key}: " + ("degrees, between 0 and 90 (reversed: true tilts the other way)." if kind == "Draft" else "mm, over 0."))
            if kind == "Chamfer" and "size2" in a and "angle" in a:
                raise bad("size2 or angle, not both: size2 is the second distance (two distances), angle goes with size (distance and angle).")
            if kind == "Thickness" and a.get("join") not in (None, "arc", "intersection"):
                raise bad("join: arc (rounded outside corners) or intersection (sharp).")
            if kind in ("Fillet", "Chamfer"):
                subs = pc.find_edges(pc.ref_shape(b, shape), a.get("edges"), pc.ref_names(b, tip))
            else:
                subs = pc.find_faces(pc.ref_shape(b, shape), a.get("faces"), pc.ref_names(b, tip))
            if kind == "Draft":
                # Read before the feature exists: once it is the tip (with no
                # shape yet) a face query has no solid to look on.
                neutral = pc.plane_ref(b, a.get("neutral", "XY"), "neutral")[0]
                pull = pc.axis_ref(b, a.get("pull", "z"), None, "pull")[0]
            f = new(b, f"PartDesign::{kind}", kind)
            f.Base = (tip, subs)
            tool = {"Fillet": "pd_fillet", "Chamfer": "pd_chamfer", "Draft": "pd_draft", "Thickness": "pd_thickness"}[kind]
            if kind == "Fillet":
                f.Radius = float(v)
                hint = "A radius larger than a face beside the edge fails, and edges that are already smooth (tangent) cannot be rounded: try smaller, or fewer edges."
            elif kind == "Chamfer":
                f.Size = float(v)
                if "size2" in a:
                    f.ChamferType = "Two distances"
                    f.Size2 = float(a["size2"])
                elif "angle" in a:
                    f.ChamferType = "Distance and Angle"
                    f.Angle = float(a["angle"])
                hint = "A chamfer wider than a face beside the edge fails: try smaller."
            elif kind == "Draft":
                f.Angle = float(v)
                f.NeutralPlane = neutral
                f.PullDirection = pull
                if a.get("reversed"):
                    f.Reversed = True
                hint = "Draft takes flat or cylindrical faces that meet the neutral plane and stand along the pull direction; reversed: true tilts them the other way."
            else:
                f.Value = float(v)
                f.Reversed = not a.get("outward", False)
                f.Join = "Intersection" if a.get("join") == "intersection" else "Arc"
                hint = "A wall thicker than an inside fillet's radius or than a thin feature fails: thinner, or join: intersection; shell before filleting."
            # A fillet or chamfer on an inside (concave) corner adds material,
            # on an outside one removes it: either way is right. An inward
            # shell always removes some.
            change = "changed" if kind in ("Fillet", "Chamfer") else ("cut" if kind == "Thickness" and not a.get("outward") else None)
            out = pc.settle(s, b, f, tool, before, change, hint=hint)
            out["on"] = subs
            return out

        return run

    def originals(b, refs):
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
            raise ToolError("invalid_input", "features: [names] — the features to repeat (feature_list names them) — or \"all\" for the whole body.")
        return [pc.in_body(b, r, ["PartDesign::"]) for r in refs]

    def whole_body(f, b):
        """The whole body transformed: FreeCAD 1.1's own mode (the
        Transformed feature's TransformMode: "Features" | "Whole shape")
        where it has it, else every additive and subtractive feature up to
        the tip as the originals. What was used."""
        if "TransformMode" in f.PropertiesList:
            try:
                modes = list(f.getEnumerationsOfProperty("TransformMode") or [])
            except Exception:
                modes = []
            # "Whole shape" in 1.1 (FeatureTransformed.cpp); "body" for a release that words it so.
            pick = next((m for m in modes if "whole" in m.lower()), None) or next((m for m in modes if "body" in m.lower()), None)
            if pick:
                f.TransformMode = pick
                return f"the whole body (FreeCAD's TransformMode \"{pick}\")"
        feats = [o for o in pc.solid_features(b, upto=None) if o is not f and o.isDerivedFrom("PartDesign::FeatureAddSub")]
        if not feats:
            raise ToolError("invalid_state", f"{b.Label} has no pad, pocket or other additive or subtractive feature to repeat.")
        f.Originals = feats
        return f"every additive and subtractive feature ({', '.join(o.Label for o in feats)}); fillets and chamfers are not repeated this way"

    def transformed(kind):
        def run(a):
            b = pc.pd_body(doc(), a.get("body"))
            pc.tip_shape(b)
            before = pc.volume(b)
            refs = a.get("features")
            whole = isinstance(refs, str) and refs.strip().lower() in ("all", "body", "whole body")
            if isinstance(refs, str) and not whole:
                refs = [refs]
            orig = None if whole else originals(b, refs)
            prior = b.Tip
            # The plane or axis is read before the feature exists: once it is
            # the tip (with no shape yet) a face query has no solid to look on.
            if kind == "Mirrored":
                ref = pc.plane_ref(b, a.get("plane", "YZ"), "plane")[0]
            elif kind == "LinearPattern":
                ref = pc.axis_ref(b, a.get("direction", "x"), None, "direction")[0]
            else:
                ref = pc.axis_ref(b, a.get("axis", "z"), None, "axis")[0]
            f = new(b, f"PartDesign::{kind}", kind)
            if whole:
                b.Tip = prior  # read the features up to the old tip
                try:
                    took = whole_body(f, b)
                finally:
                    b.Tip = f
            else:
                f.Originals = orig
            if kind == "Mirrored":
                f.MirrorPlane = ref
                tool = "pd_mirrored"
            else:
                n = a.get("occurrences", 2)
                if isinstance(n, float) and n.is_integer():
                    n = int(n)
                if not isinstance(n, int) or isinstance(n, bool) or n < 2:
                    raise ToolError("invalid_input", "occurrences: a whole number, 2 or more, the original counted.")
                f.Occurrences = n
                if kind == "LinearPattern":
                    f.Direction = ref
                    step = a.get("spacing", a.get("length"))
                    if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
                        raise ToolError("invalid_input", "spacing (mm between copies) or length (mm, first to last): one of them, over 0 — reversed: true goes the other way.")
                    # FreeCAD's Extent mode (the default; 1.1 adds Mode
                    # "Spacing" with Offset): Length is first to last.
                    f.Length = float(step) * (n - 1) if "spacing" in a else float(step)
                    tool = "pd_linear_pattern"
                else:
                    f.Axis = ref
                    ang = a.get("angle", 360)
                    if not isinstance(ang, (int, float)) or isinstance(ang, bool) or not (0 < ang <= 360):
                        raise ToolError("invalid_input", "angle: degrees, over 0 up to 360 (360 spaces the copies evenly all round; less is first to last; reversed: true turns the other way).")
                    f.Angle = float(ang)
                    tool = "pd_polar_pattern"
                if a.get("reversed"):
                    f.Reversed = True
            out = pc.settle(s, b, f, tool, before, None, hint="A copy of a pocket or hole must land on material; a copy of a pad that does not touch the body makes a second solid.")
            if whole:
                out["repeated"] = took
            return out

        return run

    def swept(kind):
        def run(a):
            b, sk = body_sketch(a, "profile")
            before = pc.volume(b)
            sub = bool(a.get("subtractive"))
            if sub and before <= 0:
                raise ToolError("invalid_state", f"{b.Label} has no solid to cut: pd_pad something first.")
            if kind == "Pipe":
                path = pc.sketch_of(doc(), a.get("path"), b)
                if path is sk:
                    raise bad("path: another sketch than the profile — the profile is swept along the path's edges.")
                if not path.Shape.Edges:
                    raise bad(f"path: {path.Label} has no edges (construction geometry does not count): sketch_add a line, arc or polyline.")
            f = new(b, f"PartDesign::{'Subtractive' if sub else 'Additive'}{kind}", kind)
            f.Profile = sk
            if kind == "Loft":
                secs = [pc.sketch_of(doc(), r, b) for r in (a.get("sections") or [])]
                if not secs or sk in secs:
                    raise ToolError("invalid_input", "sections: [sketch names] — the profiles after the first (profile), in order; each on its own plane (pd_datum_plane, or sketch_new with offset).")
                f.Sections = secs
                f.Ruled = bool(a.get("ruled", False))
                f.Closed = bool(a.get("closed", False))
                hint = "Sections must each be one closed wire and should have the same number of edges, started at matching corners; ruled: true for straight sides."
            else:
                f.Spine = (path, [f"Edge{i + 1}" for i in range(len(path.Shape.Edges))])
                hint = "The profile should sit at the path's start, square to it; the path's edges must join end to end; a path that turns tighter than the profile fails."
            out = pc.settle(s, b, f, f"pd_{kind.lower()}", before, "cut" if sub else "add", hint=hint)
            return out

        return run

    def pd_datum_plane(a):
        b = pc.pd_body(doc(), a.get("body"))
        base, what = pc.plane_ref(b, a.get("on", "XY"), "on")
        f = new(b, "PartDesign::Plane", a.get("name") or "DatumPlane")
        setattr(f, pc.support_prop(f), [(base[0], base[1][0])])
        f.MapMode = "FlatFace"
        rot = FreeCAD.Rotation()
        if a.get("rotate"):
            r = a["rotate"]
            if not isinstance(r, dict):
                raise bad("rotate: { axis: [x, y, z] in the plane's own frame (x, y in it, z its normal), angle: degrees }.")
            ax = pc.vec3(r.get("axis", [1, 0, 0]), "rotate.axis")
            rot = FreeCAD.Rotation(ax, float(r.get("angle", 0)))
        f.AttachmentOffset = FreeCAD.Placement(V(0, 0, float(a.get("offset", 0))), rot)
        doc().recompute()
        if not f.isValid():
            raise ToolError("failed", f"The datum plane would not attach to {what}: {f.getStatusString()} — nothing was kept. on takes a flat face or XY | XZ | YZ.")
        s.snapshot("pd_datum_plane")
        pl = f.Placement
        return {"plane": f.Label, "on": what, "origin": pc.geo.vec(pl.Base), "normal": pc.geo.vec(pl.Rotation.multVec(V(0, 0, 1))), "next": f"sketch_new {{ plane: \"{f.Label}\" }}", "step": len(s.steps)}

    def feature_list(a):
        b = pc.pd_body(doc(), a.get("body"))
        out = []
        steps = {}  # a MultiTransform's steps sit in the body after it, as FreeCAD keeps them
        for o in b.Group:
            if o.TypeId == "PartDesign::MultiTransform":
                steps.update({t.Name: o.Label for t in o.Transformations})
        for o in b.Group:
            if o.TypeId.startswith("App::Origin"):
                continue
            ok = o.isValid()
            e = {"name": o.Label, "type": pc.short(o), "valid": ok}
            if o.Name in steps:
                e["stepOf"] = steps[o.Name]
            if not ok:
                e["error"] = o.getStatusString()
            if o.TypeId == "Sketcher::SketchObject":
                e["dof"] = getattr(o, "DoF", None)
                e["geometry"] = len(o.Geometry)
            else:
                e.update(key_values(o))
            if o == b.Tip:
                e["tip"] = True
            out.append(e)
        return {"body": b.Label, "features": out, "tip": b.Tip.Label if b.Tip else None, **pc.body_reading(b)}

    def feature_edit(a):
        b = pc.pd_body(doc(), a.get("body"))
        f = pc.in_body(b, a.get("feature"), ["PartDesign::"])
        changes = a.get("set")
        if not isinstance(changes, dict) or not changes:
            raise ToolError("invalid_input", f"set: {{ Property: value }} by FreeCAD's property names — {f.Label}'s: {', '.join(k for k in KEYS if has(f, k))}.")
        before = pc.volume(b)
        refs = pc.ref_snapshot(b)
        bound = {p.lstrip("."): e for p, e in getattr(f, "ExpressionEngine", [])}
        done = {}
        for k, v in changes.items():
            if not has(f, k):
                raise ToolError("invalid_input", f"{k}: not a property of {f.Label} ({pc.short(f)}); FreeCAD's names, capitals and all — it has {', '.join(x for x in KEYS if has(f, x))}.")
            if k in bound:
                raise ToolError("invalid_state", f"{f.Label}.{k} is bound to {bound[k]!r}: param_set the parameter, or param_bind {{ target: \"{f.Label}.{k}\", expression: null }} first.")
            if k in ("Profile", "Placement", "BaseFeature", "Originals", "Base") or f.getTypeIdOfProperty(k).startswith("App::PropertyLink"):
                raise ToolError("invalid_input", f"{k}: a link (a sketch, edges, an axis) is not edited here — feature_remove {f.Label} and make it again with the pd_ tool.")
            try:
                enums = f.getEnumerationsOfProperty(k)
            except Exception:
                enums = None
            # "?TwoLengths" is kept in 1.1 only to read old files.
            if enums and (v not in enums or str(v).startswith("?")):
                raise ToolError("invalid_input", f"{k} = {v!r}: one of {', '.join(e for e in enums if not e.startswith('?'))}.")
            try:
                setattr(f, k, v)
            except Exception as e:
                raise ToolError("invalid_input", f"{k} = {v!r}: FreeCAD did not take it ({e}) — a number (mm, degrees), true or false, as feature_list shows it.")
            done[k] = picks.num_json(getattr(f, k))
        doc().recompute()
        repaired = pc.repair_refs(doc(), refs) if pc.broken(doc()) and refs else None
        out = pc.settle(s, b, f, "feature_edit", before)
        out["set"] = done
        if repaired:
            out["refsFound"] = repaired
            out["note"] = "The change renamed edges or faces later features use: each was found again by what it is (kind, size, place, direction). Check them with view_render."
        return out

    def feature_remove(a):
        b = pc.pd_body(doc(), a.get("body"))
        f = pc.in_body(b, a.get("feature"), ["PartDesign::", "Sketcher::"])
        # What refers to it by a property of its own: a sketch on its face, a
        # fillet of its edges, a pattern of it. The feature after it (whose
        # BaseFeature it is) does not: the body re-links that itself.
        users = list(dict.fromkeys(o.Label for o in f.InList if o != b and o.TypeId != "PartDesign::Body" and pc.uses(o, f)))  # each once: InList repeats an object per link
        if users and not a.get("force"):
            raise ToolError("invalid_state", f"{f.Label} is used by {', '.join(users)}: feature_remove those first (the last made first). force: true removes it anyway, and is refused with nothing kept if one of them then fails.")
        prof = getattr(f, "Profile", None)
        sk = (prof[0] if isinstance(prof, tuple) else prof) if prof else None
        # A MultiTransform's steps go with it, as in the window.
        steps = list(getattr(f, "Transformations", None) or []) if f.TypeId == "PartDesign::MultiTransform" else []
        before = pc.volume(b)
        label = f.Label
        # Body.removeObject first: it hands the next feature the one before
        # as its base and moves the tip back if this was the tip.
        b.removeObject(f)
        doc().removeObject(f.Name)
        removed = [label]
        for t in steps:
            l2 = t.Label
            if b.hasObject(t):
                b.removeObject(t)
            doc().removeObject(t.Name)
            removed.append(l2)
        if sk is not None and not a.get("keepSketch") and sk.TypeId == "Sketcher::SketchObject" and not [o for o in sk.InList if o != b]:
            l2 = sk.Label
            b.removeObject(sk)
            doc().removeObject(sk.Name)
            removed.append(l2)
        out = pc.settle(s, b, None, "feature_remove", before, None,
                        hint="A later feature was built on what this one made: feature_remove that one first, or feature_suppress this one instead.")
        out["removed"] = removed
        out["tip"] = b.Tip.Label if b.Tip else None
        return out

    def feature_suppress(a):
        b = pc.pd_body(doc(), a.get("body"))
        f = pc.in_body(b, a.get("feature"), ["PartDesign::"])
        if not has(f, "Suppressed"):
            raise ToolError("unavailable", f"{f.Label} ({pc.short(f)}) has no Suppressed property in this FreeCAD ({'.'.join(FreeCAD.Version()[:3])}; solid features have it from 1.0): feature_remove it, and history_undo brings it back.")
        before = pc.volume(b)
        f.Suppressed = bool(a.get("suppressed", True))
        out = pc.settle(s, b, f, "feature_suppress", before, hint="A later feature needs what this one makes (its faces or edges): suppress or remove that one first.")
        out["suppressed"] = bool(f.Suppressed)
        return out

    body = {"type": "string", "description": "The PartDesign body; may be left out when there is one."}
    sketch = {"type": "string", "description": "The sketch, in the body."}
    xyz = {"type": "array", "items": {"type": "number"}}
    face = {"type": "object", "description": "{ at: [x,y,z] a point on the face, normal: [x,y,z] outward }", "properties": {"at": xyz, "normal": xyz, "tol": {"type": "number"}}, "required": ["at"], "additionalProperties": False}
    faces = {"description": "faces: [{ at, normal }] by where they are, a reference shape_query gives (\"Face8\", \"Body.Face8\") or a list of them, or shape_query's filters ({ type, normal, near, x, y, z, … })"}
    edges = {"description": "edges: [{ near: [x,y,z] } the edge nearest a point | { face: { at, normal } } every edge of a face | { all: true }, kind: line|circle], a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges) or a list of them, or shape_query's filters ({ type: circle, radius, axis, near, … })"}
    plane = {"description": "XY | XZ | YZ, a datum plane's name, or a face { at, normal }"}
    # The transforms also take "all": the whole body.
    feats_all = {"description": "[feature names], or \"all\": the whole body (every feature up to the tip)", "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string", "enum": ["all"]}]}
    side = {"type": "string", "enum": list(SIDES)}
    reading = " Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept."
    ext = {"body": body, "sketch": sketch, "type": {"type": "string"}, "length": {"type": "number"}, "length2": {"type": "number"}, "sides": side,
           "reversed": {"type": "boolean"}, "upToFace": {"description": "The face to go up to: { at, normal }, \"Face8\", or shape_query's filters."}, "taper": {"type": "number"}}
    rev = {"body": body, "sketch": sketch, "axis": {"type": ["string", "integer"]}, "angle": {"type": "number"}, "sides": {"type": "string"}, "reversed": {"type": "boolean"}}
    return [
        Tool("pd_pad", "Pad a closed sketch into the body, along its normal: type length (length mm) | up_to_last | up_to_first | up_to_face (upToFace { at, normal } or \"Face8\"); sides one | two (length2 the other way) | symmetric; reversed; taper deg. The first pad takes a length. An open sketch (sketch_state first) or a pad inside the body is refused. Faces and edges are renumbered: query again." + reading,
             obj(ext), sketched("Pad", True), changes=True),
        Tool("pd_pocket", "Pocket a closed sketch out of the body: type length | through_all | up_to_first | up_to_face (upToFace); sides one | two (length2) | symmetric; reversed; taper. It cuts against the sketch's normal: one that cuts nothing is refused — reversed: true, or sketch on the face it enters. A cut that splits the body leaves 2 solids (allowed by its AllowCompound; health says so)." + reading,
             obj(ext), sketched("Pocket", False), changes=True),
        Tool("pd_revolution", "Revolve a closed sketch about an axis: axis V_Axis (default) | H_Axis (the sketch's) | x | y | z (the body's) | a datum line | a line's geometry id (from 0); angle deg (360); sides one | symmetric; reversed. The profile must not cross the axis. Two angles: feature_edit { Type: \"TwoAngles\", Angle2 }." + reading,
             obj(rev), revolved("Revolution"), changes=True),
        Tool("pd_groove", "Cut by revolving a closed sketch about an axis (inputs as pd_revolution). A groove that cuts nothing is refused." + reading,
             obj(rev), revolved("Groove"), changes=True),
        Tool("pd_hole", "Holes at the centre of every circle of a sketch (FreeCAD 1.1: at its points too; not construction geometry) on the face they enter, drilled against its normal: diameter mm, or thread \"M5\" (ISO coarse; \"M8x1\" fine) — threaded (default true: tap-drill size, cosmetic unless modelThread) or a clearance hole (threaded: false, fit close|normal|loose); depth mm | \"through\"; drillPoint flat|angled; cut counterbore|countersink|counterdrill with cutDiameter, cutDepth, countersinkAngle (a thread size gives standard ones). Reply adds holes, diameter, thread, cut." + reading,
             obj({"body": body, "sketch": sketch, "diameter": {"type": "number"}, "thread": {"type": "string"}, "threaded": {"type": "boolean"}, "modelThread": {"type": "boolean"}, "fit": {"type": "string"}, "depth": {"type": ["number", "string"]}, "drillPoint": {"type": "string"}, "cut": {"type": "string"},
                  "cutDiameter": {"type": "number"}, "cutDepth": {"type": "number"}, "countersinkAngle": {"type": "number"}, "reversed": {"type": "boolean"}}), pd_hole, changes=True),
        Tool("pd_fillet", "Round edges of the body: edges [{ near: [x,y,z] } the edge nearest a point | { face: { at, normal } } every edge of a face | { all: true }, kind: line|circle to filter], or what shape_query answers (\"Edge3\", \"Body.Edge3\", a list, its items) or its filters ({ type: circle, radius: 3 } every such edge; with near, the nearest); radius mm (default 1). References are good until the next change: query again after one. Smooth (tangent) edges are skipped. An inside corner gains material, an outside one loses it: both are right. Reply adds on (the edges)." + reading,
             obj({"body": body, "edges": edges, "radius": {"type": "number"}}, ["edges"]), dressup("Fillet"), changes=True),
        Tool("pd_chamfer", "Bevel edges of the body: edges as pd_fillet; size mm (default 1); size2 for two distances or angle deg for distance and angle (one of them). On an inside corner it adds material, on an outside one it removes it: only a chamfer that changes nothing is refused." + reading,
             obj({"body": body, "edges": edges, "size": {"type": "number"}, "size2": {"type": "number"}, "angle": {"type": "number"}}, ["edges"]), dressup("Chamfer"), changes=True),
        Tool("pd_draft", "Taper faces for moulding: faces [{ at, normal }] (or shape_query's references or filters), angle deg (1.5), neutral plane the faces pivot on (XY default, a datum plane, or a face; they must meet it), pull direction x|y|z (z) or a datum line, reversed." + reading,
             obj({"body": body, "faces": faces, "angle": {"type": "number"}, "neutral": plane, "pull": {"type": "string"}, "reversed": {"type": "boolean"}}, ["faces"]), dressup("Draft"), changes=True),
        Tool("pd_thickness", "Shell the body: faces [{ at, normal }] (or shape_query's references or filters) to open (removed), thickness mm of the wall (1), inward unless outward: true; join arc|intersection. A wall thicker than an inside fillet fails: shell before filleting." + reading,
             obj({"body": body, "faces": faces, "thickness": {"type": "number"}, "outward": {"type": "boolean"}, "join": {"type": "string"}}, ["faces"]), dressup("Thickness"), changes=True),
        Tool("pd_mirrored", "Mirror features (by name) across a plane: XY | XZ | YZ (default), a datum plane, or a face query; features: \"all\" mirrors the whole body (FreeCAD 1.1's TransformMode \"Whole shape\", else every pad and pocket up to the tip). A copy that misses the body makes a second solid (health says so)." + reading,
             obj({"body": body, "features": feats_all, "plane": plane}, ["features"]), transformed("Mirrored"), changes=True),
        Tool("pd_linear_pattern", "Repeat features in a line: direction x|y|z (x) or a datum line, occurrences (2 or more, the original counted), spacing mm between copies or length mm first to last, reversed; features: \"all\" repeats the whole body. A grid: pd_multitransform." + reading,
             obj({"body": body, "features": feats_all, "direction": {"type": "string"}, "occurrences": {"type": "integer"}, "spacing": {"type": "number"}, "length": {"type": "number"}, "reversed": {"type": "boolean"}}, ["features"]), transformed("LinearPattern"), changes=True),
        Tool("pd_polar_pattern", "Repeat features around an axis: axis x|y|z (the body's; z) or a datum line (pd_datum), occurrences (the original counted), angle deg (360 spreads them evenly round; less is first to last), reversed; features: \"all\" repeats the whole body." + reading,
             obj({"body": body, "features": feats_all, "axis": {"type": "string"}, "occurrences": {"type": "integer"}, "angle": {"type": "number"}, "reversed": {"type": "boolean"}}, ["features"]), transformed("PolarPattern"), changes=True),
        Tool("pd_loft", "Loft through closed sketches: profile (the first), sections [the rest, in order, each on its own plane], ruled, closed; subtractive: true cuts it. Sketches should have the same edge count and matching start corners, or it twists." + reading,
             obj({"body": body, "profile": sketch, "sections": {"type": "array", "items": {"type": "string"}}, "ruled": {"type": "boolean"}, "closed": {"type": "boolean"}, "subtractive": {"type": "boolean"}}, ["profile", "sections"]), swept("Loft"), changes=True),
        Tool("pd_pipe", "Sweep a closed profile sketch along a path sketch (all its edges, joined end to end); subtractive: true cuts it. The profile should sit across the path's start. Orientation, corners: feature_edit { Mode: \"Frenet\", Transition: \"Round corner\" }." + reading,
             obj({"body": body, "profile": sketch, "path": sketch, "subtractive": {"type": "boolean"}}, ["profile", "path"]), swept("Pipe"), changes=True),
        Tool("pd_datum_plane", "A datum plane in the body, on XY | XZ | YZ | a flat face query, offset mm along its normal, rotate { axis [x,y,z] (its own), angle deg }, name: for sketches off the body's planes (sketch_new { plane: its name }). Reply: plane, origin, normal.",
             obj({"body": body, "on": plane, "offset": {"type": "number"}, "rotate": {"type": "object"}, "name": {"type": "string"}}), pd_datum_plane, changes=True),
        Tool("feature_list", "The body's features in order: type, key values (lengths mm, angles deg, FreeCAD's type strings), what each is bound to, valid or not with FreeCAD's error, the tip, a MultiTransform's steps (stepOf); sketches with their dof. Changes nothing.", obj({"body": body}), feature_list),
        Tool("feature_edit", "Change a feature's properties by FreeCAD's names: set { Length: 20, Type: \"ThroughAll\", Reversed: true, Radius: 2, Occurrences: 4, Refine: true, … } (feature_list shows them; a wrong enumeration value lists the right ones); recomputes. Links (sketch, edges, axis) are not edited: remove and remake. A change that breaks it or a later feature is refused and undone; fillets whose edges it renumbered are found again (refsFound). A property bound to a parameter is changed with param_set.",
             obj({"body": body, "feature": {"type": "string"}, "set": {"type": "object"}}, ["feature", "set"]), feature_edit, changes=True),
        Tool("feature_remove", "Remove a feature (and its sketch unless keepSketch, when nothing else uses it; a MultiTransform's steps too). One that others use (a sketch on its face, a fillet of its edges, a pattern of it) is refused unless force. Later features that break are refused and nothing kept. Reply: removed, tip.",
             obj({"body": body, "feature": {"type": "string"}, "keepSketch": {"type": "boolean"}, "force": {"type": "boolean"}}, ["feature"]), feature_remove, changes=True),
        Tool("feature_suppress", "Suppress a feature (suppressed: false brings it back): the body is computed as if it were not there, and it stays in the history. Refused when a later feature needs its faces or edges.",
             obj({"body": body, "feature": {"type": "string"}, "suppressed": {"type": "boolean"}}, ["feature"]), feature_suppress, changes=True),
    ]
