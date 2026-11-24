# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datask2_data.py runs through the old handler and the
# new data entry of each converted tool of families/param.py, feature_more.py
# and sketch_more.py, on the stand-in FreeCAD (tests/_datask2_standin.py): its
# normal paths and each of its refusals. "sheet call N" is call N of
# private records: models/sheetfem-sheet-model.json, "model call N" of
# partdesign-model.json and "sketcher call N" of sketcher-model.json, with the
# stand-in's furniture in place of the calls before it.

# The family files whose tools were converted.
FILES = ("param", "feature_more", "sketch_more")
# Each converted tool and its group (feature_more.py shares the group "feature" with feature.py, sketch_more.py "sketch" with sketch.py).
CONVERTED = {k: "param" for k in ("param_set", "param_list", "varset_new", "varset_set", "param_remove", "param_bind")}
CONVERTED.update({k: "feature" for k in ("pd_primitive", "pd_gear", "pd_helix", "pd_multitransform", "pd_datum", "pd_binder", "pd_boolean")})
CONVERTED.update({k: "sketch" for k in ("sketch_copy", "sketch_array", "sketch_extend", "sketch_join", "sketch_carbon", "sketch_project", "sketch_to_bspline", "sketch_bspline",
                                        "sketch_merge", "sketch_mirror", "sketch_attach", "sketch_validate")})
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ('param_set', 'sheet call 37'): {'name': 'clearance', 'value': 0.5, 'unit': 'mm', 'ref': 'Params.clearance', 'new': True, 'step': 1},
    ('param_set', 'sheet call 39'): ['refused', 'invalid_input', 'half2 = \'(clearance /\': FreeCAD cannot read it as an expression — a number with unit mm | deg | "" (or another unit FreeCAD knows: cm, m, in, rad), or a formula over other parameters, "width / 2". Nothing was kept.'],
    ('param_set', "it renames a chamfer's edge, found again"): {'refsFound': {'Chamfer': 'relinked'}, 'usedBy': ['Sketch.Constraints.width', 'Pad.Length']},
    ('param_set', 'it breaks two'): ['refused', 'failed', 'width = 0.1 breaks Sketch: Sketch: conflicting (and Pad) — nothing was kept. Choose a value the features can take.'],
    ('param_list', 'sheet call 41'): {'sheet': 'Params', 'refAs': 'Params.<name>'},
    ('varset_new', 'sheet call 32'): ['refused', 'invalid_input', "values.mm: mm is a unit or constant in FreeCAD's expressions — a longer name (mm_value)."],
    ('varset_new', 'sheet call 33'): {'varset': 'NutVars', 'object': 'VarSet', 'set': {'Thickness': {'new': True, 'type': 'PropertyLength'}, 'Chamfer': {'new': True, 'type': 'PropertyAngle'}, 'Count': {'new': True, 'type': 'PropertyInteger'}}, 'refAs': 'VarSet.<name> (or NutVars.<name>: param_bind writes it by name)'},
    ('varset_set', 'sheet call 36'): ['refused', 'invalid_input', "values.size = 'thick': it is a App::PropertyLength — give a value of that kind (Quantity: unit mismatch in 'thick')."],
    ('varset_set', 'sheet call 35'): {'set': {'size': {'new': False, 'type': 'PropertyLength'}}, 'usedBy': ['Pad.Length2']},
    ('param_remove', 'sheet call 42'): {'removed': 'half', 'left': ['width', 'label'], 'step': 1},
    ('param_remove', 'one in use'): ['refused', 'invalid_state', 'width is used by Sketch.Constraints.width, Pad.Length: param_bind each to null (or another expression) first.'],
    ('param_bind', 'sheet call 14'): {'target': 'Sketch.width', 'expression': '<<Params>>.width', 'value': 40.0},
    ('param_bind', 'sheet call 16'): ['refused', 'not_found', "constraint 'Constraints[3]': not a named constraint of Sketch (a constraint is bound by its name, not its number) — they are: width, ref."],
    ('param_bind', 'a bare name'): {'expression': 'Params.width / 2 + 1', 'read': {'as': {'width': 'Params.width'}, 'note': "A bare name is the Params sheet's parameter."}},
    ('param_bind', 'unbind'): {'target': 'Pad.Length', 'expression': None, 'step': 1},
    ('pd_primitive', 'model call 37'): {'feature': 'Cut', 'type': 'SubtractiveCylinder', 'volumeChange': -250.0},
    ('pd_primitive', 'it cuts nothing'): ['refused', 'failed', "SubBox cut nothing — the profile does not meet the body that way. Nothing was kept. at and rotate place it from the body's origin; a subtractive one must overlap the body."],
    ('pd_gear', 'model call 91'): {'feature': 'Spur bore', 'teeth': 20, 'kind': 'gear', 'profile': 'Spur profile', 'pitchDiameter': 20.0, 'outsideDiameter': 22.0, 'bore': 5.0, 'step': 2},
    ('pd_gear', 'a ring gear'): {'feature': '30T teeth', 'outsideDiameter': 40.5, 'volumeChange': -200.0},
    ('pd_gear', 'a sprocket'): {'pitchDiameter': 45.813, 'chainPitch': 9.525, 'roller': 5.04825},
    ('pd_helix', 'model call 75'): {'feature': 'Coil', 'type': 'AdditiveHelix', 'helix': {'pitch': 4.0, 'height': 20.0, 'turns': 3.0}},
    ('pd_helix', 'model call 76'): ['refused', 'invalid_input', 'Two of pitch (mm per turn), height (mm) and turns — the third follows from them; got pitch.'],
    ('pd_multitransform', 'model call 38'): {'feature': 'BoreGrid', 'steps': ['BoreGrid linear 1', 'BoreGrid linear 2']},
    ('pd_multitransform', 'a kind it has not'): ['refused', 'invalid_input', 'steps[1].kind: mirror, linear, polar or scale.'],
    ('pd_datum', 'model call 39'): {'datum': 'BoreAxis', 'how': 'attached to Bore.Edge1', 'direction': [0.0, 0.0, 1.0]},
    ('pd_datum', 'model call 42'): {'datum': 'Top frame', 'kind': 'lcs', 'how': 'placed', 'axes': {'x': [1.0, 0.0, 0.0], 'y': [0.0, 1.0, 0.0], 'z': [0.0, 0.0, 1.0]}},
    ('pd_datum', 'it will not attach to the edge'): ['refused', 'failed', 'The datum line would not attach: Attachment failed — nothing was kept. on takes a point on a circle or arc edge of the body.'],
    ('pd_binder', 'model call 52'): {'binder': 'Sheet binder', 'from': 'Sheet', 'faces': ['Face1'], 'follows': 'Sheet — it updates when that changes', 'next': 'sketch_external { sketch, from: "Sheet binder" … } or sketch_new on one of its faces.'},
    ('pd_binder', 'the body itself'): ['refused', 'invalid_input', 'from: another body than this one — within a body, sketch on its faces directly.'],
    ('pd_boolean', 'model call 96'): {'feature': 'SheetCut', 'volumeChange': -300.0, 'with': ['Cutter']},
    ('pd_boolean', 'with itself'): ['refused', 'invalid_input', 'with: other bodies than Sheet itself.'],
    ('sketch_copy', 'sketcher call 40'): {'did': 'copied by [0.0, -10.0]', 'new': [7], 'step': 1},
    ('sketch_copy', 'turned as it comes, moved'): {'did': 'moved rotated 90° about [0.0, 0.0]', 'new': 'the originals, moved (ids renumbered when rotated or scaled)', 'geometry': 7},
    ('sketch_copy', 'ids it has not'): ['refused', 'invalid_input', 'geometry: [9, -1] not in TourSketch, whose ids are 0 to 6 (sketch_state lists them).'],
    ('sketch_array', 'sketcher call 39'): {'did': '2 rows × 3 columns at [10.0, 6.0]', 'new': [7, 8, 9, 10, 11]},
    ('sketch_array', 'round a quarter'): {'did': '3 round [5.0, 5.0] over 90°', 'new': [7, 8, 9, 10]},
    ('sketch_extend', 'sketcher call 42'): {'extended': 3, 'end': 2, 'by': 15.708},
    ('sketch_extend', 'to one it does not meet'): ['refused', 'not_found', 'Line 0 does not meet geometry 2 going on from its start: try the other end, or give by (mm).'],
    ('sketch_join', 'sketcher call 60'): {'joined': [[0, 2], [1, 1]], 'bspline': 7},
    ('sketch_join', 'sketcher call 61'): ['refused', 'invalid_input', 'a and b: [geometry, vertex] of two different curves in TourSketch (ids 0 to 6), vertex 1 (start) or 2 (end) — FreeCAD cannot join a curve to itself.'],
    ('sketch_carbon', 'sketcher call 31'): {'from': 'TourSketch', 'new': [0, 1, 2, 3, 4, 5, 6]},
    ('sketch_project', 'sketcher call 33'): {'from': 'TourSketch', 'edges': 5, 'ids': [-3, -4, -5, -6, -7]},
    ('sketch_project', 'an edge twice'): ['refused', 'failed', "TourSketch.Edge1 would not come in: Not able to add external shape element — nothing was added. FreeCAD takes outside geometry from the sketch's own body only (from another body: pd_binder first, then project the binder), not from anything built from Empty, and each edge once."],
    ('sketch_to_bspline', 'sketcher call 48'): {'converted': [3], 'dof': 25},
    ('sketch_bspline', 'sketcher call 49'): {'geometry': 6, 'degree': 4, 'poles': 3, 'multiplicities': [5, 1, 5]},
    ('sketch_bspline', 'it could not be lowered'): ['refused', 'failed', "Sketcher refused: the degree of 6 could not be lowered by 2 — the B-spline is as it was. A knot's index runs from 1 to the count of knots, param lies inside its knot range, and a multiplicity cannot pass the degree (the reply of a successful call lists knots and multiplicities)."],
    ('sketch_merge', 'one with outside geometry, the originals removed'): {'sketch': 'Merged sketch', 'from': ['TourSketch', 'Other'], 'constraintsLeftOut': 1, 'geometry': 9},
    ('sketch_mirror', 'sketcher call 51'): {'sketch': 'TourMirror', 'from': 'TourSketch', 'about': 'x', 'geometry': 7},
    ('sketch_attach', 'sketcher call 53'): {'on': 'XY', 'support': 'XY_Plane', 'offset': 3.0, 'rotate': 0.0},
    ('sketch_attach', "moved after a named face's feature"): {'on': 'Pad.Face1', 'support': 'Pad.Face1', 'moved': 'Early now comes after Pad in Body: its support is built before it.'},
    ('sketch_attach', 'onto a pad, another feature built from it'): ['refused', 'invalid_state', 'Pad (whose face it is) is built after TourSketch, and Pocket is built from TourSketch: attaching would make the sketch hang on a later feature (a cyclic support). Attach to an earlier face or plane, or make a new sketch on that face (sketch_new { face }).'],
    ('sketch_validate', 'all of it repaired'): {'found': {'degenerate': 2, 'missingCoincidences': 1, 'invalidConstraints': True, 'redundant': [4]}, 'fixed': ['degenerate geometry removed', 'missing coincidences added', 'invalid constraints removed', 'redundant constraints removed']},
    ('sketch_validate', 'with the auto-constrainer'): {'fixed': ['2 coincident / horizontal / vertical constraints added', 'redundant constraints removed']},
    ('sketch_validate', 'a conflict left after the repair'): ['refused', 'failed', 'Constraints [4] conflict after the repair — nothing was kept; sketch_state names them, sketch_edit deleteConstraints the one that is wrong, then validate again.'],
    ('sketch_validate', 'sketcher call 37'): {'found': {'degenerate': 0, 'missingCoincidences': 0, 'invalidConstraints': False}, 'solver': 'solved'},
}
# Refusals written in the data that no case here reaches. One: varset_new shares varset_set's loop over the properties, and a set
# just made has no property of its own names left to give (the VarSet's own are refused before): the refusal for a value an
# existing property will not take is varset_set's, and is reached there.
# The skeleton workflow's refusals (20 Nov: refs, offset, the container): the handler at BASE had no such input,
# so no case here can compare them; tests/test_datum_skeleton.py reaches each.
UNREACHED = ["varset_new: values.{pname} = {value!r}: it is a {o.getTypeIdOfProperty(pname)} — g",
             'pd_datum: refs or on, not both: on finds one round edge, refs names the referenc',
             'pd_datum: offset: { at: [x,y,z], rotate: { axis, angle } }.',
             "pd_datum: This FreeCAD makes no {kind} datum in a body: {'; '.join(tried)}",
             "pd_datum: The datum {kind} would not attach to {', '.join(att['refs'])} as {att[",
             ]


