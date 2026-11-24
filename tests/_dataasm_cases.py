# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_dataasm_data.py runs through the old handler and the
# new data entry of each converted Assembly tool of families/assembly.py and
# assembly_more.py, on the stand-in FreeCAD (tests/_dataasm_standin.py): its
# normal paths and each of its refusals.
import json
import os

# The family files whose tools were converted.
FILES = ("assembly", "assembly_more")
FIRST = ("asm_new", "asm_add", "asm_ground", "asm_joint", "asm_list", "asm_joint_remove", "asm_sweep", "asm_check")
MORE = ("asm_fits", "asm_motion", "asm_export", "asm_pose", "asm_limits", "asm_explode", "asm_sub", "asm_bom")
# Each converted tool and its group (both files are of the group "assembly").
CONVERTED = {k: "assembly" for k in FIRST + MORE}
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("asm_new", "named, another grounded"): {"assembly": "Lid box", "parts": ["Base", "Lid"], "grounded": ["Lid"]},
    ("asm_new", "a body already in an assembly"): ["refused", "invalid_state", "Base is in Assembly already: a part is in one assembly. Join it there (asm_joint { assembly: \"Assembly\" }), "
                                                   "or put Assembly itself into another with asm_sub. Nothing was made."],
    ("asm_add", "one in already and one new"): {"added": ["Pin"], "parts": ["Base", "Lid", "Pin"]},
    ("asm_ground", "one more held"): {"grounded": ["Base", "Lid"]},
    ("asm_ground", "let go"): {"grounded": []},
    ("asm_list", "nothing grounded"): {"joints": [], "solve": "no part is grounded"},
    ("asm_joint_remove", "none named"): ["refused", "not_found", "joint None is not in Assembly: asm_list lists its joints (a grounding is taken off with asm_ground { part, grounded: false })."],
    ("asm_check", "an overlap"): {"parts": 2, "overlaps": [{"parts": ["Base", "Lid"], "volume": 350.0, "at": [5.0, 5.0, 5.0]}], "verdict": "fix"},
    ("asm_check", "a part joined to nothing"): {"notConnected": ["Pin"], "verdict": "clear"},
    ("asm_check", "a screw's thread"): {"threads": 2, "verdict": "clear"},
    ("asm_sweep", "a slider into the base"): {"verdict": "collides", "collidesAt": [2.5, 5.0, 7.5, 10.0], "clearFromStart": [0.0, 0.0]},
    # bicycle finding 7: the same overlap at every step is static, not a collision the motion makes
    ("asm_sweep", "a slider that collides from the start"): {"collidesAt": None, "clearFromStart": None, "verdict": "clear"},
    ("asm_sweep", "gears drive a wheel"): {"moves": ["Lid"], "driven": [{"part": "Wheel", "via": "Gears", "turns": "degrees", "per": -2.0}], "verdict": "clear"},
    ("asm_sweep", "no steps"): ["refused", "invalid_input", "steps: 1 to 72 (got 0); each step checks every pair of parts — for a closer look sweep a shorter from/to range."],
    ("asm_joint", "named, a part moved by it"): {"joint": "Glue", "kind": "fixed", "a": "Base.Face1", "b": "Lid.Face2", "solve": "solved",
                                                 "moved": {"Lid": {"from": [0.0, 0.0, 0.0], "to": {"at": [0.0, 0.0, 20.0], "axis": [0.0, 0.0, 1.0], "angle": 0.0}, "by": 20.0}}},
    ("asm_joint", "reversed"): {"flipped": True},
    # bicycle finding 4: no turn by itself; autoFlip: true is the old way
    ("asm_joint", "turned over to stop an overlap"): {"moved": {}, "flipped": "turned over to stop the parts overlapping (autoFlip: true; leave autoFlip out to keep it as FreeCAD first put it)", "overlaps": None},
    ("asm_joint", "turning over does not help"): {"flipped": None, "warning": "Parts overlap after the solve: Base/Lid 100 mm³. The tool did not turn a part over. reversed: true turns the moved part over on the joint; "
                                                                              "autoFlip: true lets the tool try it; else check the sizes."},
    ("asm_joint", "a kind not offered"): ["refused", "invalid_input", "kind: one of fixed, revolute, cylindrical, slider, ball, distance, parallel, perpendicular, angle, rackpinion, screw, gears, belt, chain (got 'weld')."],
    ("asm_joint", "the solver finds nothing grounded"): ["refused", "failed", "The fixed joint leaves Assembly unsolved: no part is grounded — nothing was kept. asm_ground { part } holds one part first."],
    ("asm_joint", "FreeCAD will not connect it"): ["refused", "failed", "FreeCAD could not make the fixed joint between Base.Face1 and Lid.Face2: setJointConnectors: it would not"],
    ("asm_fits", "held to H7/g6"): {"verdict": "fix"},
    ("asm_fits", "no joints"): ["refused", "not_found", "No joints in Assembly to read fits from: name pairs [{ a, b }] instead."],
    ("asm_motion", "save"): {"saved": "Open", "keys": 2, "assembly": "Assembly"},
    ("asm_motion", "play a slide that clashes"): {"frames": 3, "verdict": "parts overlap in 3 of 3 frames", "left": "as it was"},
    ("asm_motion", "play and keep, placements, a limit, a file"): {"frames": 5, "left": "at the last frame", "path": "<out>/sub/open.json"},
    ("asm_export", "to the session's folder"): {"path": "<out>/Assembly.asmt", "bytes": 13},
    ("asm_pose", "by, wrapped"): {"pose": -160.0, "was": 0.0, "unit": "degrees", "moved": ["Lid"], "step": 1},
    ("asm_pose", "outside its limits"): ["refused", "invalid_input", "45 is outside Revolute's limits [-10.0 … 20.0] (it is at 0 degrees now)."],
    ("asm_pose", "into the base"): ["refused", "failed", "At -4 mm parts overlap (Base/Lid) — nothing was kept. asm_sweep finds the clear range; allowOverlap: true keeps it anyway."],
    ("asm_limits", "one cleared, one left"): {"limits": {"angleMax": 20.0}, "unit": "degrees", "step": 1},
    ("asm_limits", "min over max"): ["refused", "invalid_input", "min (30) is over max (20) on Revolute: give min below max (null clears one). Nothing was kept."],
    ("asm_explode", "along z, grounded below"): {"exploded": {"Lid": [0.0, 0.0, 12.0], "Pin": [0.0, 0.0, 6.0]}, "view": "Exploded_View", "by": "FreeCAD's Exploded View (Assembly)", "jointsOff": 1},
    ("asm_explode", "a FreeCAD with no exploded views"): {"view": None, "by": "placements moved here"},
    ("asm_explode", "collapse"): {"collapsed": True, "solve": "solved", "step": 1},
    ("asm_sub", "flexible, named"): {"as": "Pin unit", "type": "Assembly::AssemblyLink", "rigid": False},
    ("asm_sub", "a FreeCAD with plain links"): {"type": "App::Link", "rigid": True},
    ("asm_bom", "FreeCAD's own, materials recorded"): {"bom": "Assembly BOM", "native": True, "parts": [{"name": "Base", "material": "pla", "mass": 1.24, "volume": 1.0},
                                                                                                       {"name": "Lid", "material": "unobtainium", "mass": "", "volume": 0.2}]},
    ("asm_bom", "a FreeCAD with no BOM object"): {"sheet": "BOM", "native": False},
}
# Refusals written in the data that no case here reaches (the handler at BASE had no such input,
# so no case can compare them): tests/test_findings_1120.py reaches each.
UNREACHED = [
    'asm_joint: gap or offset, not both: gap is the mm between the two joined faces af',
    'asm_joint: gap: the gap across this joint cannot be measured — a or b must be a f',
    # bicycle findings 3, 4, 5 (keep, autoFlip, chain by teeth): tests/test_bicycle_1120.py reaches each.
    'asm_joint: keep turns no part over: not with reversed or autoFlip. keep holds the',
    'asm_joint: keep, or offset, rotate and gap: keep finds the offset that holds the ',
    'asm_joint: autoFlip or reversed, not both: reversed says the way round, autoFlip ',
    'asm_joint: teeth1, teeth2: for kind chain, belt and gears only.',
    'asm_joint: teeth or radii, not both: teeth1 and teeth2 set radius1 and radius2.',
    'asm_joint: chain: teeth1 and teeth2, a PartDesign Sprocket in each part, or radiu',
    'asm_joint: keep: FreeCAD gave this joint no frames to read (Placement1, Placement',
]

