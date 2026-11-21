# SPDX-License-Identifier: LGPL-2.1-or-later
# More PartDesign, beside feature.py: additive and subtractive primitives,
# helices (springs, coils, a thread cut as a helix), MultiTransform (patterns
# and mirrors chained, with Scaled), datum lines, points and coordinate
# systems, shape binders (another body's faces brought in to sketch on), and
# body booleans. Each one feature, refused with FreeCAD's error and nothing
# kept when it fails.

import FreeCAD

from .. import runners
from . import pd_common as pc
from . import picks

GROUP = "feature"
INFO = ("PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, primitives, helix, "
        "MultiTransform, datum planes, lines, points and coordinate systems, binders, booleans) and the body's feature history.")

# The tools themselves are data (agentlink/data/tools.json, "family":
# "feature_more", run by agentlink/runners.py's steps runner): each entry has
# the tool's words, its checks with their refusals, the order of its steps
# and its answer. What is here is what those entries call by name
# (docs/data-tools.md).

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
    """Where a call puts its feature from the body's origin: at [x, y, z]
    and rotate { axis, angle }."""
    at = pc.vec3(a.get("at", [0, 0, 0]), "at")
    rot = FreeCAD.Rotation()
    r = a.get("rotate")
    if r:
        rot = FreeCAD.Rotation(pc.vec3(r.get("axis", [0, 0, 1]), "rotate.axis"), float(r.get("angle", 0)))
    return FreeCAD.Placement(at, rot)


def gear_profile(doc, b, a, kind, teeth, m):
    """The profile of a gear (FreeCAD's own involute gear object, made in
    this document) or of a sprocket (its outline drawn by FreeCAD's sprocket
    builder into a sketch of the body), and what is known of it: (profile,
    { pitchDiameter, outsideDiameter | chainPitch, roller }). FreeCAD's
    makers reach for the active view while the window is up: GuiUp is held
    off for the making and put back whatever happens."""
    up = FreeCAD.GuiUp
    FreeCAD.GuiUp = False  # their makers reach for the active view otherwise
    try:
        if kind == "gear":
            import InvoluteGearFeature as G

            # As makeInvoluteGear does, but in this document: it makes
            # its object in FreeCAD.ActiveDocument, which need not be
            # the session's.
            prof = doc.addObject("Part::Part2DObjectPython", "InvoluteGear")
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
    return prof, info


def keep_teeth(prof, kind, teeth, info):
    """The teeth kept on a gear's profile, where asm_joint kind chain (and
    gears) reads them (assembly.teeth_in): FreeCAD's involute gear has its
    own NumberOfTeeth; a sprocket is a plain sketch, so it gets
    AgentLinkTeeth, AgentLinkPitch (the chain pitch, mm) and AgentLinkKind
    "sprocket" (bicycle drive of 20 Nov, finding 5). {what: property}."""
    if kind == "gear" and "NumberOfTeeth" in prof.PropertiesList:
        return {"teeth": "NumberOfTeeth", "module": "Modules"}
    rows = (("AgentLinkTeeth", "App::PropertyInteger", int(teeth), "Number of teeth (pd_gear)"),
            ("AgentLinkPitch", "App::PropertyLength", float(info.get("chainPitch") or 0.0), "Chain pitch, mm (pd_gear)"),
            ("AgentLinkKind", "App::PropertyString", kind, "What pd_gear made: sprocket or gear"))
    for name, typ, value, doc_ in rows:
        if name not in prof.PropertiesList:
            prof.addProperty(typ, name, "Agent Link", doc_)
        setattr(prof, name, value)
    return {"teeth": "AgentLinkTeeth", "pitch": "AgentLinkPitch"}


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def new(b, kind, label):
        """A new feature of the body, labelled uniquely (the label is
        chosen before the object exists, or it clashes with itself). The
        entry makes it the tip where it should be."""
        label = s.unique(label)
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

    def attach_on(b, f, pl, link=None, words=""):
        """On the plane plane_ref gave (link, words), offset to pl; the
        body's XY plane when there is none (attach_origin)."""
        if link is None:
            return attach_origin(b, f, pl)
        setattr(f, pc.support_prop(f), [(link[0], link[1][0])])
        f.MapMode = pc.plane_mode(link, words)
        f.AttachmentOffset = pl

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "new": new, "attach_origin": attach_origin, "attach_on": attach_on, "keep_teeth": keep_teeth, "snapshot": lambda tool: s.snapshot(tool), "steps": lambda: len(s.steps),
               "settle": lambda b, f, tool, before=None, must_change=None, hint="": pc.settle(s, b, f, tool, before, must_change, hint=hint),
               "unique": lambda label, *own: s.unique(label, *own), "body": lambda ref: pc.pd_body(doc(), ref),
               "sketch_of": lambda ref, b=None: pc.sketch_of(doc(), ref, b), "in_body": pc.in_body, "body_of": pc.body_of, "volume": pc.volume,
               "tip_shape": pc.tip_shape, "ref_list": picks.ref_list,
               # a datum on several references (pd_common: the skeleton workflow)
               "attach_refs": lambda *x: pc.attach_refs(*x), "world_json": pc.world_json, "placement_json": picks.placement_json,
               # FreeCAD's own
               "V": V, "placement": FreeCAD.Placement, "rotation": FreeCAD.Rotation, "setprop": setattr, "getprop": getattr, "xyz": pc.geo.vec, "vec3": pc.vec3,
               "num_json": picks.num_json,
               # faces, edges, planes and axes by where they are (pd_common)
               "find_edges": lambda *x: pc.find_edges(*x), "find_face": lambda *x: pc.find_face(*x), "ref_shape": pc.ref_shape, "ref_names": pc.ref_names,
               "plane_ref": lambda *x: pc.plane_ref(*x), "axis_ref": lambda *x: pc.axis_ref(*x), "support_prop": pc.support_prop,
               # the family's
               "PRIMS": PRIMS, "place": placement, "gear_profile": lambda b, a, kind, teeth, m: gear_profile(doc(), b, a, kind, teeth, m)}
    return runners.tools(GROUP, s, helpers, family="feature_more")
