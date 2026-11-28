# SPDX-License-Identifier: LGPL-2.1-or-later
# Result sentences as records (28 Nov, owner): `result` of a feature, a
# dress-up, sketch_add, sketch_constrain and body_check is a dict of the
# facts that no other key of the answer has; sketch_new has no result (its
# facts are keys: axes as a record, faceExtent, bodySolid); fast lists one
# record for each call that has a result. One test for each builder (its
# record for a typical input; no key repeats another key of the answer),
# fast's records, and the data check of tools.json.
import json
import os
import subprocess
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import resultline as rl  # noqa: E402

OLD = (0, 40, 0, 20, 0, 5)

# The other keys of each answer (the answers' own, agentlink/data/tools.json and agentlink/tools.py).
FEATURE_KEYS = {"feature", "type", "valid", "body", "solid", "volume", "volumeChange", "faces", "solids", "box", "bounds", "added", "removed", "beyond",
                "opens", "where", "profiles", "fills", "changed", "stored", "bodyPlacement", "containerPlacement", "boxNote", "health", "notGiven"}
DRESSUP_KEYS = FEATURE_KEYS | {"on"}
SKETCH_ADD_KEYS = {"sketch", "added", "state", "constraints", "constraintList", "dims", "dimsNote", "notGiven", "ids", "kind"}
SKETCH_CONSTRAIN_KEYS = {"sketch", "added", "state"}
BODY_CHECK_KEYS = {"body", "valid", "closed", "solids", "volume", "checkGeometry", "allowCompound", "each", "boxNote", "box", "bounds", "faces"}


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def source(*path):
    with open(os.path.join(ROOT, "agentlink", *path), encoding="utf-8") as f:
        return f.read()


