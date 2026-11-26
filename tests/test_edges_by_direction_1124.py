# SPDX-License-Identifier: LGPL-2.1-or-later
# 24 Nov QA (local models, a part with fillets on its vertical outside
# corners): edges by direction, answers that show each edge given, pocket
# and hole cards that lead with the side a cut goes in, and FreeCAD errors
# without hints that do not fit them. Run on the stand-in FreeCAD
# (tests/_datapd_standin.py) in a child process.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from agentlink.protocol import KIND_WORDS, NAMES_NOTHING, set_kind  # noqa: E402

CHILD = '''
import json, sys, tempfile
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.protocol import ToolError
from agentlink.families import pd_common as pc, refs
def refused(fn, *a):
    try:
        fn(*a)
        return None
    except ToolError as e:
        return [e.code, e.message]
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + body], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class Cards(unittest.TestCase):
    def setUp(self):
        self.e = entries()

    def test_fillet_and_chamfer_show_the_vertical_edges(self):
        for n in ("pd_fillet", "pd_chamfer"):
            d = self.e[n]["description"]
            self.assertIn("each edge with its direction, length, mid-point and side.", d, n)
        self.assertIn('{ type: "line", axis: "z" } is every straight edge along z: the vertical edges.', self.e["pd_chamfer"]["description"])
        # pd_fillet leads with the outside-only form (26 Nov QA: the plain form also took a lid's inside corners)
        self.assertIn('Without outside, { type: "line", axis: "z" } is every vertical edge, inside corners too.', self.e["pd_fillet"]["description"])
        self.assertIn("Add length or inside to keep fewer of them.", self.e["pd_fillet"]["description"])

    def test_pocket_leads_with_where_the_cut_goes(self):
        d = self.e["pd_pocket"]["description"]
        fact = "The pocket starts on its sketch's plane and goes into the body, against the sketch's normal."
        self.assertTrue(d.startswith("Pocket a closed sketch out of the body. " + fact), d)
        self.assertIn("To cut from below, sketch on the bottom face.", d)
        for later in ("sides:", "taper:", "extent:"):
            self.assertLess(d.index(fact), d.index(later), later)
        self.assertNotIn("It cuts against the normal of the sketch.", d)  # said once, first

    def test_hole_leads_with_where_it_drills(self):
        d = self.e["pd_hole"]["description"]
        fact = "Drill holes into the body from the plane of the sketch, against the sketch's normal."
        self.assertTrue(d.startswith(fact), d)
        for later in ("thread:", "counterbore", "depth:", "diameter:"):
            self.assertLess(d.index(fact), d.index(later), later)
        self.assertIn("reversed: true drills the other way.", d)

    def test_the_answer_puts_the_edge_lines(self):
        for n in ("pd_fillet", "pd_chamfer"):
            steps = json.dumps(self.e[n]["steps"])
            self.assertIn("edge_words(rs, subs)", steps, n)
            self.assertEqual(self.e[n]["answer"]["then"][0], {"put": {"on": "=seen"}}, n)


class EdgeQueries(unittest.TestCase):
    def test_axis_z_is_already_a_filter(self):
        from agentlink.families import refs

        self.assertTrue(refs.is_filter({"type": "line", "axis": "z"}, ("near", "face", "all", "kind", "tol")))

    def test_a_direction_word_is_refused_with_the_axis_form(self):
        got = child('''
out = {}
for q in ({"kind": "vertical"}, {"type": "line", "kind": "horizontal"}, {"type": "Vertical"}, [{"kind": "line"}, {"kind": "vertical"}]):
    out[json.dumps(q)] = refused(refs.pick, None, q, "edge", "edges")
out["face"] = refused(refs.pick, None, {"kind": "vertical"}, "face", "faces")
out["position"] = refused(pc._edges_legacy, None, {"face": {"side": "-z"}, "kind": "line", "position": "outer"})
print(json.dumps(out))
''')
        for q, r in got.items():
            self.assertIsNotNone(r, q)
            self.assertEqual(r[0], "invalid_input", q)
        for q in ('{"kind": "vertical"}', '{"type": "line", "kind": "horizontal"}', '{"type": "Vertical"}'):
            self.assertIn('For a direction, use axis: { type: "line", axis: "z" } is every straight edge along z', got[q][1], q)
            self.assertIn("Nothing was changed.", got[q][1])
        self.assertIn("edges: kind 'vertical' is not a kind of an edge.", got['{"kind": "vertical"}'][1])
        self.assertIn('normal: { type: "plane", normal: "+z" }', got["face"][1])
        # Unknown keys are still refused by name (417c6c4).
        self.assertTrue(got["position"][1].startswith("edges: position is not a key of an edge query."), got["position"])

    def test_edge_words(self):
        got = child('''
E = lambda p, q, c="Line": fc.Shape("edge", [fc.Vec(*p), fc.Vec(*q)], curve=c)
sh = fc.Shape("solid", [])
sh.Edges = [E((0, 0, 0), (0, 0, 10)), E((40, -30, 0), (40, 30, 0)), E((0, 0, 0), (3, 4, 0))] + [E((i, 0, 0), (i, 0, 10)) for i in range(15)]
for e in sh.Edges:
    e.Edges = [e]
