# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datapart2_data.py runs through the old handler and the
# new data entry of each converted Part tool of families/model_more.py and
# part_more.py, on the stand-in FreeCAD (tests/_datapart2_standin.py): its
# normal paths and each of its refusals.
import json
import os

# The family files whose tools were converted.
FILES = ("model_more", "part_more")
# Each converted tool and its group (both files are of the group "model").
CONVERTED = {k: "model" for k in ("part_wire", "part_split", "part_compound", "part_refine", "part_attach", "part_face", "part_ruled", "part_project", "part_slices", "part_from_mesh",
                                  "part_section", "part_offset2d", "part_extract", "part_defeature", "part_fix", "part_datum")}
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("part_wire", "a helix, tapered, left-handed"): {"object": "Spring", "type": "Helix", "closed": False, "box": [10.0, 10.0, 20.0], "step": 1},
    ("part_wire", "a bspline closed"): {"object": "Loop", "closed": True, "fit": {"maxDistance": 0.001}},
    ("part_wire", "a helix FreeCAD refuses"): ["refused", "failed", "FreeCAD refused it: Angle of helix too steep — nothing was kept."],
    ("part_wire", "a helix of too many turns"): ["refused", "invalid_input", "height / pitch is 20000 turns: FreeCAD's helix takes 10000 at most — a larger pitch or a lower height."],
    ("part_split", "a slice exploded, named"): {"object": "Half", "mode": "slice", "pieces": 2, "bodies": ["Half 1", "Half 2"], "next": None},
    ("part_split", "a slice that cut nothing"): {"pieces": 1, "note": "Not cut: still 1 piece(s) — the tools do not pass right through Block (a plane must reach past the body on every side).",
                                                 "next": "explode: true (or part_compound { explode }) makes each piece a body of its own."},
    ("part_split", "a slice by a face"): ["refused", "invalid_input", "tools: 'Pin.Face1' is an element — whole objects by name here. part_extract { refs: [\"Pin.Face1\"] } copies a face out as an object that can cut; "
                                          "part_wire { kind: \"plane\" } makes a plane."],
    ("part_compound", "explode"): {"from": "Pieces", "bodies": ["Pieces 1", "Pieces 2"], "step": 1},
    ("part_compound", "three, named"): {"object": "Kit of parts", "type": "Compound", "solids": 3, "of": ["Block", "Pin", "Far"]},
    ("part_refine", "a PartDesign body's tip"): {"body": "Housing", "done": ["Refine turned on for Pad, the body's tip (it stays parametric)"], "sound": True, "step": 1},
    ("part_refine", "a fix that leaves two shells, made solid"): {"done": ["fixed", "closed shell made solid", "coplanar faces merged"]},
    ("part_attach", "to an edge, offset and turned"): {"body": "Peg", "attachedTo": "Block.Edge3", "mode": "NormalToEdge", "note": "It follows Block from now on."},
    ("part_attach", "mode unknown"): ["refused", "invalid_input", "mode 'Sideways': not a FreeCAD attachment mode. With one reference — a flat face: FlatFace; an edge: NormalToEdge, FrenetNB, Concentric (a circle or arc); "
                                      "a vertex: Translate; a whole object: ObjectXY, ObjectXZ, ObjectYZ. All: Deactivated, Translate, ObjectXY, ObjectXZ, ObjectYZ, FlatFace, NormalToEdge, FrenetNB, Concentric, TwoPointLine, "
                                      "AxisOfCurvature, AxisOfInertia1, ObjectZ, Vertex, CenterOfCurvature, CenterOfMass."],
    ("part_face", "an outline and a hole, named"): {"object": "Plate", "wires": 2, "faces": 1, "area": 100.0},
    ("part_face", "open"): ["refused", "invalid_input", "from: 1 of the 2 wires are open — every wire must be closed (part_wire { closed: true }; a sketch's open ends joined)."],
    ("part_ruled", "an edge of a body and a wire, reversed, named"): {"object": "Sail", "type": "RuledSurface", "note": "A surface, not a solid: surface_thicken gives it thickness."},
    ("part_project", "one of two missed"): {"object": "Two on face", "onto": "Block.Face6", "how": "along [0.0, 0.0, -1.0]", "missed": "1 wire(s) did not land on the face"},
    ("part_project", "along the normals, named"): {"object": "Trace", "how": "along the face's normals", "missed": None},
    ("part_slices", "at distances, one outside"): {"object": "Block slices", "range": [0.0, 10.0], "slices": [{"at": 2.0, "wires": 1, "length": 14.142, "area": 100.0}, {"at": 5.5, "wires": 1, "length": 14.142, "area": 100.0},
                                                                                                           {"at": 40.0, "wires": 0, "length": 0, "area": 0.0}]},
    ("part_slices", "none met"): ["refused", "failed", "No slice met Block along [0.0, 0.0, 1.0] at those distances: the body runs from 0 to 10 mm along that normal (measured from the origin). at inside that range, or count. Nothing was added."],
    ("part_from_mesh", "several shells"): {"object": "Scan solid", "triangles": 12, "sound": True,
                                           "note": "The mesh sewed into 3 separate shells: only the largest (12 of 12 triangles) was made the solid — split the mesh first (meshobj_split) and convert each piece. "
                                                   "Flat triangles merged where they lie in one plane (refine); curved areas stay faceted — for a clean model, fit features instead."},
    ("part_from_mesh", "a file not there"): ["refused", "not_found", "<out>/gone.stl: no such file."],
    ("part_section", "two bodies and the face"): {"section": "Block section", "edges": 4, "closedLoops": 1, "face": "Block section face", "area_mm2": 100.0},
    ("part_section", "bodies apart"): ["refused", "invalid_state", "Block and Far do not meet: no section curves (measure gives the gap between them; part_transform moves one). Nothing was added."],
    ("part_section", "a plane that misses"): ["refused", "invalid_state", "The plane misses Block: no section. Its box runs [0.0, 0.0, 0.0] to [10.0, 10.0, 10.0] — plane.at inside it. Nothing was added."],
    ("part_offset2d", "a closed wire, the band out, named"): {"offset": "Gasket", "faces": 2, "note": "a plain shape (a closed wire's offset is taken through its face)"},
    ("part_offset2d", "a face"): {"offset": "Plate offset", "area_mm2": 101.5, "note": None},
    ("part_extract", "a solid, named"): {"shape": "Rebuilt", "build": "solid", "solids": 1, "volume_mm3": 500.0, "valid": True},
    ("part_extract", "a solid with a gap"): ["refused", "invalid_state", "The 1 faces leave a gap: a solid needs a closed shell, and tolerance 0.5 mm did not close it — every face of the solid in refs, or a larger tolerance; "
                                             "build: \"shell\" keeps the open shell to look at. Nothing was added."],
    ("part_defeature", "a hole taken away"): {"body": "Block", "facesBefore": 6, "facesAfter": 4, "volumeBefore_mm3": 1000.0, "volume_mm3": 1010.0},
    ("part_fix", "reversed in place"): {"body": "Block", "op": "reverse", "volume_mm3": -1000.0, "notes": ["a solid turned inside out has a negative volume — reverse it back if that was not the aim"]},
    ("part_fix", "sewn at a tolerance, named"): {"body": "Sewn", "op": "sew", "closed": True, "notes": ["sewn at 0.2 mm"]},
    ("part_datum", "a line on a circle's axis"): {"datum": "Datum line", "kind": "line", "type": "Part::DatumLine", "made": "datum", "mode": "AxisOfCurvature", "notes": None},
    ("part_datum", "a FreeCAD with no datums: a plane, attached"): {"type": "Part::FeaturePython", "made": "shape", "mode": "FlatFace"},
    ("part_datum", "left unattached"): {"mode": "Deactivated", "notes": ["left unattached"]},
}
# Refusals written in the data that no case here reaches: none.
# The skeleton workflow's refusals (20 Nov: refs, offset, the container): the handler at BASE had no such input,
# so no case here can compare them; tests/test_datum_skeleton.py reaches each.
UNREACHED = [
    'part_datum: to or refs, not both: to is one reference, refs is a list of one to fo',
    'part_datum: body or part, not both: the datum goes in one container.',
    'part_datum: offset: { at: [x,y,z], rotate: { axis, angle } }.',
    'part_datum: {box.Label} cannot hold a plain shape, and this FreeCAD has no datum o',
    "part_datum: The {kind} datum would not attach to {', '.join(att['refs'])} as {att[",
]

