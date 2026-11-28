# SPDX-License-Identifier: LGPL-2.1-or-later
# The result line (27 Nov): the first field of the answer of a solid feature,
# sketch_new, sketch_add, sketch_constrain and body_check. One fixed sentence
# for each fact, made from measured numbers (agentlink/resultline.py).
# Three groups:
#   - pure sentence tests (no FreeCAD);
#   - the FreeCAD-facing code on stand-ins (child processes): the numbers it
#     measures go to the sentences; result is the first key of each answer;
#   - run, batch and fast through the stand-in hub (test_fastpath.py, case result1127).
# Real shapes need a real FreeCAD: see the build report.
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import resultline as rl  # noqa: E402

BANNED = re.compile(r"\b(hole|notch|wall|wrong|probably|looks|should|will cut nothing)\b", re.I)
OLD = (0, 60, 0, 30, 0, 5)


class Pure(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual([rl.num(x) for x in (6000, 0.02, -0.0, 12.345, 1234567.5, -196.35)], ["6000", "0.02", "0", "12.35", "1234567.5", "-196.35"])
        self.assertEqual((rl.signed(5), rl.signed(-5), rl.signed(0)), ("+5", "-5", "0"))
        self.assertEqual((rl.span(0, 60), rl.span(30, 30.0005)), ("0..60", "30"))

    def test_against_inside_and_past_on_each_axis(self):
        # 27 Nov QA (F1): an axis that is inside says the distance to each side
        self.assertEqual(rl.against((10, 20, 5, 6, 1, 2), OLD), "x inside (10 from -x, 40 from +x); y inside (5 from -y, 24 from +y); z inside (1 from -z, 3 from +z)")
        for i, ax in enumerate("xyz"):
            lo = list(OLD)
            lo[2 * i] -= 7
            self.assertIn(f"{ax} past -{ax} by 7", rl.against(tuple(lo), OLD))
            hi = list(OLD)
            hi[2 * i + 1] += 3.5
            self.assertIn(f"{ax} past +{ax} by 3.5", rl.against(tuple(hi), OLD))
        both = rl.against((0, 60, 0, 30, -20, 20), OLD)
        self.assertEqual(both, "x inside (0 from -x, 0 from +x); y inside (0 from -y, 0 from +y); z past -z by 20 and past +z by 15")
        self.assertTrue(rl.against((0, 60.0004, 0, 30, 0, 5), OLD).startswith("x inside (0 from -x, 0 from +x); "))  # the equality tolerance

    def test_contact_words(self):
        self.assertEqual(rl.touch_text(["+z at z 5", "-x at x 0"], 0, None, True), "It touches the body on +z at z 5 and -x at x 0.")
        self.assertEqual(rl.touch_text(["+z at z 5"], 3, None, True), "It touches the body on +z at z 5. 3 faces of the new material were not looked at.")
        self.assertEqual(rl.touch_text([], 0, 12.5, False), "It touches the body nowhere (nearest gap 12.5 mm).")
        self.assertEqual(rl.touch_text([], 0, None, False), "It touches the body nowhere.")
        self.assertEqual(rl.touch_text([], 0, 0.0, True), "It touches the body but shares no face with it.")
        self.assertEqual(rl.touch_text([], 0, None, None), "")
        self.assertEqual(rl.opens_text(["+z at z 10"], 0), "It opens on +z at z 10.")
        self.assertEqual(rl.opens_text([], 0), "It opens on no face of the body: it is closed inside it.")
        self.assertEqual(rl.opens_text([], 0, looked=False), "")

    def test_solids(self):
        self.assertEqual(rl.solids_text(2, 1), "The body is 2 solids (was 1).")
        self.assertEqual(rl.solids_text(1, 1), "The body is 1 solid (was 1).")
        self.assertEqual(rl.solids_text(None, 1), "")

    def test_a_pad_that_touches_nowhere_and_makes_two_solids(self):
        got = rl.feature_result("Pad 2", "pd_pad", 6000, region=[(-30, 0, 30, 35, 5, 45)], old_box=OLD, faces=[], gap=12.5, touching=False, solids=2, solids_was=1)
        self.assertEqual(got, "Pad 2 added material, volume change +6000 mm³. The new material is x -30..0, y 30..35, z 5..45. "
                              "The body before is x 0..60, y 0..30, z 0..5. Against the body before: x past -x by 30; y past +y by 5; z past +z by 40. "
                              "It touches the body nowhere (nearest gap 12.5 mm). The body is 2 solids (was 1).")

    def test_a_pad_on_top(self):
        got = rl.feature_result("Pad", "pd_pad", 9000, region=[(0, 60, 0, 30, 5, 10)], old_box=OLD, faces=["+z at z 5"], touching=True, solids=1, solids_was=1)
        self.assertIn("It touches the body on +z at z 5. The body is 1 solid (was 1).", got)
        self.assertIn("x inside (0 from -x, 0 from +x); y inside (0 from -y, 0 from +y); z past +z by 5", got)

    def test_the_first_feature(self):
        got = rl.feature_result("Pad", "pd_pad", 9000, body_box=OLD, solids=1)
        self.assertEqual(got, "Pad added material, volume change +9000 mm³. The body is 1 solid, x 0..60, y 0..30, z 0..5.")

    def test_a_cut_keeps_opens_on_and_says_each_piece(self):
        pieces = [(12.5, 15, -2.5, 0, -20, 0), (-15, -12.5, -2.5, 0, -20, 0)]
        got = rl.feature_result("Pocket", "pd_pocket", -196.35, region=pieces, old_box=(-30, 30, -15, 15, -20, 20), cut=True,
                                faces=["+y at y 0", "-z at z -20"], solids=1, solids_was=1)
        self.assertIn("Pocket removed material, volume change -196.35 mm³.", got)
        self.assertIn("The removed material is in 2 pieces: x 12.5..15, y -2.5..0, z -20..0; x -15..-12.5, y -2.5..0, z -20..0.", got)
        self.assertIn("It opens on +y at y 0 and -z at z -20.", got)
        more = rl.feature_result("Pocket", "pd_pocket", -1, region=pieces[:1], region_more=3, old_box=OLD, cut=True, faces=[], solids=1, solids_was=1)
        self.assertIn("in 4 pieces: x 12.5..15, y -2.5..0, z -20..0; 3 more not shown.", more)

    def test_what_was_not_measured_is_left_out(self):
        self.assertEqual(rl.feature_result("Pad", "pd_pad", None), "Pad added material.")
        got = rl.feature_result("Pad", "pd_pad", 5, old_box=OLD, body_box=OLD, note="Not worked out: the body has more than 2000 faces.", solids=1, solids_was=1)
        self.assertIn("The body before is x 0..60", got)
        self.assertIn("Not worked out", got)
        self.assertEqual(rl.feature_head("Cut", "pd_pocket", 0.001), "Cut: volume change 0 mm³.")

    def test_a_fillet_says_its_edges_and_its_radius(self):
        got = rl.dressup_result("Fillet", "pd_fillet", -214.6, 4, "radius 5 mm", ["Edge1: line along z, 10 mm, mid [-40, -30, 5], outside"], 1, 1)
        self.assertEqual(got, "Fillet: FreeCAD was given 4 edges, radius 5 mm, volume change -214.6 mm³. Edges: Edge1: line along z, 10 mm, mid [-40, -30, 5], outside. The body is 1 solid (was 1).")
        self.assertIn("Chamfer: FreeCAD was given 1 edge, sizes 2 and 3 mm", rl.dressup_result("Chamfer", "pd_chamfer", 5, 1, "sizes 2 and 3 mm", [], 1, 1))

    def test_sketch_new_says_the_normal_range_and_the_face(self):
        axes = "x runs +X; y runs +Y; the normal points +Z. [0, 0] is at world (0, 0, 0)."
        got = rl.sketch_new_result("HoleSketch", "XY", axes, ((-40, 40), (-30, 30), (0, 10)))
        self.assertEqual(got, f"Sketch HoleSketch is on XY. {axes} The body spans sketch x -40..40, y -30..30, and along the normal 0..10 "
                              "(0 is the sketch plane; + is the way the normal points).")
        face = rl.sketch_new_result("Top", "face at [30, 15, 5]", axes, ((-30, 60), (0, 35), (-5, 0)), ((0, 60), (0, 30), (0, 0)))
        self.assertIn("along the normal -5..0", face)
        self.assertTrue(face.endswith("The face spans sketch x 0..60, y 0..30."))
        self.assertIn("The body has no solid yet.", rl.sketch_new_result("A", "XY", axes))

    def test_frames_with_x_running_minus_x(self):
        # A sketch on the +y end face of a plate (y = 30): x runs -X, y runs up, the normal is +Y.
        frame = ((0, 30, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))
        self.assertEqual(rl.frame_ranges(frame, (0, 60, 0, 30, 0, 5)), ((-60, 0), (0, 5), (-30, 0)))
        self.assertEqual(rl.world_box(frame, (0, 30), (5, 45)), (-30, 0, 30, 30, 5, 45))

    def test_sketch_add_shapes(self):
        frame = ((0, 30, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))
        rect = rl.shape_text("rectangle", [0, 1, 2, 3], (0, 30), (5, 45), rl.world_box(frame, (0, 30), (5, 45)))
        self.assertEqual(rect, "rectangle, ids 0-3: sketch x 0..30, y 5..45; world x -30..0, y 30, z 5..45.")
        circle = rl.shape_text("circle", [4], (12.5, 17.5), (-2.5, 2.5), circle=((15, 0), 2.5))
        self.assertEqual(circle, "circle, id 4: centre (15, 0), radius 2.5; sketch x 12.5..17.5, y -2.5..2.5.")
        arc = rl.shape_text("arc", [5], (0, 10), (0, 10), arc=((10, 0), (7.07, 7.07), (0, 10)))
        self.assertIn("start (10, 0), middle (7.07, 7.07), end (0, 10)", arc)
        self.assertEqual(rl.sketch_add_result([rect], 1, 1, 0), rect + " The sketch has 1 wire, 1 closed, 0 open ends.")
        self.assertEqual(rl.sketch_add_result([rect], None, None, None), rect)
        self.assertEqual(rl.id_text([0, 1, 2, 3]), "ids 0-3")
        self.assertEqual(rl.id_text([0, 2, 5]), "ids 0, 2 and 5")

    def test_sketch_constrain_says_a_big_and_a_small_move(self):
        moves = [("the end of arc 0 and the start of line 2", [("the end of arc 0", 40.0)]),
                 ("the end of arc 1 and the start of line 3", [("the start of line 3", 0.02)])]
        got = rl.constraint_result(["#4 coincident: the end of arc 0 and the start of line 2"], 14, 6, moves, ((-22.97, 185.29), (-20.35, 19.93)))
        self.assertEqual(got, "Added #4 coincident: the end of arc 0 and the start of line 2. Degrees of freedom: 14 before, 6 after. "
                              "The join of the end of arc 0 and the start of line 2 moved the end of arc 0 by 40 mm. "
                              "The join of the end of arc 1 and the start of line 3 moved the start of line 3 by 0.02 mm. "
                              "After the solve the sketch's shapes span sketch x -22.97..185.29, y -20.35..19.93.")
        self.assertNotIn("moved", rl.constraint_result(["#1 horizontal: line 0"], 5, 4))
        self.assertIn("2 more joins not shown.", rl.constraint_result(["x"], 1, 0, moves[:1], None, 2))

    def test_body_check(self):
        got = rl.body_check_result("Bracket", 2, "2 separate solids that do not touch (nearest gap 12.5 mm)", True, True, (0, 60, 0, 30, 0, 40), 14053.65)
        self.assertEqual(got, "Bracket is 2 separate solids that do not touch (nearest gap 12.5 mm); valid, closed; box x 0..60, y 0..30, z 0..40; volume 14053.65 mm³.")
        self.assertEqual(rl.body_check_result("B", 1, None, False, True, None, None), "B is 1 solid; not valid, closed.")

    def test_fast_lines_keep_the_order(self):
        rows = [("calls.0", "pd_pad", {"result": "A."}), ("calls.1", "get", {"x": 1}), ("calls.2", "pd_pocket", {"result": "B."})]
        self.assertEqual(rl.fast_lines(rows), ["calls.0 pd_pad: A.", "calls.2 pd_pocket: B."])

    def test_no_verdict_or_shape_word(self):
        said = []
        said.append(rl.feature_result("Pad", "pd_pad", 5, region=[(0, 1, 0, 1, 0, 1)], old_box=OLD, faces=[], gap=1, touching=False, solids=2, solids_was=1))
        said.append(rl.feature_result("Pocket", "pd_pocket", -5, region=[(0, 1, 0, 1, 0, 1)], old_box=OLD, cut=True, faces=[], solids=1, solids_was=1))
        said.append(rl.dressup_result("Fillet", "pd_fillet", -1, 2, "radius 1 mm", ["Edge1"], 1, 1))
        said.append(rl.sketch_new_result("S", "XY", "axes.", ((0, 1), (0, 1), (0, 1)), ((0, 1), (0, 1), (0, 0))))
        said.append(rl.sketch_add_result([rl.shape_text("arc", [0], (0, 1), (0, 1), arc=((0, 0), (1, 1), (2, 2)))], 1, 0, 2))
        said.append(rl.constraint_result(["c"], 3, 2, [("a and b", [("a", 1)])], ((0, 1), (0, 1))))
        said.append(rl.body_check_result("B", 2, "2 separate solids", True, False, OLD, 1))
        for t in said:
            self.assertIsNone(BANNED.search(t), t)
        # and no such word in any fixed text of the module
        tree = ast.parse(open(os.path.join(ROOT, "agentlink", "resultline.py"), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and not n.value.startswith("\n") and len(n.value) < 120:
                self.assertIsNone(BANNED.search(n.value), n.value)


# ---- the FreeCAD-facing code on stand-ins -------------------------------------------------

CHILD = '''
import json, sys, types
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.families import pd_common as pc
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


FAKES0 = '''
class BB:
    def __init__(s, b): s.XMin, s.XMax, s.YMin, s.YMax, s.ZMin, s.ZMax = b; s.DiagonalLength = 100.0
class Sol:
    def __init__(s, b, vol=10.0): s.BoundBox = BB(b); s.Volume = vol
class Shp:
    def __init__(s, b, solids=1, faces=6, gap=None):
        s.BoundBox = BB(b); s.Solids = [Sol(b)] * solids; s.Faces = [object()] * faces; s.gap = gap; s.Volume = 100.0
    def isNull(s): return False
    def distToShape(s, o): return (s.gap, [], [])
class Feat:
    Label = "Pad 2"; TypeId = "PartDesign::Pad"
    def __init__(s, old=None): s.BaseFeature = types.SimpleNamespace(Shape=old) if old is not None else None
pc.Part = types.SimpleNamespace(Compound=lambda x: x)
'''


FAKES = textwrap.indent(FAKES0, "        ")


class OnStandIns(unittest.TestCase):
    def test_an_add_that_touches_a_face(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5)); new = Shp((0, 60, 0, 30, 0, 10))
        pc._lids = lambda reg, skin, diag, flip=False: (["+z at z 5"], [])
        keep = {"old": old, "reg": Shp((0, 60, 0, 30, 5, 10)), "cut": False, "tol": 0.01}
        body = types.SimpleNamespace(Shape=new)
        print(json.dumps(pc.result_line(Feat(old), body, "pd_pad", 9000.0, keep)))
        ''')
        self.assertEqual(got, "Pad 2 added material, volume change +9000 mm³. The new material is x 0..60, y 0..30, z 5..10. The body before is x 0..60, y 0..30, z 0..5. "
                              "Against the body before: x inside (0 from -x, 0 from +x); y inside (0 from -y, 0 from +y); z past +z by 5. "
                              "It touches the body on +z at z 5. The body is 1 solid (was 1).")

    def test_an_add_apart_makes_two_solids_and_says_the_gap(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5)); new = Shp((0, 60, 0, 50, 0, 45), solids=2)
        pc._lids = lambda reg, skin, diag, flip=False: ([], [])
        keep = {"old": old, "reg": Shp((0, 10, 40, 50, 20, 45), gap=12.5), "cut": False, "tol": 0.01}
        print(json.dumps(pc.result_line(Feat(old), types.SimpleNamespace(Shape=new), "pd_pad", 500.0, keep)))
        ''')
        self.assertIn("It touches the body nowhere (nearest gap 12.5 mm). The body is 2 solids (was 1).", got)

    def test_a_cut_and_the_first_feature_and_a_failed_measure(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5)); new = Shp((0, 60, 0, 30, 0, 5))
        keep = {"old": old, "reg": Shp((10, 20, 10, 20, 0, 5)), "cut": True, "lids": ["+z at z 5", "-z at z 0"], "tol": 0.01}
        a = pc.result_line(Feat(old), types.SimpleNamespace(Shape=new), "pd_pocket", -500.0, keep)
        first = pc.result_line(Feat(None), types.SimpleNamespace(Shape=new), "pd_pad", 9000.0, {})
        broken = pc.result_line(Feat(old), types.SimpleNamespace(Shape=None), "pd_pad", 9000.0, {})
        print(json.dumps([a, first, broken]))
        ''')
        self.assertIn("It opens on +z at z 5 and -z at z 0.", got[0])
        self.assertEqual(got[1], "Pad 2 added material, volume change +9000 mm³. The body is 1 solid, x 0..60, y 0..30, z 0..5.")
        self.assertTrue(got[2].startswith("Pad 2 added material"))  # a failed measure never raises

    def test_a_fillet_reads_the_radius_from_the_feature(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5))
        f = Feat(old); f.TypeId = "PartDesign::Fillet"; f.Label = "Fillet"; f.Radius = types.SimpleNamespace(Value=5.0); f.Base = (None, ["Edge1", "Edge2"])
        print(json.dumps(pc.result_line(f, types.SimpleNamespace(Shape=Shp((0, 60, 0, 30, 0, 5))), "pd_fillet", -12.5, {}, ["2 edges: 2 outside (lose material)", "Edge1: line along z"])))
        ''')
        self.assertEqual(got, "Fillet: FreeCAD was given 2 edges, radius 5 mm, volume change -12.5 mm³. Edges: 2 edges: 2 outside (lose material); Edge1: line along z. The body now is x 0..60, y 0..30, z 0..5. The body is 1 solid (was 1).")

    def test_the_answer_of_each_kind_starts_with_result(self):
        got = child('''
        import tempfile
        from agentlink.families import sketch, feature
        s = fc.Session(tempfile.mkdtemp())
        b = fc.body(s, "Plate")
        fc.drawing(s, b, "PlateSketch")
        def tool(fam, name): return next(t for t in fam.tools(s) if t.name == name)
        out = {}
        out["sketch_add"] = tool(sketch, "sketch_add").fn({"sketch": "PlateSketch", "kind": "rectangle", "center": [0, 0], "size": [40, 20]})
        out["sketch_constrain"] = tool(sketch, "sketch_constrain").fn({"sketch": "PlateSketch", "type": "distance", "refs": [0], "value": 7})
        out["sketch_new"] = tool(sketch, "sketch_new").fn({"body": "Plate", "plane": "XY", "name": "S2"})
        s2 = fc.Session(tempfile.mkdtemp())
        b2 = fc.body(s2, "Tut")
        fc.sketch(s2, b2, "Profile")
        s = s2
        out["pd_pad"] = tool(feature, "pd_pad").fn({"body": "Tut", "sketch": "Profile", "length": 5})
        print(json.dumps({k: [list(v)[0], v.get("result"), v.get("axes", "")] for k, v in out.items()}))
        ''')
        for kind, (first, line, axes) in got.items():
            self.assertEqual(first, "result", kind)
            self.assertIsInstance(line, str, kind)
            # the axes words are orient.axes_line's own (they name what a pocket does); the rest is the line's
            self.assertIsNone(BANNED.search(line.replace(axes, "") if axes else line), line)
        self.assertTrue(got["sketch_add"][1].startswith("rectangle, ids 0-3: construction not given, so construction is false; sketch x"), got["sketch_add"][1])
        self.assertTrue(got["sketch_constrain"][1].startswith("Added "))
        self.assertIn("Degrees of freedom:", got["sketch_constrain"][1])
        self.assertTrue(got["sketch_new"][1].startswith("Sketch S2 is on XY."))
        self.assertTrue(got["pd_pad"][1].startswith("Pad added material"))

    def test_body_check_starts_with_result(self):
        from test_stem_findings_more import run_stub

        out = run_stub(textwrap.dedent("""
            from agentlink.tools import Session
            body = Obj("Body", "PartDesign::Body", Shape(2), "Stem")
            body.AllowCompound = True
            s = Session.__new__(Session)
            s.doc, s.meta = Doc([body]), {}
            Shape.distToShape = lambda self, o: (12.5, [], [])
            r = s.body_check({"body": "Stem"})
            print(json.dumps([list(r)[0], r["result"]]))
        """))
        self.assertEqual(out[0], "result")
        self.assertIn("2 separate solids that do not touch (nearest gap 12.5 mm)", out[1])


class Joins(unittest.TestCase):
    def test_every_join_that_moved_is_said_with_no_lower_limit(self):
        from test_qa_sketch_1124 import SETUP, in_a_process

        got = in_a_process(SETUP + '''
    from agentlink.families import sketch
    P = lambda x, y: types.SimpleNamespace(x=x, y=y)
    now = {(0, 2): P(0.0, 20.0), (3, 1): P(0.02, -12.5), (1, 1): P(50.0, 0.0), (2, 2): P(50.0, 0.0)}
    class Arc: pass
    class Line: pass
    sk = types.SimpleNamespace(Geometry=[Arc(), Line(), Line(), Line()], getPoint=lambda g, p: now[(g, p)])
    joins = [("coincident", (0, 2, 3, 1), (0.0, 60.0), (0.0, -12.5), 72.5), ("coincident", (1, 1, 2, 2), (50.0, 0.0), (50.0, 0.0), 0.0)]
    moves = sketch.join_moves(sk, joins)
    print(json.dumps([[m[1], [[w, round(d, 3)] for w, d in m[5]]] for m in moves]))
