# SPDX-License-Identifier: LGPL-2.1-or-later
# More of the Assembly workbench, beside assembly.py's joints and checks:
# fits — the hole and the shaft a joint puts together, found by their axes,
# measured and held against an ISO 286 fit; poses and joint limits — a
# joint moved and left there, inside the limits FreeCAD keeps on it; an
# exploded layout that collapses again (kept in the document); and FreeCAD's
# own bill of materials.

import json
import math
import os

import FreeCAD
import Part

from .. import iso286
from .. import paths
from .. import store
from .. import runners
from ..protocol import ToolError, bad
from ..materials import DENSITY

from . import assembly as A
from . import picks
from .picks import r4

GROUP = "assembly"
INFO = ("Assemblies (FreeCAD's Assembly workbench): parts put together, one grounded, joints solved; overlaps, sweeps, "
        "fits (hole and shaft against H7/g6 …), poses and joint limits, exploded layouts, and the bill of materials.")

V = FreeCAD.Vector
EXPLODED = "AgentLinkExploded"
POSE = "AgentLinkPose"


def vec(v):
    return [r4(v.x), r4(v.y), r4(v.z)]


def joint_frames(j):
    """The joint's two coordinate systems in the world (JCS1, JCS2), as the
    Assembly workbench reads them, or None where it cannot."""
    try:
        import UtilsAssembly as U

        return U.getJcsGlobalPlc(j.Placement1, j.Reference1), U.getJcsGlobalPlc(j.Placement2, j.Reference2)
    except Exception:
        return None


def joint_value(j, turning):
    """Where the joint is now, the way its limits are read: the turn of JCS2
    about JCS1's z (degrees, -180 … 180) or JCS2's offset along it (mm).
    None where the frames cannot be read."""
    fr = joint_frames(j)
    if fr is None:
        return None
    rel = fr[0].inverse().multiply(fr[1])
    if turning:
        x = rel.Rotation.multVec(V(1, 0, 0))
        return math.degrees(math.atan2(x.y, x.x))
    return float(rel.Base.z)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def is_exploded(asm):
    return EXPLODED in asm.PropertiesList and bool(asm.getPropertyByName(EXPLODED))


def _suppress(j, off):
    """Joint j left out of the solve (off) or back in; the property differs
    by release (Suppressed in 1.1, Activated in 1.0)."""
    if "Suppressed" in j.PropertiesList:
        j.Suppressed = bool(off)
    elif "Activated" in j.PropertiesList:
        j.Activated = not off


def _is_suppressed(j):
    if "Suppressed" in j.PropertiesList:
        return bool(j.Suppressed)
    if "Activated" in j.PropertiesList:
        return not bool(j.Activated)
    return False


# ---- elements and axes ----


def axis_of(el):
    """(point, direction) of a round element: a cylindrical face, a circle
    edge; for a flat face its middle and normal."""
    if el is None:
        return None
    if isinstance(el, Part.Face):
        srf = el.Surface
        if hasattr(srf, "Axis") and hasattr(srf, "Center") and hasattr(srf, "Radius"):
            return V(srf.Center), V(srf.Axis)
        if isinstance(srf, Part.Plane):
            u0, u1, v0, v1 = el.ParameterRange
            return el.CenterOfMass, el.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    if isinstance(el, Part.Edge) and hasattr(el.Curve, "Axis") and hasattr(el.Curve, "Radius"):
        return V(el.Curve.Center), V(el.Curve.Axis)
    return None


def cylinders(part, pt, d, tol_off=None):
    """The part's cylindrical faces on the line (pt, d): each (face, radius,
    convex, [lo, hi] along the axis)."""
    d = V(d)
    d.normalize()
    out = []
    for f in part.Shape.Faces:
        s = f.Surface
        if not (hasattr(s, "Radius") and hasattr(s, "Axis") and hasattr(s, "Center")) or isinstance(s, Part.Sphere):
            continue
        if type(s).__name__ not in ("Cylinder",):
            continue
        ax = V(s.Axis)
        ax.normalize()
        if abs(abs(ax.dot(d)) - 1) > 1e-3:
            continue
        w = V(s.Center) - pt
        off = (w - d * w.dot(d)).Length
        if off > (tol_off if tol_off is not None else max(0.5, 0.15 * s.Radius)):
            continue
        u0, u1, v0, v1 = f.ParameterRange
        p = f.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        q = p - V(s.Center)
        radial = q - ax * q.dot(ax)
        convex = n.dot(radial) > 0
        span = [(v.Point - pt).dot(d) for v in f.Vertexes] or [0.0]
        out.append((f, float(s.Radius), convex, [min(span), max(span)], off))
    return out