FACE = {"kind": "face"}


def cases(fc, tmp, old, new):
    def prep(*fns, **flags):
        def prepare(s):
            fc.fc.GuiUp = False
            fc.fc.Version = lambda: ["1", "1", "3"]
            fc.state["solves"] = 0
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    def old_release(s):
        fc.fc.Version = lambda: ["1", "0", "2"]

    def base(s):
        fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")

    def lid(s):
        fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")

    def pin(s):
        fc.a_part("Pin", (20, 0, 0), (22, 2, 10), name="Pin")

    def wheel(s):
        fc.a_part("Wheel", (40, 0, 0), (50, 10, 2), name="Wheel")

    def sunk(s):  # a lid that sits 5 mm into the base
        fc.a_part("Lid", (0, 0, 5), (10, 10, 12), name="Lid")

    def near_pin(s):  # 0.5 mm off the base
        fc.a_part("Pin", (10.5, 0, 0), (12, 2, 10), name="Pin")

    def asm(label="Assembly", parts=("Base", "Lid"), ground="Base", name="Assembly", type_="Assembly"):
        def add(s):
            a = fc.an_object("Assembly::AssemblyObject", name, label)
            a.__dict__["Type"] = type_
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            for p in parts:
                fc.into(a, fc.doc().getObject(p))
            if ground:
                g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
                g.__dict__["ObjectToGround"] = fc.doc().getObject(ground)
        return add

    def joint(kind, a, b, label=None, asm_name="Assembly", form="part", **props):
        """A joint as asm_joint leaves one: a, b "Part.Element" (or None)."""
        def add(s):
            from _dataasm_standin import JOINT_TYPES

            a_ = fc.doc().getObject(asm_name)
            jg = next(o for o in a_.Group if o.TypeId == "Assembly::JointGroup")
            j = fc.into(jg, fc.an_object("App::FeaturePython", kind, label))
            fc.joint(j, JOINT_TYPES.index(kind))

            def ref(r):
                if r is None:
                    return None
                p, _, el = r.partition(".")
                o = fc.doc().getObject(p)
                if form == "asm":
                    return [a_, [f"{p}.{el}", f"{p}.{el}"]]
                return [o, [el, el] if el else []]

            j.__dict__.update(Reference1=ref(a), Reference2=ref(b), **props)
        return add

    def hide(name):
        def do(s):
            fc.doc().getObject(name).__dict__["Visibility"] = False
        return do

    def linked(s):  # the pin held through a link, in the assembly
        ln = fc.an_object("App::Link", "Link", "Pin link", LinkedObject=fc.doc().getObject("Pin"), Shape=fc.solid("pin link", (0, 0, 0), (5, 5, 5)))
        fc.into(fc.doc().getObject("Assembly"), ln)

    def sheet_part(s):  # a face, no solid
        o = fc.body("Sheet", fc.face("sheet", [(0, 0, 50), (10, 10, 50)]), name="Sheet")
        fc.into(fc.doc().getObject("Assembly"), o)

    def boxed(s):  # the pin inside a moved App::Part of the assembly
        c = fc.an_object("App::Part", "Part", "Sub")
        c.Placement = fc.Placement(fc.Vec(0, 0, 100), fc.Rotation())
        fc.into(c, fc.doc().getObject("Pin"))
        fc.into(fc.doc().getObject("Assembly"), c)

    def screw(s):  # an M8 screw standing in the base
        o = fc.a_part("M8x25-Screw", (3, 3, 2), (7, 7, 27), name="Screw", diameter="M8")
        fc.into(fc.doc().getObject("Assembly"), o)

    def round_edges(s):
        fc.round_edge(fc.doc().getObject("Base"), 1, (5, 5, 10), (0, 0, 1), 4)
        fc.round_edge(fc.doc().getObject("Lid"), 1, (5, 5, 10), (0, 0, 1), 8)
        for name in ("Base", "Lid"):  # the second edge a straight one, with its ends
            fc.doc().getObject(name).Shape.Edges[1].pts = [fc.Vec(0, 0, 0), fc.Vec(0, 0, 10)]

    two, three, four = (base, lid), (base, lid, pin), (base, lid, pin, wheel)
    duo = (base, lid, asm())
    trio = (base, lid, pin, asm(parts=("Base", "Lid", "Pin")))
    quad = (base, lid, pin, wheel, asm(parts=("Base", "Lid", "Pin", "Wheel")))
    hinge = joint("Revolute", "Base.Face1", "Lid.Face1")
    slide = joint("Slider", "Base.Face2", "Lid.Face1")
    A, B = {"part": "Base", "element": "Face1"}, {"part": "Lid", "element": "Face2"}
    J = {"kind": "fixed", "a": A, "b": B}

    out = [
        # ---- asm_new ----
        ("asm_new", "two bodies, the first grounded", prep(*two), {"parts": ["Base", "Lid"]}),
        ("asm_new", "named, another grounded", prep(*two), {"parts": ["Base", "Lid"], "name": "Lid box", "ground": "Lid"}),
        ("asm_new", "none grounded", prep(*two), {"parts": ["Base", "Lid"], "ground": False}),
        ("asm_new", "no parts", prep(*two), {}),
        ("asm_new", "parts not a list", prep(*two), {"parts": "Base"}),
        ("asm_new", "a body already in an assembly", prep(*duo), {"parts": ["Base"], "name": "Second"}),
        ("asm_new", "an unknown body", prep(*two), {"parts": ["Nope"]}),
        ("asm_new", "ground names a part not in it", prep(*two), {"parts": ["Base"], "ground": "Lid"}),
        # ---- asm_add ----
        ("asm_add", "one more", prep(*three, asm()), {"parts": ["Pin"]}),
        ("asm_add", "one in already and one new", prep(*three, asm()), {"assembly": "Assembly", "parts": ["Lid", "Pin"]}),
        ("asm_add", "all in already", prep(*duo), {"parts": ["Base", "Lid"]}),
        ("asm_add", "no parts", prep(*duo), {}),
        ("asm_add", "an unknown assembly", prep(*three, asm()), {"assembly": "Nope", "parts": ["Pin"]}),
        ("asm_add", "no assembly", prep(*three), {"parts": ["Pin"]}),
        ("asm_add", "two assemblies, none named", prep(*three, asm(), asm("Other", ("Pin",), "Pin", "Assembly001")), {"parts": ["Pin"]}),
        # ---- asm_ground ----
        ("asm_ground", "one more held", prep(*duo), {"part": "Lid"}),
        ("asm_ground", "held already", prep(*duo), {"part": "Base", "grounded": True}),
        ("asm_ground", "let go", prep(*duo), {"part": "Base", "grounded": False}),
        ("asm_ground", "let go of one not held", prep(*duo), {"part": "Lid", "grounded": False}),
        ("asm_ground", "an unknown part", prep(*duo), {"part": "Nope"}),
        ("asm_ground", "no joint group yet", prep(base, lid, lambda s: fc.into(fc.an_object("Assembly::AssemblyObject", "Assembly"), fc.doc().getObject("Base"))), {"part": "Base"}),
        # ---- asm_list ----
        ("asm_list", "parts and joints", prep(*trio, hinge, joint("Fixed", "Lid.Face2", "Pin.Edge3", "Pinned", Suppressed=True)), {}),
        ("asm_list", "references read from the assembly down", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face2", form="asm")), {"assembly": "Assembly"}),
        ("asm_list", "a reference with no element, and none", prep(*duo, joint("Fixed", "Base", None)), {}),
        ("asm_list", "nothing grounded", prep(base, lid, asm(ground=None), solve=-6), {}),
        ("asm_list", "the solver throws", prep(*duo, solve="raise"), {}),
        ("asm_list", "a code with no words", prep(*duo, solve=-9), {}),
        ("asm_list", "no assembly", prep(*two), {}),
        # ---- asm_joint_remove ----
        ("asm_joint_remove", "by label", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face2", "Glue")), {"joint": "Glue"}),
        ("asm_joint_remove", "by object name", prep(*duo, hinge), {"joint": "Revolute", "assembly": "Assembly"}),
        ("asm_joint_remove", "not there", prep(*duo, hinge), {"joint": "Nope"}),
        ("asm_joint_remove", "none named", prep(*duo, hinge), {}),
        ("asm_joint_remove", "left unsolved", prep(*duo, hinge, solve=-1), {"joint": "Revolute"}),
        # ---- asm_check ----
        ("asm_check", "clear", prep(*duo), {}),
        ("asm_check", "an overlap", prep(base, sunk, asm()), {}),
        ("asm_check", "closer than a clearance", prep(base, lid, near_pin, asm(parts=("Base", "Lid", "Pin"))), {"clearance": 1}),
        ("asm_check", "a clearance nothing is inside", prep(*trio), {"clearance": 0.5}),
        ("asm_check", "clearance not a number", prep(*duo), {"clearance": "wide"}),
        ("asm_check", "a hidden part, still checked", prep(base, sunk, asm(), hide("Lid")), {}),
        ("asm_check", "a link, a face and a moved container", prep(*three, asm(), linked, sheet_part, boxed), {}),
        ("asm_check", "a part joined to nothing", prep(*trio, unconnected=("Pin",)), {}),
        ("asm_check", "a FreeCAD that cannot say what is connected", prep(*trio, unconnected=("Pin",), no_methods=("isPartConnected",)), {}),
        ("asm_check", "a screw's thread", prep(*duo, screw, common_share=1.0, cut_share=0.0), {}),
        ("asm_check", "unsolved", prep(*duo, solve=-1), {}),
        ("asm_check", "no assembly", prep(*two), {}),
        # ---- asm_sweep ----
        ("asm_sweep", "a hinge, 0 to 90", prep(*duo, hinge), {"joint": "Revolute"}),
        ("asm_sweep", "a range and steps", prep(*duo, hinge), {"joint": "Revolute", "from": -30, "to": 30, "steps": 3, "assembly": "Assembly"}),
        ("asm_sweep", "a slider into the base", prep(*duo, slide), {"joint": "Slider", "steps": 4}),
        ("asm_sweep", "a slider that collides from the start", prep(base, sunk, asm(), slide), {"joint": "Slider", "steps": 2}),
        ("asm_sweep", "a slider away, with a clearance", prep(base, lid, near_pin, asm(parts=("Base", "Lid", "Pin")), joint("Slider", "Base.Face1", "Lid.Face1")), {"joint": "Slider", "steps": 2, "clearance": 1}),
        ("asm_sweep", "a cylindrical turned", prep(*duo, joint("Cylindrical", "Base.Face1", "Lid.Face1")), {"joint": "Cylindrical", "turn": True, "steps": 2}),
        ("asm_sweep", "a cylindrical slid", prep(*duo, joint("Cylindrical", "Base.Face1", "Lid.Face1")), {"joint": "Cylindrical", "steps": 2}),
        ("asm_sweep", "between its limits", prep(*duo, joint("Revolute", "Base.Face1", "Lid.Face1", EnableAngleMin=True, AngleMin=-10.0, EnableAngleMax=True, AngleMax=20.0)), {"joint": "Revolute", "steps": 3}),
        ("asm_sweep", "the grounded part named second", prep(*duo, joint("Revolute", "Lid.Face1", "Base.Face1")), {"joint": "Revolute", "steps": 2}),
        ("asm_sweep", "a part carried along, after a pose", prep(*trio, joint("Revolute", "Base.Face1", "Lid.Face1", AgentLinkPose=15.0), joint("Fixed", "Lid.Face2", "Pin.Face1")), {"joint": "Revolute", "steps": 2}),
        ("asm_sweep", "gears drive a wheel", prep(*quad, hinge, joint("Revolute", "Base.Face1", "Wheel.Face1", "Axle"), joint("Gears", "Lid.Face1", "Wheel.Face1", Distance=10.0, Distance2=5.0)),
         {"joint": "Revolute", "steps": 2}),
        ("asm_sweep", "a belt the other way round, a rack and a screw", prep(*quad, hinge, joint("Revolute", "Wheel.Face1", "Base.Face1", "Axle"), joint("Belt", "Wheel.Face1", "Lid.Face1", Distance=10.0, Distance2=5.0),
                                                                              joint("Slider", "Base.Face1", "Pin.Face1", "Rail"), joint("RackPinion", "Lid.Face1", "Pin.Face1", Distance=3.0)), {"joint": "Revolute", "steps": 2}),
        ("asm_sweep", "a screw's nut, and couplings that drive nothing", prep(*quad, hinge, joint("Slider", "Base.Face1", "Pin.Face1", "Rail"), joint("Screw", "Lid.Face1", "Pin.Face1", Distance=2.0),
                                                                               joint("Gears", "Lid.Face1", "Wheel.Face1", Distance=0.0, Distance2=5.0), joint("Belt", "Base.Face1", "Wheel.Face1", Distance=1.0, Distance2=1.0)),
         {"joint": "Revolute", "steps": 1}),
        ("asm_sweep", "a slider does not turn gears", prep(*quad, slide, joint("Revolute", "Base.Face1", "Wheel.Face1", "Axle"), joint("Gears", "Lid.Face1", "Wheel.Face1", Distance=10.0, Distance2=5.0)),
         {"joint": "Slider", "steps": 1, "to": 1}),
        ("asm_sweep", "a round edge's axis and a straight edge's", prep(*duo, round_edges, joint("Revolute", "Base.Edge1", "Lid.Edge1"), joint("Slider", "Base.Edge2", "Lid.Edge2")), {"joint": "Slider", "steps": 1}),
        ("asm_sweep", "not there", prep(*duo, hinge), {"joint": "Nope"}),
        ("asm_sweep", "a grounding named", prep(*duo, hinge), {"joint": "GroundedJoint"}),
        ("asm_sweep", "a fixed joint", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face2")), {"joint": "Fixed"}),
        ("asm_sweep", "no steps", prep(*duo, hinge), {"joint": "Revolute", "steps": 0}),
        ("asm_sweep", "too many steps", prep(*duo, hinge), {"joint": "Revolute", "steps": 99}),
        ("asm_sweep", "an element that is gone", prep(*duo, joint("Revolute", "Base.Face99", "Lid.Face1")), {"joint": "Revolute"}),
        ("asm_sweep", "a reference that is gone", prep(*duo, joint("Revolute", "Base.Face1", None)), {"joint": "Revolute"}),
        ("asm_sweep", "crash: from not a number", prep(*duo, hinge), {"joint": "Revolute", "from": "start"}),
        # ---- asm_joint ----
        ("asm_joint", "fixed, by element names", prep(*duo), dict(J)),
        ("asm_joint", "named, a part moved by it", prep(*duo, joint_puts={"Lid": [0, 0, 20]}), dict(J, name="Glue", assembly="Assembly")),
        ("asm_joint", "by queries", prep(*duo), {"kind": "Revolute", "a": {"part": "Base", "element": {"kind": "face", "normal": [0, 0, 1]}}, "b": {"part": "Lid", "kind": "edge", "type": "circle"}}),
        ("asm_joint", "a query nothing matches", prep(*duo, query_hits=[]), dict(J, a={"part": "Base", "element": FACE})),
        ("asm_joint", "a query several match", prep(*duo, query_hits=[1, 2, 3]), dict(J, a={"part": "Base", "element": FACE})),
        ("asm_joint", "near picks one of several", prep(*duo, query_hits=[1, 2]), dict(J, a={"part": "Base", "element": {"kind": "face", "near": [0, 0, 30]}})),
        ("asm_joint", "an element the part has not", prep(*duo), dict(J, a={"part": "Base", "element": "Face99"})),
        ("asm_joint", "an element that is neither", prep(*duo), dict(J, a={"part": "Base", "element": 6})),
        ("asm_joint", "a kind not offered", prep(*duo), dict(J, kind="weld")),
        ("asm_joint", "no kind", prep(*duo), {"a": A, "b": B}),
        ("asm_joint", "nothing grounded", prep(base, lid, asm(ground=None)), dict(J)),
        ("asm_joint", "b left out", prep(*duo), {"kind": "fixed", "a": A}),
        ("asm_joint", "a with no part", prep(*duo), dict(J, a={"element": "Face1"})),
        ("asm_joint", "both on one part", prep(*duo), dict(J, b={"part": "Base", "element": "Face2"})),
        ("asm_joint", "a part not in it", prep(*three, asm()), dict(J, b={"part": "Pin", "element": "Face1"})),
        ("asm_joint", "a distance", prep(*duo), dict(J, kind="distance", distance=4)),
        ("asm_joint", "a distance not a number", prep(*duo), dict(J, kind="distance", distance="far")),
        ("asm_joint", "an angle, the default", prep(*duo), dict(J, kind="angle")),
        ("asm_joint", "a rack with no radius", prep(*duo), dict(J, kind="rackpinion")),
        ("asm_joint", "a rack", prep(*duo), dict(J, kind="rackpinion", radius1=6)),
        ("asm_joint", "a screw with no pitch", prep(*duo), dict(J, kind="screw")),
        ("asm_joint", "a screw", prep(*duo), dict(J, kind="screw", pitch=1.5)),
        ("asm_joint", "gears with no radius", prep(*duo), dict(J, kind="gears", radius1=0)),
        ("asm_joint", "gears with one radius", prep(*duo), dict(J, kind="gears", radius1=10)),
        ("asm_joint", "gears", prep(*duo), dict(J, kind="gears", radius1=10, radius2=5)),
        ("asm_joint", "a belt read off round edges", prep(*duo, round_edges), dict(J, kind="belt", a={"part": "Base", "element": "Edge1"}, b={"part": "Lid", "element": "Edge1"})),
        ("asm_joint", "a belt with no radius", prep(*duo), dict(J, kind="belt")),
        ("asm_joint", "offset and turned", prep(*duo), dict(J, offset=2, rotate=45)),
        ("asm_joint", "turned only", prep(*duo), dict(J, rotate=30)),
        ("asm_joint", "FreeCAD will not connect it", prep(*duo, fail=("setJointConnectors",)), dict(J)),
        ("asm_joint", "frames and undo that cannot be touched", prep(*duo, fail=("updateJCSPlacements",), no_methods=("clearUndo",)), dict(J)),
        ("asm_joint", "reversed", prep(*duo, flip_puts={"Lid": [0, 0, 30]}), dict(J, reverse=True)),
        ("asm_joint", "kept as FreeCAD put it, overlapping", prep(*duo, joint_puts={"Lid": [0, 0, -5]}), dict(J, reverse=False)),
        ("asm_joint", "turned over to stop an overlap", prep(*duo, joint_puts={"Lid": [0, 0, -5]}, flip_puts={"Lid": [0, 0, 0]}), dict(J, autoFlip=True)),
        ("asm_joint", "turning over does not help", prep(*duo, joint_puts={"Lid": [0, 0, -5]}), dict(J)),
        ("asm_joint", "turned over, it no longer solves", prep(*duo, joint_puts={"Lid": [0, 0, -5]}, flip_puts={"Lid": [0, 0, 0]}, solve=[0, -1, 0]), dict(J)),
        ("asm_joint", "a ball joint is not turned over", prep(*duo, joint_puts={"Lid": [0, 0, -5]}, flip_puts={"Lid": [0, 0, 0]}), dict(J, kind="ball")),
        ("asm_joint", "the solver finds nothing grounded", prep(*duo, solve=-6), dict(J)),
        ("asm_joint", "unsolved", prep(*duo, solve=-1), dict(J)),
        ("asm_joint", "the solver throws", prep(*duo, solve="raise"), dict(J)),
        ("asm_joint", "an older release's references", prep(*duo, old_release), dict(J)),
        ("asm_joint", "an assembly not marked as one", prep(base, lid, asm(type_="")), dict(J)),
        ("asm_joint", "a thread is not an overlap", prep(*duo, screw, common_share=1.0, cut_share=0.0), dict(J, reverse=False)),
    ]

    # ---- assembly_more.py ----
    def holed(s):  # the base with a ⌀10 hole down its middle, the pin a ⌀9.98 shaft in it
        fc.round_face(fc.doc().getObject("Base"), 3, (5, 5, 0), (0, 0, 1), 5.0, True)
        fc.round_face(fc.doc().getObject("Pin"), 3, (5, 5, 0), (0, 0, 1), 4.99, False, (2.0, 12.0))

    def two_pins(s):  # both round faces shafts
        fc.round_face(fc.doc().getObject("Base"), 3, (5, 5, 0), (0, 0, 1), 5.0, False)
        fc.round_face(fc.doc().getObject("Pin"), 3, (5, 5, 0), (0, 0, 1), 4.99, False)

    def exploded(s):
        a_ = fc.doc().getObject("Assembly")
        a_.__dict__["AgentLinkExploded"] = json.dumps({"Lid": {"base": [0, 0, 0], "q": [0, 0, 0, 1]}, "__joints_off__": ["Revolute", "Gone"]})
        fc.doc().getObject("Lid").__dict__["Placement"] = fc.Placement(fc.Vec(0, 0, 30), fc.Rotation())

    def motion(keys, asm_label="Assembly"):
        def add(s):
            fc.records()["motions"] = {"Open": {"assembly": asm_label, "keys": [{"poses": k} for k in keys]}}
        return add

    def materials(s):
        fc.records()["materials"] = {"Base": "pla", "Lid": "unobtainium", "Pin": "petg"}

    def second(s):  # another assembly, holding the pin
        asm("Other", ("Pin",), "Pin", "Assembly001")(s)

    def holds_first(s):  # the other assembly already holds the first
        ln = fc.an_object("Assembly::AssemblyLink", "AssemblyLink", "Assembly")
        ln.__dict__["LinkedObject"] = fc.doc().getObject("Assembly")
        fc.into(fc.doc().getObject("Assembly001"), ln)

    def a_file(s):
        os.makedirs(os.path.join(s.out_dir, "sub"), exist_ok=True)

    pins = (base, pin, asm(parts=("Base", "Pin")))
    PA, PB = {"part": "Base", "element": "Face3"}, {"part": "Pin", "element": "Face3"}
    limited = joint("Revolute", "Base.Face1", "Lid.Face1", EnableAngleMin=True, AngleMin=-10.0, EnableAngleMax=True, AngleMax=20.0)
    rail = joint("Slider", "Base.Face1", "Lid.Face1", EnableLengthMin=True, LengthMin=-2.0, EnableLengthMax=True, LengthMax=8.0)
    out += [
        # ---- asm_fits ----
        ("asm_fits", "a joint's hole and shaft", prep(*pins, holed, joint("Cylindrical", "Base.Face3", "Pin.Face3")), {}),
        ("asm_fits", "held to H7/g6", prep(*pins, holed, joint("Cylindrical", "Base.Face3", "Pin.Face3")), {"fit": "H7/g6", "joint": "Cylindrical"}),
        ("asm_fits", "held to H8/f7 at a size, by pairs", prep(*pins, holed), {"pairs": [{"a": PA, "b": PB, "fit": "H8/f7", "size": 10}], "assembly": "Assembly"}),
        ("asm_fits", "pairs, the fit of the call", prep(*pins, holed), {"pairs": [{"a": PA, "b": {"part": "Pin"}}], "fit": "H7/p6"}),
        ("asm_fits", "a fit that is not one", prep(*pins, holed), {"pairs": [{"a": PA, "b": PB}], "fit": "H7"}),
        ("asm_fits", "a fit ISO 286 has not", prep(*pins, holed), {"pairs": [{"a": PA, "b": PB}], "fit": "H7/q99"}),
        ("asm_fits", "flat faces apart and in contact", prep(*trio, joint("Fixed", "Base.Face1", "Lid.Face2"), joint("Fixed", "Base.Face1", "Pin.Face1", "Far")), {}),
        ("asm_fits", "a joint with nothing round, skipped", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Edge2"), joint("Fixed", "Base", None, "Loose")), {}),
        ("asm_fits", "the joint named has nothing round", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Edge2")), {"joint": "Fixed"}),
        ("asm_fits", "two shafts, no hole", prep(*pins, two_pins, joint("Cylindrical", "Base.Face3", "Pin.Face3")), {"joint": "Cylindrical"}),
        ("asm_fits", "no joints", prep(*duo), {}),
        ("asm_fits", "a pair with no part", prep(*pins, holed), {"pairs": [{"a": PA, "b": {"element": "Face3"}}]}),
        ("asm_fits", "a pair that is nothing", prep(*pins, holed), {"pairs": [None]}),
        ("asm_fits", "a joint not there", prep(*duo), {"joint": "Nope"}),
        # ---- asm_motion ----
        ("asm_motion", "list, none saved", prep(*duo, hinge), {}),
        ("asm_motion", "list", prep(*duo, hinge, motion([{"Revolute": 0}, {"Revolute": 40, "Slider": 2}])), {"action": "list"}),
        ("asm_motion", "save", prep(*duo, hinge), {"action": "save", "name": "Open", "keys": [{"Revolute": 0}, {"Revolute": 40}], "assembly": "Assembly"}),
        ("asm_motion", "save with one key", prep(*duo, hinge), {"action": "save", "name": "Open", "keys": [{"Revolute": 0}]}),
        ("asm_motion", "save with keys that are not poses", prep(*duo, hinge), {"action": "save", "name": "Open", "keys": [1, 2]}),
        ("asm_motion", "save with a joint not there", prep(*duo, hinge), {"action": "save", "name": "Open", "keys": [{"Revolute": 0}, {"Nope": 4}]}),
        ("asm_motion", "no name", prep(*duo, hinge), {"action": "play"}),
        ("asm_motion", "delete", prep(*duo, hinge, motion([{"Revolute": 0}, {"Revolute": 40}])), {"action": "delete", "name": "Open"}),
        ("asm_motion", "delete one not there", prep(*duo, hinge), {"action": "delete", "name": "Nope"}),
        ("asm_motion", "an action that is none", prep(*duo, hinge), {"action": "rewind", "name": "Open"}),
        ("asm_motion", "play one not saved", prep(*duo, hinge), {"action": "play", "name": "Open"}),
        ("asm_motion", "play, put back", prep(*duo, hinge, motion([{"Revolute": 0}, {"Revolute": 40}])), {"action": "play", "name": "Open", "steps": 2}),
        ("asm_motion", "play and keep, placements, a limit, a file", prep(*duo, hinge, a_file, motion([{"Revolute": 0}, {"Revolute": 40}, {"Revolute": 10}])),
         {"action": "play", "name": "Open", "steps": 2, "keep": True, "placements": True, "limit": 2, "path": "sub/open.json"}),
        ("asm_motion", "play a slide that clashes", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1"), motion([{"Slider": 0}, {"Slider": -4}])), {"action": "play", "name": "Open", "steps": 2, "clearance": 1}),
        ("asm_motion", "play, a joint that will not pose", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face1"), motion([{"Fixed": 0}, {"Fixed": 4}])), {"action": "play", "name": "Open"}),
        ("asm_motion", "play, frames that cannot be read", prep(*duo, hinge, motion([{"Revolute": 0}, {"Revolute": 40}]), no_frames=True), {"action": "play", "name": "Open", "steps": 1}),
        # ---- asm_export ----
        ("asm_export", "to the session's folder", prep(*duo), {}),
        ("asm_export", "to a path, a name with a space", prep(base, lid, asm("Lid box")), {"path": "box.asmt", "assembly": "Lid box"}),
        ("asm_export", "a FreeCAD that cannot", prep(*duo, no_methods=("exportAsASMT",)), {}),
        ("asm_export", "it will not write", prep(*duo, fail=("exportAsASMT",)), {"path": "x.asmt"}),
        ("asm_export", "it writes nothing", prep(*duo, asmt_writes_nothing=True), {"path": "y.asmt"}),
        ("asm_export", "no assembly", prep(*two), {}),
        # ---- asm_pose ----
        ("asm_pose", "a hinge turned to", prep(*duo, hinge), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "by, wrapped", prep(*duo, hinge), {"joint": "Revolute", "by": 200, "assembly": "Assembly"}),
        ("asm_pose", "home", prep(*duo, hinge, lambda s: fc.put("Lid", [0, 0, 0, 25])), {"joint": "Revolute", "home": True}),
        ("asm_pose", "a slider, a part carried", prep(*trio, joint("Slider", "Base.Face1", "Lid.Face1"), joint("Fixed", "Lid.Face2", "Pin.Face1")), {"joint": "Slider", "to": 6}),
        ("asm_pose", "the grounded part named second", prep(*duo, joint("Slider", "Lid.Face1", "Base.Face1")), {"joint": "Slider", "by": 3, "allowOverlap": True}),
        ("asm_pose", "a cylindrical turned", prep(*duo, joint("Cylindrical", "Base.Face1", "Lid.Face1")), {"joint": "Cylindrical", "turn": True, "to": 45}),
        ("asm_pose", "frames that cannot be read: counted", prep(*duo, hinge, no_frames=True), {"joint": "Revolute", "by": 30}),
        ("asm_pose", "counted on from before", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1", AgentLinkPose=2.0), no_frames=True), {"joint": "Slider", "to": 5}),
        ("asm_pose", "while exploded", prep(*duo, hinge, exploded), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "a joint not there", prep(*duo, hinge), {"joint": "Nope", "to": 30}),
        ("asm_pose", "a fixed joint", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face2")), {"joint": "Fixed", "to": 30}),
        ("asm_pose", "nowhere to go", prep(*duo, hinge), {"joint": "Revolute"}),
        ("asm_pose", "outside its limits", prep(*duo, limited), {"joint": "Revolute", "to": 45}),
        ("asm_pose", "under a lower limit only", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1", EnableLengthMin=True, LengthMin=1.0)), {"joint": "Slider", "to": 0.5}),
        ("asm_pose", "inside its limits", prep(*duo, limited), {"joint": "Revolute", "to": 15}),
        ("asm_pose", "an axis that cannot be read", prep(*duo, joint("Revolute", "Base.Edge1", "Lid.Edge1")), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "a reference that is gone", prep(*duo, joint("Revolute", "Base.Face1", None), no_frames=True), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "posed, it does not solve", prep(*duo, hinge, solve=-1), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "the solver moves it back", prep(*duo, hinge, solve_puts={"Lid": [0, 0, 0, 0]}), {"joint": "Revolute", "to": 30}),
        ("asm_pose", "a slider the solver moves back", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1"), solve_puts={"Lid": [0, 0, 1]}), {"joint": "Slider", "to": 6}),
        ("asm_pose", "into the base", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1")), {"joint": "Slider", "to": -4}),
        ("asm_pose", "into the base, allowed", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1")), {"joint": "Slider", "to": -4, "allowOverlap": True}),
        ("asm_pose", "crash: to not a number", prep(*duo, hinge), {"joint": "Revolute", "to": "open"}),
        # ---- asm_limits ----
        ("asm_limits", "a hinge's", prep(*duo, hinge), {"joint": "Revolute", "min": -30, "max": 60}),
        ("asm_limits", "one cleared, one left", prep(*duo, limited), {"joint": "Revolute", "min": None, "assembly": "Assembly"}),
        ("asm_limits", "a slider's upper end", prep(*duo, joint("Slider", "Base.Face1", "Lid.Face1")), {"joint": "Slider", "max": 12.5}),
        ("asm_limits", "a cylindrical's angle", prep(*duo, joint("Cylindrical", "Base.Face1", "Lid.Face1")), {"joint": "Cylindrical", "turn": True, "min": 0, "max": 90}),
        ("asm_limits", "read only", prep(*duo, rail), {"joint": "Slider"}),
        ("asm_limits", "min over max", prep(*duo, limited), {"joint": "Revolute", "min": 30}),
        ("asm_limits", "a FreeCAD with no limits", prep(*duo, hinge, no_limits=True), {"joint": "Revolute", "max": 60}),
        ("asm_limits", "a fixed joint", prep(*duo, joint("Fixed", "Base.Face1", "Lid.Face2")), {"joint": "Fixed", "max": 60}),
        ("asm_limits", "a joint not there", prep(*duo), {"joint": "Nope"}),
        ("asm_limits", "it no longer solves", prep(*duo, hinge, solve=-1), {"joint": "Revolute", "min": 10, "max": 60}),
        ("asm_limits", "crash: max not a number", prep(*duo, hinge), {"joint": "Revolute", "max": "wide"}),
        # ---- asm_explode ----
        ("asm_explode", "from the middle, FreeCAD's view", prep(*trio, hinge), {}),
        ("asm_explode", "a factor, parts named", prep(*trio, hinge), {"factor": 3, "parts": ["Pin"], "assembly": "Assembly"}),
        ("asm_explode", "along z, grounded below", prep(*trio, hinge), {"axis": "z"}),
        ("asm_explode", "along a vector with a gap, nothing grounded", prep(base, lid, pin, asm(parts=("Base", "Lid", "Pin"), ground=None)), {"axis": [1, 0, 0], "gap": 7}),
        ("asm_explode", "a part on the centre goes up", prep(base, lid, asm(parts=("Base", "Lid"), ground=None)), {"parts": ["Base"], "factor": 2}),
        ("asm_explode", "a FreeCAD with no exploded views", prep(*trio, hinge, missing=("CommandCreateView",)), {}),
        ("asm_explode", "a view that will not explode", prep(*trio, hinge, fail=("saveAssemblyAndExplode",)), {}),
        ("asm_explode", "a step that does not move its part", prep(*trio, hinge, explode_stuck=("Pin",)), {}),
        ("asm_explode", "joints the older way", prep(*trio, joint("Revolute", "Base.Face1", "Lid.Face1"), old_suppress=True), {"axis": "y"}),
        ("asm_explode", "collapse", prep(*duo, hinge, exploded), {"collapse": True}),
        ("asm_explode", "collapse what is not exploded", prep(*duo, hinge), {"collapse": True}),
        ("asm_explode", "exploded already", prep(*duo, hinge, exploded), {}),
        ("asm_explode", "everything grounded", prep(base, asm(parts=("Base",))), {}),
        ("asm_explode", "no factor at all", prep(*trio), {"factor": 1}),
        ("asm_explode", "too far", prep(*trio), {"factor": 11}),
        ("asm_explode", "an axis of nothing", prep(*trio), {"axis": [0, 0, 0]}),
        ("asm_explode", "a part not in it", prep(*trio), {"parts": ["Nope"]}),
        ("asm_explode", "crash: an axis that is no axis", prep(*trio), {"axis": "up"}),
        # ---- asm_sub ----
        ("asm_sub", "rigid", prep(*three, asm(), second), {"assembly": "Assembly", "sub": "Other"}),
        ("asm_sub", "flexible, named", prep(*three, asm(), second), {"assembly": "Assembly", "sub": "Other", "rigid": False, "name": "Pin unit"}),
        ("asm_sub", "a FreeCAD with plain links", prep(*three, asm(), second, no_types=("Assembly::AssemblyLink",)), {"assembly": "Assembly", "sub": "Other"}),
        ("asm_sub", "plain links cannot be flexible", prep(*three, asm(), second, no_types=("Assembly::AssemblyLink",)), {"assembly": "Assembly", "sub": "Other", "rigid": False}),
        ("asm_sub", "into itself", prep(*three, asm(), second), {"assembly": "Assembly", "sub": "Assembly"}),
        ("asm_sub", "into one it already holds", prep(*three, asm(), second, holds_first), {"assembly": "Assembly", "sub": "Other"}),
        ("asm_sub", "a sub not there", prep(*three, asm(), second), {"assembly": "Assembly", "sub": "Nope"}),
        ("asm_sub", "unsolved after", prep(*three, asm(), second, solve=-1), {"assembly": "Assembly", "sub": "Other"}),
        # ---- asm_bom ----
        ("asm_bom", "FreeCAD's own, materials recorded", prep(*duo, materials), {}),
        ("asm_bom", "more columns, named, a nested part", prep(*three, asm(), materials, bom_extra=("Pin", "Ghost")), {"columns": ["File Name", ".Label2", 7, "Material"], "name": "Parts list", "assembly": "Assembly"}),
        ("asm_bom", "a second one", prep(*duo, materials, lambda s: fc.into(fc.doc().getObject("Assembly"), fc.an_object("Assembly::BomGroup", "Bills_of_Materials"))), {}),
        ("asm_bom", "a FreeCAD with no BOM object", prep(*duo, materials, no_types=("Assembly::BomGroup",)), {}),
        ("asm_bom", "a BOM group but no BOM object", prep(*duo, no_types=("Assembly::BomObject",)), {"name": "Plain"}),
        ("asm_bom", "no assembly", prep(*two), {}),
    ]
    return out
