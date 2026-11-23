# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datapd_data.py runs through the old handler and the new
# data entry of each converted Part Design and Sketcher tool, on the stand-in
# FreeCAD (tests/_datapd_standin.py): its normal paths and each of its
# refusals. "model call N" is call N of private records: models/partdesign-model.json
# ("sketcher call N": of sketcher-model.json), with the stand-in's furniture
# in place of the calls before it.

# Each converted tool and its group.
CONVERTED = {n: "feature" for n in ("pd_pad", "pd_pocket", "pd_revolution", "pd_groove", "pd_hole", "pd_fillet", "pd_chamfer", "pd_draft", "pd_thickness", "pd_mirrored",
                                    "pd_linear_pattern", "pd_polar_pattern", "pd_loft", "pd_pipe", "pd_datum_plane", "feature_list", "feature_edit", "feature_remove",
                                    "feature_suppress")}
CONVERTED.update({n: "std_more" for n in ("pd_move_feature", "pd_reorder", "pd_tip", "pd_shaft")})
CONVERTED.update({n: "sketch" for n in ("pd_body_new", "sketch_new", "sketch_add", "sketch_offset", "sketch_external", "sketch_constrain", "sketch_state", "sketch_edit")})
# Each Part Design or Sketcher tool of the three family files kept as code, and why: none (private records: datapd-findings.md).
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ('pd_pad', 'model call 8'): {'feature': 'Pad', 'volume': 5300.0, 'volumeChange': 5300.0, 'solids': 1, 'step': 1},
    ('pd_pad', 'type of the other tool'): ['refused', 'invalid_input', "type 'through_all': one of length, up_to_face, up_to_first, up_to_last — a pad has no through_all: up_to_last goes to the body's far side."],
    ('pd_pad', 'two sides up to first, old FreeCAD'): ['refused', 'unavailable', 'sides two with type UpToFirst: this FreeCAD (0.21.2) has two sides for type length only — sides symmetric, or two features.'],
    ('pd_pocket', 'model call 11'): {'feature': 'Pocket', 'volumeChange': -200.0},
    ('pd_pocket', 'no solid'): ['refused', 'invalid_state', 'Body has no solid to pocket: pd_pad (or pd_primitive) first.'],
    ('pd_pocket', 'it changes nothing'): ['refused', 'failed', 'Pocket cut nothing — the profile does not meet the body that way. Nothing was kept. Check the sketch with sketch_state (closed wires, no open vertices); reversed: true goes the other way into the body.'],
    ('pd_revolution', 'model call 65'): ['refused', 'invalid_input', 'sides \'two\': one or symmetric (the angle shared both ways). Two different angles: make it one-sided, then feature_edit { feature, set: { Type: "TwoAngles", Angle2: … } }.'],
    ('pd_groove', 'symmetric, reversed, about a construction line'): {'feature': 'Groove', 'volumeChange': -100.0, 'sketchDof': 2},
    ('pd_hole', 'model call 46'): ['refused', 'invalid_input', 'thread \'M6x7\': not an ISO metric size FreeCAD has — coarse by diameter ("M5"): M4x0.7, M5x0.8, M6x1.0, M8x1.25, M10x1.5, M12x1.75, M16x2.0, M20x2.5, M24x3.0, M30x3.5 …; fine pitches for M6: M6x0.75. Other standards (UNC, UNF, BSP …): make the hole by diameter, then feature_edit its ThreadType and ThreadSize.'],
    ('pd_hole', 'model call 47'): {'feature': 'Hole', 'holes': 3, 'diameter': 6.0, 'thread': 'M6x1.0 (cosmetic)', 'cut': {'type': 'Counterbore', 'diameter': 0.0, 'depth': 0.0}},
    ('pd_hole', 'no circles'): ['refused', 'invalid_input', "Lines has no circles or points: a hole is drilled at each circle's centre and at each point — sketch_add them (not as construction) on the face the holes enter."],
    ('pd_fillet', 'model call 28'): {'feature': 'Fillet', 'on': ['Edge1'], 'volumeChange': -5.0},
    ('pd_chamfer', 'size2 and angle'): ['refused', 'invalid_input', 'size2 or angle, not both: size2 is the second distance (two distances), angle goes with size (distance and angle).'],
    ('pd_draft', 'model call 36'): {'feature': 'Draft', 'on': ['Face1']},
    ('pd_thickness', 'it hollows nothing'): ['refused', 'failed', "Thickness removed no material — the wall did not hollow the body. Nothing was kept. A wall thicker than an inside fillet's radius or than a thin feature fails: thinner, or join: intersection; shell before filleting."],
    ('pd_mirrored', 'model call 43'): {'feature': 'Mirrored', 'repeated': 'the whole body (FreeCAD\'s TransformMode "Whole shape")'},
    ('pd_mirrored', 'the whole body, nothing to repeat'): ['refused', 'invalid_state', 'Body has no pad, pocket or other additive or subtractive feature to repeat.'],
    ('pd_linear_pattern', 'model call 26'): {'feature': 'LinearPattern', 'volumeChange': 100.0},
    ('pd_polar_pattern', 'angle zero'): ['refused', 'invalid_input', 'angle: degrees, over 0 up to 360 (360 spaces the copies evenly all round; less is first to last; reversed: true turns the other way).'],
    ('pd_loft', 'model call 83'): {'feature': 'Loft', 'type': 'AdditiveLoft', 'volumeChange': 250.0},
    ('pd_pipe', 'a path with no edges'): ['refused', 'invalid_input', 'path: Bare has no edges (construction geometry does not count): sketch_add a line, arc or polyline.'],
    ('pd_datum_plane', 'model call 29'): {'plane': 'Above', 'on': 'XY', 'origin': [0.0, 0.0, 0.0], 'normal': [0.0, 0.0, 1.0], 'next': 'sketch_new { plane: "Above" }', 'step': 1},
    ('feature_edit', 'model call 70'): ['refused', 'invalid_input', "Type = 'Nope': one of Angle, UpToLast, UpToFirst, UpToFace, TwoAngles."],
    ('feature_edit', "it renames a later one's edges, found again"): {'set': {'Length': 20}, 'refsFound': {'Fillet': 'relinked', 'Chamfer': 'relinked'}},
    ('feature_remove', 'model call 32'): ['refused', 'invalid_state', 'LinearPattern is used by Chamfer: feature_remove those first (the last made first). force: true removes it anyway, and is refused with nothing kept if one of them then fails.'],
    ('feature_remove', 'with its own sketch'): {'removed': ['Pocket', 'Own'], 'tip': 'NoProfile'},
    ('feature_suppress', 'model call 30'): {'feature': 'Fillet', 'suppressed': True, 'volumeChange': 5.0},
    ('pd_move_feature', 'model call 109'): {'moved': ['Island', 'Pad 3'], 'from': 'Hist', 'to': 'Hist2', 'tip': 'Pad 3'},
    ('pd_move_feature', 'it breaks what is left'): ['refused', 'invalid_state', 'Moving H1 to Hist2 breaks H1, H2 — nothing was moved. A pocket, hole or fillet needs the solid it works on: move the features before it first (the first pad first), or rebuild it in Hist2.'],
    ('pd_reorder', 'model call 103'): {'order': ['HistBase', 'H2', 'H1'], 'tip': 'H2', 'afterTip': ['H1'], 'tipMoved': None},
    ('pd_tip', 'model call 101'): {'tip': 'H1', 'tipWas': 'H2', 'afterTip': ['H2'], 'note': None},
    ('pd_tip', 'a datum with nothing before it'): ['refused', 'invalid_input', 'feature: Datum is a Plane with no solid feature before it — the tip is a pad, pocket or other solid feature: HistBase, H1, H2.'],
    ('pd_shaft', 'model call 112'): {'shaft': 'Shaft', 'length': 60.0, 'segments': 3, 'volume': 8953.539},
    ('pd_body_new', 'a name taken'): {'body': 'Body 2', 'step': 1},
    ('sketch_new', 'sketcher call 30'): {'sketch': 'PlateCopy', 'on': 'XY', 'offset': 10.0},
    ('sketch_new', 'both'): ['refused', 'invalid_input', 'Give plane (XY, XZ, YZ, a datum plane\'s name or "Pad.Face3") or face ({ at: [x,y,z], normal: [x,y,z] } on the body\'s solid), one of them, not both.'],
    ('sketch_add', 'sketcher call 17'): {'added': [{'kind': 'rectangle', 'ids': [0, 1, 2, 3], 'constraints': [0, 7], 'dims': {'plate_width': 8, 'plate_height': 9}}, {'kind': 'circle', 'ids': [4], 'dims': {'hole_d': 10}}]},
    ('sketch_add', 'an item not an object'): ['refused', 'invalid_input', 'items[1]: an object { kind, … }.'],
    ('sketch_offset', 'sketcher call 29'): {'from': [0], 'distance': 1.0, 'added': [3]},
    ('sketch_offset', 'the offset fails'): ['refused', 'failed', 'The offset of -50 mm failed (makeOffset2D: result of offsetting is null!): a distance inward bigger than the profile allows, or a profile crossing itself.'],
    ('sketch_external', 'sketcher call 24'): {'from': 'Pad', 'edges': ['Edge1', 'Edge4'], 'ids': [-3, -4]},
    ('sketch_external', 'sketcher call 25'): ['refused', 'invalid_state', "Pad, the body's tip, is built from PlateSketch: a sketch cannot take edges from a solid made after it. Make a new sketch for what follows the solid (sketch_new { face: { at, normal } }), and bring the edges into that."],
    ('sketch_constrain', 'sketcher call 18'): {'added': [13, 14, 15]},
    ('sketch_constrain', 'sketcher call 19'): ['refused', 'invalid_state', 'These constraints over-constrain PlateSketch (conflicting constraints), and any one of them dropped clears it — new: #13 distance_x = 50: the start of line 0 and the end of line 0; existing: #8 distance_x = 40: the start of line 0 and the end of line 0. Nothing was added: leave out a new one, or sketch_edit deleteConstraints an existing one first.'],
    ('sketch_constrain', 'sketcher call 28'): ['refused', 'invalid_input', 'constraints[0]: geometry -9 is not in TopSketch — its own are 0 to 2; -1 and -2 are the axes; outside edges -3 to -4. sketch_state lists them.'],
    ('sketch_edit', 'sketcher call 20'): {'done': ['set 8 = 70'], 'geometryCount': 8},
    ('sketch_edit', 'many at once'): {'done': ['moved 6.1', 'set 9 = 22', 'construction 5 True', 'renamed 12', 'deleted constraints [11]', 'deleted geometry [7] with its constraints (later ids shift down by the count before them: 7 left, 0 to 6)', 'trimmed 1 at [40.0, 5.0, 0.0] (+0 geometry)', 'split 0 at [20.0, 0.0, 0.0]: its second part is 7', 'mirrored [4] about x: new [8] (free copies: no symmetric constraint ties them to the originals)', 'axes alignment of [2] taken off: horizontal/vertical became parallel/perpendicular']},
    ('sketch_edit', 'fillet: none fits'): ['refused', 'failed', 'No fillet of 200 mm fits there: Not able to fillet geometry Id=0, PointPos=2 — a smaller radius, or a corner where exactly two curves meet (lines and arcs).'],
    ('sketch_edit', 'it breaks the pad'): ['refused', 'failed', 'After the edit Pad fails: Pad: Wire is not closed. — nothing was kept. A feature built on this sketch needs its profile closed and its referenced edges still there: make the edit another way, or change that feature first.'],
    ('sketch_edit', 'group, before 1.2'): ['refused', 'unavailable', 'Group constraints came in FreeCAD 1.2; this is 1.1.3. To hold geometry still here: sketch_constrain { type: "fix", refs: [g] } blocks one geometry where it is.'],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []


def cases(fc, tmp):
    out = []

    def case(tool, name, prepare, args, **flags):
        def prep(s):
            fc.state["flags"] = dict(flags)
            prepare(s)
            fc.settle(s)

        out.append((tool, name, prep, args))

    # ---- furniture ----
    def empty(s):
        b = fc.body(s)
        fc.sketch(s, b, "Sketch")

    def padded(s):
        """A body with a 10 mm pad (1000 mm³) on Sketch, and a second sketch, Top."""
        b = fc.body(s)
        sk = fc.sketch(s, b, "Sketch")
        fc.feature(s, b, "Pad", Profile=sk, Length=10.0)
        fc.sketch(s, b, "Top", geometry=("Circle", "Circle", fc.geo("Circle", True), "Point", "LineSegment", fc.geo("LineSegment", True)), dof=2)
        return b

    def two_bodies(s):
        padded(s)
        b2 = fc.body(s, "Other")
        fc.sketch(s, b2, "Far")

    def none(s):
        pass

    for tool, kind in (("pd_pad", "Pad"), ("pd_pocket", "Pocket")):
        pad = tool == "pd_pad"
        case(tool, "no body", none, {"sketch": "Sketch", "length": 5})
        case(tool, "no such sketch", padded, {"sketch": "Nope", "length": 5})
        case(tool, "sketch of another body", two_bodies, {"body": "Body", "sketch": "Far", "length": 5})
        case(tool, "which sketch", padded, {"length": 5})
        case(tool, "length", padded, {"sketch": "Top", "length": 5})
        case(tool, "length on an empty body", empty, {"length": 5})
        case(tool, "type wrong", padded, {"sketch": "Top", "type": "sideways"})
        case(tool, "type of the other tool", padded, {"sketch": "Top", "type": "through_all" if pad else "up_to_last"})
        case(tool, "sides wrong", padded, {"sketch": "Top", "length": 5, "sides": "both"})
        case(tool, "up to on an empty body", empty, {"type": "up_to_first"})
        case(tool, "length missing", padded, {"sketch": "Top"})
        case(tool, "length a boolean", padded, {"sketch": "Top", "length": True})
        case(tool, "length zero", padded, {"sketch": "Top", "length": 0})
        case(tool, "two without length2", padded, {"sketch": "Top", "length": 5, "sides": "two"})
        case(tool, "two sides", padded, {"sketch": "Top", "length": 5, "length2": 3, "sides": "two"})
        case(tool, "symmetric", padded, {"sketch": "Top", "length": 5, "sides": "symmetric"})
        case(tool, "symmetric, old FreeCAD", padded, {"sketch": "Top", "length": 5, "sides": "symmetric"}, old=True)
        case(tool, "two sides, old FreeCAD", padded, {"sketch": "Top", "length": 5, "length2": 3, "sides": "two"}, old=True)
        case(tool, "two sides up to first, old FreeCAD", padded, {"sketch": "Top", "type": "up_to_first", "sides": "two"}, old=True)
        case(tool, "taper too steep", padded, {"sketch": "Top", "length": 5, "taper": 95})
        case(tool, "taper not a number", padded, {"sketch": "Top", "length": 5, "taper": "steep"})
        case(tool, "taper and reversed", padded, {"sketch": "Top", "length": 5, "taper": 5, "reversed": True})
        case(tool, "taper where FreeCAD has none", padded, {"sketch": "Top", "length": 5, "taper": 5}, old=True, no_taper=True)
        case(tool, "up to face without the face", padded, {"sketch": "Top", "type": "up_to_face"})
        case(tool, "up to face", padded, {"sketch": "Top", "upToFace": {"at": [0, 0, 10], "n": 3}})
        case(tool, "up to face by name", padded, {"sketch": "Top", "type": "up_to_face", "upToFace": "Body.Face8"})
        case(tool, "up to face not found", padded, {"sketch": "Top", "upToFace": {"miss": True}})
        case(tool, "up to first", padded, {"sketch": "Top", "type": "up_to_first"})
        case(tool, "the other end", padded, {"sketch": "Top", "type": "up_to_last" if pad else "through_all"})
        case(tool, "the other end, two sides", padded, {"sketch": "Top", "type": "up_to_last" if pad else "through_all", "sides": "two"})
        case(tool, "it fails", padded, {"sketch": "Top", "length": 5}, invalid={kind: "Wire is not closed."})
        case(tool, "it breaks a later one", padded, {"sketch": "Top", "length": 5}, invalid={"Pad": "Invalid edge link"})
        case(tool, "multiple solids", padded, {"sketch": "Top", "length": 5}, invalid={kind: "Result has multiple solids"})
        case(tool, "it changes nothing", padded, {"sketch": "Top", "length": 5}, effect={kind: 0.0})
        case(tool, "two solids", padded, {"sketch": "Top", "length": 5}, solids=2)
    case("pd_pad", "model call 8", lambda s: fc.sketch(s, fc.body(s, "Tut"), "Profile"), {"body": "Tut", "sketch": "Profile", "length": 53, "sides": "symmetric"})
    case("pd_pocket", "model call 11", lambda s: (padded(s), fc.sketch(s, s.doc.getObject("Body"), "Corner")), {"body": "Body", "sketch": "Corner", "type": "through_all", "reversed": True})
    case("pd_pocket", "model call 19", lambda s: (padded(s), fc.sketch(s, s.doc.getObject("Body"), "Window")), {"sketch": "Window", "length": 8.5, "length2": 8.5, "sides": "two"})
    case("pd_pocket", "no solid", empty, {"length": 5})

    for tool, kind in (("pd_revolution", "Revolution"), ("pd_groove", "Groove")):
        case(tool, "no body", none, {})
        case(tool, "sketch of another body", two_bodies, {"body": "Body", "sketch": "Far"})
        case(tool, "default", padded, {"sketch": "Top"})
        case(tool, "on an empty body", empty, {})
        case(tool, "angle zero", padded, {"sketch": "Top", "angle": 0})
        case(tool, "angle over", padded, {"sketch": "Top", "angle": 400})
        case(tool, "angle a word", padded, {"sketch": "Top", "angle": "half"})
        case(tool, "model call 65", padded, {"sketch": "Top", "axis": 5, "sides": "two"})
        case(tool, "symmetric, reversed, about a construction line", padded, {"sketch": "Top", "axis": 5, "angle": 90, "sides": "symmetric", "reversed": True})
        case(tool, "about a profile line", padded, {"sketch": "Top", "axis": 4})
        case(tool, "about a circle", padded, {"sketch": "Top", "axis": 0})
        case(tool, "about x", padded, {"sketch": "Top", "axis": "x"})
        case(tool, "about H_Axis", padded, {"sketch": "Top", "axis": "H_Axis"})
        case(tool, "axis wrong", padded, {"sketch": "Top", "axis": "up"})
        case(tool, "it fails", padded, {"sketch": "Top"}, invalid={kind: "Revolve axis intersects the sketch"})
        case(tool, "it changes nothing", padded, {"sketch": "Top"}, effect={kind: 0.0})

    case("pd_hole", "no body", none, {"diameter": 3})
    case("pd_hole", "sketch of another body", two_bodies, {"body": "Body", "sketch": "Far", "diameter": 3})
    case("pd_hole", "no solid", empty, {"diameter": 3})
    case("pd_hole", "model call 25", padded, {"sketch": "Top", "diameter": 2, "depth": 4})
    case("pd_hole", "no diameter", padded, {"sketch": "Top"})
    case("pd_hole", "diameter zero", padded, {"sketch": "Top", "diameter": 0})
    case("pd_hole", "depth wrong", padded, {"sketch": "Top", "diameter": 3, "depth": "deep"})
    case("pd_hole", "depth zero", padded, {"sketch": "Top", "diameter": 3, "depth": 0})
    case("pd_hole", "drill point wrong", padded, {"sketch": "Top", "diameter": 3, "drillPoint": "sharp"})
    case("pd_hole", "angled, reversed", padded, {"sketch": "Top", "diameter": 3, "drillPoint": "angled", "reversed": True})
    case("pd_hole", "fit wrong", padded, {"sketch": "Top", "thread": "M5", "fit": "tight"})
    case("pd_hole", "no circles", lambda s: (padded(s), fc.sketch(s, s.doc.getObject("Body"), "Lines", geometry=("LineSegment", fc.geo("Circle", True)))), {"sketch": "Lines", "diameter": 3})
    case("pd_hole", "no circles, old FreeCAD", lambda s: (padded(s), fc.sketch(s, s.doc.getObject("Body"), "Lines", geometry=("LineSegment", "Point"))), {"sketch": "Lines", "diameter": 3}, old=True)
    case("pd_hole", "thread coarse", padded, {"sketch": "Top", "thread": "M5"})
    case("pd_hole", "thread as FreeCAD names it", padded, {"sketch": "Top", "thread": "M8x1.25", "modelThread": True})
    case("pd_hole", "thread fine", padded, {"sketch": "Top", "thread": "m8 x 1"})
    case("pd_hole", "model call 46", padded, {"sketch": "Top", "thread": "M6x7"})
    case("pd_hole", "thread of no size", padded, {"sketch": "Top", "thread": "M7"})
    case("pd_hole", "thread not metric", padded, {"sketch": "Top", "thread": "1/4-20"})
    case("pd_hole", "clearance with a fit", padded, {"sketch": "Top", "thread": "M5", "threaded": False, "fit": "close"})
    case("pd_hole", "clearance with a fit FreeCAD lacks", padded, {"sketch": "Top", "thread": "M5", "threaded": False, "fit": "normal"})
    case("pd_hole", "clearance, old FreeCAD", padded, {"sketch": "Top", "thread": "M5", "threaded": False, "fit": "close"}, old=True)
    case("pd_hole", "model call 47", padded, {"sketch": "Top", "thread": "M6", "depth": "through", "cut": "counterbore"})
    case("pd_hole", "cut wrong", padded, {"sketch": "Top", "diameter": 3, "cut": "slot"})
    case("pd_hole", "cut wrong with a thread", padded, {"sketch": "Top", "thread": "M5", "cut": "none"})
    case("pd_hole", "cut on a diameter without cutDiameter", padded, {"sketch": "Top", "diameter": 3, "cut": "Countersink", "cutDepth": 2})
    case("pd_hole", "cut on a diameter", padded, {"sketch": "Top", "diameter": 3, "cut": "countersink", "cutDiameter": 6, "cutDepth": 2, "countersinkAngle": 82})
    case("pd_hole", "cut by a screw standard, its depth given", padded, {"sketch": "Top", "thread": "M5", "cut": "iso 4762", "cutDepth": 5})
    case("pd_hole", "cut, old FreeCAD", padded, {"sketch": "Top", "diameter": 3, "cut": "counterbore", "cutDiameter": 6}, old=True)
    case("pd_hole", "it cuts nothing", padded, {"sketch": "Top", "diameter": 3}, effect={"Hole": 0.0})
    case("pd_hole", "it fails", padded, {"sketch": "Top", "diameter": 3}, invalid={"Hole": "Hole: Resulting shape is empty"})

    for tool, kind, key, pick in (("pd_fillet", "Fillet", "radius", "edges"), ("pd_chamfer", "Chamfer", "size", "edges"), ("pd_draft", "Draft", "angle", "faces"),
                                  ("pd_thickness", "Thickness", "thickness", "faces")):
        sub = "Edge3" if pick == "edges" else "Face3"
        case(tool, "no body", none, {pick: [sub]})
        case(tool, "no solid", empty, {pick: [sub]})
        case(tool, "default", padded, {pick: [sub]})
        case(tool, "by where it is", padded, {pick: [{"n": 2, "near": [0, 0, 0], "at": [0, 0, 0]}, "Body." + sub], key: 2})
        case(tool, "nothing asked for", padded, {key: 2})
        case(tool, "not found", padded, {pick: [{"miss": True}]})
        case(tool, "size zero", padded, {pick: [sub], key: 0})
        case(tool, "size a word", padded, {pick: [sub], key: "big"})
        case(tool, "size a boolean", padded, {pick: [sub], key: True})
        case(tool, "it fails", padded, {pick: [sub]}, invalid={kind: "BRep_API: command not done"})
        case(tool, "it breaks an edge link", padded, {pick: [sub]}, invalid={"Pad": "Invalid edge link"})
        case(tool, "it changes nothing", padded, {pick: [sub]}, effect={kind: 0.0})
    case("pd_fillet", "model call 28", padded, {"body": "Body", "edges": [{"near": [26.5, -26, 8]}], "radius": 2})
    case("pd_chamfer", "model call 27", padded, {"body": "Body", "edges": [{"near": [0, 0, 26]}], "size": 1})
    case("pd_chamfer", "size2 and angle", padded, {"edges": ["Edge1"], "size2": 2, "angle": 30})
    case("pd_chamfer", "two distances", padded, {"edges": ["Edge1"], "size": 1, "size2": 2})
    case("pd_chamfer", "distance and angle", padded, {"edges": ["Edge1"], "size": 1, "angle": 30})
    case("pd_chamfer", "it adds material", padded, {"edges": ["Edge1"]}, effect={"Chamfer": 4.0})
    case("pd_draft", "model call 36", padded, {"body": "Body", "faces": [{"at": [100, 15, 5], "normal": [1, 0, 0]}], "angle": 5, "neutral": "XY", "pull": "z"})
    case("pd_draft", "negative, reversed, a face for neutral", padded, {"faces": ["Face2"], "angle": -3, "neutral": {"at": [0, 0, 0], "n": 2}, "pull": "x", "reversed": True})
    case("pd_draft", "angle 90", padded, {"faces": ["Face2"], "angle": 90})
    case("pd_draft", "neutral wrong", padded, {"faces": ["Face2"], "neutral": 7})
    case("pd_draft", "neutral not a plane", padded, {"faces": ["Face2"], "neutral": "Nope"})
    case("pd_draft", "pull wrong", padded, {"faces": ["Face2"], "pull": "up"})
    case("pd_thickness", "model call 50", padded, {"body": "Body", "faces": [{"at": [75, 60, 10], "normal": [0, 0, 1]}], "thickness": 2})
    case("pd_thickness", "outward, sharp", padded, {"faces": ["Face1"], "thickness": 2, "outward": True, "join": "intersection"})
    case("pd_thickness", "join wrong", padded, {"faces": ["Face1"], "join": "round"})
    case("pd_thickness", "it hollows nothing", padded, {"faces": ["Face1"]}, effect={"Thickness": 0.0})

    def patterned(s):
        b = padded(s)
        fc.feature(s, b, "Pocket", Profile=s.doc.getObject("Top"))
        fc.feature(s, b, "Fillet", Base=(s.doc.getObject("Pocket"), ["Edge1"]))
        fc.feature(s, b, "Plane", "Mid")
        return b

    def only_dressed(s):
        b = fc.body(s)
        fc.feature(s, b, "FeatureBase", "Base")
        fc.feature(s, b, "Fillet", Base=(s.doc.getObject("FeatureBase"), ["Edge1"]))

    for tool, kind, more in (("pd_mirrored", "Mirrored", {}), ("pd_linear_pattern", "LinearPattern", {"spacing": 6}), ("pd_polar_pattern", "PolarPattern", {})):
        case(tool, "no body", none, {"features": ["Pocket"], **more})
        case(tool, "no solid", empty, {"features": ["Pocket"], **more})
        case(tool, "one by name", patterned, {"features": ["Pocket"], **more})
        case(tool, "a name alone", patterned, {"features": "pocket", **more})
        case(tool, "no features", patterned, {**more})
        case(tool, "features empty", patterned, {"features": [], **more})
        case(tool, "features not names", patterned, {"features": [3], **more})
        case(tool, "no such feature", patterned, {"features": ["Nope"], **more})
        case(tool, "the whole body", patterned, {"features": "all", **more})
        case(tool, "the whole body, a release that words it so", patterned, {"features": " Whole Body ", **more}, transform_modes=["Features", "Transform body"])
        case(tool, "the whole body, no such mode", patterned, {"features": "all", **more}, transform_modes=["Features"])
        case(tool, "the whole body, old FreeCAD", patterned, {"features": "body", **more}, old=True)
        case(tool, "the whole body, no enumerations", patterned, {"features": "all", **more}, no_enums=True)
        case(tool, "the whole body, nothing to repeat", only_dressed, {"features": "all", **more}, old=True)
        case(tool, "a release that leaves the tip", patterned, {"features": ["Pocket"], **more}, pattern_keeps_tip=True)
        case(tool, "it fails", patterned, {"features": ["Pocket"], **more}, invalid={kind: "Transformation failed"})
    case("pd_mirrored", "model call 12", patterned, {"body": "Body", "features": ["Pocket"], "plane": "YZ"})
    case("pd_mirrored", "model call 43", patterned, {"body": "Body", "features": "all", "plane": "XZ"})
    case("pd_mirrored", "across a datum plane", patterned, {"features": ["Pad"], "plane": "Mid"})
    case("pd_mirrored", "across a face", patterned, {"features": ["Pad"], "plane": {"at": [0, 0, 0], "n": 1}})
    case("pd_mirrored", "plane wrong", patterned, {"features": ["Pad"], "plane": "XX"})
    case("pd_linear_pattern", "model call 26", patterned, {"body": "Body", "features": ["Pocket"], "direction": "x", "occurrences": 3, "spacing": 6})
    case("pd_linear_pattern", "by length, reversed", patterned, {"features": ["Pocket"], "direction": "y", "occurrences": 4.0, "length": 30, "reversed": True})
    case("pd_linear_pattern", "occurrences one", patterned, {"features": ["Pocket"], "occurrences": 1, "spacing": 6})
    case("pd_linear_pattern", "occurrences a fraction", patterned, {"features": ["Pocket"], "occurrences": 2.5, "spacing": 6})
    case("pd_linear_pattern", "occurrences a boolean", patterned, {"features": ["Pocket"], "occurrences": True, "spacing": 6})
    case("pd_linear_pattern", "no step", patterned, {"features": ["Pocket"], "occurrences": 3})
    case("pd_linear_pattern", "step zero", patterned, {"features": ["Pocket"], "occurrences": 3, "spacing": 0})
    case("pd_linear_pattern", "direction wrong", patterned, {"features": ["Pocket"], "direction": "up", "spacing": 6})
    case("pd_polar_pattern", "model call 57", patterned, {"body": "Body", "features": ["Pocket"], "axis": "z", "occurrences": 6, "angle": 360})
    case("pd_polar_pattern", "part way, reversed", patterned, {"features": ["Pocket"], "axis": "x", "occurrences": 3, "angle": 90, "reversed": True})
    case("pd_polar_pattern", "occurrences one", patterned, {"features": ["Pocket"], "occurrences": 1})
    case("pd_polar_pattern", "angle zero", patterned, {"features": ["Pocket"], "angle": 0})
    case("pd_polar_pattern", "angle a word", patterned, {"features": ["Pocket"], "angle": "round"})
    case("pd_polar_pattern", "axis wrong", patterned, {"features": ["Pocket"], "axis": "DiscAxis"})

    def sections(s):
        b = padded(s)
        fc.sketch(s, b, "Sec1")
        fc.sketch(s, b, "Sec2")
        fc.sketch(s, b, "Path", edges=3)
        fc.sketch(s, b, "Bare", edges=0)

    def sections_empty(s):
        b = fc.body(s)
        for n in ("Top", "Sec1", "Path"):
            fc.sketch(s, b, n)

    for tool, kind, more in (("pd_loft", "Loft", {"sections": ["Sec1", "Sec2"]}), ("pd_pipe", "Pipe", {"path": "Path"})):
        case(tool, "no body", none, {"profile": "Top", **more})
        case(tool, "no profile named", sections, {**more})
        case(tool, "profile of another body", lambda s: (sections(s), fc.sketch(s, fc.body(s, "Other"), "Far")), {"body": "Body", "profile": "Far", **more})
        case(tool, "additive", sections, {"profile": "Top", **more})
        case(tool, "subtractive", sections, {"profile": "Top", "subtractive": True, **more})
        case(tool, "subtractive on an empty body", sections_empty, {"profile": "Top", "subtractive": True, **{k: (["Sec1"] if k == "sections" else v) for k, v in more.items()}})
        case(tool, "the first solid", sections_empty, {"profile": "Top", **{k: (["Sec1"] if k == "sections" else v) for k, v in more.items()}})
        case(tool, "it fails", sections, {"profile": "Top", **more}, invalid={kind: "Loft: Creation failed"})
        case(tool, "it adds nothing", sections, {"profile": "Top", **more}, effect={kind: 0.0})
    case("pd_loft", "model call 83", sections, {"body": "Body", "profile": "Top", "sections": ["Sec1"], "ruled": True})
    case("pd_loft", "closed", sections, {"profile": "Top", "sections": ["Sec1", "Sec2"], "closed": True})
    case("pd_loft", "no sections", sections, {"profile": "Top"})
    case("pd_loft", "the profile among the sections", sections, {"profile": "Top", "sections": ["Sec1", "top"]})
    case("pd_loft", "no such section", sections, {"profile": "Top", "sections": ["Nope"]})
    case("pd_pipe", "model call 89", sections, {"body": "Body", "profile": "Top", "path": "Path"})
    case("pd_pipe", "the profile as its path", sections, {"profile": "Top", "path": "Top"})
    case("pd_pipe", "a path with no edges", sections, {"profile": "Top", "path": "Bare"})
    case("pd_pipe", "no such path", sections, {"profile": "Top", "path": "Nope"})

    case("pd_datum_plane", "no body", none, {})
    case("pd_datum_plane", "model call 29", padded, {"body": "Body", "on": "XY", "offset": 30, "name": "Above"})
    case("pd_datum_plane", "default", padded, {})
    case("pd_datum_plane", "a name taken", patterned, {"name": "Mid"})
    case("pd_datum_plane", "on a face, turned", padded, {"on": {"at": [0, 0, 10], "n": 2}, "rotate": {"axis": [0, 1, 0], "angle": 30}})
    case("pd_datum_plane", "on a face by name", padded, {"on": "Pad.Face3", "rotate": {}})
    case("pd_datum_plane", "turned by default", padded, {"rotate": {"angle": 15}})
    case("pd_datum_plane", "rotate not an object", padded, {"rotate": 30})
    case("pd_datum_plane", "rotate axis wrong", padded, {"rotate": {"axis": [1, 0]}})
    case("pd_datum_plane", "on wrong", padded, {"on": 3})
    case("pd_datum_plane", "it does not attach", padded, {"on": "XZ"}, invalid={"Plane": "Attachment failed"})
    case("pd_datum_plane", "old FreeCAD", padded, {"on": "YZ", "offset": -4}, old=True)

    def history(s):
        b = patterned(s)
        top = s.doc.getObject("Top")
        fc.feature(s, b, "Hole", Profile=top, ThreadSize="M5x0.8", Threaded=True)
        fc.feature(s, b, "LinearPattern", Originals=[s.doc.getObject("Hole")], Occurrences=3)
        fc.feature(s, b, "Chamfer", Base=(s.doc.getObject("LinearPattern"), ["Edge2", "Edge5"]), ChamferType="Two distances", Size2=2.0)
        fc.feature(s, b, "Revolution", "Turn", Profile=(top, ["Edge1"]), Type="TwoAngles", Angle2=20.0, Midplane=True)
        fc.feature(s, b, "Pocket", "Slot", Profile=top, SideType="Two sides", Length2=3.0, Offset=1.5, Reversed=True, TaperAngle=2.0)
        return b

    def multi(s):
        b = history(s)
        steps = [fc.feature(s, b, "LinearPattern", "Row"), fc.feature(s, b, "PolarPattern", "Ring")]
        loose = fc.feature(s, b, "Mirrored", "Loose")
        fc.feature(s, b, "MultiTransform", "Grid", Transformations=steps + [loose], Originals=[s.doc.getObject("Pad")])
        b.__dict__["Group"].remove(loose)  # a step FreeCAD keeps outside the body

    def bound(s):
        b = history(s)
        s.doc.getObject("Pad").__dict__["ExpressionEngine"] = [(".Length", "Params.height * 2")]
        fc.sketch(s, b, "Late", dof=None)

    def own_sketch(s):
        b = padded(s)
        fc.feature(s, b, "Pocket", Profile=fc.sketch(s, b, "Own"))
        fc.feature(s, b, "Pocket", "Shared", Profile=(s.doc.getObject("Top"), ["Edge1"]))
        fc.feature(s, b, "Hole", Profile=s.doc.getObject("Top"))
        fc.feature(s, b, "FeatureBase", "NoProfile")

    case("feature_list", "no body", none, {})
    case("feature_list", "empty", empty, {})
    case("feature_list", "model call 21", history, {"body": "Body"})
    case("feature_list", "model call 113", multi, {"body": "body"})
    case("feature_list", "one invalid, one bound", bound, {}, invalid={"Slot": "Pocket: Cut out failed"})
    case("feature_list", "old FreeCAD", history, {}, old=True)
    case("feature_list", "the tip moved back", lambda s: history(s).__dict__.update(Tip=s.doc.getObject("Hole")), {})
    case("feature_list", "which body", two_bodies, {})

    case("feature_edit", "no body", none, {"feature": "Pad", "set": {"Length": 20}})
    case("feature_edit", "no such feature", history, {"feature": "Nope", "set": {"Length": 20}})
    case("feature_edit", "a sketch is no feature", history, {"feature": "Top", "set": {"Length": 20}})
    case("feature_edit", "nothing to set", history, {"feature": "Pad"})
    case("feature_edit", "set not an object", history, {"feature": "Pad", "set": ["Length", 20]})
    case("feature_edit", "model call 20", history, {"body": "Body", "feature": "Slot", "set": {"Refine": True}})
    case("feature_edit", "model call 71", history, {"body": "Body", "feature": "Turn", "set": {"Angle": 180}})
    case("feature_edit", "model call 70", history, {"body": "Body", "feature": "Turn", "set": {"Type": "Nope"}})
    case("feature_edit", "several", history, {"feature": "pad", "set": {"Length": 20, "Type": "UpToLast", "Reversed": True}})
    case("feature_edit", "not a property", history, {"feature": "Pad", "set": {"Length": 20, "length2": 4}})
    case("feature_edit", "bound to a parameter", bound, {"feature": "Pad", "set": {"Length": 20}})
    case("feature_edit", "a link", history, {"feature": "Pad", "set": {"Profile": "Top"}})
    case("feature_edit", "a link by its type", history, {"feature": "Turn", "set": {"ReferenceAxis": "x"}})
    case("feature_edit", "kept only to read old files", history, {"feature": "Pad", "set": {"Type": "?TwoLengths"}})
    case("feature_edit", "FreeCAD does not take it", history, {"feature": "Pad", "set": {"Length": "long"}})
    case("feature_edit", "no enumerations to read", history, {"feature": "Pad", "set": {"Type": "Sideways"}}, no_enums=True)
    case("feature_edit", "it breaks the feature", history, {"feature": "Pad", "set": {"Length": 20}}, invalid={"Pad": "Pad: Creation failed"})
    case("feature_edit", "it breaks a later one, not repaired", history, {"feature": "Pad", "set": {"Length": 20}}, invalid={"Chamfer": "Invalid edge link"})
    case("feature_edit", "it changes nothing", history, {"feature": "Pad", "set": {"Length": 10}})
    case("feature_edit", "it renames a later one's edges, found again", history, {"feature": "Pad", "set": {"Length": 20}}, invalid_after={"Chamfer": "Invalid edge link"},
         heals=["Chamfer"])
    case("feature_edit", "it breaks a later one, nothing to find again", own_sketch, {"feature": "Pad", "set": {"Length": 20}}, invalid_after={"Hole": "Hole: no base"})

    def used(s):
        b = history(s)
        fc.sketch(s, b, "OnPad").__dict__["AttachmentSupport"] = [(s.doc.getObject("Pad"), "Face3")]
        return b

    case("feature_remove", "no body", none, {"feature": "Pad"})
    case("feature_remove", "no such feature", history, {"feature": "Nope"})
    case("feature_remove", "model call 32", history, {"body": "Body", "feature": "LinearPattern"})
    case("feature_remove", "used by a sketch, a pattern and a fillet", used, {"feature": "Pad"})
    case("feature_remove", "forced", history, {"feature": "LinearPattern", "force": True})
    case("feature_remove", "forced, and a user fails", history, {"feature": "LinearPattern", "force": True}, invalid={"Chamfer": "Invalid edge link"})
    case("feature_remove", "the tip, with its sketch", own_sketch, {"feature": "NoProfile"})
    case("feature_remove", "with its own sketch", own_sketch, {"feature": "Pocket"})
    case("feature_remove", "keeping its sketch", own_sketch, {"feature": "Pocket", "keepSketch": True})
    case("feature_remove", "a sketch others use", own_sketch, {"feature": "Shared"})
    case("feature_remove", "a sketch", own_sketch, {"feature": "Own", "force": True})
    case("feature_remove", "a MultiTransform and its steps", multi, {"feature": "Grid"})
    case("feature_remove", "a later feature breaks", own_sketch, {"feature": "Pocket"}, invalid={"Hole": "Hole: no base"})
    case("feature_remove", "the last solid", lambda s: fc.feature(s, fc.body(s), "Pad", Profile=None), {"feature": "Pad"})

    case("feature_suppress", "no body", none, {"feature": "Pad"})
    case("feature_suppress", "no such feature", history, {"feature": "Top"})
    case("feature_suppress", "model call 30", history, {"body": "Body", "feature": "Fillet"})
    case("feature_suppress", "model call 31", lambda s: history(s) and s.doc.getObject("Fillet").__dict__.update(Suppressed=True), {"body": "Body", "feature": "Fillet", "suppressed": False})
    case("feature_suppress", "old FreeCAD", history, {"feature": "Fillet"}, old=True)
    case("feature_suppress", "a later feature needs it", history, {"feature": "Pad"}, invalid={"Fillet": "Invalid edge link"})
    # ---- std_more's Part Design tools ----
    def hist(s):
        """Model calls 97-100: HistBase, H1 (a cut), H2, in body Hist; and an empty body Hist2."""
        b = fc.body(s, "Hist")
        fc.feature(s, b, "FeatureBase", "HistBase")
        fc.feature(s, b, "Pocket", "H1")
        fc.feature(s, b, "Pad", "H2", Length=0.5)
        return b

    def hist_two(s):
        b = hist(s)
        sk = fc.sketch(s, b, "Island")
        sk.__dict__["AttachmentSupport"] = [(b.Origin.OriginFeatures[3], "")]
        fc.feature(s, b, "Pad", "Pad 3", Profile=sk, Length=0.75)
        fc.body(s, "Hist2")
        box = s.doc.new("Part::Box", "Box")
        box.__dict__["Shape"] = fc.solid_of(10.0)
        return b

    def on_face(s):
        hist_two(s)
        s.doc.getObject("Island").__dict__["AttachmentSupport"] = [(s.doc.getObject("FeatureBase"), "Face3")]
        s.doc.getObject("Pad001").__dict__["Profile"] = (s.doc.getObject("Island"), ["Edge1"])

    def loose(s):
        hist_two(s)
        fc.feature(s, s.doc.getObject("Hist"), "Pocket", "Stray", Profile=fc.sketch(s, None, "Free"))
        s.doc.getObject("Hist").__dict__["Group"].remove(s.doc.getObject("Pocket001"))

    case("pd_move_feature", "model call 109", hist_two, {"feature": "Pad 3", "to": "Hist2"})
    case("pd_move_feature", "model call 111", hist_two, {"feature": "H1", "to": "Hist2"})
    case("pd_move_feature", "it breaks what is left", hist_two, {"feature": "H1", "to": "Hist2"}, invalid_after={"H2": "Pad: no base", "H1": "Pocket: no solid to cut"})
    case("pd_move_feature", "already broken, nothing new", hist_two, {"feature": "Pad 3", "to": "Hist2"}, invalid={"H2": "Pad: no base"})
    case("pd_move_feature", "a sketch on a face", on_face, {"feature": "Pad 3", "to": "Hist2"})
    case("pd_move_feature", "a sketch alone", hist_two, {"feature": "Island", "to": "Hist2"})
    case("pd_move_feature", "a feature of no body", loose, {"feature": "Stray", "to": "Hist2"})
    case("pd_move_feature", "old FreeCAD", lambda s: (hist_two(s), s.doc.getObject("Island").__dict__.update(Support=s.doc.getObject("Island").__dict__.pop("AttachmentSupport"))),
         {"feature": "Pad 3", "to": "Hist2"}, old=True)
    case("pd_move_feature", "no feature named", hist_two, {"to": "Hist2"})
    case("pd_move_feature", "no such feature", hist_two, {"feature": "Nope", "to": "Hist2"})
    case("pd_move_feature", "not a feature", hist_two, {"feature": "Box", "to": "Hist2"})
    case("pd_move_feature", "a body", hist_two, {"feature": "Hist", "to": "Hist2"})
    case("pd_move_feature", "no such body", hist_two, {"feature": "H1", "to": "Nope"})
    case("pd_move_feature", "to its own body", hist_two, {"feature": "H1", "to": "Hist"})

    case("pd_reorder", "model call 103", hist, {"feature": "H2", "before": "H1"})
    case("pd_reorder", "after the tip", hist, {"feature": "H1", "after": "H2"})
    case("pd_reorder", "after another, the tip stays", hist, {"feature": "HistBase", "after": "H1"})
    case("pd_reorder", "past the tip", lambda s: hist(s).__dict__.update(Tip=s.doc.getObject("Pocket")), {"feature": "HistBase", "after": "H2"})
    case("pd_reorder", "a sketch", hist_two, {"feature": "Island", "before": "h1"})
    case("pd_reorder", "it breaks one", hist, {"feature": "H2", "before": "HistBase"}, invalid_after={"H1": "Pocket: no solid to cut"})
    case("pd_reorder", "already broken, nothing new", hist, {"feature": "H2", "before": "HistBase"}, invalid={"H1": "Pocket: no solid to cut"})
    case("pd_reorder", "no solid left", lambda s: (hist(s), fc.state["flags"].update(effect={"HistBase": 0.0, "H2": 0.0})), {"feature": "H2", "before": "H1"})
    case("pd_reorder", "not in a body", hist_two, {"feature": "Box", "after": "H1"})
    case("pd_reorder", "both", hist, {"feature": "H2", "after": "H1", "before": "HistBase"})
    case("pd_reorder", "neither", hist, {"feature": "H2"})
    case("pd_reorder", "no such target", hist, {"feature": "H2", "before": "Nope"})
    case("pd_reorder", "next to itself", hist, {"feature": "H2", "after": "H2"})
    case("pd_reorder", "no such feature", hist, {"feature": "Nope", "after": "H2"})

    def with_datum(s):
        b = hist(s)
        fc.feature(s, b, "Plane", "Datum")
        b.__dict__["Group"].insert(0, b.__dict__["Group"].pop())  # a datum before every solid
        fc.sketch(s, b, "Late")
        return b

    def with_steps(s):
        b = hist(s)
        row = fc.feature(s, b, "LinearPattern", "Row")
        fc.feature(s, b, "MultiTransform", "Grid", Transformations=[row])

    case("pd_tip", "model call 33", hist, {"body": "Hist"})
    case("pd_tip", "model call 101", hist, {"body": "Hist", "feature": "H1"})
    case("pd_tip", "model call 102", lambda s: hist(s).__dict__.update(Tip=s.doc.getObject("Pocket")), {"body": "Hist", "feature": "H2"})
    case("pd_tip", "a sketch: the solid before it", with_datum, {"feature": "Late"})
    case("pd_tip", "a datum with nothing before it", with_datum, {"feature": "Datum"})
    case("pd_tip", "a datum in a body with no solid", lambda s: fc.feature(s, fc.body(s), "Plane", "Datum"), {"feature": "Datum"})
    case("pd_tip", "a MultiTransform's step", with_steps, {"feature": "Row"})
    case("pd_tip", "it fails", hist, {"feature": "H1"}, invalid_after={"H2": "Pad: no base"})
    case("pd_tip", "it fails, no tip before", lambda s: hist(s).__dict__.update(Tip=None), {"feature": "H1"}, invalid_after={"H2": "Pad: no base", "H1": "Pocket: nothing to cut"})
    case("pd_tip", "no tip", lambda s: hist(s).__dict__.update(Tip=None), {})
    case("pd_tip", "an empty body", lambda s: fc.body(s), {})
    case("pd_tip", "no body", none, {})
    case("pd_tip", "no such feature", hist, {"feature": "Nope"})

    case("pd_shaft", "model call 112", none, {"segments": [{"length": 20, "diameter": 10}, {"length": 30, "diameter": 16}, {"length": 10, "diameter": 16, "diameterEnd": 10}],
                                                "at": [0, 0, 60], "name": "Shaft"})
    case("pd_shaft", "along z, a name taken", lambda s: s.doc.new("Part::Feature", "Shaft"), {"segments": [{"length": 20, "diameter": 10}], "axis": "z"})
    case("pd_shaft", "along y, a shell from the revolve", none, {"segments": [{"length": 20, "diameter": 10}, {"length": 5, "diameter": 10}], "axis": "y", "name": "Pin"},
         revolve_shell=True, shell_volume=1570.8)
    case("pd_shaft", "no segments", none, {})
    case("pd_shaft", "a segment not an object", none, {"segments": [{"length": 20, "diameter": 10}, 30]})
    case("pd_shaft", "a segment of no length", none, {"segments": [{"length": 20, "diameter": 10}, {"diameter": 16}]})
    case("pd_shaft", "a taper to nothing", none, {"segments": [{"length": 20, "diameter": 10, "diameterEnd": 0}]})
    # ---- the sketch family ----
    P, V = fc.part, fc.Vec
    font = tmp + "/font.ttf"
    open(font, "w").close()

    def rect_curves(w=40.0, h=20.0, x=0.0, y=0.0):
        c = [V(x, y, 0), V(x + w, y, 0), V(x + w, y + h, 0), V(x, y + h, 0)]
        return [P.LineSegment(c[i], c[(i + 1) % 4]) for i in range(4)]

    RECT_CONS = [("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)] + [("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1), ("Vertical", 3)]

    def plate(s):
        """Sketcher calls 15-18: body Plate, PlateSketch a 40 x 20 rectangle with named sizes, a hole, an ellipse, a point and a construction line."""
        b = fc.body(s, "Plate")
        fc.drawing(s, b, "PlateSketch", rect_curves() + [P.Circle(V(1, 9, 0), None, 5.0), P.Ellipse(V(8, 0, 0), V(0, 3, 0), V()), P.Point(V(3, 3, 0)),
                                                         (P.LineSegment(V(0, 0, 0), V(0, 30, 0)), True)],
                   RECT_CONS + [("plate_width", ("DistanceX", 0, 1, 0, 2, 40.0)), ("plate_height", ("DistanceY", 1, 1, 1, 2, 20.0)), ("hole_d", ("Diameter", 4, 10.0)),
                                ("lean", ("Angle", 7, 1.5708)), ("Distance", 4, 3, 6, 1, 6.0)])
        return b

    def plate_padded(s):
        """… and a pad on it (sketcher call 22), with TopSketch (a circle and an arc) after the pad."""
        b = plate(s)
        fc.feature(s, b, "Pad", Profile=s.doc.getObject("PlateSketch"), Length=2.0)
        fc.drawing(s, b, "TopSketch", [P.Circle(V(2, -18, 0), None, 3.0), P.ArcOfCircle(P.Circle(V(), None, 4.0), 0.0, 1.5), P.BSplineCurve([V(0, 0, 0), V(5, 5, 0)])])
        return b

    def loose_sketch(s):
        plate(s)
        fc.drawing(s, None, "Free", rect_curves())

    case("pd_body_new", "model call 3", none, {"name": "Tut"})
    case("pd_body_new", "default", none, {})
    case("pd_body_new", "a name taken", lambda s: fc.body(s), {})

    case("sketch_new", "model call 4", lambda s: fc.body(s, "Tut"), {"body": "Tut", "plane": "XY", "name": "Master"})
    case("sketch_new", "no body", none, {"plane": "XY"})
    case("sketch_new", "neither plane nor face", padded, {})
    case("sketch_new", "both", padded, {"plane": "XY", "face": {"at": [0, 0, 0]}})
    case("sketch_new", "sketcher call 23", padded, {"body": "Body", "face": {"at": [0, -20, 2], "normal": [0, 0, 1], "n": 3}, "name": "TopSketch"})
    case("sketch_new", "a face not found", padded, {"face": {"at": [0, 0, 99], "miss": True}})
    case("sketch_new", "a face on an empty body", empty, {"face": {"at": [0, 0, 0]}})
    case("sketch_new", "sketcher call 30", padded, {"body": "Body", "plane": "XY", "name": "PlateCopy", "offset": 10})
    case("sketch_new", "on a datum plane, flipped, a name taken", patterned, {"plane": "Mid", "flip": True, "name": "Top"})
    case("sketch_new", "on a named face, offset", padded, {"plane": "Pad.Face3", "offset": -2.5})
    case("sketch_new", "a face, offset", padded, {"face": {"at": [0, 0, 10], "n": 2}, "offset": 4})
    case("sketch_new", "plane wrong", padded, {"plane": "XW"})
    case("sketch_new", "it does not attach", padded, {"plane": "XZ"}, invalid={"Sketch001": "Attachment failed: face is not planar"})
    case("sketch_new", "old FreeCAD", padded, {"plane": "YZ"}, old=True)

    case("sketch_add", "sketcher call 3", lambda s: fc.drawing(s, fc.body(s, "Star"), "StarSketch"),
         {"sketch": "StarSketch", "items": [{"kind": "line", "from": [0, 0], "to": [0.0, 30.0], "construction": True}, {"kind": "line", "from": [0, 0], "to": [-28.5, 9.3], "construction": True}]})
    case("sketch_add", "sketcher call 17", lambda s: fc.drawing(s, fc.body(s, "Plate"), "PlateSketch"),
         {"sketch": "PlateSketch", "items": [{"kind": "rectangle", "center": [0, 0], "size": [60, 80], "dims": True, "name": "plate"},
                                             {"kind": "circle", "center": [1, 9], "radius": 5, "dims": True, "name": "hole"}]})
    case("sketch_add", "model call 7", plate, {"sketch": "PlateSketch", "items": [{"kind": "polyline", "points": [[0, 0], [0, 26], [-5, 26], [-26, 0]], "closed": True}]})
    case("sketch_add", "sizes without a name, on what is there", plate, {"items": [{"kind": "rectangle", "corner": [5, 5], "size": [10, 4], "dims": True}, {"kind": "arc", "radius": 4, "dims": True}]})
    case("sketch_add", "a name that is a number", plate, {"items": [{"kind": "circle", "diameter": 6, "dims": True, "name": 7}]})
    case("sketch_add", "every other kind", plate, {"items": [
        {"kind": "point", "at": [1, 2]}, {"kind": "rounded_rectangle", "size": [20, 10], "radius": 2, "dims": True, "name": "pad"},
        {"kind": "polygon", "sides": 5, "radius": 8, "rotation": 18, "dims": True}, {"kind": "slot", "from": [0, 0], "to": [10, 0], "radius": 2, "dims": True},
        {"kind": "arc_slot", "radius": 10, "width": 2, "start": 10, "end": 80, "construction": True}, {"kind": "bspline", "points": [[0, 0], [5, 4], [9, 1]]},
        {"kind": "bspline", "points": [[0, 0], [5, 4], [9, 1], [12, 6]], "interpolate": False, "degree": 2}, {"kind": "ellipse", "major": 10, "minor": 6, "rotation": 30},
        {"kind": "arc3", "points": [[0, 0], [5, 5], [10, 0]], "dims": True}, {"kind": "circle3", "points": [[0, 0], [5, 5], [10, 0]], "dims": True},
        {"kind": "parabola", "focal": 2, "rotation": 90}, {"kind": "hyperbola", "major": 3, "minor": 2}, {"kind": "polyline", "points": [[0, 0], [4, 0], [4, 3]]}]})
    case("sketch_add", "no sketch", none, {"items": [{"kind": "point", "at": [0, 0]}]})
    case("sketch_add", "which sketch", plate_padded, {"items": [{"kind": "point", "at": [0, 0]}]})
    case("sketch_add", "no items", plate, {})
    case("sketch_add", "items not a list", plate, {"items": {"kind": "point"}})
    case("sketch_add", "an item not an object", plate, {"items": [{"kind": "point", "at": [0, 0]}, "circle"]})
    case("sketch_add", "kind wrong", plate, {"items": [{"kind": "squiggle"}]})
    case("sketch_add", "a shape's own check, after one was added", plate, {"items": [{"kind": "point", "at": [0, 0]}, {"kind": "circle", "radius": 0}]})
    case("sketch_add", "three points on a line", plate, {"items": [{"kind": "arc3", "points": [[0, 0], [5, 0], [10, 0]]}]})

    case("sketch_offset", "sketcher call 29", plate_padded, {"sketch": "TopSketch", "distance": 1, "geometry": [0], "construction": True})
    case("sketch_offset", "the whole profile", plate, {"distance": 2})
    case("sketch_offset", "inward, sharp", plate, {"distance": -2, "geometry": [0, 1, 2, 3], "join": "intersection"})
    case("sketch_offset", "out is out", plate, {"distance": 2, "geometry": [0, 1, 2, 3]}, offset_inward=True)
    case("sketch_offset", "an arc, a spline and an open chain", plate_padded, {"sketch": "TopSketch", "distance": 1, "geometry": [1, 2], "join": "tangent"})
    case("sketch_offset", "an open chain", plate, {"distance": 1, "geometry": [0, 1]})
    case("sketch_offset", "distance zero", plate, {"distance": 0})
    case("sketch_offset", "distance a boolean", plate, {"distance": True})
    case("sketch_offset", "no distance", plate, {})
    case("sketch_offset", "an id out of range", plate, {"distance": 1, "geometry": [0, 12]})
    case("sketch_offset", "an id that is a word", plate, {"distance": 1, "geometry": ["0"]})
    case("sketch_offset", "an id that is a fraction", plate, {"distance": 1, "geometry": [1.0]})
    case("sketch_offset", "an id that is true", plate, {"distance": 1, "geometry": [True]})
    case("sketch_offset", "it does not join", plate, {"distance": 1}, no_join=True)
    case("sketch_offset", "join wrong", plate, {"distance": 1, "join": "round"})
    case("sketch_offset", "the offset fails", plate, {"distance": -50}, no_offset=True)
    case("sketch_offset", "no sketch", none, {"distance": 1})

    case("sketch_external", "sketcher call 24", plate_padded, {"sketch": "TopSketch", "edges": [{"type": "circle", "near": [5, 10, 2]}, {"type": "line", "near": [0, -40, 2], "first": 4}]})
    case("sketch_external", "sketcher call 25", plate_padded, {"sketch": "PlateSketch", "edges": ["Edge1"]})
    case("sketch_external", "by name", plate_padded, {"sketch": "TopSketch", "edges": ["Edge7", "Pad.Edge2"]})
    case("sketch_external", "every match, and the nearest of several", plate_padded, {"sketch": "TopSketch", "edges": [{"type": "line", "hits": 3}, {"type": "circle", "hits": 3, "first": 7, "near": [0, 0, 0]}]})
    case("sketch_external", "one already there", plate_padded, {"sketch": "TopSketch", "edges": ["Edge7", "Edge7"]})
    case("sketch_external", "old FreeCAD", plate_padded, {"sketch": "TopSketch", "edges": ["Edge7", "Edge2"]}, old=True)
    case("sketch_external", "nothing matches", plate_padded, {"sketch": "TopSketch", "edges": ["Edge1", {"type": "circle", "radius": 99, "hits": 0}]})
    case("sketch_external", "near wrong", plate_padded, {"sketch": "TopSketch", "edges": [{"hits": 2, "near": [0, 0]}]})
    case("sketch_external", "no edges", plate_padded, {"sketch": "TopSketch"})
    case("sketch_external", "edges not a list", plate_padded, {"sketch": "TopSketch", "edges": "Edge1"})
    case("sketch_external", "in no body", loose_sketch, {"sketch": "Free", "edges": ["Edge1"]})
    case("sketch_external", "no solid yet", plate, {"edges": ["Edge1"]})
    case("sketch_external", "no sketch", none, {"edges": ["Edge1"]})

    def with_outside(s):
        plate_padded(s)
        s.doc.getObject("TopSketch").__dict__["ExternalGeo"] += [("Pad", "Edge7"), ("Pad", "Edge2")]

    case("sketch_constrain", "sketcher call 4", plate, {"sketch": "PlateSketch", "constraints": [{"type": "coincident", "refs": [[7, 1], "origin"]}]})
    case("sketch_constrain", "sketcher call 18", plate, {"sketch": "PlateSketch", "constraints": [
        {"type": "symmetric", "refs": [[0, 1], [1, 2], "origin"]}, {"type": "point_on_object", "refs": [[4, 3], -2]}, {"type": "distance_y", "refs": [[4, 3]], "value": 10, "name": "hole_y"}]})
    case("sketch_constrain", "sketcher call 19", plate, {"sketch": "PlateSketch", "constraints": [{"type": "distance_x", "refs": [[0, 1], [0, 2]], "value": 50}]})
    case("sketch_constrain", "sketcher call 27", with_outside, {"sketch": "TopSketch", "constraints": [
        {"type": "point_on_object", "refs": [[0, 3], -2]}, {"type": "distance", "refs": [[0, 3], [-3, 3]], "value": 30, "name": "pitch"}, {"type": "radius", "refs": [0], "value": 3}]})
    case("sketch_constrain", "sketcher call 28", with_outside, {"sketch": "TopSketch", "constraints": [{"type": "distance", "refs": [[0, 3], -9], "value": 5}]})
    case("sketch_constrain", "a geometry it has not, no outside edges", plate, {"constraints": [{"type": "horizontal", "refs": [0]}, {"type": "vertical", "refs": [8]}]})
    case("sketch_constrain", "the others", plate, {"constraints": [
        {"type": "Parallel", "refs": [0, 2]}, {"type": "tangent", "refs": [4, 5]}, {"type": "tangent", "refs": [[0, 2], [1, 1]]}, {"type": "equal", "refs": [1, 3]},
        {"type": "symmetric", "refs": [[0, 1], [0, 2], 7]}, {"type": "distance", "refs": [7], "value": 30}, {"type": "distance", "refs": [[6, 1], 0], "value": 3},
        {"type": "distance-x", "refs": [[6, 1]], "value": 3}, {"type": "diameter", "refs": [5], "value": 4}, {"type": "angle", "refs": [0, 7], "value": 90},
        {"type": "angle", "refs": [1], "value": 90, "name": "up"}, {"type": "block", "refs": [5]}, {"type": "fix", "refs": [[4, 3]], "name": "pin"},
        {"type": "vertical", "refs": [[0, 1], [3, 1]]}]})
    case("sketch_constrain", "redundant: the same size again", plate, {"constraints": [{"type": "horizontal", "refs": [7]}, {"type": "distance_x", "refs": [[0, 1], [0, 2]], "value": 40, "name": "again"}]})
    case("sketch_constrain", "it clashes, and no one of them clears it", plate, {"constraints": [{"type": "distance_x", "refs": [[0, 1], [0, 2]], "value": 50}]}, no_toggle=True)
    case("sketch_constrain", "the solver fails", plate, {"constraints": [{"type": "horizontal", "refs": [7]}]}, solve=-1)
    case("sketch_constrain", "malformed", plate, {"constraints": [{"type": "horizontal", "refs": [7]}, {"type": "equal", "refs": [0, 2]}]}, malformed=[13, 14], solve=-5)
    case("sketch_constrain", "FreeCAD will not take it", plate, {"constraints": [{"type": "horizontal", "refs": [7]}, {"type": "radius", "refs": [0], "value": 3}]})
    case("sketch_constrain", "a type it has not", plate, {"constraints": [{"type": "horizontal", "refs": [7]}, {"type": "concentric", "refs": [4, 5]}]})
    case("sketch_constrain", "refs in the wrong form", plate, {"constraints": [{"type": "coincident", "refs": [0, 1]}]})
    case("sketch_constrain", "no value", plate, {"constraints": [{"type": "radius", "refs": [4]}]})
    case("sketch_constrain", "a vertex it has not", plate, {"constraints": [{"type": "coincident", "refs": [[0, 1], [1, 5]]}]})
    case("sketch_constrain", "a ref that is no ref", plate, {"constraints": [{"type": "coincident", "refs": [[0, 1], "middle"]}]})
    case("sketch_constrain", "fix the origin", plate, {"constraints": [{"type": "lock", "refs": [[-1, 1]]}]})
    case("sketch_constrain", "one not an object", plate, {"constraints": [{"type": "horizontal", "refs": [7]}, "vertical"]})
    case("sketch_constrain", "no constraints", plate, {})
    case("sketch_constrain", "no sketch", none, {"constraints": [{"type": "horizontal", "refs": [0]}]})

    def clashing(s):
        plate(s)
        sk = s.doc.getObject("PlateSketch")
        c = fc.Constraint("DistanceX", 0, 1, 0, 2, 55.0)
        sk.__dict__["Constraints"].append(c)
        sk.solve()

    def open_profile(s):
        fc.drawing(s, fc.body(s), "Open", rect_curves()[:3] + [P.LineSegment(V(50, 0, 0), V(60, 0, 0))])

    def off_axis(s):
        b = plate(s)
        s.doc.getObject("PlateSketch").__dict__["AttachmentOffset"] = fc.Placement(V(0, 0, 5))
        fc.drawing(s, b, "Bare")

    case("sketch_state", "sketcher call 13", plate, {"sketch": "PlateSketch"})
    case("sketch_state", "without detail", plate, {"detail": False})
    case("sketch_state", "over-constrained", clashing, {})
    case("sketch_state", "open, with free ends", open_profile, {})
    case("sketch_state", "nothing drawn", off_axis, {"sketch": "Bare"})
    case("sketch_state", "invalid", off_axis, {"sketch": "PlateSketch"}, invalid={"PlateSketch": "Sketch with malformed constraints"}, partly=[2])
    case("sketch_state", "no sketch", none, {})
    case("sketch_state", "no such sketch", plate, {"sketch": "Nope"})

    def bound_size(s):
        plate(s)
        s.doc.getObject("PlateSketch").__dict__["ExpressionEngine"] = [(".Constraints.plate_width", "Params.width"), ("Constraints[9]", "Params.height")]

    E = "PlateSketch"
    case("sketch_edit", "nothing asked", plate, {})
    case("sketch_edit", "an empty request", plate, {"delete": [], "deleteConstraints": []})
    case("sketch_edit", "no sketch", none, {"delete": [0]})
    case("sketch_edit", "sketcher call 20", plate, {"sketch": E, "set": [{"constraint": "plate_width", "value": 70}]})
    case("sketch_edit", "sketcher call 45", plate, {"sketch": E, "construction": {"geo": 5, "on": True}, "move": {"geo": 4, "vertex": 3, "to": [32, -12]}})
    case("sketch_edit", "sketcher call 46", plate, {"sketch": E, "delete": [7]})
    case("sketch_edit", "sketcher call 47", plate, {"sketch": E, "fillet": {"at": [0, 2], "radius": 2}})
    case("sketch_edit", "sketcher call 44", plate, {"sketch": E, "mirror": {"geos": [4], "about": "y"}})
    case("sketch_edit", "sketcher call 56", plate, {"sketch": E, "fillet": {"geos": [0, 1], "near": [[35, 0], [40, 4]], "radius": 2}})
    case("sketch_edit", "sketcher call 57", plate, {"sketch": E, "trim": {"geo": 1, "at": [-13, 0]}})
    case("sketch_edit", "sketcher call 58", plate, {"sketch": E, "split": {"geo": 4, "at": [0, 10]}})
    case("sketch_edit", "on a padded body", plate_padded, {"sketch": E, "set": {"constraint": 8, "value": 44}})
    case("sketch_edit", "it breaks the pad", plate_padded, {"sketch": E, "delete": [0]}, invalid_after={"Pad": "Pad: Wire is not closed."})
    case("sketch_edit", "move a line, a point", plate, {"move": {"geo": 0, "to": [1, 1]}})
    case("sketch_edit", "move a point", plate, {"move": {"geo": 6, "to": [1, 1]}})
    case("sketch_edit", "move a circle", plate, {"move": {"geo": 4, "to": [1, 1]}})
    case("sketch_edit", "move: no such geometry", plate, {"move": {"geo": 40, "to": [1, 1]}})
    case("sketch_edit", "move: geometry by word", plate, {"move": {"geo": "0", "to": [1, 1]}})
    case("sketch_edit", "move: vertex wrong", plate, {"move": {"geo": 0, "vertex": 4, "to": [1, 1]}})
    case("sketch_edit", "move: vertex true", plate, {"move": {"geo": 0, "vertex": True, "to": [1, 1]}})
    case("sketch_edit", "move: to wrong", plate, {"move": {"geo": 0, "to": [1]}})
    case("sketch_edit", "move: held", plate, {"move": {"geo": 0, "vertex": 1, "to": [1, 1]}}, raises={"moveGeometry": ("ValueError", "Failed to move geometry")})
    case("sketch_edit", "set: several, an angle", plate, {"set": [{"constraint": 9, "value": 25}, {"constraint": "lean", "value": 45}, {"constraint": "hole_d", "value": 8.5}]})
    case("sketch_edit", "set: no such constraint", plate, {"set": [{"constraint": "depth", "value": 5}]})
    case("sketch_edit", "set: no such id", plate, {"set": [{"constraint": 99, "value": 5}]})
    case("sketch_edit", "set: value a word", plate, {"set": [{"constraint": 8, "value": "wide"}]})
    case("sketch_edit", "set: no value to set", plate, {"set": [{"constraint": 0, "value": 5}]})
    case("sketch_edit", "set: a diameter of nothing", plate, {"set": [{"constraint": "hole_d", "value": 0}]})
    case("sketch_edit", "set: a distance of nothing", plate, {"set": [{"constraint": 12, "value": 0}]})
    case("sketch_edit", "set: bound by name", bound_size, {"set": [{"constraint": "plate_width", "value": 50}]})
    case("sketch_edit", "set: bound by id", bound_size, {"set": [{"constraint": 9, "value": 50}]})
    case("sketch_edit", "set: it does not solve", plate, {"set": [{"constraint": 8, "value": 50}, {"constraint": 9, "value": 5}]}, raises={"setDatum": ("ValueError", "Datum 50.00 mm for the constraint with index 8 is invalid")})
    case("sketch_edit", "construction off", plate, {"construction": {"geo": 7, "on": False}})
    case("sketch_edit", "construction: no such geometry", plate, {"construction": {"geo": -1}})
    case("sketch_edit", "rename", plate, {"rename": {"constraint": "lean", "name": "tilt"}})
    case("sketch_edit", "rename to nothing", plate, {"rename": {"constraint": 8}})
    case("sketch_edit", "rename: no such constraint", plate, {"rename": {"constraint": "nope", "name": "x"}})
    case("sketch_edit", "delete constraints", plate, {"deleteConstraints": [0, "lean", 0, 3]})
    case("sketch_edit", "delete constraints: one it has not", plate, {"deleteConstraints": [0, 77]})
    case("sketch_edit", "delete", plate, {"delete": [5, 4, 5]})
    case("sketch_edit", "delete: one it has not", plate, {"delete": [5, 44]})
    case("sketch_edit", "fillet: a chamfer", plate, {"fillet": {"at": [0, 2], "radius": 2, "chamfer": True}})
    case("sketch_edit", "fillet: a chamfer between two", plate, {"fillet": {"geos": [0, 1], "near": [[35, 0], [40, 4]], "radius": 1.5, "chamfer": True}})
    case("sketch_edit", "fillet: a chamfer, old FreeCAD", plate, {"fillet": {"at": [0, 2], "radius": 2, "chamfer": True}}, old=True)
    case("sketch_edit", "fillet: no radius", plate, {"fillet": {"at": [0, 2]}})
    case("sketch_edit", "fillet: at not a pair", plate, {"fillet": {"at": 0, "radius": 2}})
    case("sketch_edit", "fillet: at with three", plate, {"fillet": {"at": [0, 2, 1], "radius": 2}})
    case("sketch_edit", "fillet: a vertex that is a word", plate, {"fillet": {"at": [0, "end"], "radius": 2}})
    case("sketch_edit", "fillet: no such geometry", plate, {"fillet": {"at": [40, 2], "radius": 2}})
    case("sketch_edit", "fillet: three geos", plate, {"fillet": {"geos": [0, 1, 2], "near": [[35, 0], [40, 4]], "radius": 2}})
    case("sketch_edit", "fillet: geos without near", plate, {"fillet": {"geos": [0, 1], "radius": 2}})
    case("sketch_edit", "fillet: neither", plate, {"fillet": {"radius": 2}})
    case("sketch_edit", "fillet: geos, one it has not", plate, {"fillet": {"geos": [0, 41], "near": [[35, 0], [40, 4]], "radius": 2}})
    case("sketch_edit", "fillet: near wrong", plate, {"fillet": {"geos": [0, 1], "near": [[35, 0], [40]], "radius": 2}})
    case("sketch_edit", "fillet: none fits", plate, {"fillet": {"at": [0, 2], "radius": 200}}, raises={"fillet": ("ValueError", "Not able to fillet geometry Id=0, PointPos=2")})
    case("sketch_edit", "fillet: FreeCAD's own error", plate, {"fillet": {"at": [0, 2], "radius": 2}}, raises={"fillet": ("RuntimeError", "BRepFilletAPI failed")})
    case("sketch_edit", "fillet: another value error", plate, {"fillet": {"at": [0, 2], "radius": 2}}, raises={"fillet": ("ValueError", "Wrong arguments")})
    case("sketch_edit", "fillet: nothing came of it", plate, {"fillet": {"at": [0, 2], "radius": 2}}, nothing=["fillet"])
    case("sketch_edit", "trim: a piece left", plate, {"trim": {"geo": 1, "at": [40, 5]}}, trim_splits=True)
    case("sketch_edit", "trim: it will not", plate, {"trim": {"geo": 1, "at": [40, 5]}}, raises={"trim": ("ValueError", "Unable to trim curve")})
    case("sketch_edit", "trim: at wrong", plate, {"trim": {"geo": 1}})
    case("sketch_edit", "trim: no such geometry", plate, {"trim": {"geo": 91, "at": [0, 0]}})
    case("sketch_edit", "split: it will not", plate, {"split": {"geo": 1, "at": [40, 5]}}, raises={"split": ("ValueError", "Failed to split")})
    case("sketch_edit", "split: at wrong", plate, {"split": {"geo": 1, "at": "middle"}})
    case("sketch_edit", "mirror about the origin", plate, {"mirror": {"geos": [4, 5], "about": "origin"}})
    case("sketch_edit", "mirror about x, by default y", plate, {"mirror": {"geos": [0]}})
    case("sketch_edit", "mirror about a line", plate, {"mirror": {"geos": [4], "about": 7}})
    case("sketch_edit", "mirror: nothing to mirror", plate, {"mirror": {"about": "x"}})
    case("sketch_edit", "mirror: about wrong", plate, {"mirror": {"geos": [4], "about": "z"}})
    case("sketch_edit", "mirror: about a line it has not", plate, {"mirror": {"geos": [4], "about": 70}})
    case("sketch_edit", "mirror: it will not", plate, {"mirror": {"geos": [4], "about": "x"}}, raises={"addSymmetric": ("ValueError", "Invalid geometry")})
    case("sketch_edit", "group", plate, {"group": [1, 0, 1]}, fc12=True)
    case("sketch_edit", "group, before 1.2", plate, {"group": [0, 1]})
    case("sketch_edit", "group: one", plate, {"group": [1, 1]})
    case("sketch_edit", "text", plate, {"text": {"text": "AB", "at": [2, 3], "height": 4, "font": font, "construction": True}}, fc12=True)
    case("sketch_edit", "text, before 1.2", plate, {"text": {"text": "AB", "font": font}})
    case("sketch_edit", "text: no words", plate, {"text": {"at": [0, 0]}})
    case("sketch_edit", "text: no height", plate, {"text": {"text": "A", "height": 0, "font": font}})
    case("sketch_edit", "text: at wrong", plate, {"text": {"text": "A", "at": [0]}})
    case("sketch_edit", "expose internal geometry", plate, {"exposeInternal": [5, 5]})
    case("sketch_edit", "expose: a line has none", plate, {"exposeInternal": [5, 0]})
    case("sketch_edit", "expose: one it has not", plate, {"exposeInternal": [50]})
    case("sketch_edit", "axes alignment off", plate, {"removeAxesAlignment": [0, 1]})
    case("sketch_edit", "axes alignment: it will not", plate, {"removeAxesAlignment": [0, 1]}, raises={"removeAxesAlignment": ("RuntimeError", "constraints could not be rewritten")})
    case("sketch_edit", "axes alignment: one it has not", plate, {"removeAxesAlignment": [0, 100]})
    case("sketch_edit", "many at once", plate, {"move": {"geo": 6, "to": [4, 4]}, "set": {"constraint": "plate_height", "value": 22}, "construction": {"geo": 5}, "rename": {"constraint": 12, "name": "gap"},
                                                "deleteConstraints": ["lean"], "delete": [7], "trim": {"geo": 1, "at": [40, 5]}, "split": {"geo": 0, "at": [20, 0]},
                                                "mirror": {"geos": [4], "about": "x"}, "removeAxesAlignment": [2]})
    case("sketch_edit", "a sketch in no body", loose_sketch, {"sketch": "Free", "construction": {"geo": 0}})
    return out