''')
        # the first join moved a point 40 mm and the other 0.02 mm; the second did not move: not said
        self.assertEqual(got, [[[0, 2, 3, 1], [["the end of arc 0", 40.0], ["the start of line 3", 0.02]]]])


class ThroughTheHub(unittest.TestCase):
    _got = []

    @classmethod
    def hub(cls):
        if not cls._got:
            r = subprocess.run([sys.executable, os.path.join(HERE, "test_fastpath.py"), "child", "result1127"], capture_output=True, text=True, timeout=180, cwd=ROOT)
            if r.returncode != 0:
                raise AssertionError(r.stderr[-3000:])
            cls._got.append(json.loads(r.stdout.strip().splitlines()[-1]))
        return cls._got[0]

    def test_run_has_result_first(self):
        self.assertEqual(list(self.hub()["run"]["body"])[0], "result")

    def test_each_call_of_a_batch_has_result_first(self):
        rows = self.hub()["batch"]["body"]["results"]
        self.assertEqual([list(r["result"])[0] for r in rows if "result" in r["result"]], ["result", "result"])
        self.assertNotIn("result", rows[1]["result"])

    def test_fast_lists_the_result_lines_in_order_and_keeps_its_facts(self):
        body = self.hub()["fast"]["body"]
        self.assertEqual(list(body)[0], "result")
        self.assertEqual(body["result"], ["calls.0 probe_result: Probe 5 made one object.", "calls.2 probe_result: Probe 7 made one object."])
        self.assertIn("fast", body)
        self.assertIn("made", body)
        self.assertNotIn("result", self.hub()["fastNone"]["body"])


if __name__ == "__main__":
    unittest.main()
