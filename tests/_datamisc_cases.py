# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datamisc_data.py runs through the old handler and the
# new data entry of each converted tool of families/measure.py,
# inspection.py, notes.py, robot.py and ifc.py, on the stand-in FreeCAD
# (tests/_datamisc_standin.py): its normal paths and each of its refusals.
import json
import os

# The family files whose tools were converted.
FILES = ("measure", "inspection", "notes", "robot", "ifc")
# Each converted tool and its group (ifc.py's are of the group "bim", "family": "ifc").
CONVERTED = {**{k: "measure" for k in ("measure_keep", "shape_query", "measure", "section", "measure_mass", "clearance")},
             **{k: "inspection" for k in ("insp_run", "insp_update", "insp_read", "insp_list", "insp_faces", "insp_export")},
             **{k: "notes" for k in ("note_add", "note_list", "note_answer", "note_done", "note_delete", "steps_list", "steps_render")},
             **{k: "robot" for k in ("robot_trajectory", "robot_new", "robot_move", "robot_path", "robot_run", "robot_export")},
             **{k: "bim" for k in ("ifc_open", "ifc_find", "ifc_edit", "ifc_remove", "ifc_save", "ifc_diff")}}
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {('shape_query', 'two listed, more left'): {'found': 6, 'more': 4},
 ('shape_query', 'limit 0'): ['refused', 'invalid_input', 'limit: how many to list, 1 … 500 (20 by default); found counts them all.'],
 ('measure', 'two parallel faces'): {'distance': 0.0, 'angle': 180.0, 'gap': 10.0},
 ('measure', 'a face and a line'): {'angle': 90.0, 'angleIs': "between the line and the face's plane"},
 ('measure', 'the same face twice'): ['refused', 'invalid_input', 'a and b are the same (Block.Face1): give two different things, or a alone to read one.'],
 ('section', 'two regions with holes'): {'area': 80.0, 'regions': 2},
 ('section', 'the plane misses'): ['refused', 'not_found', 'The plane through [0.0, 0.0, 50.0] normal [0.0, 0.0, 1.0] misses Block (box [0.0, 0.0, 0.0] to [10.0, 10.0, 10.0]): move at.'],
 ('measure_mass', 'printed, no material: PLA'): {'density': 1.24, 'densityFrom': 'assumed pla: printed, and no material_set', 'mass': 1.24},
 ('measure_mass', 'a library card by id'): {'densityFrom': 'Aluminum 6061 (FreeCAD library)',
                                            'mass': 2.7,
                                            'principal': {'moments': [5.4, 8.1, 10.8], 'axes': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}},
 ('measure_mass', 'a card with no density'): ['refused', 'invalid_input', "material 'Foam': its card has no density — give density in g/cm³ (material_get { id } shows what the card holds)."],
 ('measure_mass', "an add-on's answer"): {'mass': 12.5, 'from': 'the mass_properties service of an installed add-on'},
 ('clearance', 'interference'): {'state': 'interference', 'interference': 500.0},
 ('clearance', 'clear, not by enough'): {'state': 'clear', 'meets': False},
 ('measure_keep', "a vertex's position"): {'measure': 'Position Block.Vertex3', 'value': [1.2346, 2.0, 3.0], 'unit': 'mm', 'step': 1},
 ('measure_keep', 'a diameter on FreeCAD 1.1'): ['refused',
                                                 'unavailable',
                                                 "This FreeCAD has no Measure::MeasureDiameter (No document object type called 'Measure::MeasureDiameter'): FreeCAD 1.1 keeps a radius but not a "
                                                 'diameter — kind radius on the same edge, or measure { a, b } answers the same without keeping it.'],
 ('measure_keep', "a radius of a cylinder's face"): ['refused',
                                                     'invalid_input',
                                                     'of: Block.Face3 is a face (cylinder); kind radius takes one circular edge (a circle or arc, not a cylindrical face). measure { a } reads a '
                                                     "cylinder's radius without keeping it."],
 ('measure_keep', 'it would not compute'): ['refused',
                                            'failed',
                                            "FreeCAD's MeasureDistance could not measure Block.Face1, Block.Face2: Radius of cylinder too small — nothing was kept. measure { a, b } reads the same "
                                            'without keeping it.'],
 ('insp_run', 'a body, its mesh as asked'): {'actual': 'Pin as inspected',
                                             'points': 4,
                                             'measuredOn': 'Pin as inspected: 4 points about 2 mm apart (spacing), hidden',
                                             'thicknessNote': "Thickness is stored on the feature, but FreeCAD 1.1's Inspection does not use it when measuring: the distances are the same with or "
                                                              'without it.',
                                             'step': 1},
 ('insp_run', 'points against two, with a band, named'): {'inspection': 'First article',
                                                          'tolerance': [-0.15, 0.25],
                                                          'inTolerancePercent': 77.7778,
                                                          'verdict': 'fail',
                                                          'worst': [{'at': [2.0, 2.0, 10.0], 'distance': -0.2}, {'at': [8.0, 5.0, 10.0], 'distance': -0.2}]},
 ('insp_run', 'tolerance past the search radius'): ['refused',
                                                    'invalid_input',
                                                    'tolerance reaches past search_radius (1.5 mm): points out of tolerance would read as out of reach. Raise search_radius.'],
 ('insp_run', 'a file that reads empty'): ['refused', 'failed', 'Inspection measured no points: empty holds none (the file read as empty — is it a mesh FreeCAD reads?) — nothing was kept.'],
 ('insp_update', 'the band cleared'): {'searchRadius': 1.0, 'rms': 0.1333, 'step': 1},
 ('insp_update', 'the band it has past a smaller radius'): ['refused',
                                                            'invalid_input',
                                                            'tolerance reaches past search_radius (0.2 mm): points out of tolerance would read as out of reach. Raise search_radius in the same call.'],
 ('insp_list', 'two, one with a band'): {'inspections': [{'inspection': 'Check', 'actual': 'Scan', 'nominals': ['Block'], 'points': 9, 'rms': 0.1333, 'outOfReachPercent': 0.0},
                                                         {'inspection': 'Other',
                                                          'actual': 'Scan',
                                                          'nominals': ['Block'],
                                                          'points': 9,
                                                          'rms': 0.1333,
                                                          'inTolerancePercent': 22.2222,
                                                          'verdict': 'fail',
                                                          'outOfReachPercent': 0.0}]},
 ('insp_faces', 'with a band'): {'faces': [{'face': 'Block.Face1', 'points': 9, 'mean': -0.0222, 'min': -0.2, 'max': 0.2, 'rms': 0.1333, 'outOfTolerance': 3, 'verdict': 'fail'}],
                                 'facesMeasured': 1,
                                 'failing': ['Block.Face1']},
 ('insp_faces', 'a body far away'): ['refused', 'not_found', 'Check: no measured point lies within 1 mm of a face of Far — a larger reach, or the body is not where the actual is.'],
 ('insp_export', "the label's spaces"): {'files': {'csv': {'path': '<out>/First-article.csv', 'rows': 9}, 'json': {'path': '<out>/First-article.json'}},
                                         'summary': {'rms': 0.15, 'min': -0.3, 'max': 0.2, 'inTolerancePercent': 75.0, 'verdict': 'fail'}},
 ('note_add', 'on the first of the faces picked'): {'note': {'id': 1,
                                                             'by': 'agent',
                                                             'text': 'These two',
                                                             'at': [10.0, 5.0, 5.0],
                                                             'done': False,
                                                             'body': 'Block',
                                                             'face': 'Face5',
                                                             'made': '2026-11-16T12:00:00'},
                                                    'note_count': 1},
 ('note_list', 'one that moved to another face'): {'followed': [{'id': 4, 'from': 'Face5', 'to': 'Face2', 'at': [5.0, 5.0, 0.0], 'body': 'Block'},
                                                                {'id': 5, 'from': 'Face1', 'to': None, 'at': [1.0, 1.0, 1.0]}]},
 ('note_list', 'the faces could not be looked for'): {'notFollowed': "The notes' faces were not looked for again (TypeError: 'NoneType' object is not iterable): faces may have moved.",
                                                      'waiting': [1]},
 ('note_answer', 'an answer'): {'note': {'id': 1,
                                         'by': 'person',
                                         'text': 'Can this wall be thicker?',
                                         'at': [1.0, 2.0, 3.0],
                                         'done': False,
                                         'answer': 'Yes: 3 mm now.',
                                         'made': '2026-11-15T09:00:00'}},
 ('note_delete', 'one of two'): {'deleted': 1, 'left': 1},
 ('steps_list', 'a feature that failed'): {'count': 3,
                                           'steps': [{'name': 'Pad', 'label': 'Pad', 'type': 'Pad', 'volume': 1200.0, 'change': 1200.0, 'key': 'Length 12.00 mm', 'step': 1},
                                                     {'name': 'Pocket', 'label': 'Pocket', 'type': 'Pocket', 'volume': 1000.0, 'change': -200.0, 'failed': True, 'key': 'Depth 4.0', 'step': 2},
                                                     {'name': 'Fillet', 'label': 'Fillet', 'type': 'Fillet', 'volume': 1000.2, 'change': 0.2, 'key': 'Radius 1.5', 'tip': True, 'step': 3}]},
 ('steps_render', 'a step with no shape is left out'): {'files': ['<out>/steps_Housing/step_01.png', '<out>/steps_Housing/step_03.png'], 'sheet': '<out>/steps_Housing/steps.png'},
 ('steps_render', 'view wrong'): ['refused', 'invalid_input', 'view: iso, iso-front-left, iso-rear-left, iso-rear-right, top, bottom, front, rear, left, right.'],
 ('robot_new', 'a KUKA model this FreeCAD ships, with its picture'): {'robot': 'Robot kr16', 'model': "KUKA KR16 (FreeCAD's library)", 'step': 1},
 ('robot_new', 'placed, with a tool'): {'tcp': {'at': [0.0, 0.0, 120.0], 'ypr': [0.0, 0.0, 0.0]}, 'flange': {'at': [0.0, 0.0, 0.0], 'ypr': [0.0, 0.0, 0.0]}},
 ('robot_new', 'kinematics not there'): ['refused',
                                         'not_found',
                                         'kinematics: <out>/gone.csv — no such file. A CSV: one header line, then six lines (axis 1 … 6) of a, alpha, d, theta, rotDir, maxAngle, minAngle, velocity '
                                         '(Denavit-Hartenberg, mm and degrees).'],
 ('robot_move', 'out of reach'): {'axes': [1.0, 2.0, 3.0, 0.0, 0.0, 0.0], 'reached': False, 'off_mm': 4990.13},
 ('robot_move', "the solver's whole turns taken out"): {'axes': [10.0, 20.0, 30.0, 0.0, 0.0, 0.0], 'reached': True},
 ('robot_path', 'three waypoints'): {'trajectory': 'Trajectory', 'waypoints': 3, 'length': 700.0, 'seconds': 1.6, 'step': 1},
 ('robot_path', 'no edge trajectory in this FreeCAD'): ['refused', 'unavailable', "This FreeCAD's Robot module has no edge trajectory (Robot::Edge2TracObject): give waypoints instead."],
 ('robot_run', 'misses the far end'): {'verdict': 'misses 4 of 9 points',
                                       'worst_mm': 2000.0,
                                       'axes': [{'axis': 1, 'from': -160.0, 'to': 150.0},
                                                {'axis': 2, 'from': 0.0, 'to': 0.0},
                                                {'axis': 3, 'from': 0.0, 'to': 0.0},
                                                {'axis': 4, 'from': 4.0, 'to': 4.0},
                                                {'axis': 5, 'from': 5.0, 'to': 5.0},
                                                {'axis': 6, 'from': 6.0, 'to': 6.0}]},
 ('robot_run', 'reaches all'): {'verdict': 'reaches all', 'samples': 5},
 ('robot_trajectory', "an older module's trajectory: no size, no length"): {'waypoints': 3, 'length_mm': None},
 ('robot_trajectory', 'add unknown'): ['refused',
                                       'invalid_input',
                                       "add: UseOrientation (ypr replaces each waypoint's orientation) | AddPosition (move added) | AddOrientation (ypr turned on top) | AddPositionAndOrientation "
                                       '(both) | DontChange.'],
 ('robot_export', 'to a path in a folder'): {'path': '<out>/krl/seam.src', 'lines': 5},
 ('robot_export', 'the full form on FreeCAD 1.1'): ['refused',
                                                    'unavailable',
                                                    "This FreeCAD's full KRL export writes no file (KukaExporter.ExportFullSub is empty in 1.1): leave full out for the compact form."],
 ('ifc_open', "a file in the session's folder"): {'schema': 'IFC4', 'project': 'Annex', 'classes': {'IfcBuildingStorey': 2, 'IfcWall': 2, 'IfcSlab': 1, 'IfcWindow': 1}, 'elements': 6},
 ('ifc_open', 'not there'): ['refused', 'not_found', "path 'gone.ifc': no such file (a relative path is looked for in the session's output folder, where bim_export writes)."],
 ('ifc_find', 'two of four listed'): {'count': 4, 'more': 2},
 ('ifc_find', 'a class IFC has not'): ['refused',
                                       'invalid_input',
                                       "class 'Wall': not an IFC class in IFC4. Classes are written IfcWall, IfcSlab, IfcBeam, IfcWindow, IfcSpace …; ifc_open lists those in the file."],
 ('ifc_edit', 'everything at once'): {'changed': 1, 'done': {'attributes': 1, 'properties': 1, 'material': 1, 'storey': 1, 'classification': 1}},
 ('ifc_edit', 'classified where IfcOpenShell cannot: a property set'): {'done': {'classification': 1, 'classificationAs': 'property set (this IfcOpenShell could not add a classification reference)'}},
 ('ifc_edit', 'too many match'): ['refused', 'invalid_input', '5 elements match: narrow it, or max: 5 to change them all.'],
 ('ifc_edit', 'a storey the file has not'): ['refused', 'not_found', "storey_to 'Roof': the file's storeys are Ground, First (by name, exactly)."],
 ('ifc_remove', 'one'): {'removed': [{'id': '0wall00000000000000000', 'class': 'IfcWall', 'name': 'Outer wall 1', 'storey': 'Ground'}]},
 ('ifc_save', 'a copy beside it'): {'path': '<out>/house_edited.ifc', 'edits': 2, 'overwrote': False},
 ('ifc_diff', 'a property changed and one added'): {'changed': [{'id': '0wall00000000000000000',
                                                                 'class': 'IfcWall',
                                                                 'name': 'Outer wall 1',
                                                                 'changes': {'Pset_WallCommon.FireRating': ['REI30', 'REI60'], 'Pset_WallCommon.Reference': [None, 'W']}}],
                                                    'counts': {'added': 0, 'removed': 0, 'changed': 1, 'same': 5}},
 ('ifc_diff', 'b not there'): ['refused', 'not_found', "b 'b.ifc': no such file (a relative path is looked for in the session's output folder)."]}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []


def cases(fc, tmp, old, new):
    V = fc.Vec

    def prep(*fns, **flags):
        def prepare(s):
            fc.fc.GuiUp = False
            fc.hooks._SERVICES.clear()
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    none = prep()

    def record(name, value):
        """A record of the document as the tools keep them (agentlink/store.py)."""
        def put(s):
            from agentlink import store

            store.write(s.doc, name, value)
        return put

    # ---- measuring -------------------------------------------------------------------------

    def block(s):
        sh = fc.solid("block", (0, 0, 0), (10, 10, 10))
        sh.pts = [V(0, 0, 0), V(10, 0, 0), V(10, 10, 10)]
        sh.els = {"Face1": {"com": (5, 5, 10)}, "Face2": {"com": (5, 5, 0)}, "Face3": {"surface": "Cylinder", "radius": 4.0, "center": (5, 5, 0), "com": (5, 5, 5)},
                  "Face4": {"surface": "Cone", "com": (2, 2, 2)}, "Face5": {"normal": V(1, 0, 0), "com": (10, 5, 5)}, "Face6": {"surface": "Toroid", "radius": 6.0, "center": (1, 1, 1)},
                  "Edge1": {"pts": [V(0, 0, 0), V(10, 0, 0)], "mid": (5, 0, 0)}, "Edge2": {"curve": "Circle", "radius": 4.0, "center": (5, 5, 10), "closed": True},
                  "Edge3": {"curve": "Ellipse", "center": (5, 5, 0)}, "Edge4": {"curve": "BSplineCurve"}, "Edge5": {"pts": [V(0, 0, 0), V(0, 0, 10)], "mid": (0, 0, 5)},
                  "Edge6": {"pts": [V(3, 3, 3)]}, "Edge7": {"curve": "broken"}}
        fc.body("Block", sh)

    def ball(s):
        sh = fc.solid("ball", (20, 0, 0), (30, 10, 10), faces=2, edges=1)
        sh.els = {"Face1": {"surface": "Sphere", "radius": 5.0, "center": (25, 5, 5)}, "Face2": {"surface": "BSplineSurface", "no_normal": True}, "Edge1": {"curve": "Circle", "closed": False}}
        fc.body("Ball", sh)

    def pin(s):
        fc.body("Pin", fc.solid("pin", (5, 5, 5), (15, 15, 15)))

    def far(s):
        fc.body("Far", fc.solid("far", (100, 100, 100), (110, 110, 110)))

    def twin(s):
        fc.body("Twin", fc.solid("twin", (0, 0, 0), (10, 10, 10), solids=2, kind="Compound"))

    def skin(s):
        fc.body("Skin", fc.solid("skin", (0, 0, 0), (10, 10, 0), kind="Shell", solids=0))

    T = "shape_query"
    yield T, "the faces of the one body", prep(block), {}
    yield T, "edges", prep(block), {"kind": "edge", "body": "Block"}
    yield T, "vertices", prep(block), {"kind": "vertex"}
    yield T, "two listed, more left", prep(block), {"limit": 2}
    yield T, "limit a fraction", prep(block), {"limit": 2.9}
    yield T, "cylinders by type and radius", prep(block), {"type": "cylinder", "radius": 4}
    yield T, "by normal, sorted by height", prep(block), {"normal": [0, 0, 1], "sort": "-z"}
    yield T, "edges of a face, by axis", prep(block), {"kind": "edge", "of": "Block.Face1", "axis": [1, 0, 0]}
    yield T, "near a point", prep(block), {"near": [5, 5, 12], "limit": 3}
    yield T, "none found", prep(block), {"type": "sphere"}
    yield T, "limit 0", prep(block), {"limit": 0}
    yield T, "limit over 500", prep(block), {"limit": 501}
    yield T, "limit not a number", prep(block), {"limit": "all"}
    yield T, "kind wrong", prep(block), {"kind": "solid"}
    yield T, "sort wrong", prep(block), {"sort": "volume"}
    yield T, "body not here", prep(block), {"body": "Gone"}
    yield T, "two bodies, none said", prep(block, pin), {}
    yield T, "of not a face", prep(block), {"of": "Block.Edge1"}

    T = "measure"
    yield T, "a flat face alone", prep(block), {"a": "Face1"}
    yield T, "a cylinder's face alone", prep(block), {"a": "Block.Face3"}
    yield T, "a circle alone", prep(block), {"a": "Edge2", "body": "Block"}
    yield T, "a body alone", prep(block), {"a": "Block"}
    yield T, "a point alone", none, {"a": [1, 2, 3]}
    yield T, "a vertex alone", prep(block), {"a": "Block.Vertex2"}
    yield T, "two parallel faces", prep(block), {"a": "Block.Face1", "b": "Block.Face2"}
    yield T, "two faces at an angle", prep(block), {"a": "Block.Face1", "b": "Block.Face5"}
    yield T, "two straight edges", prep(block), {"a": "Block.Edge1", "b": "Block.Edge5"}
    yield T, "a face and a line", prep(block), {"a": "Block.Face1", "b": "Block.Edge5"}
    yield T, "a line and a face", prep(block), {"a": "Block.Edge1", "b": "Block.Face5"}
    yield T, "two round ones", prep(block, ball), {"a": "Block.Face3", "b": "Ball.Face1"}
    yield T, "a round face and a circle", prep(block), {"a": "Face6", "b": "Edge2", "body": "Block"}
    yield T, "two bodies", prep(block, far), {"a": "Block", "b": "Far"}
    yield T, "a point and a face, a distance given", prep(block, dist=7.25), {"a": [0, 0, 20], "b": "Block.Face1"}
    yield T, "two points alike", none, {"a": [1, 2, 3], "b": [1, 2, 3]}
    yield T, "a curved face and a line: no angle", prep(block), {"a": "Block.Face4", "b": "Block.Edge1"}
    yield T, "the same face twice", prep(block), {"a": "Block.Face1", "b": "Face1"}
    yield T, "the same body twice", prep(block), {"a": "Block", "b": "Block"}
    yield T, "a left out", prep(block), {"b": "Block.Face1"}
    yield T, "a not a reference", prep(block), {"a": 5}
    yield T, "b not here", prep(block), {"a": "Block.Face1", "b": "Gone.Face1"}
    yield T, "a face the body has not", prep(block), {"a": "Block.Face9"}
    yield T, "a null", prep(block), {"a": None}

    T = "section"
    yield T, "through the origin, along z", prep(block), {}
    yield T, "at a point, along x", prep(block), {"body": "Block", "normal": "+x", "at": [5, 5, 5]}
    yield T, "at an offset", prep(block), {"normal": [0, 0, 2], "offset": 4}
    yield T, "two regions with holes", prep(block, regions=2, loops=2), {"offset": 1}
    yield T, "outlines capped", prep(block, chord_points=9), {"maxPoints": 4, "tolerance": 0.5}
    yield T, "maxPoints a fraction", prep(block, chord_points=9), {"maxPoints": 6.5}
    yield T, "the plane misses", prep(block), {"at": [0, 0, 50]}
    yield T, "the plane misses by its offset", prep(block), {"offset": -3}
    yield T, "tolerance 0", prep(block), {"tolerance": 0}
    yield T, "tolerance not a number", prep(block), {"tolerance": "fine"}
    yield T, "maxPoints 2", prep(block), {"maxPoints": 2}
    yield T, "maxPoints too many", prep(block), {"maxPoints": 20001}
    yield T, "maxPoints not a number", prep(block), {"maxPoints": True}
    yield T, "a miss comes before a bad tolerance", prep(block), {"at": [0, 0, 50], "tolerance": 0}
    yield T, "normal of no length", prep(block), {"normal": [0, 0, 0]}
    yield T, "at not a point", prep(block), {"at": [1]}
    yield T, "offset not a number", prep(block), {"offset": "2"}
    yield T, "no solid", prep(skin), {"body": "Skin"}
    yield T, "no body", none, {}
    yield T, "crash: the cut fails", prep(block, fail=("common",)), {}

    T = "measure_mass"
    alu = {"alu-id": {"id": "alu-id", "name": "Aluminum 6061", "density": 2.7, "source": "FreeCAD library"}, "foam-id": {"id": "foam-id", "name": "Foam"}}

    def addon(answer):
        def put(s):
            def service(session, args):
                fc.log("mass_properties", args)
                if isinstance(answer, Exception):
                    raise answer
                return answer
            fc.hooks.provide("mass_properties", service)
        return put

    class Refusal(Exception):
        code, message = "invalid_state", "The slicer has not run for Block."

    yield T, "density given", prep(block), {"density": 1.25}
    yield T, "a stock material", prep(block), {"body": "Block", "material": "PETG"}
    yield T, "the material recorded", prep(block, record("materials", {"Block": "abs"})), {}
    yield T, "printed, no material: PLA", prep(block, record("setups", [{"type": "print", "bodies": ["Block"]}])), {}
    yield T, "a library card by id", prep(block, library=alu), {"material": "alu-id"}
    yield T, "a library card by name, recorded", prep(block, record("materials", {"Block": "aluminum 6061"}), library=alu), {}
    yield T, "a custom material of the document", prep(block, record("materialDefs", {"custom:1": {"name": "Brass mix", "density": 8.4}})), {"material": "custom:1"}
    yield T, "a card with no density", prep(block, library=alu), {"material": "foam-id"}
    yield T, "a material nobody knows", prep(block), {"material": "unobtainium"}
    yield T, "nothing to go by", prep(block), {}
    yield T, "density 0", prep(block), {"density": 0}
    yield T, "density below 0", prep(block), {"density": -1}
    yield T, "density not a number", prep(block), {"density": "1.2"}
    yield T, "two solids: no principal axes", prep(twin), {"density": 1.0}
    yield T, "principal axes not to be had", prep(block, no_principal=True), {"density": 1.0}
    yield T, "an add-on's answer", prep(block, addon({"body": "Block", "mass": 12.5, "inserts": 2})), {}
    yield T, "an add-on, but density given", prep(block, addon({"mass": 12.5})), {"density": 1.0}
    yield T, "an add-on, but material given", prep(block, addon({"mass": 12.5})), {"material": "pla"}
    yield T, "an add-on's refusal", prep(block, addon(Refusal())), {}
    yield T, "an add-on that fails: this tool's own", prep(block, addon(RuntimeError("boom")), record("materials", {"Block": "pla"})), {}
    yield T, "an add-on answering no dict", prep(block, addon("12 g")), {}
    yield T, "no solid", prep(skin), {"body": "Skin", "density": 1.0}
    yield T, "body not here", prep(block), {"body": "Gone"}
    yield T, "crash: material a number", prep(block), {"material": 7}

    T = "clearance"
    yield T, "clear", prep(block, far), {"a": "Block", "b": "Far"}
    yield T, "clear by enough", prep(block, far), {"a": "Block", "b": "Far", "min": 50}
    yield T, "clear, not by enough", prep(block, far), {"a": "Far", "b": "Block", "min": 500}
    yield T, "interference", prep(block, pin), {"a": "Block", "b": "Pin"}
    yield T, "interference, min asked", prep(block, pin), {"a": "Block", "b": "Pin", "min": 1}
    yield T, "touching", prep(block, pin, common_share=0.0), {"a": "Block", "b": "Pin"}
    yield T, "touching, min not a number (not read)", prep(block, pin, common_share=0.0), {"a": "Block", "b": "Pin", "min": "1"}
    yield T, "min not a number", prep(block, far), {"a": "Block", "b": "Far", "min": "1"}
    yield T, "the same body", prep(block), {"a": "Block", "b": "Block"}
    yield T, "the same body, by default", prep(block), {"b": "Block"}
    yield T, "a left out of two", prep(block, far), {"b": "Far"}
    yield T, "b not here", prep(block), {"a": "Block", "b": "Gone"}
    yield T, "a has no solid", prep(block, skin), {"a": "Skin", "b": "Block"}
    yield T, "crash: the boolean fails", prep(block, pin, fail=("common",)), {"a": "Block", "b": "Pin"}

    T = "measure_keep"
    no_diameter = ("Measure::MeasureDiameter",)
    yield T, "a distance between two faces", prep(block), {"of": ["Block.Face1", "Block.Face3"]}
    yield T, "an angle between two edges, named", prep(block), {"kind": "angle", "of": ["Block.Edge1", "Block.Edge5"], "name": "Corner"}
    yield T, "an angle between a face and an edge", prep(block), {"kind": "angle", "of": ["Face1", "Edge1"]}
    yield T, "a length of two edges", prep(block), {"kind": "length", "of": ["Block.Edge1", "Block.Edge2"]}
    yield T, "an area of one face, as a quantity", prep(block, quantities=True), {"kind": "area", "of": "Block.Face4"}
    yield T, "a radius", prep(block), {"kind": "radius", "of": ["Block.Edge2"]}
    yield T, "a vertex's position", prep(block), {"kind": "position", "of": ["Block.Vertex3"]}
    yield T, "a distance from a vertex", prep(block), {"of": ["Block.Vertex1", "Block.Edge3"]}
    yield T, "a name taken", prep(block), {"kind": "radius", "of": ["Block.Edge2"], "name": "Block"}
    yield T, "a diameter where FreeCAD has one", prep(block), {"kind": "diameter", "of": ["Block.Edge2"]}
    yield T, "a diameter on FreeCAD 1.1", prep(block, no_types=no_diameter), {"kind": "diameter", "of": ["Block.Edge2"]}
    yield T, "a FreeCAD with no Measure objects", prep(block, no_types=("Measure::MeasureDistance",)), {"of": ["Block.Face1", "Block.Face2"]}
    yield T, "kind wrong", prep(block), {"kind": "volume", "of": ["Block.Face1"]}
    yield T, "crash: kind a list", prep(block), {"kind": ["area"], "of": ["Block.Face1"]}
    yield T, "of left out", prep(block), {}
    yield T, "one element for a distance", prep(block), {"of": ["Block.Face1"]}
    yield T, "no edges for a length", prep(block), {"kind": "length", "of": []}
    yield T, "two for a radius", prep(block), {"kind": "radius", "of": ["Block.Edge2", "Block.Edge2"]}
    yield T, "a point for a position", prep(block), {"kind": "position", "of": [[1, 2, 3]]}
    yield T, "a whole object", prep(block), {"kind": "area", "of": ["Block"]}
    yield T, "a radius of a cylinder's face", prep(block), {"kind": "radius", "of": ["Block.Face3"]}
    yield T, "a diameter of a line", prep(block), {"kind": "diameter", "of": ["Block.Edge1"]}
    yield T, "an angle of a circle", prep(block), {"kind": "angle", "of": ["Block.Edge1", "Block.Edge2"]}
    yield T, "a distance to a cone", prep(block), {"of": ["Block.Face1", "Block.Face4"]}
    yield T, "a length of a face", prep(block), {"kind": "length", "of": ["Block.Edge1", "Block.Face1"]}
    yield T, "an area of a vertex", prep(block), {"kind": "area", "of": ["Block.Vertex1"]}
    yield T, "an edge whose curve cannot be read", prep(block), {"kind": "radius", "of": ["Block.Edge7"]}
    yield T, "an element not here", prep(block), {"kind": "area", "of": ["Gone.Face1"]}
    yield T, "it would not compute", prep(block, objects_invalid=True), {"of": ["Block.Face1", "Block.Face2"]}
    yield T, "marked invalid, no status to read", prep(block, state=["Touched", "Invalid"], no_status=True), {"kind": "length", "of": ["Block.Edge1"]}

    # ---- inspection ---------------------------------------------------------------------------

    GRID = [(x, y, 10.0) for y in (2.0, 5.0, 8.0) for x in (2.0, 5.0, 8.0)]
    BIG = 3.4e38

    def scan(s):
        o = fc.doc().new("Mesh::Feature", "Scan", Mesh=fc.MeshData(pts=GRID))
        o.__dict__["Label"] = "Scan"

    def cloud(s):
        fc.doc().new("Points::Feature", "Cloud", Points=fc.Cloud(pts=GRID))

    def empty(s):
        fc.doc().new("Mesh::Feature", "Empty", Mesh=fc.MeshData(pts=[]))

    def sketch(s):
        fc.doc().new("Sketcher::SketchObject", "Sketch")

    def inspected(label="Check", actual="Scan", nominals=("Block",), distances=None, band=None, radius=1.0, **kw):
        def make(s):
            d = fc.doc()
            got = [0.1 * ((i % 5) - 2) for i in range(9)] if distances is None else distances
            o = d.new("Inspection::Feature", "Inspection", Actual=d.getObject(actual) or (d.getObjectsByLabel(actual) or [None])[0],
                      Nominals=[d.getObjectsByLabel(n)[0] for n in nominals], SearchRadius=radius, Thickness=0.0, Distances=list(got), **kw)
            o.__dict__["Label"] = label
            if band:
                o.__dict__.update(ToleranceLow=band[0], ToleranceHigh=band[1])
        return make

    def scan_file(name, text="solid"):
        def put(s):
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        return put

    T = "insp_run"
    yield T, "a mesh against a body", prep(block, scan), {"actual": "Scan", "nominals": ["Block"]}
    yield T, "points against two, with a band, named", prep(block, pin, cloud), {"actual": "Cloud", "nominals": ["Block", "Pin"], "tolerance": [-0.15, 0.25], "name": "First article", "worst": 2}
    yield T, "a tolerance as a number, all inside", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "tolerance": 0.5, "search_radius": 2}
    yield T, "a body as the actual", prep(block, pin), {"actual": "Pin", "nominals": ["Block"]}
    yield T, "a body, its mesh as asked", prep(block, pin), {"actual": "Pin", "nominals": ["Block"], "deflection": 0.5, "spacing": 2, "cap": 10, "thickness": 0.2}
    yield T, "a mesh file", prep(block, scan_file("part scan.STL")), {"file": "part scan.STL", "nominals": ["Block"]}
    yield T, "a points file", prep(block, scan_file("cloud.xyz")), {"file": "cloud.xyz", "nominals": ["Block"]}
    yield T, "a points file on an older FreeCAD", prep(block, scan_file("cloud.asc"), missing=("Points.Points",)), {"file": "cloud.asc", "nominals": ["Block"]}
    yield T, "out of reach: the note", prep(block, scan, distances=[0.1, BIG, -BIG, 0.2, 0.0, 0.1, 0.1, 0.1, 0.1]), {"actual": "Scan", "nominals": ["Block"], "tolerance": 0.5}
    yield T, "thickness given", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "thickness": 1.5}
    yield T, "a name taken", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "name": "Scan"}
    yield T, "a file not there", prep(block), {"file": "gone.stl", "nominals": ["Block"]}
    yield T, "a file of another kind", prep(block, scan_file("part.step")), {"file": "part.step", "nominals": ["Block"]}
    yield T, "a file with no extension", prep(block, scan_file("scan")), {"file": "scan", "nominals": ["Block"]}
    yield T, "a file that reads empty", prep(block, scan_file("empty.stl"), file_points=[]), {"file": "empty.stl", "nominals": ["Block"]}
    yield T, "neither actual nor file", prep(block), {"nominals": ["Block"]}
    yield T, "actual not here", prep(block), {"actual": "Gone", "nominals": ["Block"]}
    yield T, "actual a sketch", prep(block, sketch), {"actual": "Sketch", "nominals": ["Block"]}
    yield T, "deflection too fine", prep(block, pin), {"actual": "Pin", "nominals": ["Block"], "deflection": 0.0001}
    yield T, "deflection too coarse", prep(block, pin), {"actual": "Pin", "nominals": ["Block"], "deflection": 6}
    yield T, "spacing below 0", prep(block, pin), {"actual": "Pin", "nominals": ["Block"], "spacing": -1}
    yield T, "no nominals", prep(block, scan), {"actual": "Scan"}
    yield T, "nominals empty", prep(block, scan), {"actual": "Scan", "nominals": []}
    yield T, "a nominal not here", prep(block, scan), {"actual": "Scan", "nominals": ["Gone"]}
    yield T, "a nominal a sketch", prep(block, scan, sketch), {"actual": "Scan", "nominals": ["Block", "Sketch"]}
    yield T, "the actual among the nominals", prep(block, scan), {"actual": "Scan", "nominals": ["Block", "scan"]}
    yield T, "search_radius 0", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "search_radius": 0}
    yield T, "search_radius not a number", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "search_radius": "1"}
    yield T, "tolerance 0", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "tolerance": 0}
    yield T, "tolerance upside down", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "tolerance": [1, -1]}
    yield T, "tolerance past the search radius", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "tolerance": [-0.1, 2.5], "search_radius": 1.5}
    yield T, "thickness not a number", prep(block, scan), {"actual": "Scan", "nominals": ["Block"], "thickness": "thin"}
    yield T, "a mesh with no points", prep(block, empty), {"actual": "Empty", "nominals": ["Block"]}
    yield T, "crash: deflection not a number", prep(block, pin), {"actual": "Pin", "nominals": ["Block"], "deflection": "fine"}
    yield T, "crash: the file's mesh fails", prep(block, scan_file("bad.obj"), fail=("Mesh",)), {"file": "bad.obj", "nominals": ["Block"]}
    yield T, "crash: no Points module", prep(block, scan_file("cloud.pcd"), missing=("Points",)), {"file": "cloud.pcd", "nominals": ["Block"]}

    T = "insp_update"
    yield T, "a wider search radius", prep(block, scan, inspected()), {"search_radius": 2.5}
    yield T, "a band set, by name", prep(block, scan, inspected(), inspected("Other")), {"inspection": "Other", "tolerance": [-0.05, 0.15], "worst": 1}
    yield T, "a band as a number", prep(block, scan, inspected()), {"tolerance": 0.3}
    yield T, "the band cleared", prep(block, scan, inspected(band=(-0.1, 0.1))), {"tolerance": None}
    yield T, "the band cleared where there was none", prep(block, scan, inspected()), {"tolerance": None}
    yield T, "thickness and nominals", prep(block, pin, scan, inspected()), {"thickness": 0.4, "nominals": ["Pin", "Block"]}
    yield T, "radius and tolerance together", prep(block, scan, inspected()), {"search_radius": 5, "tolerance": 3}
    yield T, "nothing to change", prep(block, scan, inspected()), {"inspection": "Check"}
    yield T, "nothing to change but worst", prep(block, scan, inspected()), {"worst": 3}
    yield T, "search_radius 0", prep(block, scan, inspected()), {"search_radius": 0}
    yield T, "search_radius not a number", prep(block, scan, inspected()), {"search_radius": [1]}
    yield T, "tolerance past the radius it has", prep(block, scan, inspected()), {"tolerance": 3}
    yield T, "the band it has past a smaller radius", prep(block, scan, inspected(band=(-0.5, 0.5))), {"search_radius": 0.2}
    yield T, "tolerance wrong", prep(block, scan, inspected()), {"tolerance": [1, 2, 3]}
    yield T, "tolerance below 0", prep(block, scan, inspected()), {"tolerance": -1}
    yield T, "a nominal not here", prep(block, scan, inspected()), {"nominals": ["Gone"]}
    yield T, "a nominal a sketch", prep(block, scan, sketch, inspected()), {"nominals": ["Sketch"]}
    yield T, "a nominal the actual", prep(block, scan, inspected()), {"nominals": ["Scan"]}
    yield T, "nominals empty: nothing set", prep(block, scan, inspected()), {"nominals": []}
    yield T, "thickness not a number", prep(block, scan, inspected()), {"thickness": "x"}
    yield T, "no inspection", prep(block), {"search_radius": 1}
    yield T, "two, none said", prep(block, scan, inspected(), inspected("Other")), {"search_radius": 1}
    yield T, "an inspection not here", prep(block, scan, inspected()), {"inspection": "Gone", "search_radius": 1}

    T = "insp_read"
    yield T, "the one there is", prep(block, scan, inspected(band=(-0.15, 0.15))), {}
    yield T, "by name, three worst", prep(block, scan, inspected(), inspected("Other")), {"inspection": "Other", "worst": 3}
    yield T, "by its object's name", prep(block, scan, inspected()), {"inspection": "Inspection"}
    yield T, "all in tolerance", prep(block, scan, inspected(band=(-1, 1))), {}
    yield T, "all alike", prep(block, scan, inspected(distances=[0.2] * 9)), {}
    yield T, "none measured", prep(block, scan, inspected(distances=[BIG] * 9)), {}
    yield T, "points that do not line up: no worst", prep(block, scan, inspected(distances=[0.1, 0.2])), {}
    yield T, "no inspection", none, {}
    yield T, "two, none said", prep(block, scan, inspected(), inspected("Other")), {}
    yield T, "not here", prep(block, scan, inspected()), {"inspection": "Gone"}
    yield T, "crash: worst not a number", prep(block, scan, inspected()), {"worst": "all"}

    T = "insp_list"
    yield T, "none", none, {}
    yield T, "one", prep(block, scan, inspected()), {}
    yield T, "two, one with a band", prep(block, scan, inspected(), inspected("Other", band=(-0.05, 0.05))), {}

    T = "insp_faces"
    yield T, "by the nominal's faces", prep(block, scan, inspected()), {}
    yield T, "with a band", prep(block, scan, inspected(band=(-0.15, 0.15))), {"limit": 2}
    yield T, "with a band all pass", prep(block, scan, inspected(band=(-1.0, 1.0))), {"deflection": 0.2}
    yield T, "by a body named", prep(block, pin, scan, inspected()), {"body": "Pin", "reach": 20}
    yield T, "a body far away", prep(block, far, scan, inspected()), {"body": "Far"}
    yield T, "a small reach", prep(block, scan, inspected()), {"reach": 0.001}
    yield T, "a body with no faces", prep(block, scan, inspected()), {"body": "Scan"}
    yield T, "a body not here", prep(block, scan, inspected()), {"body": "Gone"}
    yield T, "nominals with no faces", prep(block, scan, cloud, inspected(nominals=("Cloud",))), {}
    yield T, "points that do not line up", prep(block, scan, inspected(distances=[0.1])), {}
    yield T, "no inspection", none, {}
    yield T, "crash: reach not a number", prep(block, scan, inspected()), {"reach": "far"}
    yield T, "crash: deflection not a number", prep(block, scan, inspected()), {"deflection": "fine"}

    T = "insp_export"
    yield T, "the report", prep(block, scan, inspected(band=(-0.15, 0.15))), {}
    yield T, "named, no band", prep(block, scan, inspected("First article")), {"name": "run 7", "worst": 1}
    yield T, "the label's spaces", prep(block, scan, inspected("First article", distances=[0.1, BIG, -0.3, 0.2, 0.0, 0.1, 0.1, 0.1, 0.1], band=(-0.15, 0.15))), {}
    yield T, "more distances than points", prep(block, scan, inspected(distances=[0.1] * 11)), {}
    yield T, "no inspection", none, {}
    yield T, "not here", prep(block, scan, inspected()), {"inspection": "Gone"}

    # ---- notes and steps --------------------------------------------------------------------------

    for mods in (old, new):
        if "notes" in mods:
            mods["notes"].datetime = fc.Clock

    def noted(*notes, next_id=None):
        """The document's notes as they are kept: each { id, by, text, at, … }."""
        rows = [{"done": False, "made": "2026-11-15T09:00:00", **n} for n in notes]
        return record("notes", {"next": next_id or len(rows) + 1, "notes": rows})

    ask = {"id": 1, "by": "person", "text": "Can this wall be thicker?", "at": [1.0, 2.0, 3.0]}
    told = {"id": 2, "by": "agent", "text": "Hole moved 2 mm.", "at": [0.0, 0.0, 0.0], "done": True}
    pinned = {"id": 3, "by": "person", "text": "Chamfer this face", "at": [5.0, 5.0, 10.0], "body": "Block", "face": "Face1", "answer": "Done, 1 mm."}
    moved = {"id": 4, "by": "agent", "text": "Check this side", "at": [5.0, 5.0, 0.0], "body": "Block", "face": "Face2", "movedFrom": {"face": "Face5", "at": [9.0, 9.0, 0.0]}}
    loose = {"id": 5, "by": "agent", "text": "A remark", "at": [1.0, 1.0, 1.0], "movedFrom": {"face": "Face1", "at": [0.0, 0.0, 0.0]}}

    odd = {"id": 6, "by": "agent", "text": "Pinned with no point", "at": None, "body": "Block", "face": "Face1"}

    T = "note_add"
    yield T, "at a point", prep(block), {"text": "Is 2 mm enough here?", "at": [1, 2.5, 3]}
    yield T, "at a point, on a body", prep(block, pin), {"text": "Too thin?", "at": [0, 0, 0], "body": "Pin"}
    yield T, "on a face", prep(block), {"text": "Chamfer?", "faces": "Face3"}
    yield T, "on the first of the faces picked", prep(block, pin), {"text": "These two", "body": "Block", "faces": ["Face5", "Face1"]}
    yield T, "on a face by a filter", prep(block, picks=["Face2"]), {"text": "The bottom", "faces": {"normal": [0, 0, -1]}}
    yield T, "a second note", prep(block, noted(ask, told)), {"text": "And here", "at": [0, 0, 0]}
    yield T, "text a number", prep(block), {"text": 42, "at": [0, 0, 0]}
    yield T, "no text", prep(block), {"at": [0, 0, 0]}
    yield T, "text blank", prep(block), {"text": "   ", "at": [0, 0, 0]}
    yield T, "neither at nor faces", prep(block), {"text": "Where?"}
    yield T, "at two numbers", prep(block), {"text": "Here", "at": [1, 2]}
    yield T, "at with a word", prep(block), {"text": "Here", "at": [1, 2, "3"]}
    yield T, "at with a true", prep(block), {"text": "Here", "at": [1, 2, True]}
    yield T, "at not a list", prep(block), {"text": "Here", "at": "origin"}
    yield T, "body not here", prep(block), {"text": "Here", "at": [0, 0, 0], "body": "Gone"}
    yield T, "faces, two bodies, none said", prep(block, pin), {"text": "Here", "faces": "Face1"}
    yield T, "a face the body has not", prep(block), {"text": "Here", "faces": "Face9"}

    T = "note_list"
    yield T, "none", none, {}
    yield T, "the person's waiting", prep(block, noted(ask, told, pinned)), {}
    yield T, "the open ones", prep(block, noted(ask, told, pinned)), {"open": True}
    yield T, "none waiting", prep(block, noted(told, pinned)), {}
    yield T, "one that moved to another face", prep(block, noted(moved, loose)), {}
    yield T, "the faces could not be looked for", prep(block, noted(ask, odd)), {}

    T = "note_answer"
    yield T, "an answer", prep(noted(ask, told)), {"id": 1, "text": "  Yes: 3 mm now. "}
    yield T, "a second answer replaces the first", prep(noted(pinned)), {"id": 3, "text": "2 mm after all."}
    yield T, "id as text", prep(noted(ask)), {"id": "1", "text": "Yes."}
    yield T, "a number as the answer", prep(noted(ask)), {"id": 1, "text": 3}
    yield T, "no text", prep(noted(ask)), {"id": 1}
    yield T, "text blank", prep(noted(ask)), {"id": 1, "text": " "}
    yield T, "no such note", prep(noted(ask)), {"id": 7, "text": "Yes."}
    yield T, "crash: no id", prep(noted(ask)), {"text": "Yes."}

    T = "note_done"
    yield T, "ticked off", prep(noted(ask, told)), {"id": 1}
    yield T, "opened again", prep(noted(ask, told)), {"id": 2, "done": False}
    yield T, "done as a word", prep(noted(ask)), {"id": 1, "done": "yes"}
    yield T, "no such note", prep(noted(ask)), {"id": 9}
    yield T, "no notes at all", none, {"id": 1}

    T = "note_delete"
    yield T, "one of two", prep(noted(ask, told)), {"id": 1}
    yield T, "the last", prep(noted(told, next_id=3)), {"id": 2}
    yield T, "no such note", prep(noted(ask)), {"id": 2}
    yield T, "crash: id a word", prep(noted(ask)), {"id": "one"}

    def housing(label="Housing", features=3, null=()):
        def make(s):
            d = fc.doc()
            b = d.new("PartDesign::Body", "Body", Group=[])
            b.__dict__["Label"] = label
            sk = d.new("Sketcher::SketchObject", "Sketch")
            kinds = [("Pad", "PartDesign::Pad", {"Length": fc.ns(UserString="12.00 mm")}, 1200.0), ("Pocket", "PartDesign::Pocket", {"Depth": 4.0}, 1000.0),
                     ("Fillet", "PartDesign::Fillet", {"Radius": 1.5}, 1000.2), ("Mirror", "PartDesign::Mirrored", {}, 2000.4), ("Hole", "PartDesign::Hole", {"Occurrences": 2}, 1990.0)][:features]
            group = [sk]
            for name, type_, props, vol in kinds:
                sh = fc.solid(name.lower(), (0, 0, 0), (10, 10, 12), volume=vol)
                if name in null:
                    sh.null = True
                group.append(d.new(type_, name, kinds=("PartDesign::Feature",), Shape=sh, **props))
            group.insert(2, d.new("PartDesign::Plane", "DatumPlane"))
            b.__dict__.update(Group=group, Tip=group[-1], Shape=fc.solid(label.lower(), (0, 0, 0), (10, 10, 12)) if features else fc.Shape())
        return make

    T = "steps_list"
    yield T, "the one body's features", prep(housing()), {}
    yield T, "with its sketches, by name", prep(housing(), housing("Lid", 4)), {"body": "Lid", "sketches": True}
    yield T, "by its object's name", prep(housing()), {"body": "Body"}
    yield T, "a feature that failed", prep(housing(), invalid_types=("PartDesign::Pocket",)), {}
    yield T, "an empty body", prep(housing(features=0)), {}
    yield T, "no PartDesign body", prep(block), {}
    yield T, "two, none said", prep(housing(), housing("Lid")), {}
    yield T, "not here", prep(housing()), {"body": "Lid"}
    yield T, "not here, and none at all", prep(block), {"body": "Block"}

    T = "steps_render"
    yield T, "a picture a step and the sheet", prep(housing()), {}
    yield T, "five steps: two rows, from the top, small", prep(housing("Lid", 5), housing()), {"body": "Lid", "view": "TOP", "width": 200, "height": 120, "path": "lid build"}
    yield T, "no sheet", prep(housing()), {"sheet": False}
    yield T, "the sheet kept out of the reply", prep(housing()), {"inline": False}
    yield T, "a step with no shape is left out", prep(housing(null=("Pocket",))), {}
    yield T, "no step has a shape: no sheet", prep(housing(features=1, null=("Pad",))), {}
    yield T, "a label with other characters", prep(housing("Gear box #2")), {"sheet": False}
    yield T, "no features yet", prep(housing(features=0)), {}
    yield T, "view wrong", prep(housing()), {"view": "under"}
    yield T, "width too small", prep(housing()), {"width": 100}
    yield T, "height too large", prep(housing()), {"height": 2001}
    yield T, "width a fraction", prep(housing()), {"width": 480.0}
    yield T, "height a true", prep(housing()), {"height": True}
    yield T, "no PartDesign body", prep(block), {}
    yield T, "not here", prep(housing()), {"body": "Lid"}

    # ---- robots -----------------------------------------------------------------------------------

    def arm(label="Arm", tool=None, axes=(0, 0, 0, 0, 0, 0), **kw):
        def make(s):
            o = fc.doc().new("Robot::RobotObject", "Robot", kinds=("Robot::RobotObject",), Tcp=fc.Placement(V(*[10.0 * x for x in axes[:3]])),
                             Tool=fc.Placement(V(*tool)) if tool else fc.Placement(), Error="", **{f"Axis{i + 1}": float(x) for i, x in enumerate(axes)}, **kw)
            o.__dict__["Label"] = label
        return make

    def path(label="Path", pts=((0, 0, 0), (300, 0, 0), (300, 400, 0)), speed=100.0, **kw):
        def make(s):
            o = fc.doc().new("Robot::TrajectoryObject", "Trajectory", Trajectory=fc.Trajectory([fc.point(V(*p), speed) for p in pts]), **kw)
            o.__dict__["Label"] = label
        return make

    def kuka_files(*names):
        def put(s):
            folder = os.path.join(s.out_dir, "resources", "Mod", "Robot", "Lib", "Kuka")
            os.makedirs(folder, exist_ok=True)
            for n in names:
                with open(os.path.join(folder, n), "w", encoding="utf-8") as f:
                    f.write("a,alpha,d,theta\n")
            fc.state["flags"]["resources"] = os.path.join(s.out_dir, "resources")
        return put

    def own_kinematics(s):
        with open(os.path.join(s.out_dir, "my arm.csv"), "w", encoding="utf-8") as f:
            f.write("a,alpha,d,theta\n")

    pose = {"at": [100, 200, 300], "ypr": [0, 90, 0]}

    T = "robot_new"
    yield T, "the default: no KUKA file here", none, {}
    yield T, "puma, named", none, {"model": "puma", "name": "Old faithful"}
    yield T, "a KUKA model this FreeCAD ships, with its picture", prep(kuka_files("kr16.csv", "kr16.wrl")), {"model": "kr16"}
    yield T, "a KUKA model by its library name, no picture", prep(kuka_files("kr125_3.csv")), {"model": "kr125", "name": "Big"}
    yield T, "a model it does not ship", prep(kuka_files("kr16.csv")), {"model": "kr500"}
    yield T, "kinematics of your own", prep(own_kinematics), {"kinematics": "my arm.csv", "model": "mine"}
    yield T, "placed, with a tool", none, {"model": "puma", "at": [500, 0, 0], "ypr": [90, 0, 0], "tool": {"at": [0, 0, 120]}}
    yield T, "placed by ypr alone, a tool turned about an axis", none, {"ypr": [0, 0, 45], "tool": {"at": [0, 0, 50], "axis": [0, 0, 1], "angle": 30}}
    yield T, "a second robot: the name taken", prep(arm("Robot kr16")), {}
    yield T, "the default's name taken", prep(arm("Robot (FreeCAD default)")), {"model": "puma"}
    yield T, "model unknown", none, {"model": "ur5"}
    yield T, "kinematics not there", none, {"kinematics": "gone.csv"}
    yield T, "kinematics not a path", none, {"kinematics": 7}
    yield T, "tool not an object", none, {"tool": [0, 0, 100]}
    yield T, "tool's ypr wrong", none, {"tool": {"ypr": [0, 0]}}
    yield T, "at wrong", none, {"at": [1]}

    T = "robot_move"
    yield T, "by axes", prep(arm()), {"axes": [10, -20, 30, 0, 45, 0]}
    yield T, "by axes, by name of two", prep(arm(), arm("Other")), {"robot": "Other", "axes": [1, 2, 3, 4, 5, 6]}
    yield T, "to a tool point", prep(arm()), {"tcp": pose}
    yield T, "to a tool point, a tool set", prep(arm(tool=(0, 0, 100))), {"tcp": pose}
    yield T, "the solver's whole turns taken out", prep(arm(), turns=2), {"tcp": pose}
    yield T, "out of reach", prep(arm(axes=(1, 2, 3, 0, 0, 0))), {"tcp": {"at": [5000, 0, 0]}}
    yield T, "out of reach, FreeCAD says so", prep(arm(), says_error=True), {"tcp": {"at": [5000, 0, 0]}}
    yield T, "home: all axes 0", prep(arm(axes=(5, 5, 5, 5, 5, 5))), {"home": True}
    yield T, "home as the person set it", prep(arm(Home=[0, -90, 90, 0, 0, 0])), {"home": True}
    yield T, "nothing asked", prep(arm()), {}
    yield T, "home false", prep(arm()), {"home": False}
    yield T, "axes and tcp", prep(arm()), {"axes": [0, 0, 0, 0, 0, 0], "tcp": pose}
    yield T, "tcp and home", prep(arm()), {"tcp": pose, "home": True}
    yield T, "five axes", prep(arm()), {"axes": [0, 0, 0, 0, 0]}
    yield T, "axes with a word", prep(arm()), {"axes": [0, 0, 0, 0, 0, "x"]}
    yield T, "axes not a list", prep(arm()), {"axes": 30}
    yield T, "tcp not an object", prep(arm()), {"tcp": [1, 2, 3]}
    yield T, "tcp's axis of no length", prep(arm()), {"tcp": {"at": [1, 2, 3], "axis": [0, 0, 0], "angle": 10}}
    yield T, "no robot", none, {"home": True}
    yield T, "two, none said", prep(arm(), arm("Other")), {"home": True}
    yield T, "not a robot", prep(arm(), block), {"robot": "Block", "home": True}
    yield T, "not here", prep(arm()), {"robot": "Gone", "home": True}

    def rail(s):
        fc.body("Rail", fc.curves("rail", [((0, 0, 0), (100, 0, 0)), ((100, 0, 0), (100, 50, 0))]))

    way = [{"at": [0, 0, 0]}, {"at": [300, 0, 0], "ypr": [0, 90, 0], "type": "ptp", "speed": 250, "cont": True, "name": "Corner"}, {"at": [300, 400, 0], "type": "CIRC"}]

    T = "robot_path"
    yield T, "three waypoints", none, {"waypoints": way}
    yield T, "two, named, a wait", none, {"waypoints": [{"at": [0, 0, 0]}, {"at": [0, 0, 100], "type": "WAIT"}], "name": "Lift"}
    yield T, "a name taken", prep(path("Trajectory")), {"waypoints": way}
    yield T, "along two edges", prep(rail), {"edges": ["Rail.Edge1", "Rail.Edge2"], "deviation": 0.1, "useRotation": True}
    yield T, "along all of an object's edges", prep(rail), {"edges": "Rail", "name": "Seam"}
    yield T, "the longer type name on another build", prep(rail, no_types=("Robot::Edge2TracObject",)), {"edges": ["Rail.Edge1"]}
    yield T, "no edge trajectory in this FreeCAD", prep(rail, no_types=("Robot::Edge2TracObject", "Robot::Edge2TrajectoryObject")), {"edges": ["Rail.Edge1"]}
    yield T, "a face given as an edge", prep(block), {"edges": ["Block.Face1"]}
    yield T, "edges of two objects", prep(rail, block), {"edges": ["Rail.Edge1", "Block.Edge1"]}
    yield T, "an edge not here", prep(rail), {"edges": ["Gone.Edge1"]}
    yield T, "no waypoints", none, {}
    yield T, "one waypoint", none, {"waypoints": [{"at": [0, 0, 0]}]}
    yield T, "waypoints not a list", none, {"waypoints": {"at": [0, 0, 0]}}
    yield T, "a waypoint not an object", none, {"waypoints": [{"at": [0, 0, 0]}, [1, 2, 3]]}
    yield T, "a type unknown", none, {"waypoints": [{"at": [0, 0, 0]}, {"at": [1, 0, 0], "type": "SPLINE"}]}
    yield T, "a speed of 0", none, {"waypoints": [{"at": [0, 0, 0], "speed": 0}, {"at": [1, 0, 0]}]}
    yield T, "a speed not a number", none, {"waypoints": [{"at": [0, 0, 0]}, {"at": [1, 0, 0], "speed": "fast"}]}
    yield T, "a waypoint's at wrong", none, {"waypoints": [{"at": [0, 0, 0]}, {"at": "there"}]}
    yield T, "a waypoint's ypr wrong", none, {"waypoints": [{"at": [0, 0, 0], "ypr": [1, 2, True]}, {"at": [1, 0, 0]}]}
    yield T, "crash: deviation not a number", prep(rail), {"edges": ["Rail.Edge1"], "deviation": "tight"}

    T = "robot_run"
    yield T, "reaches all", prep(arm(), path()), {"trajectory": "Path", "samples": 5}
    yield T, "a hundred samples by default, a tool set", prep(arm(tool=(0, 0, 100)), path()), {"robot": "Arm", "trajectory": "Path"}
    yield T, "misses the far end", prep(arm(axes=(1, 2, 3, 4, 5, 6)), path(pts=((0, 0, 0), (4000, 0, 0)))), {"trajectory": "Path", "samples": 9}
    yield T, "misses, FreeCAD says why", prep(arm(), path(pts=((0, 0, 0), (4000, 0, 0))), says_error=True), {"trajectory": "Path", "samples": 3}
    yield T, "more than twenty misses", prep(arm(), path(pts=((3000, 0, 0), (4000, 0, 0)))), {"trajectory": "Path", "samples": 30}
    yield T, "a trajectory with a base of its own", prep(arm(), path(Base=fc.Placement(V(0, 0, 50)))), {"trajectory": "Path", "samples": 2}
    yield T, "whole turns are the same pose", prep(arm(), path(), turns=1), {"trajectory": "Path", "samples": 3}
    yield T, "no duration", prep(arm(), path(pts=((1, 1, 1), (1, 1, 1)))), {"trajectory": "Path"}
    yield T, "one sample", prep(arm(), path()), {"trajectory": "Path", "samples": 1}
    yield T, "too many samples", prep(arm(), path()), {"trajectory": "Path", "samples": 5001}
    yield T, "trajectory left out", prep(arm(), path()), {}
    yield T, "not a trajectory", prep(arm(), path()), {"trajectory": "Arm"}
    yield T, "not a trajectory, and none here", prep(arm()), {"trajectory": "Arm"}
    yield T, "trajectory not here", prep(arm(), path()), {"trajectory": "Gone"}
    yield T, "no robot", prep(path()), {"trajectory": "Path"}
    yield T, "crash: samples a word", prep(arm(), path()), {"trajectory": "Path", "samples": "many"}

    T = "robot_trajectory"
    yield T, "two joined", prep(path(), path("Back", pts=((300, 400, 0), (0, 0, 0)))), {"op": "join", "trajectories": ["Path", "Back"]}
    yield T, "joined, named", prep(path(), path("Back")), {"op": "join", "trajectories": ["Path", "Back", "Path"], "name": "Loop"}
    yield T, "dressed: speed and acceleration", prep(path()), {"op": "dress", "trajectory": "Path", "speed": 50, "acceleration": 200}
    yield T, "dressed: moved", prep(path()), {"op": "dress", "trajectory": "Path", "move": [0, 0, 25], "cont": True}
    yield T, "dressed: turned", prep(path()), {"op": "dress", "trajectory": "Path", "ypr": [0, 0, 90], "cont": False}
    yield T, "dressed: moved and turned, named", prep(path()), {"op": "dress", "trajectory": "Path", "move": [1, 2, 3], "ypr": [10, 20, 30], "name": "Shifted"}
    yield T, "dressed: ypr replaces the orientations", prep(path()), {"op": "dress", "trajectory": "Path", "ypr": [0, 90, 0], "add": "UseOrientation"}
    yield T, "dressed: add spelt right", prep(path()), {"op": "dress", "trajectory": "Path", "ypr": [0, 90, 0], "add": "AddOrientation"}
    yield T, "dressed: add given, nothing to add", prep(path()), {"op": "dress", "trajectory": "Path", "add": "Sideways"}
    yield T, "dressed on a build with the shorter type name", prep(path(), no_types=("Robot::TrajectoryDressUpObject",)), {"op": "dress", "trajectory": "Path", "speed": 10}
    yield T, "dressed where ContType cannot be set", prep(path(), no_props=("ContType",)), {"op": "dress", "trajectory": "Path", "cont": True}
    yield T, "an older module's trajectory: no size, no length", prep(path(), bare_trajectories=True), {"op": "dress", "trajectory": "Path"}
    yield T, "add unknown", prep(path()), {"op": "dress", "trajectory": "Path", "move": [0, 0, 1], "add": "Sideways"}
    yield T, "one to join", prep(path()), {"op": "join", "trajectories": ["Path"]}
    yield T, "none to join", prep(path()), {"op": "join"}
    yield T, "a joined one not a trajectory", prep(path(), block), {"op": "join", "trajectories": ["Path", "Block"]}
    yield T, "dress: trajectory left out", prep(path()), {"op": "dress"}
    yield T, "op unknown", prep(path()), {"op": "reverse"}
    yield T, "op left out", prep(path()), {}
    yield T, "op a list", prep(path()), {"op": ["join"]}
    yield T, "move of two numbers", prep(path()), {"op": "dress", "trajectory": "Path", "move": [1, 2]}
    yield T, "crash: ypr of four numbers", prep(path()), {"op": "dress", "trajectory": "Path", "ypr": [1, 2, 3, 4]}
    yield T, "crash: speed a word", prep(path()), {"op": "dress", "trajectory": "Path", "speed": "slow"}

    T = "robot_export"
    yield T, "the compact form", prep(arm(), path()), {"trajectory": "Path"}
    yield T, "to a path in a folder", prep(arm(), path("Weld seam")), {"trajectory": "Weld seam", "path": "krl/seam"}
    yield T, "to a path that ends .SRC", prep(arm(), path()), {"trajectory": "Path", "path": "OUT.SRC"}
    yield T, "the label's spaces", prep(arm(), path("Weld seam")), {"robot": "Arm", "trajectory": "Weld seam"}
    yield T, "the full form where FreeCAD writes it", prep(arm(), path(), full_writes=True), {"trajectory": "Path", "full": True}
    yield T, "the full form on FreeCAD 1.1", prep(arm(), path()), {"trajectory": "Path", "full": True}
    yield T, "the exporter wrote nothing", prep(arm(), path(), writes_nothing=True), {"trajectory": "Path"}
    yield T, "the exporter failed", prep(arm(), path(), fail=("krl",)), {"trajectory": "Path"}
    yield T, "no exporter module", prep(arm(), path(), missing=("KukaExporter",)), {"trajectory": "Path"}
    yield T, "trajectory not here", prep(arm()), {"trajectory": "Gone"}
    yield T, "no robot", prep(path()), {"trajectory": "Path"}

    # ---- IFC edited in place -------------------------------------------------------------------------

    def building(walls=2, **extra):
        ents = [{"id": 1, "class": "IfcProject", "Name": "Annex"},
                {"id": 2, "class": "IfcBuildingStorey", "GlobalId": "0storeyGround000000001", "Name": "Ground", "Elevation": 0.0},
                {"id": 3, "class": "IfcBuildingStorey", "GlobalId": "0storeyFirst0000000002", "Name": "First", "Elevation": 3000.0},
                {"id": 4, "class": "IfcMaterial", "Name": "Brick"},
                {"id": 5, "class": "IfcMaterialLayerSet", "MaterialLayers": []},
                {"id": 6, "class": "IfcPropertySet", "Name": "Pset_WallCommon", "props": {"IsExternal": True, "FireRating": "REI30"}},
                {"id": 7, "class": "IfcSlab", "GlobalId": "0slab00000000000000001", "Name": "Floor slab", "storey": 2, "material": 5, "ObjectType": "FLOOR",
                 "qtos": {"Qto_SlabBaseQuantities": {"NetArea": 42.5}}, "Tag": "S1"},
                {"id": 8, "class": "IfcWindow", "GlobalId": "0window000000000000001", "Name": None}]
        for i in range(walls):
            ents.append({"id": 20 + i, "class": "IfcWall", "GlobalId": f"0wall{i:017d}", "Name": f"Outer wall {i + 1}", "Description": "load-bearing", "storey": 2 + i % 2,
                         "material": 4, "psets": {"Pset_WallCommon": 6} if i == 0 else {}})
        for e in ents:
            e.update(extra.get(e.get("Name") or "", {}))
        return {"schema": "IFC4", "entities": ents}

    def ifc_at(name, model=None, text=None):
        def put(s):
            os.makedirs(os.path.dirname(os.path.join(s.out_dir, name)), exist_ok=True)
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text if text is not None else json.dumps(model or building()))
        return put

    def open_ifc(name="house.ifc", model=None, edits=0):
        def do(s):
            ifc_at(name, model)(s)
            import ifcopenshell

            s._agentlink_ifc = {"file": ifcopenshell.open(os.path.join(s.out_dir, name)), "path": os.path.join(s.out_dir, name), "edits": edits}
        return do

    wall0, wall1 = "0wall" + "0" * 17, "0wall" + "0" * 16 + "1"

    T = "ifc_open"
    yield T, "a file in the session's folder", prep(ifc_at("house.ifc")), {"path": "house.ifc"}
    yield T, "one with no project and no storeys", prep(ifc_at("bare.ifc", {"schema": "IFC2X3", "entities": []})), {"path": "bare.ifc"}
    yield T, "no path", none, {}
    yield T, "not there", none, {"path": "gone.ifc"}
    yield T, "not an IFC file", prep(ifc_at("notes.ifc", text="hello")), {"path": "notes.ifc"}

    T = "ifc_find"
    yield T, "every product", prep(open_ifc()), {}
    yield T, "walls, in detail", prep(open_ifc()), {"class": "IfcWall", "detail": True}
    yield T, "a slab in detail: quantities, layers", prep(open_ifc()), {"class": "IfcSlab", "detail": True}
    yield T, "by name and storey", prep(open_ifc(model=building(4))), {"name": "outer", "storey": "ground"}
    yield T, "by a property", prep(open_ifc()), {"where": {"Pset_WallCommon.IsExternal": True}}
    yield T, "by ids", prep(open_ifc()), {"ids": [wall1, "0slab00000000000000001"]}
    yield T, "two of four listed", prep(open_ifc(model=building(4))), {"class": "IfcWall", "limit": 2}
    yield T, "on an older IfcOpenShell", prep(open_ifc(), old_psets=True), {"class": "IfcSlab", "detail": True}
    yield T, "none", prep(open_ifc()), {"class": "IfcBeam"}
    yield T, "no file open", none, {}
    yield T, "an id not in the file", prep(open_ifc()), {"ids": [wall0, "Outer wall 1"]}
    yield T, "a class IFC has not", prep(open_ifc()), {"class": "Wall"}
    yield T, "where without a set", prep(open_ifc()), {"where": {"IsExternal": True}}
    yield T, "crash: limit a word", prep(open_ifc()), {"limit": "all"}

    T = "ifc_edit"
    yield T, "attributes of one", prep(open_ifc()), {"ids": [wall0], "attributes": {"Name": "North wall", "Tag": "W-01"}}
    yield T, "properties: a set it has and a new one", prep(open_ifc()), {"ids": [wall0], "properties": {"Pset_WallCommon.FireRating": "REI60", "Pset_Mine.Batch": 7, "Pset_Mine.Lot": "A"}}
    yield T, "a material the file has", prep(open_ifc()), {"class": "IfcWindow", "material": "Brick"}
    yield T, "a new material, on walls that have one", prep(open_ifc()), {"class": "IfcWall", "material": "Concrete C30"}
    yield T, "moved to a storey", prep(open_ifc()), {"name": "outer", "storey_to": "First"}
    yield T, "classified", prep(open_ifc()), {"class": "IfcWall", "classification": {"system": "Uniclass 2015", "code": "Ss_25_10", "title": "Walls"}}
    yield T, "classified again: the system made once", prep(open_ifc()), {"class": "IfcWall", "classification": {"code": "Ss_25"}, "max": 2}
    yield T, "classified where IfcOpenShell cannot: a property set", prep(open_ifc(), fail=("classification.add_reference",)), {"ids": [wall0], "classification": {"code": "Ss_25_10"}}
    yield T, "everything at once", prep(open_ifc(edits=3)), {"storey": "Ground", "class": "IfcWall", "attributes": {"Description": "checked"}, "properties": {"Pset_QA.Checked": True},
                                                            "material": "Brick", "storey_to": "First", "classification": {"system": "X", "code": "1", "title": "One"}}
    yield T, "an older IfcOpenShell: one product a call", prep(open_ifc(), one_product=True), {"ids": [wall0], "material": "Brick", "storey_to": "First", "classification": {"code": "Ss"}}
    yield T, "by a property", prep(open_ifc()), {"where": {"Pset_WallCommon.FireRating": "REI30"}, "attributes": {"ObjectType": "EXTERNAL"}}
    yield T, "no file open", none, {"ids": [wall0], "attributes": {"Name": "x"}}
    yield T, "none match", prep(open_ifc()), {"class": "IfcBeam", "attributes": {"Name": "x"}}
    yield T, "nothing to change", prep(open_ifc()), {"class": "IfcWall"}
    yield T, "nothing to change: all empty", prep(open_ifc()), {"class": "IfcWall", "attributes": {}, "material": ""}
    yield T, "no filter", prep(open_ifc()), {"attributes": {"Description": "all"}}
    yield T, "too many match", prep(open_ifc(model=building(5))), {"class": "IfcWall", "attributes": {"Tag": "W"}, "max": 4}
    yield T, "classification without a code", prep(open_ifc()), {"class": "IfcWall", "classification": {"system": "Uniclass 2015"}}
    yield T, "classification a word", prep(open_ifc()), {"class": "IfcWall", "classification": "Ss_25_10"}
    yield T, "a property without a set", prep(open_ifc()), {"class": "IfcWall", "properties": {"FireRating": "REI60"}}
    yield T, "a storey the file has not", prep(open_ifc()), {"class": "IfcWall", "storey_to": "Roof"}
    yield T, "a storey, in a file with none", prep(open_ifc(model={"schema": "IFC4", "entities": [{"id": 1, "class": "IfcWall", "GlobalId": wall0, "Name": "W"}]})), {"class": "IfcWall", "storey_to": "Roof"}
    yield T, "an attribute IFC has not", prep(open_ifc()), {"ids": [wall0], "attributes": {"FireRating": "REI60"}}
    yield T, "an id not in the file", prep(open_ifc()), {"ids": ["nope"], "attributes": {"Name": "x"}}
    yield T, "crash: the property set cannot be made", prep(open_ifc(), fail=("pset.add_pset",)), {"ids": [wall1], "properties": {"Pset_Mine.Batch": 7}}
    yield T, "crash: max a word", prep(open_ifc()), {"class": "IfcWall", "attributes": {"Tag": "W"}, "max": "all"}

    T = "ifc_remove"
    yield T, "one", prep(open_ifc()), {"ids": [wall0]}
    yield T, "two, after other edits", prep(open_ifc(edits=2)), {"ids": [wall1, "0window000000000000001"]}
    yield T, "no ids", prep(open_ifc()), {}
    yield T, "ids empty", prep(open_ifc()), {"ids": []}
    yield T, "an id not in the file", prep(open_ifc()), {"ids": [wall0, "nope"]}
    yield T, "no file open", none, {"ids": [wall0]}
    yield T, "crash: the removal fails", prep(open_ifc(), fail=("root.remove_product",)), {"ids": [wall0]}

    T = "ifc_save"
    yield T, "a copy beside it", prep(open_ifc(edits=2)), {}
    yield T, "to a path in a folder", prep(open_ifc("in/house.ifc")), {"path": "out/changed.ifc"}
    yield T, "over the file it came from", prep(open_ifc(edits=1)), {"overwrite": True}
    yield T, "overwrite wins over a path", prep(open_ifc()), {"overwrite": True, "path": "other.ifc"}
    yield T, "no file open", none, {}

    renamed = building(3, **{"Outer wall 1": {"Name": "North wall", "material": 5, "storey": 3, "Tag": "W1", "psets": {}}, "Floor slab": {"ObjectType": "ROOF"}})
    renamed["entities"] = [e for e in renamed["entities"] if e.get("Name") != "Outer wall 2"]
    refired = building()
    refired["entities"][5]["props"] = {"IsExternal": True, "FireRating": "REI60", "Reference": "W"}

    T = "ifc_diff"
    yield T, "two alike", prep(ifc_at("a.ifc"), ifc_at("b.ifc")), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "one added, one removed, two changed", prep(ifc_at("a.ifc"), ifc_at("b.ifc", renamed)), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "the other way", prep(ifc_at("a.ifc"), ifc_at("b.ifc", renamed)), {"a": "b.ifc", "b": "a.ifc"}
    yield T, "a property changed and one added", prep(ifc_at("a.ifc"), ifc_at("b.ifc", refired)), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "all added, the first one listed", prep(ifc_at("a.ifc", {"schema": "IFC4", "entities": []}), ifc_at("b.ifc", building(1))), {"a": "a.ifc", "b": "b.ifc", "limit": 1}
    yield T, "b left out", prep(ifc_at("a.ifc")), {"a": "a.ifc"}
    yield T, "a left out", prep(ifc_at("a.ifc")), {"b": "a.ifc"}
    yield T, "a not there", prep(ifc_at("b.ifc")), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "b not there", prep(ifc_at("a.ifc")), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "a not an IFC file", prep(ifc_at("a.ifc", text="{}"), ifc_at("b.ifc")), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "b not an IFC file", prep(ifc_at("a.ifc"), ifc_at("b.ifc", text="ISO-10303-21;")), {"a": "a.ifc", "b": "b.ifc"}
    yield T, "crash: limit a word", prep(ifc_at("a.ifc"), ifc_at("b.ifc")), {"a": "a.ifc", "b": "b.ifc", "limit": "few"}