def fit_of(code):
    hole, _, shaft = str(code).partition("/")
    if not hole or not shaft:
        raise bad("fit: hole/shaft, e.g. \"H7/g6\", \"H7/p6\", \"H8/f7\".")
    return hole.strip(), shaft.strip()


def _view_provider(CV, cls, o):
    """o's view provider from CommandCreateView, where o has a ViewObject
    (the window); nothing headless."""
    vo = getattr(o, "ViewObject", None)
    if vo is None:
        return False
    vp = getattr(CV, cls, None)
    if vp is None:
        raise RuntimeError(f"{cls} is not in this FreeCAD's Assembly")
    vp(vo)
    return True


def _exploded_view(asm, which, moves):
    """FreeCAD's own Exploded View of the assembly (CommandCreateView's
    ExplodedView with a Normal move step a part), its moves applied:
    (the view object, None), or (None, why) where it cannot be made here —
    nothing it made is left behind then."""
    try:
        import CommandCreateView as CV
        import UtilsAssembly as UA
    except Exception as e:  # noqa: BLE001 - an older FreeCAD, or no pivy headless
        return None, f"Assembly's exploded views are not here ({type(e).__name__}: {e})"
    made = []
    before = {o.Name: FreeCAD.Vector(o.Placement.Base) for o in which}
    try:
        view = UA.getViewGroup(asm).newObject("App::FeaturePython", "Exploded View")
        made.append(view)
        CV.ExplodedView(view)
        # In the window each object gets its view provider before anything
        # is set on it, as Create Exploded View's task does: applying a step
        # draws its lines through it (headless there is no ViewObject).
        _view_provider(CV, "ViewProviderExplodedView", view)
        steps = []
        for o in which:
            st = asm.newObject("App::FeaturePython", "Move")
            made.append(st)
            CV.ExplodedViewStep(st, 0)
            _view_provider(CV, "ViewProviderExplodedViewStep", st)
            st.References = [asm, [o.Name + "."]]
            st.MovementTransform = FreeCAD.Placement(moves[o.Name], FreeCAD.Rotation())
            steps.append(st)
        view.Group = steps
        view.Proxy.saveAssemblyAndExplode(view)
        off = [o.Label for o in which if (o.Placement.Base - (before[o.Name] + moves[o.Name])).Length > 1e-6]
        if off:
            raise RuntimeError(f"its steps did not move {', '.join(off[:3])}")
        return view, None
    except Exception as e:  # noqa: BLE001 - put back as it was
        for o in which:
            o.Placement = FreeCAD.Placement(before[o.Name], o.Placement.Rotation)
        for x in reversed(made):
            try:
                x.Document.removeObject(x.Name)
            except Exception:
                pass
        return None, f"FreeCAD's Exploded View could not be made here: {e}"


def joint_of(asm, name):
    """The assembly's joint of that label or object name; a grounding is
    not one. Refused in its own words where there is none (five tools
    share it)."""
    j = next((x for x in A._joints(asm).Group if name in (x.Label, x.Name)), None)
    if j is None or getattr(j, "ObjectToGround", None) is not None:
        raise ToolError("not_found", f"joint {name!r} is not a joint of {asm.Label} — asm_list names its joints (label or object name).")
    return j