def cases(fc, tmp, old, new):
    out = []
    V, P = fc.Vec, fc.part

    def case(tool, name, prepare, args, **flags):
        def prep(s):
            fc.state["flags"] = dict(flags)
            prepare(s)
            fc.settle(s)

        out.append((tool, name, prep, args))

    def none(s):
        pass

    _param(fc, case, none, V, P)
    _feature(fc, case, none, V, P)
    _sketch(fc, case, none, V, P)
    return out


def _param(fc, case, none, V, P):
    def sheet(s):
        return fc.params(s, [("width", "=40 mm", "the width"), ("half", "=width / 2"), ("label", "=<<steel>>")])

    def model(s):
        """A body: Sketch (a line 40 long, sized by "width", measured by "ref"), Pad on it bound to Params.width, a Chamfer on the pad's edge; the Params sheet."""
        b = fc.body(s)
        sk = fc.drawing(s, b, "Sketch", [P.LineSegment(V(0, 0, 0), V(40, 0, 0))], [("width", ("DistanceX", 0, 1, 0, 2, 40.0)), ("ref", ("DistanceY", 0, 1, 0, 2, 0.0)), ("Horizontal", 0)])
        sk.__dict__["Constraints"][1].Driving = False
        pad = fc.feature(s, b, "Pad", Profile=sk, Length=10.0)
        fc.feature(s, b, "Chamfer", Base=(pad, ["Edge2"]))
        ss = sheet(s)
        fc.bound(pad, "Length", "Params.width / 4")
        fc.bound(sk, "Constraints.width", "<<Params>>.width")
        return ss

    def sets(s):
        model(s)
        fc.varset(s, "Dims", size=("App::PropertyLength", (55, "mm")), count=("App::PropertyInteger", 3), ratio=("App::PropertyFloat", 0.5))
        fc.bound(s.doc.getObject("Pad"), "Length2", "VarSet.size")

    def two_sets(s):
        sets(s)
        fc.varset(s, "More", note=("App::PropertyString", "steel"))

    T = "param_set"
    case(T, "sheet call 37", none, {"name": "clearance", "value": 0.5, "note": "hole clearance"})
    case(T, "sheet call 38", sheet, {"name": "W", "value": 1})
    case(T, "sheet call 39", sheet, {"name": "half2", "value": "(clearance /"})
    case(T, "one changed, what uses it", model, {"name": "width", "value": 50})
    case(T, "a cell address", none, {"name": "A1", "value": 1})
    case(T, "a unit", none, {"name": "mm", "value": 1})
    case(T, "no name", none, {"value": 1})
    case(T, "a boolean", none, {"name": "on", "value": True})
    case(T, "a list", none, {"name": "on", "value": [1]})
    case(T, "a formula", sheet, {"name": "third", "value": "=width / 3", "note": 7})
    case(T, "degrees", sheet, {"name": "lean", "value": 30, "unit": "deg"})
    case(T, "no unit", sheet, {"name": "count", "value": 3, "unit": ""})
    case(T, "a number FreeCAD cannot read", sheet, {"name": "odd", "value": 3, "unit": "??"})
    case(T, "text in brackets", sheet, {"name": "stuff", "value": "<<oak>>"})
    case(T, "an alias FreeCAD refuses", sheet, {"name": "odd", "value": 1}, bad_alias=["odd"])
    case(T, "it does not evaluate", sheet, {"name": "twice", "value": "nope * 2"})
    case(T, "it breaks the pad", model, {"name": "width", "value": 0.1}, invalid_after={"Pad": "Pad: length too small"})
    case(T, "it breaks two", model, {"name": "width", "value": 0.1}, invalid_after={"Pad": "Pad: length too small", "Sketch": "Sketch: conflicting"})
    case(T, "it breaks the sheet", model, {"name": "bad", "value": "nope + 1"}, invalid_after={"Params": "Invalid cell"})
    case(T, "it renames a chamfer's edge, found again", model, {"name": "width", "value": 60}, invalid_after={"Chamfer": "Invalid edge link"}, heals=["Chamfer"])
    case(T, "one failing from the start", model, {"name": "width", "value": 60}, invalid={"Chamfer": "Invalid edge link"})

    T = "param_list"
    case(T, "nothing", none, {})
    case(T, "sets and no sheet", lambda s: fc.varset(s, "Dims", size=("App::PropertyLength", (55, "mm"))), {})
    case(T, "sheet call 41", model, {})
    case(T, "with sets", two_sets, {})
    case(T, "a hidden variable", sets, {}, hidden_vars=["count"])

    T = "varset_new"
    case(T, "sheet call 32", model, {"name": "NutVars", "properties": {"Thickness": "8.4 mm", "Chamfer": "30 deg", "Count": 2, "mm": 1}})
    case(T, "sheet call 33", model, {"name": "NutVars", "properties": {"Thickness": "8.4 mm", "Chamfer": "30 deg", "Count": 2}})
    case(T, "every kind", none, {"properties": {"size": "55 mm", "depth": "-5 mm", "angle": "30 deg", "count": 3, "ratio": 0.5, "on": True, "note": "text", "force": "3 N", "num": "2.5"}, "group": "Sizes"})
    case(T, "no properties", none, {"name": "Empty"})
    case(T, "a blank name", none, {"name": "  "})
    case(T, "a name not text", none, {"name": 5})
    case(T, "a name taken", sets, {"name": "Dims"})
    case(T, "no VarSet in this FreeCAD", none, {"name": "Dims"}, no_varset=True)
    case(T, "properties not an object", none, {"name": "Dims", "properties": "size"})
    case(T, "a name with a digit first", none, {"name": "Dims", "properties": {"1x": 1}})
    case(T, "a cell address", none, {"name": "Dims", "properties": {"ok": 1, "B2": 1}})
    case(T, "the set's own property", none, {"name": "Dims", "properties": {"Label": "x"}})
    case(T, "a value of no kind", none, {"name": "Dims", "properties": {"size": [1]}})
    case(T, "a unit FreeCAD does not know", none, {"name": "Dims", "properties": {"size": "5 zz"}})
    case(T, "it breaks the pad", sets, {"name": "New", "properties": {"size": "5 mm"}}, invalid_after={"Pad": "Pad: no"})

    T = "varset_set"
    case(T, "none here", model, {"properties": {"size": "60 mm"}})
    case(T, "which one", two_sets, {"properties": {"size": "60 mm"}})
    case(T, "no such set", sets, {"varset": "Nope", "properties": {"size": "60 mm"}})
    case(T, "sheet call 35", sets, {"varset": "Dims", "properties": {"size": "10.8 mm"}})
    case(T, "sheet call 36", sets, {"varset": "Dims", "properties": {"size": "thick"}})
    case(T, "the only one, by its object name too", sets, {"properties": {"size": "60 mm", "extra": "2 in", "ratio": 2.0}, "group": "Other"})
    case(T, "by object name", two_sets, {"varset": "VarSet001", "properties": {"note": "oak"}})
    case(T, "no properties", sets, {"varset": "Dims"})
    case(T, "a unit", sets, {"properties": {"pi": 3}})
    case(T, "a name not a name", sets, {"properties": {"a-b": 3}})
    case(T, "own", sets, {"properties": {"Placement": 3}})
    case(T, "a value of no kind", sets, {"properties": {"x": None}})
    case(T, "a new one FreeCAD refuses", sets, {"properties": {"x": "5 zz"}})
    case(T, "text for a count", sets, {"properties": {"count": "many"}})
    case(T, "it breaks the pad", sets, {"properties": {"size": "0.1 mm"}}, invalid_after={"Pad": "Pad: no"})
    case(T, "it renames a chamfer's edge, found again", sets, {"properties": {"size": "70 mm"}}, invalid_after={"Chamfer": "Invalid edge link"}, heals=["Chamfer"])

    T = "param_remove"
    case(T, "no sheet", none, {"name": "clearance"})
    case(T, "sheet call 47", sheet, {"name": "clearance"})
    case(T, "one in use", model, {"name": "width"})
    case(T, "sheet call 42", model, {"name": "half"})
    case(T, "the last", sheet, {"name": "label"})
    case(T, "it breaks the sheet", model, {"name": "half"}, invalid_after={"Params": "Invalid cell"})

    T = "param_bind"
    case(T, "no target", model, {"expression": "width"})
    case(T, "a target with no dot", model, {"target": "Pad", "expression": "width"})
    case(T, "no such object", model, {"target": "Nope.Length", "expression": "width"})
    case(T, "sheet call 13", model, {"target": "Pad.Length", "expression": "Params.half"})
    case(T, "sheet call 14", model, {"target": "Sketch.width", "expression": "<<Params>>.width"})
    case(T, "sheet call 16", model, {"target": "Sketch.Constraints[3]", "expression": "Params.width"})
    case(T, "a constraint by Constraints.name", model, {"target": "Sketch.Constraints.width", "expression": "width * 2"})
    case(T, "a sketch with no named constraint", lambda s: fc.drawing(s, None, "Bare", [P.LineSegment(V(0, 0, 0), V(4, 0, 0))], [("Horizontal", 0)]), {"target": "Bare.width", "expression": "1 mm"})
    case(T, "a reference dimension", model, {"target": "Sketch.ref", "expression": "width"})
    case(T, "a sketch's own property", model, {"target": "Sketch.MapMode", "expression": "width"})
    case(T, "not a property", model, {"target": "Pad.Nope", "expression": "width"})
    case(T, "unbind", model, {"target": "Pad.Length", "expression": None})
    case(T, "unbind with an empty string", model, {"target": "Sketch.width", "expression": ""})
    case(T, "unbinding breaks", model, {"target": "Pad.Length", "expression": None}, invalid_after={"Pad": "Pad: no"})
    case(T, "a bare name", model, {"target": "Pad.Length", "expression": "width / 2 + 1"})
    case(T, "a variable set by its label", sets, {"target": "Pad.Length", "expression": "Dims.size / 2"})
    case(T, "it does not evaluate", model, {"target": "Pad.Length", "expression": "nope"})
    case(T, "it does not evaluate, with sets", sets, {"target": "Pad.Length", "expression": "nope + 1"})
    case(T, "it does not evaluate, nothing to name", lambda s: fc.feature(s, fc.body(s), "Pad"), {"target": "Pad.Length", "expression": "nope"})
    case(T, "FreeCAD refuses it", model, {"target": "Pad.Length", "expression": "width"}, no_bind="Pad.Length reads itself")
    case(T, "it breaks two", model, {"target": "Pad.Length", "expression": "width"}, invalid_after={"Pad": "Pad: no", "Chamfer": "No edges"})
    case(T, "a number as the expression", model, {"target": "Pad.Length", "expression": 5})
    case(T, "a value that cannot be read back", model, {"target": "Pad.Length.Value", "expression": "width"})