print(json.dumps({"few": pc.edge_words(sh, ["Edge1", "Edge2", "Edge3"]), "many": pc.edge_words(sh, ["Edge%d" % i for i in range(1, 19)])}))
''')
        self.assertEqual(got["few"], ["3 edges: 1 along y, 1 along z, 1 slanted", "Edge1: line along z, 10 mm, mid [0, 0, 5]", "Edge2: line along y, 60 mm, mid [40, 0, 0]",
                                      "Edge3: line along [0.6, 0.8, 0], 5 mm, mid [1.5, 2, 0]"])
        self.assertEqual(len(got["many"]), 14)
        self.assertEqual(got["many"][0], "18 edges: 16 along z, 1 along y, 1 slanted")
        self.assertEqual(got["many"][-1], "… and 6 more edges (18 in all)")

    def test_fillet_answer_lists_the_edges(self):
        got = child('''
import importlib
from _datapd_cases import cases
feat = importlib.import_module("agentlink.families.feature")
out = {}
for tool, case, prepare, args in cases(fc, tempfile.mkdtemp()):
    if tool in ("pd_fillet", "pd_chamfer") and case == "by where it is":
        s = fc.Session(tempfile.mkdtemp()); prepare(s)
        t = [x for x in feat.tools(s) if x.name == tool][0]
        out[tool] = t.fn(args)["on"]
print(json.dumps(out))
''')
        for n in ("pd_fillet", "pd_chamfer"):
            self.assertEqual(got[n], ["2 edges: 2 along x", "Edge2: line along x, 1 mm, mid [1.5, 0, 0]", "Edge3: line along x, 1 mm, mid [2.5, 0, 0]"], n)


SETTLE = '''
class Doc:
    def recompute(self):
        pass
class S:
    doc = Doc()
class F:
    Label = "Pocket"
    TypeId = "PartDesign::Pocket"
class B:
    Label = "Body"
HINT = "Check the sketch with sketch_state (closed wires, no open vertices); reversed: true goes the other way into the body."
out = {}
for err in ("SketchBased: Up to face: Must not intersect sketch!", "BRep_API: command not done", "Wire is not closed.",
            "Creating a face from sketch failed", "SketchBased: Up to face: Must not be parallel to extrusion direction!"):
    pc.newly_broken = lambda doc, err=err: [{"object": "Pocket", "type": "Pocket", "error": err}]
    pc.profile_words = lambda f: ""
    out[err] = refused(pc.settle, S(), B(), F(), "pd_pocket", 100.0, "cut", HINT)
out["fit"] = [pc.fit_hint(HINT), pc.fit_hint(HINT, "Wire is not closed."), pc.fit_hint("Check the sketch with sketch_state (closed wires)."), pc.fit_hint("Other words.")]
print(json.dumps(out))
'''


class Hints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.got = child(SETTLE)

    def test_sketch_check_only_for_sketch_errors(self):
        g = self.got
        for err in ("SketchBased: Up to face: Must not intersect sketch!", "BRep_API: command not done",
                    "SketchBased: Up to face: Must not be parallel to extrusion direction!"):
            self.assertNotIn("sketch_state", g[err][1], err)
        for err in ("Wire is not closed.", "Creating a face from sketch failed"):
            self.assertIn("Check the sketch with sketch_state (closed wires, no open vertices)", g[err][1], err)
            self.assertNotIn(NAMES_NOTHING, g[err][1], err)
        self.assertEqual(g["fit"], ["reversed: true goes the other way into the body.",
                                    "Check the sketch with sketch_state (closed wires, no open vertices); reversed: true goes the other way into the body.",
                                    "", "Other words."])

    def test_up_to_face_says_what_it_means(self):
        m = self.got["SketchBased: Up to face: Must not intersect sketch!"][1]
        self.assertIn("The face to go up to touches the sketch (often it is the face that the sketch is on).", m)
        self.assertIn("or use extent length.", m)
        self.assertNotIn(NAMES_NOTHING, m)
        self.assertIn("parallel to the direction of the feature", self.got["SketchBased: Up to face: Must not be parallel to extrusion direction!"][1])

    def test_an_error_that_names_nothing_says_so(self):
        m = self.got["BRep_API: command not done"][1]
        self.assertTrue(m.endswith("nothing was kept. reversed: true goes the other way into the body. " + NAMES_NOTHING), m)


class KindSentence(unittest.TestCase):
    def test_no_fixable_sentence_where_nothing_is_named(self):
        e = set_kind({"code": "failed", "message": "Fillet (Fillet) failed: BRep_API: command not done — nothing was kept. " + NAMES_NOTHING})
        self.assertEqual(e["kind"], "fixable")
        self.assertNotIn(KIND_WORDS["fixable"], e["message"])
        self.assertTrue(e["message"].endswith(NAMES_NOTHING))
        # Once only, again and again.
        self.assertEqual(set_kind(dict(e))["message"], e["message"])

    def test_the_fixable_sentence_stays_where_a_change_is_named(self):
        e = set_kind({"code": "invalid_input", "message": "radius: mm, over 0."})
        self.assertTrue(e["message"].endswith(KIND_WORDS["fixable"]))


if __name__ == "__main__":
    unittest.main()