def pair_fit(pa, ea, pb, eb, fit, size):
    """How two parts' elements go together, one algorithm: with a round
    element, the hole and the shaft of about one size (within 20%) on its
    axis — the pair nearest in diameter, then the longest engaged — as
    { kind: round, hole, shaft, clearance, as, engagement, axisOffset }, and
    with fit ("H7/g6"; size the nominal, else the larger diameter to the
    nearest 0.05 mm) each held to ISO 286 (fit, verdict, fix). Two flat
    faces: their gap and angle. Refuses in its own words where neither is
    so, where no hole and shaft are found, or the fit is not one."""
    def round_axis(el):
        g = getattr(el, "Surface", None) if isinstance(el, Part.Face) else getattr(el, "Curve", None)
        return axis_of(el) if el is not None and hasattr(g, "Radius") else None

    ax = round_axis(ea) or round_axis(eb)
    if ax is None:
        # two flat faces: how they sit on one another
        if isinstance(ea, Part.Face) and isinstance(eb, Part.Face):
            d, pts, _ = ea.distToShape(eb)
            na, nb = axis_of(ea)[1], axis_of(eb)[1]
            ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(na.dot(nb)) / (na.Length * nb.Length or 1)))))
            return {"kind": "faces", "parts": [pa.Label, pb.Label], "gap": r4(d), "angle": r4(ang), "contact": d < 1e-4 and ang < 0.01,
                    "note": "Flat faces: the gap between them and how far from parallel." if d > 1e-4 else "Flat faces in contact."}
        raise ToolError("invalid_input", f"{pa.Label} and {pb.Label}: neither element is round (a hole's face or rim, a pin's face), and they are not two flat faces — name the round ones with pairs: [{{ a: {{ part, element: {{ kind: \"face\", type: \"cylinder\" }} }}, b }}].")
    pt, d = ax
    ca, cb = cylinders(pa, pt, d), cylinders(pb, pt, d)
    best = None
    for fa in ca:
        for fb in cb:
            if fa[2] == fb[2]:
                continue  # both holes, or both shafts
            hole, shaft = (fa, fb) if not fa[2] else (fb, fa)
            D, dd = 2 * hole[1], 2 * shaft[1]
            if abs(D - dd) > max(0.5, 0.2 * D):
                continue
            lo, hi = max(fa[3][0], fb[3][0]), min(fa[3][1], fb[3][1])
            eng = max(0.0, hi - lo)
            key = (abs(D - dd), -eng)
            if best is None or key < best[0]:
                best = (key, hole, shaft, eng, (pa if hole is fa else pb), (pb if hole is fa else pa))
    if best is None:
        raise ToolError("not_found", f"No hole and shaft of about one size (within 20%) on the axis through {vec(pt)} between {pa.Label} and {pb.Label}: one part needs a cylindrical hole there and the other a pin — shape_query {{ body, kind: \"face\", type: \"cylinder\" }} lists each part's round faces with their radii.")
    _, hole, shaft, eng, ph, ps = best
    D, dd = 2 * hole[1], 2 * shaft[1]
    c = D - dd
    out = {"kind": "round", "hole": {"part": ph.Label, "diameter": r4(D)}, "shaft": {"part": ps.Label, "diameter": r4(dd)},
           "clearance": r4(c), "as": "clearance" if c > 1e-6 else "interference" if c < -1e-6 else "line to line",
           "engagement": r4(eng), "axisOffset": r4(abs(hole[4] - shaft[4]))}
    if fit:
        hc, sc = fit_of(fit)
        # the size both are made to: the larger, to the nearest 0.05 mm
        # (10 for a 10.000 hole on a 9.98 pin; 6.35 for a quarter inch)
        N = float(size) if size else round(round(max(D, dd) / 0.05) * 0.05, 3)
        try:
            hes, hei = iso286.limits(N, hc)
            ses, sei = iso286.limits(N, sc)
        except ValueError as e:
            raise bad(f"fit: {e}")
        lo_c, hi_c = (N + hei) - (N + ses), (N + hes) - (N + sei)
        kind = "clearance" if lo_c >= 0 else "interference" if hi_c <= 0 else "transition"
        hole_ok = N + hei - 1e-9 <= D <= N + hes + 1e-9
        shaft_ok = N + sei - 1e-9 <= dd <= N + ses + 1e-9
        out["fit"] = {"code": f"{hc}/{sc}", "nominal": r4(N), "type": kind, "clearanceRange": [r4(lo_c), r4(hi_c)],
                      "hole": {"limits": [r4(N + hei), r4(N + hes)], "ok": hole_ok},
                      "shaft": {"limits": [r4(N + sei), r4(N + ses)], "ok": shaft_ok}}
        out["verdict"] = "pass" if hole_ok and shaft_ok else "fix"
        if not (hole_ok and shaft_ok):
            tips = []
            if not hole_ok:
                tips.append(f"the hole is ⌀{D:g}, {hc} wants {N + hei:g} … {N + hes:g}")
            if not shaft_ok:
                tips.append(f"the shaft is ⌀{dd:g}, {sc} wants {N + sei:g} … {N + ses:g}")
            out["fix"] = "; ".join(tips) + " — modelled at nominal sizes is usual: size them into the band, or say the fit is for the drawing only."
    return out