def sentences(x):
    """Every string of a record that has more than one word (a sentence), apart from the side words ("+z at z 5")."""
    if isinstance(x, str):
        if len(x.split()) > 1 and " at " not in x:
            yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from sentences(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from sentences(v)


class Builders(unittest.TestCase):
    def test_a_pad_is_a_record_of_what_no_other_key_has(self):
        got = rl.feature_result("pd_pad", 4000, region=[(0, 40, 0, 20, 5, 10)], old_box=OLD, faces=["+z at z 5"], touching=True, solids=1, solids_was=1)
        self.assertEqual(got, {"material": "added", "bodyBefore": {"x": [0.0, 40.0], "y": [0.0, 20.0], "z": [0.0, 5.0]},
                               "againstBefore": {"x": {"inside": {"-x": 0.0, "+x": 0.0}}, "y": {"inside": {"-y": 0.0, "+y": 0.0}}, "z": {"past": {"+z": 5.0}}},
                               "touches": {"touching": True, "faces": ["+z at z 5"]}, "solidsWas": 1})
        self.assertFalse(set(got) & FEATURE_KEYS)
        self.assertEqual(list(sentences(got)), [])
        # the first feature of a body: the body is the answer's bounds; the span along the normal is added by the caller (normalSpan)
        self.assertEqual(rl.feature_result("pd_pad", 4000), {"material": "added"})

    def test_a_pocket_keeps_opens_in_the_answer_and_counts_what_was_not_looked_at(self):
        got = rl.feature_result("pd_pocket", -50, region=[(1, 2, 1, 2, 0, 5), (5, 6, 5, 6, 0, 5)], old_box=OLD, cut=True, faces=["+z at z 5"], faces_more=3,
                                solids=1, solids_was=1, profiles=rl.profiles_rec(2, 2, [75, 25], 0))
        self.assertEqual(got["material"], "removed")
        self.assertEqual(len(got["pieces"]), 2)
        self.assertEqual((got["opensNotLooked"], got["partialProfilePercent"], got["profileCount"]), (3, [75.0, 25.0], 2))
        self.assertNotIn("touches", got)
        self.assertFalse(set(got) & FEATURE_KEYS)
        self.assertEqual(list(sentences(got)), [])

    def test_a_fillet_or_chamfer_has_edges_size_and_no_edge_lines(self):
        edges = [{"edge": "Edge%d" % i, "kind": "line", "along": "z", "length": 10.0, "mid": [0.0, 0.0, 5.0], "side": "outside"} for i in range(1, 5)]
        got = rl.dressup_result(4, {"size": 1.0}, edges, 1, 1, changed=4)
        self.assertEqual(got, {"edgesGiven": 4, "edgesChanged": 4, "size": 1.0, "solidsWas": 1})
        self.assertFalse(set(got) & DRESSUP_KEYS)
        self.assertEqual(rl.dressup_result(2, {"size": 2.0, "size2": 3.0}, edges[:1])["edgesNotShown"], 1)
        self.assertEqual(rl.dressup_result(1, {"size": 2.0, "angle": 30.0}), {"edgesGiven": 1, "size": 2.0, "angle": 30.0})
        self.assertEqual(list(sentences(got)), [])

    def test_sketch_add_has_a_record_for_each_item_and_the_lies(self):
        frame = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
        rect = rl.shape_rec((-20, 20), (-10, 10), rl.world_box(frame, (-20, 20), (-10, 10)))
        circle = rl.shape_rec((0, 4), (0, 4), circle=((2, 2), 2))
        lies = rl.lies_rec("body", (-20, 20, -10, 10, 0, 0), OLD)
        got = rl.sketch_add_result([rect, circle], 0, [lies])
        self.assertEqual(list(got), ["shapes", "lies", "openEnds"])
        self.assertEqual(got["shapes"][0]["worldBox"], {"x": [-20.0, 20.0], "y": [-10.0, 10.0], "z": [0.0, 0.0]})
        self.assertEqual(got["shapes"][1]["circle"], {"center": [2.0, 2.0], "radius": 2.0})
        self.assertEqual(got["lies"][0]["against"], "body")
        self.assertEqual(got["lies"][0]["axes"]["x"], {"past": {"-x": 20.0}})
        self.assertFalse(set(got) & SKETCH_ADD_KEYS)
        self.assertEqual(list(sentences(got)), [])

    def test_sketch_constrain_has_the_constraint_records_and_the_moves(self):
        con = {"id": 4, "type": "Coincident", "refs": [[0, 2], [2, 1]]}
        moves = [{"join": [[0, 2], [2, 1]], "moved": [{"ref": [0, 2], "mm": 40.0}]}]
        got = rl.constraint_result([con], 14, moves, ((-22.97, 185.29), (-20.35, 19.93)), 2)
        self.assertEqual(got, {"constraints": [con], "dofBefore": 14, "moved": moves, "joinsNotShown": 2,
                               "sketchExtent": {"x": [-22.97, 185.29], "y": [-20.35, 19.93]}})
        self.assertFalse(set(got) & SKETCH_CONSTRAIN_KEYS)
        self.assertEqual(list(sentences(got)), [])

    def test_body_check_has_the_gap_of_several_solids_only(self):
        self.assertEqual(rl.body_check_result(12.5), {"nearestGap": 12.5, "solidsTouch": False})
        self.assertEqual(rl.body_check_result(0.0), {"nearestGap": 0.0, "solidsTouch": True})
        self.assertEqual(rl.body_check_result(None), {})
        self.assertFalse(set(rl.body_check_result(1.0)) & BODY_CHECK_KEYS)

    def test_the_sentence_builders_are_gone(self):
        for gone in ("sketch_new_result", "feature_head", "lies_text", "touch_text", "opens_text", "profiles_text", "shape_text", "default_text", "fast_lines"):
            self.assertFalse(hasattr(rl, gone), gone)


class Fast(unittest.TestCase):
    def test_one_record_for_each_call_that_has_a_result(self):
        rows = [("calls.0", "pd_pad", {"result": {"material": "added"}, "feature": "Pad", "volumeChange": 4000.0, "step": 7}),
                ("calls.1", "get", {"x": 1}),
                ("calls.2", "sketch_add", {"result": {"shapes": [{}]}, "sketch": "Sketch"}),
                ("calls.3", "pd_pocket", {"result": {}, "volumeChange": -1})]
        got = rl.fast_steps(rows)
        self.assertEqual(got, [{"call": "calls.0", "tool": "pd_pad", "object": "Pad", "volumeChange": 4000.0, "historyStep": 7},
                               {"call": "calls.2", "tool": "sketch_add", "object": "Sketch"}])
        self.assertEqual(rl.fast_steps([]), [])

    def test_the_records_are_those_of_session_states_steps(self):
        from agentlink import protocol

        body = {"result": {"material": "removed"}, "feature": "Pocket", "volumeChange": -3.5, "step": 2}
        self.assertEqual(rl.fast_steps([("calls.4", "pd_pocket", body)])[0], protocol.step_line("calls.4", "pd_pocket", body))
        self.assertIn("_resultline.fast_steps(", source("fastpath.py"))


CHILD = '''
import json, sys, types
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.families import pd_common as pc, sketch
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class SketchNew(unittest.TestCase):
    def test_axes_is_a_record_and_the_constants_are_on_the_card(self):
        got = child('''
        from agentlink import orient
        fr = {"origin": (0, -15, 0), "xAxis": (1, 0, 0), "yAxis": (0, 0, 1), "normal": (0, -1, 0)}
        tilt = {"origin": (0, 0, 0), "xAxis": (1, 0, 0), "yAxis": (0, 0.6, 0.8), "normal": (0, -0.8, 0.6)}
        print(json.dumps([orient.axes_rec(fr), orient.axes_rec(tilt)]))
        ''')
        self.assertEqual(got[0], {"x": "+X", "y": "+Z", "normal": "-Y"})
        self.assertEqual(got[1]["x"], "+X")
        self.assertTrue(got[1]["normal"].startswith("mostly "), got[1])
        e = entries()["sketch_new"]
        fields = e["answer"]["fields"]
        self.assertNotIn("result", fields)
        self.assertNotIn("note", fields)
        effects = " | ".join(e["card"]["effects"])
        self.assertIn("A pad grows along the normal, and a pocket or a hole cuts against it", effects)
        self.assertIn("Coordinates are the sketch's: x along xAxis, y along yAxis, from origin (world mm)", effects)
        returns = e["card"]["returns"]
        self.assertNotIn("result", returns)
        for k in ("axes", "bodyExtent", "bodySolid", "faceExtent", "frame"):
            self.assertIn(k, returns, k)

    def test_the_face_extent_and_body_solid(self):
        got = child('''
        class V:
            def __init__(s, x, y, z=0.0): s.x, s.y, s.z = x, y, z
        sketch.V = V
        rot = types.SimpleNamespace(multVec=lambda v: {(1, 0, 0): V(1, 0, 0), (0, 1, 0): V(0, 1, 0), (0, 0, 1): V(0, 0, 1)}[(v.x, v.y, v.z)])
        pl = types.SimpleNamespace(Base=V(0, 0, 5), Rotation=rot)
        sk = types.SimpleNamespace(getGlobalPlacement=lambda: pl)
        bb = types.SimpleNamespace(XMin=-25.04, XMax=25.04, YMin=-20.0, YMax=20.0, ZMin=0.0, ZMax=5.0)
        shape = types.SimpleNamespace(isNull=lambda: False, Solids=[1], BoundBox=bb)
        face = types.SimpleNamespace(BoundBox=types.SimpleNamespace(XMin=-25.04, XMax=25.04, YMin=-20.0, YMax=20.0, ZMin=5.0, ZMax=5.0))
        body = types.SimpleNamespace(Shape=shape)
        link = (types.SimpleNamespace(Shape=types.SimpleNamespace(getElement=lambda n: face)), ["Face6"])
        empty = types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[], BoundBox=bb))
        print(json.dumps([sketch.face_extent(link, sk), sketch.face_extent((link[0], [""]), sk), sketch.body_has_solid(body), sketch.body_has_solid(empty)]))
        ''')
        self.assertEqual(got[0], {"x": [-25.0, 25.0], "y": [-20.0, 20.0]})
        self.assertIsNone(got[1])  # not on a face
        self.assertEqual(got[2:], [True, False])
        f = entries()["sketch_new"]["answer"]["fields"]
        self.assertEqual(f["bodySolid"], {"when": "=not body_has_solid(b)", "value": False})
        self.assertEqual(f["faceExtent"], {"when": "=fext", "value": "=fext"})
        self.assertEqual(f["bodyExtent"], {"when": "=ext", "value": "=ext"})


class OnTheStandIn(unittest.TestCase):
    def test_the_settle_answer_of_a_fillet_has_result_first_and_the_edge_records_in_on(self):
        from test_factsonly_1127 import SETTLE, child as fchild

        got = fchild(SETTLE + '''
        body = types.SimpleNamespace(Label="Body", Shape=Shp())
        vol[0] = 97.0
        r = pc.settle(sess, body, feat("Fillet", Radius=2.0), "pd_fillet", 100.0, "changed", seen=[{"edge": "Edge1", "kind": "line", "along": "z", "length": 10.0, "mid": [0.0, 0.0, 5.0]}])
        print(json.dumps([list(r)[0], r["result"], sorted(set(r["result"]) & set(r))]))
        ''')
        self.assertEqual(got[0], "result")
        self.assertIn("edgesGiven", got[1])
        self.assertEqual(got[2], [])  # no key of result is another key of the answer


class Data(unittest.TestCase):
    def test_tools_json_is_valid(self):
        from agentlink import tooldata

        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            self.assertEqual(tooldata.check(json.load(f)), [])

    def test_each_changed_card_names_the_new_keys(self):
        e = entries()
        for n in ("pd_pad", "pd_pocket", "pd_revolution", "pd_groove", "pd_hole", "pd_draft", "pd_thickness", "pd_mirrored", "pd_linear_pattern", "pd_polar_pattern", "pd_loft", "pd_pipe"):
            r = e[n]["card"]["returns"]
            for k in ("result.material", "result.bodyBefore", "result.againstBefore", "result.touches", "result.normalSpan", "result.solidsWas"):
                self.assertIn(k, r, (n, k))
            self.assertEqual(r["result.bodyBefore"]["unit"], "mm")
        for n in ("pd_fillet", "pd_chamfer"):
            r = e[n]["card"]["returns"]
            for k in ("result.edgesGiven", "result.edgesChanged", "result.size"):
                self.assertIn(k, r, (n, k))
            self.assertNotIn("edges", r)
            self.assertIn("side (outside | inside)", r["on"]["means"])
        for k in ("result.shapes", "result.lies", "result.openEnds", "added.notGiven"):
            self.assertIn(k, e["sketch_add"]["card"]["returns"], k)
        for k in ("result.constraints", "result.dofBefore", "result.moved", "result.sketchExtent"):
            self.assertIn(k, e["sketch_constrain"]["card"]["returns"], k)
        for n in ("sketch_state", "sketch_merge", "sketch_mirror", "sketch_attach", "sketch_new"):
            self.assertIn("{ x, y, normal }", e[n]["card"]["returns"]["axes"]["means"], n)
        text = json.dumps({n: x["card"] for n, x in e.items() if n.startswith(("pd_", "sketch_"))})
        self.assertNotIn("one-line summary", text)

    def test_sketch_add_names_its_inputs_not_given_and_lists_the_constraints_as_records(self):
        steps = json.dumps(entries()["sketch_add"]["steps"])
        self.assertIn('{"put": {"notGiven": "=by_default(it)"}', steps)
        self.assertNotIn("byDefault", steps)
        self.assertIn('"constraintList": "=con_list(sk, cids)"', steps)
        self.assertNotIn("con_brief", steps)

    def test_no_reader_of_the_old_sentences_is_left(self):
        for path in (("families", "sketch.py"), ("families", "pd_common.py"), ("fastpath.py",), ("tools.py",)):
            text = source(*path)
            for old in ("sketch_new_result", "new_result", "check_in_result", "fast_lines", "solidsSaid", "feature_head", "lies_text", "default_text"):
                self.assertNotIn(old, text, (path, old))


if __name__ == "__main__":
    unittest.main()