SQ = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]]


def cases(fc, tmp, old, new):
    def prep(*fns, **flags):
        def prepare(s):
            fc.fc.GuiUp = False
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    def window(s):
        fc.fc.GuiUp = True

    def block(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)))

    def pin(s):
        fc.body("Pin", fc.solid("pin", (5, 5, 5), (15, 15, 15)))

    def far(s):
        fc.body("Far", fc.solid("far", (100, 100, 100), (110, 110, 110)))

    def pieces(s):
        fc.body("Pieces", fc.solid("pieces", (0, 0, 0), (10, 10, 10), solids=2, kind="Compound"))

    def sketch(s):
        fc.body("Sketch", fc.wire("sketch outline", SQ), type_="Sketcher::SketchObject", name="Sketch")

    def hole(s):
        fc.body("Hole", fc.wire("hole outline", [[2, 2, 0], [4, 2, 0], [4, 4, 0]]), name="Hole")

    def open_sketch(s):
        fc.body("Open", fc.wire("open line", SQ[:3], closed=False), type_="Sketcher::SketchObject", name="Open")

    def loose(s):
        fc.body("Loose", fc.wire("loose edges", SQ, kind="Compound", wires=0), name="Loose")

    def two_wires(s):
        fc.body("Two", fc.wire("two outlines", SQ, kind="Compound", wires=2), name="Two")

    def path(s):
        fc.body("Path", fc.wire("path line", [(0, 0, 0), (0, 0, 50)], closed=False), name="Path")

    def bare(s):
        fc.body("Bare", fc.solid("bare", (0, 0, 0), (1, 1, 1), edges=0, faces=0, solids=0, kind="Compound"), name="Bare")

    def cutter(s):
        fc.body("Cutter", fc.face("cutter plane", [(-5, -5, 5), (15, 15, 5)], area=400.0), type_="Part::Plane", name="Plane")

    def peg(s):
        o = fc.doc().new("Part::Cylinder", "Cylinder", Shape=fc.solid("peg", (0, 0, 0), (2, 2, 8)), **fc.attachable())
        o.__dict__["Label"] = "Peg"

    def pd_body(s):
        tip = fc.doc().new("PartDesign::Pad", "Pad", Refine=False)
        fc.body("Housing", fc.solid("housing", (0, 0, 0), (10, 10, 10), faces=9), type_="PartDesign::Body", name="PDBody", Tip=tip)

    def pd_body_worse(s):  # 7a8477d: the tip's Refine halves the body (as a bad refine of a boolean's faces)
        tip = fc.doc().new("PartDesign::Pad", "Pad", Refine=False)
        good = fc.solid("housing", (0, 0, 0), (10, 10, 10), faces=9)
        worse = fc.solid("refined housing", (0, 0, 0), (10, 10, 10), volume=500.0, faces=6)
        fc.body("Housing", good, type_="PartDesign::Body", name="PDBody", Tip=tip, computes=lambda o: worse if tip.Refine else good)

    def mesh(n=12):
        def add(s):
            o = fc.doc().new("Mesh::Feature", "Mesh", Mesh=fc.MeshData(facets=n))
            o.__dict__["Label"] = "Scan"
        return add

    def a_file(name, text=""):
        def add(s):
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        return add

    none = prep()

    T = "part_wire"
    yield T, "a line", none, {"kind": "line", "from": [0, 0, 0], "to": [10, 0, 5]}
    yield T, "a line of no length", none, {"kind": "line", "from": [1, 2, 3], "to": [1, 2, 3]}
    yield T, "a line with no from", none, {"kind": "line", "to": [1, 2, 3]}
    yield T, "a circle placed, named", none, {"kind": "circle", "radius": 4, "at": [1, 2, 3], "normal": [1, 0, 0], "name": "Ring"}
    yield T, "a circle of radius 0", none, {"kind": "circle", "radius": 0}
    yield T, "a circle's radius not a number", none, {"kind": "circle", "radius": "big"}
    yield T, "an arc", none, {"kind": "arc", "radius": 4, "start": 300, "end": 60}
    yield T, "an arc as it comes", none, {"kind": "arc", "radius": 4}
    yield T, "an arc out of range", none, {"kind": "arc", "radius": 4, "start": -10, "end": 60}
    yield T, "an arc of nothing", none, {"kind": "arc", "radius": 4, "start": 30, "end": 30}
    yield T, "an ellipse", none, {"kind": "ellipse", "major": 20, "minor": 10}
    yield T, "an ellipse the wrong way", none, {"kind": "ellipse", "major": 5, "minor": 10}
    yield T, "an ellipse of no width", none, {"kind": "ellipse", "major": 5, "minor": 0}
    yield T, "a polygon", none, {"kind": "polygon", "sides": 5, "radius": 8}
    yield T, "a polygon as it comes", none, {"kind": "polygon", "radius": 8}
    yield T, "a polygon given points", none, {"kind": "polygon", "points": SQ}
    yield T, "a polygon of two sides", none, {"kind": "polygon", "sides": 2, "radius": 3}
    yield T, "a polygon of no radius", none, {"kind": "polygon", "radius": 0}
    yield T, "a helix, tapered, left-handed", none, {"kind": "helix", "pitch": 2, "height": 20, "radius": 5, "taper": 10, "leftHanded": True, "name": "Spring"}
    yield T, "a helix", none, {"kind": "helix", "pitch": 2, "height": 20, "radius": 5}
    yield T, "a helix of no pitch", none, {"kind": "helix", "pitch": 0, "height": 20, "radius": 5}
    yield T, "a helix of no height", none, {"kind": "helix", "pitch": 2, "height": -1, "radius": 5}
    yield T, "a helix of no radius", none, {"kind": "helix", "pitch": 2, "height": 20, "radius": 0}
    yield T, "a helix of too many turns", none, {"kind": "helix", "pitch": 0.001, "height": 20, "radius": 5}
    yield T, "a helix tapered flat", none, {"kind": "helix", "pitch": 2, "height": 20, "radius": 5, "taper": 95}
    yield T, "a helix FreeCAD refuses", prep(invalid_types=("Part::Helix",), status="Angle of helix too steep"), {"kind": "helix", "pitch": 2, "height": 20, "radius": 5}
    yield T, "a spiral", none, {"kind": "spiral", "growth": 2, "turns": 3}
    yield T, "a spiral from a radius", none, {"kind": "spiral", "growth": 0, "turns": 1.5, "radius": 4}
    yield T, "a spiral shrinking", none, {"kind": "spiral", "growth": -1, "turns": 3}
    yield T, "a spiral of no turns", none, {"kind": "spiral", "growth": 1, "turns": 0}
    yield T, "a spiral from under 0", none, {"kind": "spiral", "growth": 1, "turns": 2, "radius": -1}
    yield T, "a plane", none, {"kind": "plane", "length": 30, "width": 20, "at": [0, 0, 5]}
    yield T, "a plane of no length", none, {"kind": "plane", "length": 0, "width": 20}
    yield T, "a plane of no width", none, {"kind": "plane", "length": 30, "width": 0}
    yield T, "a polyline", none, {"kind": "polyline", "points": SQ[:3]}
    yield T, "a polyline closed", none, {"kind": "polyline", "points": SQ, "closed": True, "name": "Outline"}
    yield T, "a polyline given closed", none, {"kind": "polyline", "points": SQ + [SQ[0]]}
    yield T, "a polyline of one point", none, {"kind": "polyline", "points": [[0, 0, 0]]}
    yield T, "a polyline closed of two", none, {"kind": "polyline", "points": SQ[:2], "closed": True}
    yield T, "a polyline with no points", none, {"kind": "polyline"}
    yield T, "a polyline with a corner twice", none, {"kind": "polyline", "points": [SQ[0], SQ[1], SQ[1], SQ[2]]}
    yield T, "a polyline with a corner that is no point", none, {"kind": "polyline", "points": [SQ[0], "there"]}
    yield T, "a polyline from a file", prep(a_file("pts.json", json.dumps(SQ))), {"kind": "polyline", "points_file": "pts.json", "closed": True}
    yield T, "a polyline from a file by key", prep(a_file("sets.json", json.dumps({"inner": SQ[:3], "outer": SQ}))), {"kind": "polyline", "points_file": "sets.json", "key": "outer"}
    yield T, "a file of two outlines", prep(a_file("sets.json", json.dumps({"inner": SQ[:3], "outer": SQ}))), {"kind": "polyline", "points_file": "sets.json"}
    yield T, "points and a file", prep(a_file("pts.json", json.dumps(SQ))), {"kind": "polyline", "points_file": "pts.json", "points": SQ}
    yield T, "a file that is no path", none, {"kind": "bspline", "points_file": "  "}
    yield T, "a file that is a number", none, {"kind": "polyline", "points_file": 7}
    yield T, "a bspline", none, {"kind": "bspline", "points": SQ}
    yield T, "a bspline closed", none, {"kind": "bspline", "points": SQ, "closed": True, "name": "Loop"}
    yield T, "a bspline given closed", none, {"kind": "bspline", "points": SQ + [SQ[0]]}
    yield T, "a bspline of three, ends alike", none, {"kind": "bspline", "points": [SQ[0], SQ[1], SQ[0]]}
    yield T, "a bspline of one point", none, {"kind": "bspline", "points": [[1, 1, 1]]}
    yield T, "a bspline with a point twice", none, {"kind": "bspline", "points": [SQ[0], SQ[0], SQ[2]]}
    yield T, "a bspline FreeCAD cannot fit", prep(fail=("interpolate",)), {"kind": "bspline", "points": SQ}
    yield T, "a bspline that does not close", prep(open_wires=True), {"kind": "bspline", "points": SQ, "closed": True}
    yield T, "a bspline from a file", prep(a_file("pts.csv", "0,0,0\n10,0,0\n10,10,0\n")), {"kind": "bspline", "points_file": "pts.csv"}
    yield T, "kind wrong", none, {"kind": "square"}
    yield T, "kind left out", none, {}
    yield T, "kind a list", none, {"kind": ["line"], "name": "X"}
    yield T, "crash: kind a number", none, {"kind": 5}
    yield T, "a name taken", prep(block), {"kind": "circle", "radius": 2, "name": "Block"}

    T = "part_split"
    yield T, "a slice", prep(block, cutter), {"bodies": ["Block"], "tools": ["Cutter"]}
    yield T, "a slice in the window, named, not split", prep(block, cutter, window), {"mode": "slice", "bodies": ["Block"], "tools": ["Cutter"], "split": False, "name": "Two halves"}
    yield T, "a slice exploded", prep(block, cutter), {"bodies": ["Block"], "tools": ["Cutter"], "explode": True}
    yield T, "a slice exploded, named", prep(block, cutter), {"bodies": ["Block"], "tools": ["Cutter"], "explode": True, "name": "Half"}
    yield T, "a slice that cut nothing", prep(block, cutter, pieces=1), {"bodies": ["Block"], "tools": ["Cutter"]}
    yield T, "a slice of two bodies", prep(block, pin, cutter), {"bodies": ["Block", "Pin"], "tools": ["Cutter"]}
    yield T, "a slice of none", prep(block, cutter), {"bodies": [], "tools": ["Cutter"]}
    yield T, "a slice with no tools", prep(block), {"bodies": ["Block"]}
    yield T, "a slice by a face", prep(block, pin), {"bodies": ["Block"], "tools": ["Pin.Face1"]}
    yield T, "a face of a body", prep(block, pin), {"bodies": ["Block.Face2"], "tools": ["Pin"]}
    yield T, "a body not here", prep(block), {"bodies": ["Nothing"], "tools": ["Block"]}
    yield T, "fragments", prep(block, pin), {"mode": "fragments", "bodies": ["Block", "Pin"]}
    yield T, "fragments in the window, not split, named", prep(block, pin, window), {"mode": "fragments", "bodies": ["Block", "Pin"], "split": False, "name": "Bits"}
    yield T, "fragments of one", prep(block), {"mode": "fragments", "bodies": ["Block"]}
    yield T, "xor", prep(block, pin), {"mode": "xor", "bodies": ["Block", "Pin"], "explode": True}
    yield T, "xor in the window", prep(block, pin, window), {"mode": "xor", "bodies": ["Block", "Pin"]}
    yield T, "xor of one", prep(block), {"mode": "xor", "bodies": ["Block"]}
    yield T, "mode wrong", prep(block), {"mode": "halve", "bodies": ["Block"]}
    yield T, "mode a list", prep(block), {"mode": ["slice"], "bodies": ["Block"]}
    yield T, "nothing made", prep(block, cutter, split="null"), {"bodies": ["Block"], "tools": ["Cutter"]}
    yield T, "not valid", prep(block, pin, invalid_types=("Part::FeaturePython",), status="Tools do not cross"), {"mode": "fragments", "bodies": ["Block", "Pin"]}
    yield T, "crash: no BOPTools", prep(block, cutter, missing=("BOPTools",)), {"bodies": ["Block"], "tools": ["Cutter"]}

    T = "part_compound"
    yield T, "two bodies", prep(block, pin), {"bodies": ["Block", "Pin"]}
    yield T, "three, named", prep(block, pin, far), {"bodies": ["Block", "Pin", "Far"], "name": "Kit of parts"}
    yield T, "one body", prep(block), {"bodies": ["Block"]}
    yield T, "nothing", prep(block), {}
    yield T, "a body not here", prep(block), {"bodies": ["Block", "Gone"]}
    yield T, "explode", prep(pieces), {"explode": "Pieces"}
    yield T, "explode, named", prep(pieces), {"explode": "Pieces", "name": "Part"}
    yield T, "explode one solid", prep(block), {"explode": "Block"}
    yield T, "a compound FreeCAD refuses", prep(block, pin, invalid_types=("Part::Compound",)), {"bodies": ["Block", "Pin"]}

    T = "part_refine"
    yield T, "a body", prep(block), {"body": "Block"}
    yield T, "the only body, named", prep(block), {"name": "Clean"}
    yield T, "fixed first", prep(block), {"body": "Block", "fix": True, "tolerance": 0.01}
    yield T, "a fix that fails", prep(block, fail=("fix",)), {"body": "Block", "fix": True}
    yield T, "a fix that leaves a shell, made solid", prep(block, fix_opens=1), {"body": "Block", "fix": True}
    yield T, "a fix that leaves two shells, made solid", prep(block, fix_opens=2), {"body": "Block", "fix": True}
    yield T, "a fix that leaves a shell no solid comes from", prep(block, fix_opens=1, fail=("Solid",)), {"body": "Block", "fix": True}
    yield T, "not sound after", prep(pieces), {"body": "Pieces"}
    yield T, "a PartDesign body's tip", prep(pd_body), {"body": "Housing"}
    yield T, "a PartDesign body's tip, not sound", prep(pd_body, objects_invalid=True, bool_invalid=True), {"body": "Housing"}
    yield T, "a PartDesign body's tip, made worse", prep(pd_body_worse), {"body": "Housing"}
    yield T, "a PartDesign body, named", prep(pd_body), {"body": "Housing", "name": "Plain"}
    yield T, "a PartDesign body, fixed", prep(pd_body), {"body": "Housing", "fix": True}
    yield T, "no body", none, {}
    yield T, "crash: refine fails", prep(block, fail=("removeSplitter",)), {"body": "Block"}

    T = "part_attach"
    yield T, "to a face", prep(block, peg), {"body": "Peg", "to": "Block.Face6"}
    yield T, "to an edge, offset and turned", prep(block, peg), {"body": "Peg", "to": "Block.Edge3", "offset": [1, 2, 3], "rotate": 45}
    yield T, "to a vertex", prep(path, peg), {"body": "Peg", "to": "Path.Vertex1"}
    yield T, "to a whole object", prep(block, peg), {"body": "Peg", "to": "Block"}
    yield T, "mode given", prep(block, peg), {"body": "Peg", "to": "Block.Edge1", "mode": "Concentric"}
    yield T, "mode unknown", prep(block, peg), {"body": "Peg", "to": "Block.Edge1", "mode": "Sideways"}
    yield T, "an older FreeCAD's Support", prep(block, peg, old_support=True), {"body": "Peg", "to": "Block.Face1"}
    yield T, "a FreeCAD that lists no modes", prep(block, peg, map_modes=[]), {"body": "Peg", "to": "Block"}
    yield T, "a plain shape", prep(block, pin), {"body": "Pin", "to": "Block.Face6"}
    yield T, "to left out", prep(block, peg), {"body": "Peg"}
    yield T, "to with no object", prep(block, peg), {"body": "Peg", "to": "Face6"}
    yield T, "to itself", prep(block, peg), {"body": "Peg", "to": "Peg"}
    yield T, "to its own face", prep(block, peg), {"body": "Peg", "to": "Peg.Face1"}
    yield T, "to a face that is not there", prep(block, peg), {"body": "Peg", "to": "Block.Face60"}
    yield T, "it would not attach", prep(block, peg, invalid_types=("Part::Cylinder",), status="Attachment failed"), {"body": "Peg", "to": "Block.Face6"}
    yield T, "body not here", prep(block), {"body": "Peg", "to": "Block"}
    yield T, "offset wrong", prep(block, peg), {"body": "Peg", "to": "Block", "offset": [1]}

    T = "part_face"
    yield T, "a sketch", prep(sketch), {"from": ["Sketch"]}
    yield T, "an outline and a hole, named", prep(sketch, hole), {"from": ["Sketch", "Hole"], "name": "Plate"}
    yield T, "loose edges", prep(loose), {"from": ["Loose"]}
    yield T, "nothing", prep(sketch), {"from": []}
    yield T, "from left out", prep(sketch), {}
    yield T, "an object with no edge", prep(bare), {"from": ["Bare"]}
    yield T, "open", prep(sketch, open_sketch), {"from": ["Sketch", "Open"]}
    yield T, "no face", prep(sketch, fail=("makeFace",)), {"from": ["Sketch"]}
    yield T, "not here", prep(sketch), {"from": ["Gone"]}

    T = "part_ruled"
    yield T, "two wires", prep(sketch, path), {"a": "Sketch", "b": "Path"}
    yield T, "an edge of a body and a wire, reversed, named", prep(block, path), {"a": "Block.Edge3", "b": "Path", "reversed": True, "name": "Sail"}
    yield T, "a left out", prep(path), {"b": "Path"}
    yield T, "b not a name", prep(path), {"a": "Path", "b": 3}
    yield T, "no edge", prep(bare, path), {"a": "Bare", "b": "Path"}
    yield T, "an edge with no object", prep(block, path), {"a": "Path", "b": "Edge3"}
    yield T, "a face", prep(block, path), {"a": "Block.Face1", "b": "Path"}
    yield T, "an edge that is not there", prep(block, path), {"a": "Block.Edge99", "b": "Path"}
    yield T, "a surface FreeCAD refuses", prep(sketch, path, invalid_types=("Part::RuledSurface",)), {"a": "Sketch", "b": "Path"}

    T = "part_project"
    yield T, "along a direction", prep(sketch, block), {"shape": "Sketch", "onto": "Block.Face6", "direction": [0, 0, -1]}
    yield T, "along the normals, named", prep(sketch, block), {"shape": "Sketch", "onto": "Block.Face6", "name": "Trace"}
    yield T, "loose edges", prep(loose, block), {"shape": "Loose", "onto": "Block.Face1"}
    yield T, "one of two missed", prep(two_wires, block, misses=("two outlines.Wire2",)), {"shape": "Two", "onto": "Block.Face6", "direction": "-z"}
    yield T, "all missed along a direction", prep(sketch, block, misses="all"), {"shape": "Sketch", "onto": "Block.Face6", "direction": [0, 0, 1]}
    yield T, "all missed along the normals", prep(sketch, block, misses="all"), {"shape": "Sketch", "onto": "Block.Face6"}
    yield T, "OCC fails", prep(sketch, block, fail=("project",)), {"shape": "Sketch", "onto": "Block.Face6"}
    yield T, "onto a whole body", prep(sketch, block), {"shape": "Sketch", "onto": "Block"}
    yield T, "onto left out", prep(sketch, block), {"shape": "Sketch"}
    yield T, "nothing to project", prep(bare, block), {"shape": "Bare", "onto": "Block.Face6"}
    yield T, "direction of no length", prep(sketch, block), {"shape": "Sketch", "onto": "Block.Face6", "direction": [0, 0, 0]}
    yield T, "shape not here", prep(block), {"shape": "Sketch", "onto": "Block.Face6"}

    T = "part_slices"
    yield T, "five as it comes", prep(block), {}
    yield T, "three along x, named", prep(block), {"body": "Block", "normal": [1, 0, 0], "count": 3, "name": "Ribs"}
    yield T, "at distances, one outside", prep(block), {"body": "Block", "at": [2, 5.5, 40]}
    yield T, "along a slanted normal", prep(block), {"body": "Block", "normal": [1, -1, 0], "count": 2}
    yield T, "open outlines", prep(block, slice_closed=False), {"body": "Block", "count": 1}
    yield T, "two loops a slice", prep(block, slice_loops=2), {"body": "Block", "count": 2}
    yield T, "loops no face comes from", prep(block, slice_loops=2, fail=("makeFace",)), {"body": "Block", "count": 1}
    yield T, "at empty", prep(block), {"body": "Block", "at": []}
    yield T, "at too many", prep(block), {"body": "Block", "at": [1] * 501}
    yield T, "at not numbers", prep(block), {"body": "Block", "at": [1, "two"]}
    yield T, "count 0", prep(block), {"body": "Block", "count": 0}
    yield T, "count too many", prep(block), {"body": "Block", "count": 501}
    yield T, "none met", prep(block), {"body": "Block", "at": [-5, 30]}
    yield T, "no body", none, {"count": 2}

    T = "part_from_mesh"
    yield T, "a mesh object", prep(mesh()), {"mesh": "Scan"}
    yield T, "a file, named, not refined", prep(a_file("scan.stl")), {"file": "scan.stl", "name": "Casting", "refine": False, "tolerance": 0.1}
    yield T, "a file as it comes", prep(a_file("scan.stl")), {"file": "scan.stl"}
    yield T, "a file not there", none, {"file": "gone.stl"}
    yield T, "neither", prep(mesh()), {}
    yield T, "not a mesh", prep(block), {"mesh": "Block"}
    yield T, "mesh not here", prep(block), {"mesh": "Scan"}
    yield T, "too many triangles", prep(mesh(200)), {"mesh": "Scan", "maxFacets": 100}
    yield T, "too few triangles", prep(mesh(3)), {"mesh": "Scan"}
    yield T, "tolerance 0", prep(mesh()), {"mesh": "Scan", "tolerance": 0}
    yield T, "tolerance not a number", prep(mesh()), {"mesh": "Scan", "tolerance": "fine"}
    yield T, "no faces from it", prep(mesh(), fail=("makeShapeFromMesh",)), {"mesh": "Scan"}
    yield T, "no solid from it", prep(mesh(), fail=("Solid",)), {"mesh": "Scan"}
    yield T, "several shells", prep(mesh(), mesh_shells=3), {"mesh": "Scan"}
    yield T, "no shell sewn", prep(mesh(), mesh_shells=0), {"mesh": "Scan"}
    yield T, "refine fails, kept", prep(mesh(), fail=("removeSplitter",)), {"mesh": "Scan"}
    yield T, "not sound", prep(mesh(), solid_volume=1.0, bool_invalid=True, objects_invalid=False), {"mesh": "Scan"}
    yield T, "crash: no Mesh module", prep(mesh(), missing=("Mesh",)), {"mesh": "Scan"}

    def plate(s):
        fc.body("Plate", fc.face("plate face", SQ, area=100.0), name="Plate")

    def open_body(s):
        fc.body("Skin", fc.solid("skin", (0, 0, 0), (10, 10, 10), closed=False, solids=0, kind="Shell"), name="Skin")

    def loose_faces(s):
        fc.body("Faces", fc.solid("faces", (0, 0, 0), (10, 10, 10), solids=0, shells=0, kind="Compound"), name="Faces")

    def two_shells(s):
        fc.body("Twin", fc.solid("twin", (0, 0, 0), (10, 10, 10), solids=0, shells=2, kind="Compound"), name="Twin")

    T = "part_section"
    yield T, "two bodies", prep(block, pin), {"body": "Block", "with": "Pin"}
    yield T, "two bodies, approximate, named", prep(block, pin), {"body": "Block", "with": "Pin", "approximate": True, "name": "Cut line"}
    yield T, "two bodies, a plain shape", prep(block, pin), {"body": "Block", "with": "Pin", "parametric": False}
    yield T, "two bodies and the face", prep(block, pin), {"body": "Block", "with": "Pin", "face": True}
    yield T, "a plane", prep(block), {"body": "Block", "plane": {"normal": [0, 0, 1], "at": [0, 0, 5]}}
    yield T, "a plane as it comes, the face, named", prep(block), {"body": "Block", "plane": {}, "face": True, "name": "Floor"}
    yield T, "a plane, no face from the curves", prep(block, fail=("makeFace",)), {"body": "Block", "plane": {"at": [0, 0, 5]}, "face": True}
    yield T, "a plane that misses", prep(block), {"body": "Block", "plane": {"normal": [0, 0, 1], "at": [0, 0, 100]}}
    yield T, "bodies apart", prep(block, far), {"body": "Block", "with": "Far"}
    yield T, "bodies apart, a plain shape", prep(block, far), {"body": "Block", "with": "Far", "parametric": False}
    yield T, "neither with nor plane", prep(block), {"body": "Block"}
    yield T, "a plane's normal of no length", prep(block), {"body": "Block", "plane": {"normal": [0, 0, 0]}}
    yield T, "body not here", prep(block), {"body": "Gone", "with": "Block"}
    yield T, "with not here", prep(block), {"body": "Block", "with": "Gone"}

    T = "part_offset2d"
    yield T, "a closed wire, out", prep(sketch), {"shape": "Sketch", "distance": 2}
    yield T, "a closed wire, the band out, named", prep(sketch), {"shape": "Sketch", "distance": 2, "fill": True, "name": "Gasket"}
    yield T, "a closed wire, the band in, sharp", prep(sketch), {"shape": "Sketch", "distance": -1, "fill": True, "join": "intersection", "intersection": True}
    yield T, "a closed wire OCC refuses", prep(sketch, fail=("makeOffset2D",)), {"shape": "Sketch", "distance": -20}
    yield T, "a closed wire no face comes from", prep(sketch, fail=("makeFace",)), {"shape": "Sketch", "distance": 1}
    yield T, "a face", prep(plate), {"shape": "Plate", "distance": 1.5, "join": "tangent", "fill": True, "intersection": True}
    yield T, "an open wire, named", prep(open_sketch), {"shape": "Open", "distance": 1, "name": "Kerf"}
    yield T, "an open wire, a plain shape", prep(open_sketch), {"shape": "Open", "distance": 1, "parametric": False}
    yield T, "nothing left", prep(open_sketch, offset2d="null"), {"shape": "Open", "distance": -9}
    yield T, "distance left out", prep(sketch), {"shape": "Sketch"}
    yield T, "no wire or face", prep(bare), {"shape": "Bare", "distance": 1}
    yield T, "join wrong", prep(sketch), {"shape": "Sketch", "distance": 1, "join": "round"}
    yield T, "shape not here", prep(sketch), {"shape": "Gone", "distance": 1}
    yield T, "crash: distance not a number", prep(sketch), {"shape": "Sketch", "distance": "wide"}

    T = "part_extract"
    yield T, "a face copied", prep(block), {"refs": ["Block.Face3"]}
    yield T, "one ref as a string", prep(block), {"refs": "Block.Edge2", "name": "Rim"}
    yield T, "several copied, a whole object among them", prep(block, pin), {"refs": ["Block.Face3", "Block.Edge2", "Pin"], "build": "copy"}
    yield T, "a shell of a whole body", prep(block), {"refs": ["Block"], "build": "shell"}
    yield T, "a shell sewn", prep(block, shell_closed=False, sews=True), {"refs": ["Block.Face1", "Block.Face2"], "build": "shell", "tolerance": 0.1}
    yield T, "a shell fused where sewing leaves it open", prep(block, shell_closed=False), {"refs": ["Block.Face1", "Block.Face2"], "build": "shell"}
    yield T, "a shell left open", prep(block, shell_closed=False, fail=("multiFuse",)), {"refs": ["Block.Face1", "Block.Face2"], "build": "shell"}
    yield T, "a solid, named", prep(block), {"refs": ["Block"], "build": "solid", "name": "Rebuilt"}
    yield T, "a solid inside out", prep(block, solid_volume=-500.0), {"refs": ["Block"], "build": "solid"}
    yield T, "a solid with a gap", prep(block, shell_closed=False), {"refs": ["Block.Face1"], "build": "solid", "tolerance": 0.5}
    yield T, "a shell of no face", prep(path), {"refs": ["Path"], "build": "shell"}
    yield T, "a wire", prep(block), {"refs": ["Block.Edge1", "Block.Edge2"], "build": "wire"}
    yield T, "wires of two runs", prep(block, runs=2), {"refs": ["Block.Face1"], "build": "wire"}
    yield T, "a wire of no edge", prep(bare), {"refs": ["Bare"], "build": "wire"}
    yield T, "a face", prep(sketch), {"refs": ["Sketch"], "build": "face"}
    yield T, "a face of open edges", prep(open_sketch), {"refs": ["Open"], "build": "face"}
    yield T, "build wrong", prep(block), {"refs": ["Block"], "build": "mesh"}
    yield T, "build a list", prep(block), {"refs": ["Block"], "build": ["copy"]}
    yield T, "refs empty", prep(block), {"refs": []}
    yield T, "refs left out, a solid asked", prep(block), {"build": "solid"}
    yield T, "refs a number", prep(block), {"refs": 5}
    yield T, "a ref not here", prep(block), {"refs": ["Gone.Face1"]}

    T = "part_defeature"
    yield T, "a hole taken away", prep(block), {"body": "Block", "faces": ["Face3", "Block.Face4"]}
    yield T, "the only body, named", prep(block), {"faces": ["Face1"], "name": "Plain"}
    yield T, "faces left out", prep(block), {"body": "Block"}
    yield T, "not a face", prep(block), {"body": "Block", "faces": ["Face1", "Edge2"]}
    yield T, "a name where a face is meant", prep(block), {"body": "Block", "faces": ["Block"]}
    yield T, "a face that is not there", prep(block), {"body": "Block", "faces": ["Face77"]}
    yield T, "OCC refuses", prep(block, fail=("defeaturing",)), {"body": "Block", "faces": ["Face1"]}
    yield T, "left as it was", prep(block, defeature="same"), {"body": "Block", "faces": ["Face1"]}
    yield T, "nothing back", prep(block, defeature="null"), {"body": "Block", "faces": ["Face1"]}
    yield T, "no solid back", prep(block, defeature="no solid"), {"body": "Block", "faces": ["Face1"]}
    yield T, "no body", none, {"faces": ["Face1"]}

    T = "part_fix"
    yield T, "reversed in place", prep(block), {"body": "Block", "op": "reverse"}
    yield T, "reversed, named", prep(block), {"body": "Block", "op": "reverse", "name": "Inside out"}
    yield T, "a primitive reversed", prep(peg), {"body": "Peg", "op": "reverse"}
    yield T, "a surface reversed", prep(plate), {"body": "Plate", "op": "reverse"}
    yield T, "a solid of its shell", prep(block), {"body": "Block", "op": "solid"}
    yield T, "solids of two shells, named", prep(two_shells), {"body": "Twin", "op": "solid", "name": "Pair"}
    yield T, "a solid of loose faces", prep(loose_faces), {"body": "Faces", "op": "solid"}
    yield T, "a solid inside out, turned", prep(block, solid_volume=-500.0), {"body": "Block", "op": "solid"}
    yield T, "an open shell", prep(open_body), {"body": "Skin", "op": "solid"}
    yield T, "loose faces that make no shell", prep(loose_faces, fail=("makeShell",)), {"body": "Faces", "op": "solid"}
    yield T, "sewn", prep(open_body, sews=True), {"body": "Skin", "op": "sew"}
    yield T, "sewn at a tolerance, named", prep(loose_faces), {"body": "Faces", "op": "sew", "tolerance": 0.2, "name": "Sewn"}
    yield T, "sewn, the fix after failing", prep(open_body, fail=("fix",)), {"body": "Skin", "op": "sew"}
    yield T, "fixed", prep(block), {"body": "Block", "op": "fix"}
    yield T, "fixed at a tolerance", prep(open_body, fix_mends=True), {"body": "Skin", "op": "fix", "tolerance": 0.05}
    yield T, "crash: the fix fails", prep(block, fail=("fix",)), {"body": "Block", "op": "fix"}
    yield T, "op wrong", prep(block), {"body": "Block", "op": "mend"}
    yield T, "op left out", prep(block), {"body": "Block"}
    yield T, "op a list", prep(block), {"body": "Block", "op": ["fix"]}
    yield T, "body not here", prep(block), {"body": "Gone", "op": "fix"}

    T = "part_datum"
    no_part = ("Part::DatumPoint", "Part::DatumLine", "Part::DatumPlane", "Part::LocalCoordinateSystem")
    no_datums = no_part + ("PartDesign::Point", "PartDesign::Line", "PartDesign::Plane", "PartDesign::CoordinateSystem")
    yield T, "a plane as it comes", none, {}
    yield T, "a point placed, named", none, {"kind": "point", "at": [1, 2, 3], "name": "Origin of it"}
    yield T, "a line along a normal", none, {"kind": "line", "at": [0, 0, 5], "normal": [1, 0, 0]}
    yield T, "a plane turned by axis and angle", none, {"kind": "plane", "axis": [0, 1, 0], "angle": 30}
    yield T, "a csys with a normal (not used)", none, {"kind": "csys", "normal": [1, 0, 0]}
    yield T, "kind wrong", none, {"kind": "axis"}
    yield T, "crash: kind a list", none, {"kind": ["plane"]}
    yield T, "normal of no length", none, {"kind": "plane", "normal": [0, 0, 0]}
    yield T, "a plane on a face", prep(block), {"kind": "plane", "to": "Block.Face6", "at": [0, 0, 2]}
    yield T, "a plane on an edge", prep(block), {"to": "Block.Edge1"}
    yield T, "a csys on a vertex", prep(path), {"kind": "csys", "to": "Path.Vertex2"}
    yield T, "a plane on a vertex", prep(path), {"kind": "plane", "to": "Path.Vertex1"}
    yield T, "a csys on a face", prep(block), {"kind": "csys", "to": "Block.Face2"}
    yield T, "a csys on an edge", prep(block), {"kind": "csys", "to": "Block.Edge2"}
    yield T, "a plane on a whole object", prep(block), {"to": "Block"}
    yield T, "a point on a vertex", prep(path), {"kind": "point", "to": "Path.Vertex1"}
    yield T, "a point on a straight edge", prep(block), {"kind": "point", "to": "Block.Edge1"}
    yield T, "a point on a round edge", prep(block, round_edges=True), {"kind": "point", "to": "Block.Edge1"}
    yield T, "a point on a face", prep(block), {"kind": "point", "to": "Block.Face1"}
    yield T, "a line along a straight edge", prep(block), {"kind": "line", "to": "Block.Edge1"}
    yield T, "a line on a circle's axis", prep(block, round_edges=True), {"kind": "line", "to": "Block.Edge1"}
    yield T, "a line on a vertex", prep(path), {"kind": "line", "to": "Path.Vertex1"}
    yield T, "a line on a face", prep(block), {"kind": "line", "to": "Block.Face1"}
    yield T, "a line on a face, mode given", prep(block), {"kind": "line", "to": "Block.Face1", "mode": "AxisOfInertia1"}
    yield T, "mode Deactivated asked: by what to is", prep(block), {"kind": "plane", "to": "Block.Face1", "mode": "Deactivated"}
    yield T, "mode unknown", prep(block), {"kind": "plane", "to": "Block.Face1", "mode": "Sideways"}
    yield T, "PartDesign's where Part has none", prep(block, no_types=no_part), {"kind": "plane", "to": "Block.Face1"}
    yield T, "a FreeCAD with no datums: a point", prep(no_types=no_datums), {"kind": "point"}
    yield T, "a FreeCAD with no datums: a line", prep(no_types=no_datums), {"kind": "line", "normal": [0, 1, 0]}
    yield T, "a FreeCAD with no datums: a plane, attached", prep(block, no_types=no_datums), {"kind": "plane", "to": "Block.Face1"}
    yield T, "a FreeCAD with no datums: a csys", prep(no_types=no_datums), {"kind": "csys", "name": "Frame"}
    yield T, "a FreeCAD with no datums nor attachment", prep(block, no_types=no_datums, fail=("addExtension",)), {"kind": "plane", "to": "Block.Face1"}
    yield T, "a FreeCAD with no datums nor attachment, free", prep(no_types=no_datums, fail=("addExtension",)), {"kind": "plane"}
    yield T, "an older FreeCAD's Support", prep(block, old_support=True), {"kind": "plane", "to": "Block.Face1"}
    yield T, "left unattached", prep(block, detaches=True), {"kind": "plane", "to": "Block.Face1"}
    yield T, "it would not attach", prep(block, invalid_types=("Part::DatumPlane",), status="Attachment failed"), {"kind": "plane", "to": "Block.Face1"}
    yield T, "to not here", prep(block), {"kind": "plane", "to": "Gone.Face1"}
    yield T, "a name taken", prep(block), {"kind": "plane", "name": "Block"}