def limits_of(j):
    """A joint's kind and the limits FreeCAD keeps on it that are on:
    { angleMin, angleMax, lengthMin, lengthMax }."""
    kind = str(getattr(j, "JointType", "")).lower()
    out = {}
    if getattr(j, "EnableAngleMin", False):
        out["angleMin"] = r4(j.AngleMin)
    if getattr(j, "EnableAngleMax", False):
        out["angleMax"] = r4(j.AngleMax)
    if getattr(j, "EnableLengthMin", False):
        out["lengthMin"] = r4(j.LengthMin)
    if getattr(j, "EnableLengthMax", False):
        out["lengthMax"] = r4(j.LengthMax)
    return kind, out


def moving_group(doc, asm, j):
    """What asm_pose moves on a joint: the part that is not grounded (the
    second unless it is) with the parts joined beyond it, short of grounded
    parts and the part it moves on, and the axis read off its element (the
    other's where it has none). ({ name: part }, (point, direction));
    (None, None) where no axis or no moving part can be read."""
    p1, e1, _ = A.ref_element(doc, j.Reference1)
    p2, e2, _ = A.ref_element(doc, j.Reference2)
    grounded = A._grounded(asm)
    fixed_side, moving, el = (p1, p2, e2) if p2 not in grounded else (p2, p1, e1)
    ax = axis_of(el) if el is not None else None
    if ax is None:
        ax = axis_of(e1 if el is e2 else e2)
    if ax is None or moving is None:
        return None, None
    group, todo = {moving.Name: moving}, [moving]
    others = [x for x in A._joints(asm).Group if x is not j and getattr(x, "ObjectToGround", None) is None]
    while todo:
        cur = todo.pop()
        for x in others:
            q1, _, _ = A.ref_element(doc, getattr(x, "Reference1", None))
            q2, _, _ = A.ref_element(doc, getattr(x, "Reference2", None))
            for here, there in ((q1, q2), (q2, q1)):
                if here is not None and there is not None and here.Name == cur.Name and there.Name not in group and there not in grounded and there is not fixed_side:
                    group[there.Name] = there
                    todo.append(there)
    return group, ax


def pose_move(doc, j, group, centre, axis, turning, by):
    """The move that takes a joint by degrees or mm: about (or along) the
    axis through centre — JCS1's z where the joint's frames can be read,
    the axis the value is read on; a part on the first reference's side
    moves the other way. (the placement to multiply each part's by, the
    axis one long)."""
    fr = joint_frames(j)
    sign = 1.0
    if fr is not None:
        centre, axis = fr[0].Base, fr[0].Rotation.multVec(V(0, 0, 1))
        p1, _, _ = A.ref_element(doc, j.Reference1)
        if p1 is not None and p1.Name in group:
            sign = -1.0
    axis = V(axis)
    axis.normalize()
    if turning:
        rot = FreeCAD.Rotation(axis, sign * by)
        return FreeCAD.Placement(centre - rot.multVec(centre), rot), axis
    return FreeCAD.Placement(axis * (sign * by), FreeCAD.Rotation()), axis


def standing(j):
    """Where a joint stands before a motion is played, to put it back to:
    read off its frames (a revolute's angle, else its slide), else what
    asm_pose has counted on it, else 0."""
    kind = str(getattr(j, "JointType", "")).lower()
    v = joint_value(j, kind == "revolute")
    return v if v is not None else (float(getattr(j, POSE, 0.0)) if POSE in j.PropertiesList else 0.0)


def key_frames(keys, between):
    """The frames of a saved motion: between steps from each key pose to
    the next, straight-line, the last key itself closing the last run; a
    joint a key leaves out holds what the other key says."""
    frames = []
    for i in range(len(keys) - 1):
        k0, k1 = keys[i]["poses"], keys[i + 1]["poses"]
        for st in range(between if i < len(keys) - 2 else between + 1):
            f = st / between
            frames.append({j: k0.get(j, k1.get(j, 0.0)) + (k1.get(j, k0.get(j, 0.0)) - k0.get(j, k1.get(j, 0.0))) * f for j in set(k0) | set(k1)})
    return frames


