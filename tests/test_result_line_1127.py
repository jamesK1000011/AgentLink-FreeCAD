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
        self.assertEqual(rl.box_rec(OLD), {"x": [0.0, 60.0], "y": [0.0, 30.0], "z": [0.0, 5.0]})

    def test_against_inside_and_past_on_each_axis(self):
        # 27 Nov QA (F1): an axis that is inside says the distance to each side
        self.assertEqual(rl.against_rec((10, 20, 5, 6, 1, 2), OLD), {"x": {"inside": {"-x": 10.0, "+x": 40.0}}, "y": {"inside": {"-y": 5.0, "+y": 24.0}},
                                                                    "z": {"inside": {"-z": 1.0, "+z": 3.0}}})
        for i, ax in enumerate("xyz"):
            lo = list(OLD)
            lo[2 * i] -= 7
            self.assertEqual(rl.against_rec(tuple(lo), OLD)[ax], {"past": {f"-{ax}": 7.0}})
            hi = list(OLD)
            hi[2 * i + 1] += 3.5
            self.assertEqual(rl.against_rec(tuple(hi), OLD)[ax], {"past": {f"+{ax}": 3.5}})
        both = rl.against_rec((0, 60, 0, 30, -20, 20), OLD)
        self.assertEqual(both["x"], {"inside": {"-x": 0.0, "+x": 0.0}})
        self.assertEqual(both["z"], {"past": {"-z": 20.0, "+z": 15.0}})
        self.assertEqual(rl.against_rec((0, 60.0004, 0, 30, 0, 5), OLD)["x"], {"inside": {"-x": 0.0, "+x": 0.0}})  # the equality tolerance

    def test_contact_records(self):
        self.assertEqual(rl.touch_rec(["+z at z 5", "-x at x 0"], 0, None, True), {"touching": True, "faces": ["+z at z 5", "-x at x 0"]})
        self.assertEqual(rl.touch_rec(["+z at z 5"], 3, None, True), {"touching": True, "faces": ["+z at z 5"], "facesNotLooked": 3})
        self.assertEqual(rl.touch_rec([], 0, 12.5, False), {"touching": False, "gap": 12.5})
        self.assertEqual(rl.touch_rec([], 0, None, False), {"touching": False})
        self.assertEqual(rl.touch_rec([], 0, 0.0, True), {"touching": True, "faces": []})
        self.assertEqual(rl.touch_rec([], 0, None, None), {})

    def test_a_pad_that_touches_nowhere_and_makes_two_solids(self):
        got = rl.feature_result("pd_pad", 6000, region=[(-30, 0, 30, 35, 5, 45)], old_box=OLD, faces=[], gap=12.5, touching=False, solids=2, solids_was=1)
        self.assertEqual(got, {"material": "added", "bodyBefore": {"x": [0.0, 60.0], "y": [0.0, 30.0], "z": [0.0, 5.0]},
                               "againstBefore": {"x": {"past": {"-x": 30.0}}, "y": {"past": {"+y": 5.0}}, "z": {"past": {"+z": 40.0}}},
                               "touches": {"touching": False, "gap": 12.5}, "solidsWas": 1})

    def test_a_pad_on_top(self):
        got = rl.feature_result("pd_pad", 9000, region=[(0, 60, 0, 30, 5, 10)], old_box=OLD, faces=["+z at z 5"], touching=True, solids=1, solids_was=1)
        self.assertEqual(got["touches"], {"touching": True, "faces": ["+z at z 5"]})
        self.assertEqual(got["againstBefore"], {"x": {"inside": {"-x": 0.0, "+x": 0.0}}, "y": {"inside": {"-y": 0.0, "+y": 0.0}}, "z": {"past": {"+z": 5.0}}})

    def test_the_first_feature(self):
        # the body's box, volume and solids are the answer's own keys: only the material is left
        self.assertEqual(rl.feature_result("pd_pad", 9000), {"material": "added"})

    def test_a_cut_keeps_opens_on_and_says_each_piece(self):
        pieces = [(12.5, 15, -2.5, 0, -20, 0), (-15, -12.5, -2.5, 0, -20, 0)]
        got = rl.feature_result("pd_pocket", -196.35, region=pieces, old_box=(-30, 30, -15, 15, -20, 20), cut=True,
                                faces=["+y at y 0", "-z at z -20"], solids=1, solids_was=1)
        self.assertEqual(got["material"], "removed")
        self.assertEqual(got["pieces"], [{"x": [12.5, 15.0], "y": [-2.5, 0.0], "z": [-20.0, 0.0]}, {"x": [-15.0, -12.5], "y": [-2.5, 0.0], "z": [-20.0, 0.0]}])
        self.assertNotIn("touches", got)
        self.assertNotIn("opens", got)  # the answer's opens lists the faces
        more = rl.feature_result("pd_pocket", -1, region=pieces[:1], region_more=3, old_box=OLD, cut=True, faces=[], faces_more=8, solids=1, solids_was=1)
        self.assertEqual((more["piecesNotShown"], more["opensNotLooked"], len(more["pieces"])), (3, 8, 1))

    def test_what_was_not_measured_is_left_out(self):
        self.assertEqual(rl.feature_result("pd_pad", None), {"material": "added"})
        self.assertEqual(rl.feature_result("pd_cut", None), {})
        got = rl.feature_result("pd_pad", 5, old_box=OLD, solids=1, solids_was=1)
        self.assertEqual(got, {"material": "added", "bodyBefore": rl.box_rec(OLD), "solidsWas": 1})
        self.assertEqual(rl.feature_result("pd_pocket", 0.001), {})  # a volume change that rounds to 0 has no material word
        self.assertEqual(rl.material("pd_pocket", -0.006), "removed")

    def test_a_dress_up_says_edges_given_and_edges_changed(self):
        edges = [{"edge": "Edge1", "kind": "line", "along": "z", "length": 10.0, "mid": [-40.0, -30.0, 5.0], "side": "outside"}]
        got = rl.dressup_result(4, {"size": 5.0}, edges, 1, 1, changed=4)
        self.assertEqual(got, {"edgesGiven": 4, "edgesChanged": 4, "size": 5.0, "edgesNotShown": 3, "solidsWas": 1})
        self.assertEqual(rl.dressup_result(1, {"size": 2.0, "size2": 3.0}), {"edgesGiven": 1, "size": 2.0, "size2": 3.0})

    def test_frames_with_x_running_minus_x(self):
        # A sketch on the +y end face of a plate (y = 30): x runs -X, y runs up, the normal is +Y.
        frame = ((0, 30, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))
        self.assertEqual(rl.frame_ranges(frame, (0, 60, 0, 30, 0, 5)), ((-60, 0), (0, 5), (-30, 0)))
        self.assertEqual(rl.world_box(frame, (0, 30), (5, 45)), (-30, 0, 30, 30, 5, 45))

    def test_sketch_add_shapes(self):
        frame = ((0, 30, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))
        rect = rl.shape_rec((0, 30), (5, 45), rl.world_box(frame, (0, 30), (5, 45)))
        self.assertEqual(rect, {"sketchExtent": {"x": [0.0, 30.0], "y": [5.0, 45.0]}, "worldBox": {"x": [-30.0, 0.0], "y": [30.0, 30.0], "z": [5.0, 45.0]}})
        circle = rl.shape_rec((12.5, 17.5), (-2.5, 2.5), circle=((15, 0), 2.5))
        self.assertEqual(circle["circle"], {"center": [15.0, 0.0], "radius": 2.5})
        arc = rl.shape_rec((0, 10), (0, 10), arc=((10, 0), (7.07, 7.07), (0, 10)))
        self.assertEqual(arc["arc"], {"start": [10.0, 0.0], "middle": [7.07, 7.07], "end": [0.0, 10.0]})
        self.assertEqual(rl.shape_rec(line=((0, 0), (3, 4)))["line"], {"from": [0.0, 0.0], "to": [3.0, 4.0]})
        self.assertEqual(rl.sketch_add_result([rect], 0), {"shapes": [rect], "openEnds": 0})
        self.assertEqual(rl.sketch_add_result([rect], None), {"shapes": [rect]})

    def test_sketch_constrain_says_a_big_and_a_small_move(self):
        con = {"id": 4, "type": "Coincident", "refs": [[0, 2], [2, 1]]}
        moves = [{"join": [[0, 2], [2, 1]], "moved": [{"ref": [0, 2], "mm": 40.0}]}, {"join": [[1, 2], [3, 1]], "moved": [{"ref": [3, 1], "mm": 0.02}]}]
        got = rl.constraint_result([con], 14, moves, ((-22.97, 185.29), (-20.35, 19.93)))
        self.assertEqual(got, {"constraints": [con], "dofBefore": 14, "moved": moves, "sketchExtent": {"x": [-22.97, 185.29], "y": [-20.35, 19.93]}})
        self.assertNotIn("moved", rl.constraint_result([con], 5))
        self.assertEqual(rl.constraint_result([con], None, moves[:1], None, 2)["joinsNotShown"], 2)

    def test_body_check(self):
        self.assertEqual(rl.body_check_result(12.5), {"nearestGap": 12.5, "solidsTouch": False})
        self.assertEqual(rl.body_check_result(0.0), {"nearestGap": 0.0, "solidsTouch": True})
        self.assertEqual(rl.body_check_result(None), {})  # one solid: valid, closed, solids, volume, checkGeometry are the answer's keys

    def test_no_sentence_in_a_record(self):
        said = [rl.feature_result("pd_pad", 5, region=[(0, 1, 0, 1, 0, 1)], old_box=OLD, faces=[], gap=1, touching=False, solids=2, solids_was=1),
                rl.feature_result("pd_pocket", -5, region=[(0, 1, 0, 1, 0, 1)], old_box=OLD, cut=True, faces=[], solids=1, solids_was=1),
                rl.dressup_result(2, {"size": 1.0}, [{"edge": "Edge1"}], 1, 1),
                rl.sketch_add_result([rl.shape_rec(arc=((0, 0), (1, 1), (2, 2)))], 2),
                rl.constraint_result([{"id": 0, "type": "Horizontal", "refs": [[0, 0]]}], 3, [], ((0, 1), (0, 1))),
                rl.body_check_result(3.0)]

        def strings(x):
            if isinstance(x, str):
                yield x
            elif isinstance(x, dict):
                for k, v in x.items():
                    yield k
                    yield from strings(v)
            elif isinstance(x, (list, tuple)):
                for v in x:
                    yield from strings(v)

        for r in said:
            for t in strings(r):
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
        self.assertEqual(got, {"material": "added", "bodyBefore": {"x": [0.0, 60.0], "y": [0.0, 30.0], "z": [0.0, 5.0]},
                               "againstBefore": {"x": {"inside": {"-x": 0.0, "+x": 0.0}}, "y": {"inside": {"-y": 0.0, "+y": 0.0}}, "z": {"past": {"+z": 5.0}}},
                               "touches": {"touching": True, "faces": ["+z at z 5"]}, "solidsWas": 1})

    def test_an_add_apart_makes_two_solids_and_says_the_gap(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5)); new = Shp((0, 60, 0, 50, 0, 45), solids=2)
        pc._lids = lambda reg, skin, diag, flip=False: ([], [])
        keep = {"old": old, "reg": Shp((0, 10, 40, 50, 20, 45), gap=12.5), "cut": False, "tol": 0.01}
        print(json.dumps(pc.result_line(Feat(old), types.SimpleNamespace(Shape=new), "pd_pad", 500.0, keep)))
        ''')
        self.assertEqual(got["touches"], {"touching": False, "gap": 12.5})
        self.assertEqual(got["solidsWas"], 1)

    def test_a_cut_and_the_first_feature_and_a_failed_measure(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5)); new = Shp((0, 60, 0, 30, 0, 5))
        keep = {"old": old, "reg": Shp((10, 20, 10, 20, 0, 5)), "cut": True, "lids": ["+z at z 5", "-z at z 0"], "tol": 0.01}
        a = pc.result_line(Feat(old), types.SimpleNamespace(Shape=new), "pd_pocket", -500.0, keep)
        first = pc.result_line(Feat(None), types.SimpleNamespace(Shape=new), "pd_pad", 9000.0, {})
        broken = pc.result_line(Feat(old), types.SimpleNamespace(Shape=None), "pd_pad", 9000.0, {})
        print(json.dumps([a, first, broken]))
        ''')
        self.assertEqual(got[0]["material"], "removed")
        self.assertNotIn("touches", got[0])
        self.assertEqual(got[1], {"material": "added"})  # the first feature: the body is the answer's bounds
        self.assertEqual(got[2]["material"], "added")  # a failed measure never raises

    def test_a_fillet_reads_the_radius_from_the_feature(self):
        got = child(FAKES + '''
        old = Shp((0, 60, 0, 30, 0, 5))
        f = Feat(old); f.TypeId = "PartDesign::Fillet"; f.Label = "Fillet"; f.Radius = types.SimpleNamespace(Value=5.0); f.Base = (None, ["Edge1", "Edge2"])
        print(json.dumps(pc.result_line(f, types.SimpleNamespace(Shape=Shp((0, 60, 0, 30, 0, 5))), "pd_fillet", -12.5, {}, [{"edge": "Edge1", "kind": "line", "along": "z"}])))
        ''')
        self.assertEqual(got, {"edgesGiven": 2, "size": 5.0, "edgesNotShown": 1, "solidsWas": 1, **({"edgesChanged": got["edgesChanged"]} if "edgesChanged" in got else {})})

    def test_the_answer_of_each_kind_has_result_first_and_it_is_a_record(self):
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
        for kind, (first, rec, axes) in got.items():
            if kind == "sketch_new":
                self.assertNotEqual(first, "result")  # 28 Nov: sketch_new has no result; its facts are keys
                self.assertIsNone(rec)
                self.assertEqual(axes, {"x": "+X", "y": "+Y", "normal": "+Z"})
                continue
            self.assertEqual(first, "result", kind)
            self.assertIsInstance(rec, dict, kind)
        self.assertEqual(len(got["sketch_add"][1]["shapes"]), 1)
        self.assertEqual(set(got["sketch_add"][1]["shapes"][0]), {"sketchExtent", "worldBox"})
        self.assertEqual(got["sketch_constrain"][1]["constraints"][0]["type"], "Distance")
        self.assertIn("dofBefore", got["sketch_constrain"][1])
        self.assertEqual(got["pd_pad"][1]["material"], "added")

    def test_body_check_has_result_for_several_solids_only(self):
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
        self.assertEqual(out, ["result", {"nearestGap": 12.5, "solidsTouch": False}])


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

    def test_fast_lists_one_record_for_each_call_with_a_result_in_order_and_keeps_its_facts(self):
        body = self.hub()["fast"]["body"]
        self.assertEqual(list(body)[0], "result")
        self.assertEqual(body["result"], [{"call": "calls.0", "tool": "probe_result", "volumeChange": 5.0}, {"call": "calls.2", "tool": "probe_result", "volumeChange": 5.0}])
        self.assertIn("fast", body)
        self.assertIn("made", body)
        self.assertNotIn("result", self.hub()["fastNone"]["body"])


if __name__ == "__main__":
    unittest.main()
