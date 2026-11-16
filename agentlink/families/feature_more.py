# SPDX-License-Identifier: LGPL-2.1-or-later
# More PartDesign, beside feature.py: additive and subtractive primitives,
# helices (springs, coils, a thread cut as a helix), MultiTransform (patterns
# and mirrors chained, with Scaled), datum lines, points and coordinate
# systems, shape binders (another body's faces brought in to sketch on), and
# body booleans. Each one feature, refused with FreeCAD's error and nothing
# kept when it fails.

import FreeCAD

from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import pd_common as pc
from . import picks

GROUP = "feature"
INFO = ("PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, primitives, helix, "
        "MultiTransform, datum planes, lines, points and coordinate systems, binders, booleans) and the body's feature history.")

V = FreeCAD.Vector
PRIMS = {
    # kind: (FreeCAD name, {argument: (property, default)})
    "box": ("Box", {"length": ("Length", 10), "width": ("Width", 10), "height": ("Height", 10)}),
    "cylinder": ("Cylinder", {"radius": ("Radius", 5), "height": ("Height", 10), "angle": ("Angle", 360)}),
    "sphere": ("Sphere", {"radius": ("Radius", 5)}),
    "cone": ("Cone", {"radius1": ("Radius1", 5), "radius2": ("Radius2", 0), "height": ("Height", 10)}),
    "ellipsoid": ("Ellipsoid", {"radius1": ("Radius1", 6), "radius2": ("Radius2", 4), "radius3": ("Radius3", 0)}),
    "torus": ("Torus", {"radius1": ("Radius1", 10), "radius2": ("Radius2", 2)}),
    "prism": ("Prism", {"sides": ("Polygon", 6), "circumradius": ("Circumradius", 5), "height": ("Height", 10)}),
    "wedge": ("Wedge", {"xmin": ("Xmin", 0), "xmax": ("Xmax", 10), "ymin": ("Ymin", 0), "ymax": ("Ymax", 10), "zmin": ("Zmin", 0), "zmax": ("Zmax", 10),
                        "x2min": ("X2min", 2), "x2max": ("X2max", 8), "z2min": ("Z2min", 2), "z2max": ("Z2max", 8)}),
}