def play(pose, asm, frames, start, clearance, placements, keep):
    """A motion played: each frame's joints posed in turn (pose: asm_pose
    itself, overlaps allowed), the overlaps of each frame read, and — unless
    keep — every joint put back to where it stood whatever happened (which
    is why this is code: the steps have no "finally").
    (a row a frame, the frames that clash)."""
    rows, clash_at = [], []
    try:
        for n, fr in enumerate(frames):
            for jn, v in sorted(fr.items()):
                pose({"assembly": asm.Label, "joint": jn, "to": v, "allowOverlap": True})
            hits, _ = A._overlaps(A._parts(asm), float(clearance))
            row = {"frame": n, "poses": {k: r4(v) for k, v in fr.items()}}
            if hits:
                row["overlaps"] = ["/".join(h["parts"]) for h in hits]
                clash_at.append(n)
            if placements:
                row["parts"] = {o.Label: A._placement(o) for o in A._parts(asm)}
            rows.append(row)
    finally:
        if not keep:
            for jn, v in start.items():
                try:
                    pose({"assembly": asm.Label, "joint": jn, "to": v, "allowOverlap": True})
                except ToolError:
                    pass
    return rows, clash_at


def write_json(p, value):
    """value written to the file p as JSON."""
    with open(p, "w") as f:
        json.dump(value, f, indent=1)


def collapse(doc, asm, parts):
    """An exploded assembly put back: each part where asm_explode found it,
    the joints it turned off back on, and the record emptied."""
    kept = json.loads(asm.getPropertyByName(EXPLODED))
    for o in parts:
        if o.Name in kept:
            m = kept[o.Name]
            o.Placement = FreeCAD.Placement(V(*m["base"]), FreeCAD.Rotation(*m["q"]))
    for jn in kept.get("__joints_off__", []):
        jo = doc.getObject(jn)
        if jo is not None:
            _suppress(jo, False)
    setattr(asm, EXPLODED, "")


def bounds(parts):
    """The box round every part where it stands."""
    bb = FreeCAD.BoundBox()
    for o in parts:
        bb.add(A._shape(o).BoundBox)
    return bb


def where_parts_sit(parts):
    """Each part's placement as asm_explode keeps it to collapse to:
    { name: { base [x, y, z], q (the rotation's quaternion) } }."""
    return {o.Name: {"base": [o.Placement.Base.x, o.Placement.Base.y, o.Placement.Base.z], "q": list(o.Placement.Rotation.Q)} for o in parts}