def _feature(fc, case, none, V, P):
    def empty(s):
        b = fc.body(s)
        fc.sketch(s, b, "Wire")
        return b

    def solid(s):
        """A body with a 10 mm pad (1000 mm³) on Sketch, a pocket Bore in it, and a second sketch, Wire (a circle and a construction line)."""
        b = fc.body(s)
        sk = fc.sketch(s, b, "Sketch")
        fc.feature(s, b, "Pad", Profile=sk, Length=10.0)
        fc.feature(s, b, "Pocket", "Bore", Profile=sk)
        fc.sketch(s, b, "Wire", geometry=("Circle", fc.geo("LineSegment", True)))
        return b

    def bodies(s):
        """Sheet (a solid), Cutter (a solid), Cap (empty)."""
        for name in ("Sheet", "Cutter"):
            b = fc.body(s, name)
            fc.feature(s, b, "Pad", name + "Base", Profile=fc.sketch(s, b, name + "Sketch"), Length=10.0)
        fc.body(s, "Cap")

    T = "pd_primitive"
    case(T, "no body", none, {"kind": "box"})
    case(T, "model call 35", empty, {"body": "Body", "kind": "box", "size": {"length": 40, "width": 30, "height": 10}, "at": [60, 0, 0], "name": "PlateBase"}, effect={"PlateBase": 12000.0})
    case(T, "model call 37", solid, {"kind": "cylinder", "size": {"radius": 2, "height": 20}, "at": [68, 8, -5], "subtractive": True, "name": "Cut"}, effect={"Cut": -250.0})
    for kind in ("box", "cylinder", "sphere", "cone", "ellipsoid", "torus", "prism", "wedge"):
        label = {"box": "Box", "cylinder": "Cylinder", "sphere": "Sphere", "cone": "Cone", "ellipsoid": "Ellipsoid", "torus": "Torus", "prism": "Prism", "wedge": "Wedge"}[kind]
        case(T, f"a {kind} as it comes", solid, {"kind": kind}, effect={label: 300.0})
    case(T, "a prism of 6.5 sides, turned", solid, {"kind": "prism", "size": {"sides": 6.5, "height": 3}, "rotate": {"axis": [1, 0, 0], "angle": 90}}, effect={"Prism": 80.0})
    case(T, "kind wrong", solid, {"kind": "cube"})
    case(T, "kind missing", solid, {})
    case(T, "subtractive with no solid", empty, {"kind": "box", "subtractive": True})
    case(T, "size not an object", solid, {"kind": "box", "size": [1, 2, 3]})
    case(T, "a size it does not take", solid, {"kind": "sphere", "size": {"radius": 3, "height": 2}})
    case(T, "a size not a number", solid, {"kind": "box", "size": {"length": "long"}})
    case(T, "a size a boolean", solid, {"kind": "box", "size": {"width": True}})
    case(T, "at wrong", solid, {"kind": "box", "at": [1, 2]})
    case(T, "it adds nothing", solid, {"kind": "box"})
    case(T, "it cuts nothing", solid, {"kind": "box", "subtractive": True})
    case(T, "it fails", solid, {"kind": "torus", "name": "Ring"}, effect={"Ring": 10.0}, invalid_after={"Ring": "Torus: radius2 must be smaller"})

    T = "pd_gear"
    case(T, "no body", none, {})
    case(T, "model call 91", empty, {"body": "Body", "kind": "gear", "teeth": 20, "module": 1, "thickness": 5, "bore": 5, "at": [-60, 60, 0], "name": "Spur"}, effect={"Spur bore": -20.0})
    case(T, "as it comes", empty, {})
    case(T, "shifted, coarse", empty, {"shift": 0.3, "highPrecision": False, "pressureAngle": 25, "module": 2, "teeth": 12})
    case(T, "shift where FreeCAD has none", empty, {"shift": 0.3}, no_shift=True)
    case(T, "a sprocket", empty, {"kind": "sprocket", "teeth": 15})
    case(T, "a sprocket, its chain given", empty, {"kind": "sprocket", "teeth": 15, "pitch": 12.7, "roller": 7.9, "bore": 8, "name": "Chainwheel"}, effect={"Chainwheel bore": -30.0})
    case(T, "a ring gear", empty, {"internal": True, "teeth": 30, "rim": 4}, effect={"Ring gear 30T": 900.0})
    case(T, "a ring gear, named", empty, {"internal": True, "name": "Annulus"}, effect={"Annulus": 900.0})
    case(T, "a ring gear whose ring adds nothing", empty, {"internal": True})
    case(T, "rim zero", empty, {"internal": True, "rim": 0})
    case(T, "kind wrong", empty, {"kind": "rack"})
    case(T, "two teeth", empty, {"teeth": 2})
    case(T, "no thickness", empty, {"thickness": 0})
    case(T, "module zero", empty, {"module": 0})
    case(T, "an internal sprocket", empty, {"kind": "sprocket", "internal": True})
    case(T, "a bore below zero", empty, {"bore": -2})
    case(T, "a bore in a ring gear", empty, {"bore": 4, "internal": True})
    case(T, "a pad of no volume in an empty body", empty, {}, effect={"Gear 20T pad": 0.0})
    case(T, "the bore fails", empty, {"bore": 50}, invalid_after={"Gear 20T pad bore": "Cylinder: too large"})

    T = "pd_helix"
    case(T, "model call 75", solid, {"body": "Body", "profile": "Wire", "axis": 1, "pitch": 4, "height": 20, "name": "Coil"}, effect={"Coil": 150.0})
    case(T, "model call 76", solid, {"profile": "Wire", "pitch": 4})
    case(T, "all three", solid, {"profile": "Wire", "pitch": 4, "height": 20, "turns": 5})
    case(T, "none of them", solid, {"profile": "Wire"})
    case(T, "no such profile", solid, {"profile": "Nope", "pitch": 4, "height": 20})
    case(T, "pitch zero", solid, {"profile": "Wire", "pitch": 0, "height": 20})
    case(T, "turns not a number", solid, {"profile": "Wire", "pitch": 2, "turns": "five"})
    case(T, "height a boolean", solid, {"profile": "Wire", "height": True, "turns": 3})
    case(T, "pitch and turns, tapered, left-handed, reversed", solid, {"profile": "Wire", "pitch": 2, "turns": 5, "taper": 5, "leftHanded": True, "reversed": True}, effect={"Helix": 90.0})
    case(T, "a flat spiral", solid, {"profile": "Wire", "height": 0, "turns": 5, "growth": 2, "axis": "z"}, effect={"Helix": 90.0})
    case(T, "growth where FreeCAD has none", solid, {"profile": "Wire", "height": 10, "turns": 5, "growth": 2}, effect={"Helix": 90.0}, no_growth=True)
    case(T, "growth with pitch", solid, {"profile": "Wire", "pitch": 2, "turns": 5, "growth": 2})
    case(T, "growth and taper", solid, {"profile": "Wire", "height": 10, "turns": 5, "growth": 2, "taper": 3})
    case(T, "height zero without growth", solid, {"profile": "Wire", "height": 0, "turns": 5})
    case(T, "a mode FreeCAD does not take", solid, {"profile": "Wire", "pitch": 2, "turns": 5}, effect={"Helix": 90.0}, refuses={"AdditiveHelix": ("Mode",)})
    case(T, "a thread cut", solid, {"profile": "Wire", "pitch": 1, "height": 8, "subtractive": True, "name": "Thread"}, effect={"Thread": -40.0})
    case(T, "a cut with no solid", empty, {"profile": "Wire", "pitch": 1, "height": 8, "subtractive": True})
    case(T, "a cut that misses", solid, {"profile": "Wire", "pitch": 1, "height": 8, "subtractive": True})

    T = "pd_multitransform"
    two = [{"kind": "linear", "direction": "x", "occurrences": 2, "spacing": 24}, {"kind": "linear", "direction": "y", "occurrences": 2, "spacing": 14}]
    case(T, "model call 38", solid, {"body": "Body", "features": ["Bore"], "name": "BoreGrid", "steps": two})
    case(T, "every kind of step", solid, {"features": "Bore", "steps": [{"kind": "mirror"}, {"kind": "mirror", "plane": "XZ"}, {"kind": "polar", "occurrences": 6},
                                                                      {"kind": "polar", "axis": "x", "angle": 90, "occurrences": 3, "reversed": True},
                                                                      {"kind": "linear", "length": 30, "occurrences": 4, "reversed": True}, {"kind": "scale", "occurrences": 4, "reversed": True},
                                                                      {"kind": "scale", "factor": 1.5}]})
    case(T, "no solid", empty, {"features": ["Bore"], "steps": two})
    case(T, "no features", solid, {"steps": two})
    case(T, "a feature not in the body", solid, {"features": ["Nope"], "steps": two})
    case(T, "no steps", solid, {"features": ["Bore"]})
    case(T, "a step not an object", solid, {"features": ["Bore"], "steps": [two[0], "mirror"]})
    case(T, "a kind it has not", solid, {"features": ["Bore"], "steps": [two[0], {"kind": "helix"}]})
    case(T, "one occurrence", solid, {"features": ["Bore"], "steps": [{"kind": "polar", "occurrences": 1}]})
    case(T, "a linear step with no spacing", solid, {"features": ["Bore"], "steps": [{"kind": "linear"}]})
    case(T, "a spacing of zero", solid, {"features": ["Bore"], "steps": [{"kind": "linear", "spacing": 0}]})
    case(T, "a plane it has not", solid, {"features": ["Bore"], "steps": [{"kind": "mirror", "plane": "Nope"}]})
    case(T, "it fails", solid, {"features": ["Bore"], "steps": two}, invalid_after={"MultiTransform": "Transformation failed"})

    T = "pd_datum"
    case(T, "model call 39", solid, {"body": "Body", "kind": "line", "on": {"near": [68, 10, 10]}, "name": "BoreAxis"})
    case(T, "model call 40", solid, {"kind": "line", "at": [80, 15, 0], "direction": [0, 0, 1], "name": "MidAxis"})
    case(T, "model call 41", solid, {"kind": "point", "at": [60, 0, 10], "name": "Corner point"})
    case(T, "model call 42", solid, {"kind": "lcs", "at": [80, 15, 10], "rotate": {"axis": [0, 0, 1], "angle": 90}, "name": "Top frame"})
    case(T, "as they come", empty, {"kind": "line"})
    case(T, "a point on a round edge, its kind given", solid, {"kind": "point", "on": {"n": 4, "kind": "arc"}})
    case(T, "a frame on an edge", solid, {"kind": "lcs", "on": {"n": 2}})
    case(T, "kind wrong", solid, {"kind": "plane"})
    case(T, "on not an object", solid, {"kind": "line", "on": "Edge4"})
    case(T, "on with no solid", empty, {"kind": "line", "on": {"near": [0, 0, 0]}})
    case(T, "on with no edge there", solid, {"kind": "line", "on": {"miss": True}})
    case(T, "direction zero", solid, {"kind": "line", "direction": [0, 0, 0]})
    case(T, "at wrong", solid, {"kind": "point", "at": "here"})
    case(T, "it will not attach", solid, {"kind": "point", "name": "P"}, invalid_after={"P": "Attachment failed"})
    case(T, "it will not attach to the edge", solid, {"kind": "line", "on": {"n": 1}, "name": "L"}, invalid_after={"L": "Attachment failed"})

    T = "pd_binder"
    case(T, "model call 52", bodies, {"body": "Cap", "from": "Sheet", "faces": [{"at": [75, 60, 0], "normal": [0, 0, -1]}]})
    case(T, "the whole of it, frozen, named", bodies, {"body": "Cap", "from": "Sheet", "frozen": True, "name": "Ref"})
    case(T, "two faces of a feature", bodies, {"body": "Cap", "from": "CutterBase", "faces": [{"at": [0, 0, 0], "n": 2}, {"at": [0, 0, 0], "n": 3}]})
    case(T, "frozen where FreeCAD has no BindMode", bodies, {"body": "Cap", "from": "Sheet", "frozen": True}, no_bindmode=True)
    case(T, "no from", bodies, {"body": "Cap"})
    case(T, "no such object", bodies, {"body": "Cap", "from": "Nope"})
    case(T, "the body itself", bodies, {"body": "Sheet", "from": "Sheet"})
    case(T, "a feature of the body itself", bodies, {"body": "Sheet", "from": "SheetBase"})
    case(T, "a body with no shape", bodies, {"body": "Sheet", "from": "Cap"})
    case(T, "no face there", bodies, {"body": "Cap", "from": "Sheet", "faces": [{"at": [0, 0, 0], "miss": True}]})
    case(T, "a face by its index", bodies, {"body": "Cap", "from": "Sheet", "faces": ["Face1"]})
    case(T, "it does not take", bodies, {"body": "Cap", "from": "Sheet"}, invalid_after={"Binder": "Binder: cyclic"})

    T = "pd_boolean"
    case(T, "model call 96", bodies, {"body": "Sheet", "op": "cut", "with": ["Cutter"], "name": "SheetCut"}, effect={"SheetCut": -300.0})
    case(T, "a fuse, one name", bodies, {"body": "Sheet", "with": "Cutter"}, effect={"Fuse": 400.0})
    case(T, "the common part", bodies, {"body": "Sheet", "op": "common", "with": ["Cutter"]}, effect={"Common": -600.0})
    case(T, "op wrong", bodies, {"body": "Sheet", "op": "xor", "with": ["Cutter"]})
    case(T, "with nothing", bodies, {"body": "Sheet"})
    case(T, "with itself", bodies, {"body": "Sheet", "with": ["Cutter", "Sheet"]})
    case(T, "with no such body", bodies, {"body": "Sheet", "with": ["Nope"]})
    case(T, "no solid", bodies, {"body": "Cap", "with": ["Cutter"]})
    case(T, "a fuse that adds nothing", bodies, {"body": "Sheet", "with": ["Cutter"]})
    case(T, "a cut that cuts nothing", bodies, {"body": "Sheet", "op": "cut", "with": ["Cutter"]})