def placement(a):
    at = pc.vec3(a.get("at", [0, 0, 0]), "at")
    rot = FreeCAD.Rotation()
    r = a.get("rotate")
    if r:
        rot = FreeCAD.Rotation(pc.vec3(r.get("axis", [0, 0, 1]), "rotate.axis"), float(r.get("angle", 0)))
    return FreeCAD.Placement(at, rot)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def new(b, kind, label):
        label = s.unique(label)  # before the object exists, or it clashes with itself
        f = b.newObject(kind, kind.split("::")[-1])
        f.Label = label
        return f

    def attach_origin(b, f, pl, mode="FlatFace"):
        """On the body's XY plane, offset to pl: parametric (it moves with
        the body) and the same in every release. mode: the attacher's map
        mode — FlatFace for what has a plane (sketches, primitives, datum
        planes, coordinate systems); a datum line takes ObjectZ (along the
        plane's z, from its origin) and a datum point ObjectOrigin: their
        attachers refuse FlatFace as a wrong mode (Part/App/Attacher.cpp,
        AttachEngineLine / AttachEnginePoint)."""
        xy = pc.origin_feature(b, "XY_Plane")
        setattr(f, pc.support_prop(f), [(xy, "")])
        f.MapMode = mode
        f.AttachmentOffset = pl

    # ---- primitives ----

    def pd_primitive(a):
        b = pc.pd_body(doc(), a.get("body"))
        kind = picks.choice(a, "kind", PRIMS, f"kind: one of {', '.join(PRIMS)}.")
        sub = bool(a.get("subtractive"))
        before = pc.volume(b)
        if sub and before <= 0:
            raise ToolError("invalid_state", f"{b.Label} has no solid to cut: an additive pd_primitive or a pd_pad first.")
        if a.get("size") is not None and not isinstance(a["size"], dict):
            raise bad(f"size: {{ … }} — {kind} takes {', '.join(PRIMS[kind][1])}.")
        name, props = PRIMS[kind]
        f = new(b, f"PartDesign::{'Subtractive' if sub else 'Additive'}{name}", a.get("name") or f"{'Sub' if sub else ''}{name}")
        unknown = [k for k in (a.get("size") or {}) if k not in props]
        if unknown:
            raise bad(f"size.{unknown[0]}: {kind} takes {', '.join(props)} (mm; degrees for angle; a count for sides).")
        for k, (prop, default) in props.items():
            v = (a.get("size") or {}).get(k, default)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise bad(f"size.{k}: a number (mm; degrees for angle; a count for sides).")
            setattr(f, prop, int(v) if prop == "Polygon" else float(v))
        attach_origin(b, f, placement(a))
        if b.Tip != f:
            b.Tip = f
        return pc.settle(s, b, f, "pd_primitive", before, "cut" if sub else "add",
                         hint="at and rotate place it from the body's origin; a subtractive one must overlap the body.")

    # ---- gears and sprockets ----

    def pd_gear(a):
        """An involute gear or a chain sprocket: PartDesign's own profile
        (parametric: edit its teeth later), padded to a thickness."""
        b = pc.pd_body(doc(), a.get("body"))
        kind = a.get("kind", "gear")
        if kind not in ("gear", "sprocket"):
            raise bad("kind: gear (involute) | sprocket (roller chain).")
        teeth = int(a.get("teeth", 20))
        if teeth < 3:
            raise bad("teeth: 3 or more.")
        thick = float(a.get("thickness", 5))
        if thick <= 0:
            raise bad("thickness: above 0 mm.")
        m = float(a.get("module", 1))
        if kind == "gear" and m <= 0:
            raise bad("module: above 0 mm (pitch diameter = module × teeth).")
        if a.get("internal") and kind != "gear":
            raise bad("internal: a ring gear is kind gear; a sprocket has outside teeth only.")
        if a.get("bore") and (float(a["bore"]) < 0 or a.get("internal")):
            raise bad("bore: mm across, over 0, for an outside gear or sprocket (a ring gear is open already; rim sets its wall).")
        before = pc.volume(b)
        up = FreeCAD.GuiUp
        FreeCAD.GuiUp = False  # their makers reach for the active view otherwise
        try:
            if kind == "gear":
                import InvoluteGearFeature as G

                # As makeInvoluteGear does, but in this document: it makes
                # its object in FreeCAD.ActiveDocument, which need not be
                # the session's.
                prof = doc().addObject("Part::Part2DObjectPython", "InvoluteGear")
                G._InvoluteGear(prof)
                prof.NumberOfTeeth, prof.Modules = teeth, f"{m} mm"
                prof.PressureAngle = f"{float(a.get('pressureAngle', 20))} deg"
                prof.ExternalGear = not a.get("internal", False)
                prof.HighPrecision = bool(a.get("highPrecision", True))
                shift = 0.0
                if a.get("shift") is not None and hasattr(prof, "ProfileShiftCoefficient"):
                    shift = prof.ProfileShiftCoefficient = float(a["shift"])
                # tip circle: module × (teeth + 2 × (addendum + shift)); addendum 1 by default
                add = float(getattr(prof, "AddendumCoefficient", 1.0))
                info = {"pitchDiameter": round(m * teeth, 3), "outsideDiameter": round(m * (teeth + 2 * (add + shift)), 3) if not a.get("internal") else None}
            elif kind == "sprocket":
                # The sprocket's own object asks its dialog for the chain table;
                # its outline is drawn with the same builder.
                from fcsprocket import fcsprocket
                from fcsprocket import sprocket as S

                pitch = float(a.get("pitch", 9.525))
                roller = float(a.get("roller", 0.53 * pitch))
                w = fcsprocket.FCWireBuilder()
                S.CreateSprocket(w, pitch, teeth, roller)
                # A Part::Feature may not sit in a body: the outline goes in as a sketch.
                prof = b.newObject("Sketcher::SketchObject", "Sprocket")
                for g in w.wire:
                    prof.addGeometry(g, False)
                import math

                info = {"pitchDiameter": round(pitch / math.sin(math.pi / teeth), 3), "chainPitch": pitch, "roller": roller}
        finally:
            FreeCAD.GuiUp = up
        if prof not in b.Group:
            b.addObject(prof)
        prof.Label = s.unique(a.get("name") and a["name"] + " profile" or f"{kind.capitalize()} {teeth}T", prof)
        attach_origin(b, prof, placement(a))
        doc().recompute()
        if kind == "gear" and a.get("internal"):
            # an internal gear: a ring round the teeth, the teeth cut from it
            rim = float(a.get("rim", 3 * m))
            if rim <= 0:
                raise bad("rim: mm of wall outside the teeth, above 0.")
            ring = new(b, "PartDesign::AdditiveCylinder", a.get("name") or f"Ring gear {teeth}T")
            ring.Radius, ring.Height = m * teeth / 2 + 1.25 * m + rim, thick
            attach_origin(b, ring, placement(a))
            pc.settle(s, b, ring, "pd_gear", before, "add")
            pad = new(b, "PartDesign::Pocket", f"{teeth}T teeth")
            pad.Profile = prof
            pad.Type = "ThroughAll"
            pad.Reversed = True
            info["outsideDiameter"] = round(2 * float(ring.Radius), 3)
            before = pc.volume(b)
            must = "cut"
        else:
            pad = new(b, "PartDesign::Pad", a.get("name") or f"{kind.capitalize()} {teeth}T pad")
            pad.Profile = prof
            pad.Length = thick
            must = "add"
        if a.get("bore"):
            info["bore"] = float(a["bore"])
        out = pc.settle(s, b, pad, "pd_gear", before, must, hint="the gear lies on the body's XY plane at at; a body with a solid already needs the gear beside it, not inside.")
        if a.get("bore"):
            hole = new(b, "PartDesign::SubtractiveCylinder", f"{pad.Label} bore")
            hole.Radius, hole.Height = float(a["bore"]) / 2, thick + 2
            pl = placement(a)
            attach_origin(b, hole, FreeCAD.Placement(pl.Base + V(0, 0, -1), pl.Rotation))
            out = pc.settle(s, b, hole, "pd_gear", None)
        return {**out, "teeth": teeth, "kind": kind, "profile": prof.Label, **{k: v for k, v in info.items() if v is not None}}

    # ---- helix ----

    def pd_helix(a):
        b = pc.pd_body(doc(), a.get("body"))
        sk = pc.sketch_of(doc(), a.get("profile"), b)
        sub = bool(a.get("subtractive"))
        before = pc.volume(b)
        if sub and before <= 0:
            raise ToolError("invalid_state", f"{b.Label} has no solid to cut a helix into: pd_pad or pd_primitive first.")
        pitch, height, turns = a.get("pitch"), a.get("height"), a.get("turns")
        given = [k for k, v in (("pitch", pitch), ("height", height), ("turns", turns)) if v is not None]
        if len(given) != 2:
            raise bad("Two of pitch (mm per turn), height (mm) and turns — the third follows from them" + (f"; got {', '.join(given) or 'none'}." if len(given) != 3 else ": leave one out."))
        for k, v in (("pitch", pitch), ("height", height), ("turns", turns)):
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0) and not (k == "height" and v == 0 and a.get("growth")):
                raise bad(f"{k}: a number over 0" + (" (mm)." if k != "turns" else "."))
        f = new(b, f"PartDesign::{'Subtractive' if sub else 'Additive'}Helix", a.get("name") or "Helix")
        f.Profile = sk
        f.ReferenceAxis = pc.axis_ref(b, a.get("axis", "V_Axis"), sk, "axis")[0]
        modes = {("height", "pitch"): "pitch-height-angle", ("pitch", "turns"): "pitch-turns-angle", ("height", "turns"): "height-turns-angle"}
        mode = modes[tuple(sorted(given))]
        # growth (mm wider each turn, a conical spiral) is a mode of its
        # own, by height and turns; it was set and then ignored. In that
        # mode FreeCAD works the cone angle out itself: taper is not used.
        if a.get("growth"):
            if tuple(sorted(given)) != ("height", "turns"):
                raise bad("growth: with height and turns (FreeCAD's height-turns-growth), not pitch.")
            if a.get("taper"):
                raise bad("growth or taper, one of them: growth is mm wider per turn, taper the cone's angle in degrees.")
            mode = "height-turns-growth"
        try:
            f.Mode = mode
        except Exception:
            pass
        if pitch is not None:
            f.Pitch = float(pitch)
        if height is not None:
            f.Height = float(height)
        if turns is not None:
            f.Turns = float(turns)
        if a.get("taper"):
            f.Angle = float(a["taper"])
        if a.get("growth") and "Growth" in f.PropertiesList:
            f.Growth = float(a["growth"])
        if a.get("leftHanded"):
            f.LeftHanded = True
        if a.get("reversed"):
            f.Reversed = True
        if b.Tip != f:
            b.Tip = f
        out = pc.settle(s, b, f, "pd_helix", before, "cut" if sub else "add",
                        hint="The profile is swept around the axis: it must be closed, off the axis and not across it; a pitch smaller than the profile's height makes the turns run into one another."
                        + (" A cut must pass through the body." if sub else " An added helix must touch the body's solid, if it has one, or it is a second solid."))
        out["helix"] = {k: picks.num_json(getattr(f, p)) for k, p in (("pitch", "Pitch"), ("height", "Height"), ("turns", "Turns"))}
        return out

    # ---- MultiTransform ----

    def pd_multitransform(a):
        b = pc.pd_body(doc(), a.get("body"))
        pc.tip_shape(b)
        before = pc.volume(b)
        refs = a.get("features") or []
        if isinstance(refs, str):
            refs = [refs]
        if not refs:
            raise bad("features: [names] — the features to repeat (feature_list names them).")
        orig = [pc.in_body(b, r, ["PartDesign::"]) for r in refs]
        steps = a.get("steps") or []
        if not steps or not all(isinstance(st, dict) for st in steps):
            raise bad("steps: [{ kind: mirror | linear | polar | scale, … }] — applied in turn, each to what the steps before made.")
        mt = new(b, "PartDesign::MultiTransform", a.get("name") or "MultiTransform")
        mt.Originals = orig
        subs = []
        for i, st in enumerate(steps):
            k = st.get("kind")
            if k == "mirror":
                t = b.newObject("PartDesign::Mirrored", "Mirrored")
                t.MirrorPlane = pc.plane_ref(b, st.get("plane", "YZ"), f"steps[{i}].plane")[0]
            elif k in ("linear", "polar", "scale"):
                n = int(st.get("occurrences", 2))
                if n < 2:
                    raise bad(f"steps[{i}].occurrences: 2 or more, the original counted.")
                if k == "linear":
                    step = st.get("spacing", st.get("length"))
                    if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
                        raise bad(f"steps[{i}]: spacing (mm between copies) or length (mm, first to last), over 0.")
                    t = b.newObject("PartDesign::LinearPattern", "LinearPattern")
                    t.Direction = pc.axis_ref(b, st.get("direction", "x"), None, f"steps[{i}].direction")[0]
                    t.Length = float(step) * (n - 1) if "spacing" in st else float(step)
                elif k == "polar":
                    t = b.newObject("PartDesign::PolarPattern", "PolarPattern")
                    t.Axis = pc.axis_ref(b, st.get("axis", "z"), None, f"steps[{i}].axis")[0]
                    t.Angle = float(st.get("angle", 360))
                else:
                    t = b.newObject("PartDesign::Scaled", "Scaled")
                    t.Factor = float(st.get("factor", 2))
                t.Occurrences = n
                if st.get("reversed") and "Reversed" in t.PropertiesList:
                    t.Reversed = True
            else:
                raise bad(f"steps[{i}].kind: mirror, linear, polar or scale.")
            t.Label = s.unique(f"{mt.Label} {k} {i + 1}", t)
            # A step stays in the body, as FreeCAD's own task panel and
            # tests leave it (Body.newObject, then Transformations): the
            # body does not count a MultiTransform's steps as solid features
            # (Body::isSolidFeature), and outside the body their plane and
            # axis links would cross its boundary.
            subs.append(t)
        mt.Transformations = subs
        # each step was the tip while it was still a feature of its own
        if b.Tip != mt:
            b.Tip = mt
        out = pc.settle(s, b, mt, "pd_multitransform", before, None, hint="A copy of a pocket must land on material; a scale step grows the copies about the originals' centre and comes after a pattern step with the same occurrences.")
        out["steps"] = [t.Label for t in subs]
        return out

    # ---- datums ----

    def pd_datum(a):
        b = pc.pd_body(doc(), a.get("body"))
        kind = a.get("kind")
        types = {"line": "PartDesign::Line", "point": "PartDesign::Point", "lcs": "PartDesign::CoordinateSystem"}
        if kind not in types:
            raise bad("kind: line, point or lcs (a coordinate system); a plane is pd_datum_plane.")
        default = {"line": "DatumLine", "point": "DatumPoint", "lcs": "LCS"}[kind]
        label = s.unique(a.get("name") or default)
        f = b.newObject(types[kind], default)
        f.Label = label
        how = "placed"
        on = a.get("on")
        if on is not None:
            # attached to the model: a round edge's axis or centre
            tip, shape = pc.tip_shape(b)
            q = dict(on) if isinstance(on, dict) else None
            if q is None:
                raise bad("on: { near: [x, y, z] } a point on a round edge of the body — its axis (line) or centre (point); or leave on out and give at (and direction).")
            q.setdefault("kind", "circle")
            edge = pc.find_edges(pc.ref_shape(b, shape), [q], pc.ref_names(b, tip))[0]
            setattr(f, pc.support_prop(f), [(tip, edge)])
            f.MapMode = {"line": "AxisOfCurvature", "point": "CenterOfCurvature", "lcs": "ObjectXY"}[kind]
            how = f"attached to {tip.Label}.{edge}"
        else:
            pl = FreeCAD.Placement()
            at = pc.vec3(a.get("at", [0, 0, 0]), "at")
            if kind == "line":
                d = pc.vec3(a.get("direction", [0, 0, 1]), "direction")
                if d.Length < 1e-9:
                    raise bad("direction: not zero.")
                pl = FreeCAD.Placement(at, FreeCAD.Rotation(V(0, 0, 1), d))
            elif kind == "lcs":
                pl = placement(a)
            else:
                pl = FreeCAD.Placement(at, FreeCAD.Rotation())
            attach_origin(b, f, pl, {"line": "ObjectZ", "point": "ObjectOrigin", "lcs": "FlatFace"}[kind])
        doc().recompute()
        if not f.isValid():
            raise ToolError("failed", f"The datum {kind} would not attach: {f.getStatusString()} — nothing was kept." + (" on takes a point on a circle or arc edge of the body." if on is not None else ""))
        s.snapshot("pd_datum")
        pl = f.Placement
        out = {"datum": f.Label, "kind": kind, "how": how, "at": pc.geo.vec(pl.Base), "step": len(s.steps)}
        if kind == "line":
            out["direction"] = pc.geo.vec(pl.Rotation.multVec(V(0, 0, 1)))
            out["use"] = "pd_polar_pattern, pd_revolution and pd_helix take it by name as their axis."
        if kind == "lcs":
            out["axes"] = {k: pc.geo.vec(pl.Rotation.multVec(v)) for k, v in (("x", V(1, 0, 0)), ("y", V(0, 1, 0)), ("z", V(0, 0, 1)))}
        return out

    # ---- binders and booleans ----

    def pd_binder(a):
        b = pc.pd_body(doc(), a.get("body"))
        src = None
        ref = a.get("from")
        if not isinstance(ref, str) or not ref:
            raise bad("from: the name of another body (or a feature of one) to bind — session_state names the bodies.")
        for o in doc().Objects:
            if ref in (o.Label, o.Name) and hasattr(o, "Shape"):
                src = o
                break
        if src is None:
            raise ToolError("not_found", f"from {ref!r}: no object with a shape has that name — a body or feature to bind (session_state names the bodies).")
        if src is b or (pc.body_of(src) is b):
            raise bad("from: another body than this one — within a body, sketch on its faces directly.")
        subs = []
        if getattr(src, "Shape", None) is None or src.Shape.isNull():
            raise ToolError("invalid_state", f"{src.Label} has no shape yet to bind: give it a solid first.")
        for q in a.get("faces") or []:
            i, _ = pc.find_face(src.Shape, q)
            subs.append(f"Face{i + 1}")
        label = s.unique(a.get("name") or f"{src.Label} binder")
        f = b.newObject("PartDesign::SubShapeBinder", "Binder")
        f.Label = label
        f.Support = [(src, tuple(subs) if subs else ("",))]
        if "BindMode" in f.PropertiesList and a.get("frozen"):
            f.BindMode = "Frozen"
        doc().recompute()
        if not f.isValid():
            raise ToolError("failed", f"The binder did not take {src.Label}: {f.getStatusString()} — nothing was kept. faces are found on {src.Label} in the document's coordinates.")
        s.snapshot("pd_binder")
        sh = f.Shape
        return {"binder": f.Label, "from": src.Label, "faces": subs or "whole", "shape": {"faces": len(sh.Faces), "edges": len(sh.Edges)},
                "follows": "frozen" if a.get("frozen") else f"{src.Label} — it updates when that changes",
                "next": f"sketch_external {{ sketch, from: \"{f.Label}\" … }} or sketch_new on one of its faces.", "step": len(s.steps)}

    def pd_boolean(a):
        b = pc.pd_body(doc(), a.get("body"))
        pc.tip_shape(b)
        before = pc.volume(b)
        op = {"fuse": "Fuse", "cut": "Cut", "common": "Common"}.get(a.get("op", "fuse"))
        if op is None:
            raise bad("op: fuse, cut or common.")
        tools_ = []
        for r in picks.ref_list(a.get("with")) or []:
            o = pc.pd_body(doc(), r)
            if o is b:
                raise bad(f"with: other bodies than {b.Label} itself.")
            tools_.append(o)
        if not tools_:
            raise bad("with: [body names] — the other PartDesign bodies to fuse with, cut away or keep the common part of (a plain Part solid first becomes a body with pd_clone).")
        f = new(b, "PartDesign::Boolean", a.get("name") or op)
        f.Type = op
        f.addObjects(tools_)
        if b.Tip != f:
            b.Tip = f
        out = pc.settle(s, b, f, "pd_boolean", before, {"Fuse": "add", "Cut": "cut"}.get(op),
                        hint="The bodies must overlap this one as they stand in the document; they move inside the boolean and follow their own edits.")
        out["with"] = [o.Label for o in tools_]
        return out

    size_schema = {"type": "object", "description": "Sizes by kind: box length/width/height; cylinder radius/height/angle; sphere radius; cone radius1/radius2/height; ellipsoid radius1 (z)/radius2 (x)/radius3 (y; 0: as radius2); torus radius1/radius2; prism sides/circumradius/height; wedge xmin…zmax, x2min…z2max (its face at ymax)."}
    place = {"at": {"type": "array", "items": {}}, "rotate": {"type": "object"}}
    return [
        Tool("pd_primitive", "A PartDesign primitive: kind box | cylinder | sphere | cone | ellipsoid | torus | prism | wedge, size { … } (mm), at [x, y, z] (a box's corner, a round one's base centre) and rotate { axis, angle } from the body's origin; subtractive: true cuts it out (it must overlap the body). Parametric, attached to the body's XY plane. Reply as pd_pad's.",
             obj({"body": {"type": "string"}, "kind": {"type": "string", "enum": list(PRIMS)}, "size": size_schema, "subtractive": {"type": "boolean"}, "name": {"type": "string"}, **place}, ["kind"]), pd_primitive, changes=True),
        Tool("pd_gear", "An involute gear (kind gear: teeth, module, pressureAngle 20, shift, internal with rim mm of wall) or a roller-chain sprocket (kind sprocket: teeth, pitch 9.525 for #35 / 12.7 for #40, roller diameter) as a padded PartDesign feature on the body's XY plane: thickness, bore mm, at. Beside a solid already in the body it is a second solid. Answers the pitch and outside diameters.",
             obj({"body": {"type": "string"}, "kind": {"type": "string", "enum": ["gear", "sprocket"]}, "teeth": {"type": "integer"}, "module": {"type": "number"}, "pressureAngle": {"type": "number"},
                  "internal": {"type": "boolean"}, "rim": {"type": "number"}, "shift": {"type": "number"}, "highPrecision": {"type": "boolean"}, "pitch": {"type": "number"}, "roller": {"type": "number"},
                  "thickness": {"type": "number"}, "bore": {"type": "number"}, "at": {"type": "array", "items": {}}, "name": {"type": "string"}}), pd_gear, changes=True),
        Tool("pd_helix", "Sweep a closed sketch's profile in a helix about an axis (default the sketch's V_Axis; H_Axis, x | y | z, a datum line, a line's id): two of pitch (mm per turn), height (mm), turns; taper (degrees) or growth (mm per turn, with height and turns: a spiral), leftHanded, reversed; subtractive: true cuts it (a thread, a groove). Keep the profile off the axis and under the pitch; many turns are slow. Reply adds helix.",
             obj({"body": {"type": "string"}, "profile": {"type": "string"}, "axis": {"type": ["string", "integer"]}, "pitch": {"type": "number"}, "height": {"type": "number"}, "turns": {"type": "number"},
                  "taper": {"type": "number"}, "growth": {"type": "number"}, "leftHanded": {"type": "boolean"}, "reversed": {"type": "boolean"}, "subtractive": {"type": "boolean"}, "name": {"type": "string"}}, ["profile"]), pd_helix, changes=True),
        Tool("pd_multitransform", "Repeat features through a chain of steps, each on what the steps before made: steps [{ kind: mirror, plane } | { kind: linear, direction, occurrences, spacing } | { kind: polar, axis, angle, occurrences } | { kind: scale, factor, occurrences }] — a grid is two linear steps; a bolt circle mirrored is polar then mirror. The steps stay in the body (feature_list: stepOf) and go with it.",
             obj({"body": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}, "steps": {"type": "array", "items": {"type": "object"}}, "name": {"type": "string"}}, ["features", "steps"]), pd_multitransform, changes=True),
        Tool("pd_datum", "A datum: kind line (at, direction; along z by default), point (at) or lcs (a coordinate system: at, rotate { axis, angle }) placed from the body's origin; or on: { near: [x,y,z] } a round edge — its axis (line) or centre (point), attached so it follows the model. A line serves by name as an axis or direction. Reply: datum, at, direction.",
             obj({"body": {"type": "string"}, "kind": {"type": "string", "enum": ["line", "point", "lcs"]}, "direction": {"type": "array", "items": {}}, "on": {"type": "object"}, "name": {"type": "string"}, **place}, ["kind"]), pd_datum, changes=True),
        Tool("pd_binder", "Bring another body's faces (or all of it) into this body as a shape binder (a SubShapeBinder), to sketch on or project from: from (body or feature), faces [{ at, normal } …] on it (none: the whole shape), frozen: true keeps it as it is now. Reply: binder, faces, next.",
             obj({"body": {"type": "string"}, "from": {"type": "string"}, "faces": {"type": "array", "items": {"type": "object"}}, "frozen": {"type": "boolean"}, "name": {"type": "string"}}, ["from"]), pd_binder, changes=True),
        Tool("pd_boolean", "A boolean inside a body with other PartDesign bodies: op fuse (default) | cut | common, with [body names]. The tool bodies move inside the boolean, stay editable and are followed; a fuse or cut that changes nothing is refused.",
             obj({"body": {"type": "string"}, "op": {"type": "string", "enum": ["fuse", "cut", "common"]}, "with": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}}, ["with"]), pd_boolean, changes=True),
    ]