def axis_dir(ax):
    """An axis given as "x" | "y" | "z" or [x, y, z], as a vector (not yet
    one long: the entry refuses a null one)."""
    return V(*{"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[ax]) if isinstance(ax, str) and ax in "xyz" and len(ax) == 1 else V(*ax)


def stacked(parts, which, grounded, C, d, gap, factor):
    """The moves of an explosion along an axis d (one long): the parts
    stacked in the order they sit, each a gap past the last — gap mm, else
    the largest part's size along d times (factor - 1). With a grounded
    part the others go out from its side; with none, both ways from the
    middle. { name: vector }."""
    order = sorted(which, key=lambda o: (A._shape(o).BoundBox.Center - C).dot(d))
    size = max((max(abs(A._shape(o).BoundBox.XLength * d.x), abs(A._shape(o).BoundBox.YLength * d.y), abs(A._shape(o).BoundBox.ZLength * d.z)) for o in parts), default=10.0)
    gap = float(gap or size * (factor - 1))
    mid = (len(order) - 1) / 2.0
    ref_ground = [(A._shape(o).BoundBox.Center - C).dot(d) for o in grounded] or [0.0]
    g0 = sum(ref_ground) / len(ref_ground)
    moves = {}
    for i, o in enumerate(order):
        side = (A._shape(o).BoundBox.Center - C).dot(d) - g0
        k = (i - mid) if not grounded else (i + 1 if side >= 0 else -(len(order) - i))
        moves[o.Name] = d * (k * gap)
    return moves


def spread(which, bb, factor):
    """The moves of an explosion from the middle: each part (factor - 1)
    times further out from the box's centre; one that sits on the centre
    goes up. { name: vector }."""
    moves = {}
    for o in which:
        v = A._shape(o).BoundBox.Center - bb.Center
        if v.Length < 1e-6:
            v = V(0, 0, 1) * (bb.ZLength * 0.5 + 1)
        moves[o.Name] = v * (factor - 1)
    return moves


def joints_off(asm):
    """Every joint of the assembly still in the solve left out of it (and
    put back on collapse): otherwise the next solve, from any assembly
    tool, pulls an exploded assembly back together. Their names."""
    off = []
    for jo in (A._joints(asm).Group if A._joints(asm) is not None else []):
        if getattr(jo, "ObjectToGround", None) is None and hasattr(jo, "JointType") and not _is_suppressed(jo):
            _suppress(jo, True)
            off.append(jo.Name)
    return off


def keep_exploded(asm, kept):
    """Where the parts sat, kept on the assembly (in the file) as JSON, so
    it collapses after reopening too."""
    if EXPLODED not in asm.PropertiesList:
        asm.addProperty("App::PropertyString", EXPLODED, "AgentLink", "Where the parts sat before asm_explode, to collapse to (JSON)")
    setattr(asm, EXPLODED, json.dumps(kept))


def bom_object(asm):
    """FreeCAD's own bill of materials (an Assembly::BomObject in the
    assembly's BomGroup, made where there is none): (it, True), or
    (None, False) on a FreeCAD without one."""
    bom = None
    try:
        grp = next((o for o in asm.Group if o.TypeId == "Assembly::BomGroup"), None) or asm.newObject("Assembly::BomGroup", "Bills of Materials")
        bom = grp.newObject("Assembly::BomObject", "Bill of Materials")
        return bom, True
    except Exception:
        return bom, False


def density_of(doc, m):
    """g/cm³ of a recorded material: a filament key's, else the card's
    (a FreeCAD library card, a stock key, a custom material); None."""
    if not m:
        return None
    if m in DENSITY:
        return DENSITY[m]
    try:
        from . import material as _material

        c = _material.card(doc, m)
        return float(c["density"]) if c and c.get("density") else None
    except Exception:  # noqa: BLE001
        return None


SOLID_NOT_PRINTED = ("solid, not as printed: the part is in a print setup. An installed add-on that owns mass gives the printed estimate "
                     "(walls and infill); slice gives the slicer's own figure.")


def bom_row(o, mats, session=None):
    """A part's row of the bill: its material as recorded (material_set),
    mass in g from its volume where the material's density is known, and
    volume in cm³. Test drive of 20 Nov, finding 11: a part in a print setup was
    given its solid mass (228 g where the slice said 89 g): there the mass
    is the printed estimate of the add-on that owns mass (massAs says how,
    solidMass keeps the solid one), else the solid mass marked as such."""
    m = mats.get(o.Label)
    vol = o.Shape.Volume / 1000.0
    doc = getattr(session, "doc", None) if session is not None else None
    rho = DENSITY[m] if m in DENSITY else density_of(doc, m)
    row = {"name": o.Label, "material": m or "", "mass": (round(vol * rho, 2) if rho else ""), "volume": round(vol, 3)}
    if session is not None and doc is not None and store.setup_of(doc, o.Label, "print"):
        from .measure import printed_mass

        got = printed_mass(session, o.Label)
        if got is not None:
            row["solidMass"], row["mass"], row["massAs"] = row["mass"], got["mass"], got["as"]
        elif row["mass"] != "":
            row["massAs"] = SOLID_NOT_PRINTED
    return row


def fill_native(doc, bom, rows, mats, session=None):
    """Material, Mass (g) and Volume (cm3) filled into FreeCAD's BOM by
    name, row by row as it generated them (custom columns are kept by
    FreeCAD across regenerations); a part inside a sub-assembly is found in
    the document by its label."""
    from .. import cells as Cc

    def nested(label):
        o = next((x for x in doc.Objects if x.Label == label and hasattr(x, "Shape") and not x.Shape.isNull() and x.Shape.Solids
                  and x.TypeId not in ("Assembly::AssemblyObject", "Assembly::AssemblyLink")), None)
        return None if o is None else bom_row(o, mats, session)

    hdr = [bom.getContents(Cc.name(1, c)).lstrip("'") for c in range(1, len(bom.columnsNames) + 1)]
    name_col = hdr.index("Name") + 1 if "Name" in hdr else 2
    r = 2
    while bom.getContents(Cc.name(r, name_col)):
        nm = bom.getContents(Cc.name(r, name_col)).lstrip("'")
        row = next((x for x in rows if x["name"] == nm), None) or nested(nm)
        if row:
            for colname, key in (("Material", "material"), ("Mass (g)", "mass"), ("Volume (cm3)", "volume")):
                if colname in hdr and row[key] != "":
                    bom.set(Cc.name(r, hdr.index(colname) + 1), str(row[key]) if key != "material" else "'" + row[key])
        r += 1


def fill_sheet(bom, rows):
    """A plain spreadsheet filled as the bill, where FreeCAD has no BOM
    object: the header, then a row a part."""
    from .. import cells as Cc

    hdr = ["Index", "Name", "Quantity", "Material", "Mass (g)", "Volume (cm3)"]
    for c, h in enumerate(hdr, 1):
        bom.set(Cc.name(1, c), "'" + h)
    for i, row in enumerate(rows, 2):
        vals = [str(i - 1), row["name"], "1", row["material"], row["mass"], row["volume"]]
        for c, v in enumerate(vals, 1):
            if v != "":
                bom.set(Cc.name(i, c), ("'" + v) if c in (2, 4) else str(v))


def tools(session):
    s = session

    def doc():
        """The session's document."""
        return s.doc

    made = []

    def pose(args):
        """asm_pose itself, as asm_motion's play calls it."""
        return next(t for t in made if t.name == "asm_pose").fn(args)

    # What the tools' entries (agentlink/data/tools.json, "family": "assembly_more") call by name.
    # FreeCAD's own are reached when called, not here.
    helpers = {"doc": doc, "unique": lambda label: s.unique(label), "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps),
               "settled": lambda tool, read: picks.finish(s, tool, read, recompute=False), "r4": r4, "vec": vec, "prop": lambda o, name: getattr(o, name),
               "in_session": lambda p: p if os.path.isabs(os.path.expanduser(p)) else os.path.join(s.out_dir, p), "noted": lambda p: paths.made(s, p),
               "expanduser": lambda p: os.path.expanduser(p), "isfile": lambda p: os.path.isfile(p), "filesize": lambda p: os.path.getsize(p), "write_json": write_json,
               "motions": lambda: store.read(doc(), "motions", {}) or {}, "keep_motions": lambda allm: store.write(doc(), "motions", allm),
               "materials": lambda: store.materials(doc()),
               # FreeCAD's own
               "placement": lambda *x: FreeCAD.Placement(*x),
               # assembly.py's
               "assembly": lambda ref: A._assembly(doc(), ref), "part_of": A._part, "element": lambda part, q, what: A._element(s, part, q, what), "joints": A._joints,
               "parts": A._parts, "grounded": A._grounded, "status": A._status, "overlaps": A._overlaps, "placement_of": A._placement,
               "ref_pair": lambda r: A.ref_element(doc(), r)[:2],
               # the family's
               "joint_of": joint_of, "pair_fit": pair_fit, "limits_of": limits_of, "joint_value": joint_value, "wrap180": wrap180, "is_exploded": is_exploded,
               "moving_group": lambda asm, j: moving_group(doc(), asm, j), "pose_move": lambda j, *rest: pose_move(doc(), j, *rest), "standing": standing,
               "key_frames": key_frames, "play": lambda *x: play(pose, *x), "collapse": lambda asm, parts: collapse(doc(), asm, parts), "bounds": bounds,
               "where_parts_sit": where_parts_sit, "axis_dir": axis_dir, "unit": A.unit, "stacked": stacked, "spread": spread, "exploded_view": _exploded_view,
               "joints_off": joints_off, "keep_exploded": keep_exploded, "bom_object": bom_object, "bom_row": lambda o, mats: bom_row(o, mats, s),
               "fill_native": lambda bom, rows, mats: fill_native(doc(), bom, rows, mats, s), "fill_sheet": fill_sheet,
               # tables
               "POSE": POSE}
    made.extend(runners.tools(GROUP, s, helpers, family="assembly_more"))
    return made