def _sketch(fc, case, none, V, P):
    def curves():
        return [P.LineSegment(V(0, 0, 0), V(40, 0, 0)), P.LineSegment(V(40, 0, 0), V(40, 20, 0)), P.Circle(V(10, 10, 0), None, 3.0),
                P.ArcOfCircle(P.Circle(V(20, 10, 0), None, 5.0), 0.0, 1.5708), (P.LineSegment(V(0, 0, 0), V(0, 30, 0)), True), P.Point(V(3, 3, 0)),
                P.BSplineCurve([V(0, 20, 0), V(5, 25, 0), V(10, 20, 0)])]

    CONS = [("Horizontal", 0), ("Vertical", 1), ("width", ("DistanceX", 0, 1, 0, 2, 40.0)), ("Radius", 2, 3.0)]

    def tour(s):
        """Body with TourSketch: two lines, a circle, an arc, a construction line, a point and a B-spline; Other (a line tied to outside geometry) and Empty after it."""
        b = fc.body(s)
        fc.drawing(s, b, "TourSketch", curves(), CONS)
        fc.drawing(s, b, "Other", [P.LineSegment(V(0, 0, 0), V(0, 9, 0)), (P.Circle(V(1, 1, 0), None, 1.0), True)], [("Vertical", 0), ("PointOnObject", 0, 1, -9), ("Equal", 0, 1)])
        fc.drawing(s, b, "Empty")
        return b

    def padded(s):
        """… a pad on TourSketch, Early (a sketch before the pad that nothing uses) and Top after the pad."""
        b = fc.body(s)
        early = fc.drawing(s, b, "Early", [P.Circle(V(0, 0, 0), None, 2.0)])
        early.__dict__.update(AttachmentSupport=[(s.doc.getObject("XY_Plane"), "")], MapMode="FlatFace")
        sk = fc.drawing(s, b, "TourSketch", curves(), CONS)
        fc.feature(s, b, "Pad", Profile=sk, Length=10.0)
        fc.drawing(s, b, "Top", [P.Circle(V(0, 0, 0), None, 2.0), P.LineSegment(V(0, 0, 0), V(4, 0, 0))])
        return b

    def twice(s):
        padded(s)
        fc.feature(s, s.doc.getObject("Body"), "Pocket", Profile=s.doc.getObject("TourSketch"))

    def loose(s):
        fc.drawing(s, None, "Loose", [P.LineSegment(V(0, 0, 0), V(4, 0, 0)), (P.LineSegment(V(0, 0, 0), V(0, 4, 0)), True)], [("Horizontal", 0)])
        fc.drawing(s, None, "Loose2", [P.ArcOfCircle(P.Circle(V(2, 1, 0), None, 5.0), 0.5, 2.0)])

    def doubled(same=True):
        def prepare(s):
            b = fc.body(s)
            fc.drawing(s, b, "TourSketch", curves(), CONS + [("DistanceX", 0, 1, 0, 2, 40.0 if same else 50.0)])
        return prepare

    T = "sketch_copy"
    case(T, "no sketch", none, {"by": [1, 1]})
    case(T, "sketcher call 40", tour, {"sketch": "TourSketch", "geometry": [2], "by": [0, -10]})
    case(T, "sketcher call 41", tour, {"sketch": "TourSketch", "geometry": [6], "scale": {"center": [30, -10], "factor": 2}})
    case(T, "all of it, cloned", tour, {"sketch": "TourSketch", "by": [5, 5], "clone": True})
    case(T, "moved by", tour, {"sketch": "TourSketch", "geometry": [0, 1], "by": [5, 5], "move": True})
    case(T, "turned", tour, {"sketch": "TourSketch", "geometry": [0], "rotate": {"center": [1, 2], "angle": 30}})
    case(T, "turned as it comes, moved", tour, {"sketch": "TourSketch", "geometry": [1, 0], "rotate": {}, "move": True})
    case(T, "scaled as it comes", tour, {"sketch": "TourSketch", "geometry": [2], "scale": {}})
    case(T, "a factor of zero", tour, {"sketch": "TourSketch", "geometry": [2], "scale": {"factor": 0}})
    case(T, "none of the three", tour, {"sketch": "TourSketch", "geometry": [2]})
    case(T, "geometry not a list", tour, {"sketch": "TourSketch", "geometry": 2, "by": [1, 1]})
    case(T, "geometry empty", tour, {"sketch": "TourSketch", "geometry": [], "by": [1, 1]})
    case(T, "geometry with a boolean", tour, {"sketch": "TourSketch", "geometry": [True], "by": [1, 1]})
    case(T, "ids it has not", tour, {"sketch": "TourSketch", "geometry": [0, 9, -1], "by": [1, 1]})
    case(T, "by wrong", tour, {"sketch": "TourSketch", "by": [1]})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "geometry": [0], "by": [5, 5], "move": True}, invalid_after={"Pad": "Pad: Wire is not closed."})

    T = "sketch_array"
    case(T, "sketcher call 39", tour, {"sketch": "TourSketch", "geometry": [2], "rows": 2, "cols": 3, "spacing": [10, 6]})
    case(T, "as it comes", tour, {"sketch": "TourSketch", "geometry": [2]})
    case(T, "one column, constrained, cloned", tour, {"sketch": "TourSketch", "geometry": [2], "rows": 3, "cols": 1, "constrain": True, "clone": True})
    case(T, "round, as it comes", tour, {"sketch": "TourSketch", "geometry": [2], "polar": {"count": 4}})
    case(T, "round a quarter", tour, {"sketch": "TourSketch", "geometry": [2, 3], "polar": {"center": [5, 5], "count": 3, "angle": 90}})
    case(T, "round, one", tour, {"sketch": "TourSketch", "geometry": [2], "polar": {"count": 1}})
    case(T, "no rows", tour, {"sketch": "TourSketch", "geometry": [2], "rows": 0})
    case(T, "one in all", tour, {"sketch": "TourSketch", "geometry": [2], "rows": 1, "cols": 1})
    case(T, "no step along x", tour, {"sketch": "TourSketch", "geometry": [2], "spacing": [0, 5]})
    case(T, "no step along y", tour, {"sketch": "TourSketch", "geometry": [2], "rows": 2, "spacing": [5, 0]})
    case(T, "ids it has not", tour, {"sketch": "TourSketch", "geometry": [12]})
    case(T, "geometry not ids", tour, {"sketch": "TourSketch", "geometry": ["a"]})
    case(T, "FreeCAD refuses it", tour, {"sketch": "TourSketch", "geometry": [2], "constrain": True}, raises={"addRectangularArray": ("ValueError", "Cannot constrain a circle")})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "geometry": [2]}, invalid_after={"Pad": "Pad: profile crosses itself"})

    T = "sketch_extend"
    case(T, "sketcher call 42", tour, {"sketch": "TourSketch", "geo": 3, "end": 2, "by": 15.708})
    case(T, "sketcher call 43", tour, {"sketch": "TourSketch", "geo": 1, "end": 2, "by": 2})
    case(T, "shortened at the start", tour, {"sketch": "TourSketch", "geo": 0, "end": 1, "by": -3})
    case(T, "as far as another", tour, {"sketch": "TourSketch", "geo": 0, "to": 1})
    case(T, "no geo", tour, {"sketch": "TourSketch", "by": 2})
    case(T, "geo it has not", tour, {"sketch": "TourSketch", "geo": 9, "by": 2})
    case(T, "a circle", tour, {"sketch": "TourSketch", "geo": 2, "by": 2})
    case(T, "end three", tour, {"sketch": "TourSketch", "geo": 0, "end": 3, "by": 2})
    case(T, "end a boolean", tour, {"sketch": "TourSketch", "geo": 0, "end": True, "by": 2})
    case(T, "to for an arc", tour, {"sketch": "TourSketch", "geo": 3, "to": 1})
    case(T, "to itself", tour, {"sketch": "TourSketch", "geo": 0, "to": 0})
    case(T, "to one it has not", tour, {"sketch": "TourSketch", "geo": 0, "to": 44})
    case(T, "to one it does not meet", tour, {"sketch": "TourSketch", "geo": 0, "end": 1, "to": 2}, gap=4.0)
    case(T, "to one it reaches already", tour, {"sketch": "TourSketch", "geo": 0, "to": 1}, meet=(40.0, 0.0, 0.0))
    case(T, "by nothing", tour, {"sketch": "TourSketch", "geo": 0})
    case(T, "by not a number", tour, {"sketch": "TourSketch", "geo": 0, "by": "far"})
    case(T, "its constraints hold it", tour, {"sketch": "TourSketch", "geo": 0, "by": 5}, raises={"extend": ("ValueError", "Not able to extend")})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "geo": 0, "by": 5}, invalid_after={"Pad": "Pad: Wire is not closed."})

    T = "sketch_join"
    case(T, "sketcher call 60", tour, {"sketch": "TourSketch", "a": [0, 2], "b": [1, 1], "continuity": 0})
    case(T, "sketcher call 61", tour, {"sketch": "TourSketch", "a": [0, 2], "b": [0, 1]})
    case(T, "smooth", tour, {"sketch": "Other", "a": [0, 2], "b": [1, 1], "continuity": 1})
    case(T, "not pairs", tour, {"sketch": "TourSketch", "a": [0, 2], "b": 1})
    case(T, "a vertex of three", tour, {"sketch": "TourSketch", "a": [0, 3], "b": [1, 1]})
    case(T, "continuity two", tour, {"sketch": "TourSketch", "a": [0, 2], "b": [1, 1], "continuity": 2})
    case(T, "FreeCAD refuses it", tour, {"sketch": "TourSketch", "a": [0, 2], "b": [2, 1]}, raises={"join": ("ValueError", "Cannot join closed curves")})
    case(T, "nothing came of it", tour, {"sketch": "Other", "a": [0, 2], "b": [1, 1]}, nothing=["join"])
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "a": [0, 2], "b": [1, 1]}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_carbon"
    case(T, "sketcher call 31", tour, {"sketch": "Empty", "from": "TourSketch"})
    case(T, "as construction", tour, {"sketch": "Other", "from": "TourSketch", "construction": True})
    case(T, "from itself", tour, {"sketch": "Other", "from": "Other"})
    case(T, "no such source", tour, {"sketch": "Other", "from": "Nope"})
    case(T, "FreeCAD refuses it", tour, {"sketch": "Other", "from": "TourSketch"}, raises={"carbonCopy": ("ValueError", "Selection is not valid")})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "from": "Top"}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_project"
    case(T, "sketcher call 33", tour, {"sketch": "Empty", "from": "TourSketch"})
    case(T, "edges by name and by where", tour, {"sketch": "Empty", "from": "TourSketch", "edges": ["Edge1", "Vertex2", {"n": 3}]})
    case(T, "defining", tour, {"sketch": "Empty", "from": "TourSketch", "edges": ["Edge1"], "defining": True})
    case(T, "defining where FreeCAD has none", tour, {"sketch": "Empty", "from": "TourSketch", "edges": ["Edge1"], "defining": True}, no_defining=True)
    case(T, "no such object", tour, {"sketch": "Empty", "from": "Nope"})
    case(T, "no from", tour, {"sketch": "Empty"})
    case(T, "an edge not named", tour, {"sketch": "Empty", "from": "TourSketch", "edges": ["Edge1", 5]})
    case(T, "nothing to bring in", tour, {"sketch": "Other", "from": "Empty"})
    case(T, "an edge twice", tour, {"sketch": "Empty", "from": "TourSketch", "edges": ["Edge1", "Edge1"]})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "from": "Top"}, invalid_after={"Pad": "Pad: cyclic"})

    T = "sketch_to_bspline"
    case(T, "sketcher call 48", tour, {"sketch": "TourSketch", "geometry": [3]})
    case(T, "two", tour, {"sketch": "TourSketch", "geometry": [0, 2]})
    case(T, "all of Other", tour, {"sketch": "Other"})
    case(T, "a point", tour, {"sketch": "TourSketch", "geometry": [1, 5]})
    case(T, "ids it has not", tour, {"sketch": "TourSketch", "geometry": [30]})
    case(T, "geometry not a list", tour, {"sketch": "TourSketch", "geometry": "all"})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "geometry": [0]}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_bspline"
    case(T, "sketcher call 49", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree", "by": 1})
    case(T, "sketcher call 50", tour, {"sketch": "TourSketch", "geo": 6, "op": "knot", "param": 0.5, "multiplicity": 1})
    case(T, "a knot's multiplicity", tour, {"sketch": "TourSketch", "geo": 6, "op": "knot", "knot": 2, "by": -1})
    case(T, "a knot as it comes", tour, {"sketch": "TourSketch", "geo": 6, "op": "knot"})
    case(T, "degree as it comes", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree"})
    case(T, "lowered", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree", "by": -1})
    case(T, "lowered where FreeCAD cannot", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree", "by": -1}, no_lower=True)
    case(T, "it could not be lowered", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree", "by": -2}, lower_fails=True)
    case(T, "by nothing", tour, {"sketch": "TourSketch", "geo": 6, "op": "degree", "by": 0})
    case(T, "op wrong", tour, {"sketch": "TourSketch", "geo": 6, "op": "poles"})
    case(T, "not a B-spline", tour, {"sketch": "TourSketch", "geo": 0, "op": "degree"})
    case(T, "geo it has not", tour, {"sketch": "TourSketch", "geo": 60, "op": "degree"})
    case(T, "geo not a number", tour, {"sketch": "TourSketch", "geo": "6", "op": "degree"})
    case(T, "a knot FreeCAD refuses", tour, {"sketch": "TourSketch", "geo": 6, "op": "knot", "param": 7}, raises={"insertBSplineKnot": ("ValueError", "Knot out of range")})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "geo": 6, "op": "degree"}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_merge"
    case(T, "sketcher call 52", tour, {"sketches": ["TourSketch", "Empty"], "name": "TourBoth"})
    case(T, "one with outside geometry, the originals removed", tour, {"sketches": ["TourSketch", "Other"], "remove": True})
    case(T, "outside a body", loose, {"sketches": ["Loose", "Loose2"]})
    case(T, "one name", tour, {"sketches": ["TourSketch"]})
    case(T, "not a list", tour, {"sketches": "TourSketch"})
    case(T, "one it has not", tour, {"sketches": ["TourSketch", "Nope"]})
    case(T, "it breaks the pad", padded, {"sketches": ["TourSketch", "Top"], "remove": True}, invalid_after={"Pad": "Pad: no profile"})

    T = "sketch_mirror"
    case(T, "sketcher call 51", tour, {"sketch": "TourSketch", "about": "x", "name": "TourMirror"})
    case(T, "left to right", tour, {"sketch": "TourSketch"})
    case(T, "about the origin, a name taken", tour, {"sketch": "TourSketch", "about": "origin", "name": "Other"})
    case(T, "outside a body", loose, {"sketch": "Loose2", "about": "y"})
    case(T, "an empty one", tour, {"sketch": "Empty"})
    case(T, "an attached one", padded, {"sketch": "Early"})
    case(T, "about wrong", tour, {"sketch": "TourSketch", "about": "z"})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch"}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_attach"
    case(T, "sketcher call 53", tour, {"sketch": "TourSketch", "plane": "XY", "offset": 3})
    case(T, "flipped and turned on a later feature's face", padded, {"sketch": "Top", "plane": "Pad.Face3", "flip": True, "rotate": 45})
    case(T, "on a face found, the sketch moved after it", padded, {"sketch": "Early", "face": {"at": [0, 0, 10], "n": 2}})
    case(T, "moved after a named face's feature", padded, {"sketch": "Early", "plane": "Pad.Face1", "offset": -1})
    case(T, "it could not be moved", padded, {"sketch": "Early", "plane": "Pad.Face1"}, no_insert=True)
    case(T, "onto the pad built from it", padded, {"sketch": "TourSketch", "plane": "Pad.Face1"})
    case(T, "onto a pad, another feature built from it", twice, {"sketch": "TourSketch", "plane": "Pad.Face1"})
    case(T, "in no body", loose, {"sketch": "Loose", "plane": "XY"})
    case(T, "neither", tour, {"sketch": "TourSketch"})
    case(T, "both", tour, {"sketch": "TourSketch", "plane": "XY", "face": {"at": [0, 0, 0]}})
    case(T, "a plane it has not", tour, {"sketch": "TourSketch", "plane": "Nope"})
    case(T, "it will not attach", padded, {"sketch": "Top", "plane": "XZ"}, invalid_after={"Top": "Attachment: not a plane"})
    case(T, "it breaks the pad", padded, {"sketch": "TourSketch", "plane": "YZ"}, invalid_after={"Pad": "Pad: no"})

    T = "sketch_validate"
    case(T, "sketcher call 37", tour, {"sketch": "TourSketch"})
    case(T, "sketcher call 38", tour, {"sketch": "TourSketch", "fix": True})
    case(T, "what it finds", doubled(), {"sketch": "TourSketch", "precision": 0.1}, degenerate=2, missing=1, invalid_cons=True, malformed=[1])
    case(T, "an older Sketcher", tour, {"sketch": "TourSketch"}, old_detect=True, missing=3)
    case(T, "a Sketcher with no detectors", tour, {"sketch": "TourSketch"}, no_detect=True)
    case(T, "all of it repaired", doubled(), {"sketch": "TourSketch", "fix": True}, degenerate=2, missing=1, invalid_cons=True)
    case(T, "with the auto-constrainer", tour, {"sketch": "TourSketch", "fix": True, "autoconstrain": True, "angle": 2}, auto_adds=2)
    case(T, "coincidences FreeCAD will not add", tour, {"sketch": "TourSketch", "fix": True}, missing=2, raises={"makeMissingPointOnPointCoincident": ("ValueError", "No missing coincidences")})
    case(T, "a conflict left after the repair", doubled(False), {"sketch": "TourSketch", "fix": True})
    case(T, "the repair stops", tour, {"sketch": "TourSketch", "fix": True}, invalid_cons=True, raises={"validateConstraints": ("RuntimeError", "Sketch is corrupt")})
    case(T, "the repair breaks the pad", padded, {"sketch": "TourSketch", "fix": True}, degenerate=1, invalid_after={"Pad": "Pad: Wire is not closed."})
