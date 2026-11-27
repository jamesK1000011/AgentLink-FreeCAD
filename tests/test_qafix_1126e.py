# SPDX-License-Identifier: LGPL-2.1-or-later
# Four fixes from the blind QA series 1126e (stand-in FreeCAD: the words and
# the logic; the geometry facts need a real FreeCAD):
#   A. body_check and session_state say what was measured of several solids
#      in one Body ("N separate solids ..."), never "on purpose";
#   B. the sketch todo joins a line to an arc as the sketch_add card says
#      (tangent on their two end points), not with coincident;
#   C. a profile that cut only part says how much of its volume it cut;
#   F. the repeat stop compares the real sketch when a batch renamed it.
import json
import os
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_answers_where_1126 import child  # noqa: E402
from test_qa_sketch_1124 import SETUP, in_a_process  # noqa: E402
from test_stem_findings_more import run_stub  # noqa: E402


class SolidsSaidAsMeasured(unittest.TestCase):
    BODY = textwrap.dedent("""
        from agentlink.tools import Session
        body = Obj("Body", "PartDesign::Body", Shape(2), "Stem")
        body.AllowCompound = True
        s = Session.__new__(Session)
        s.doc, s.meta = Doc([body]), {}
    """)

    def test_body_check_says_separate_solids_and_their_gap_not_on_purpose(self):
        out = run_stub(self.BODY + textwrap.dedent("""
            Shape.distToShape = lambda self, o: (12.5, [], [])
            r = s.body_check({"body": "Stem"})
            print(json.dumps({"said": r["solidsSaid"], "allow": r["allowCompound"], "graded": "ok" in r or "problems" in r, "row": s._body_row(body)["multiSolid"]}))
        """))
        self.assertEqual(out["said"], "2 separate solids that do not touch (nearest gap 12.5 mm)")
        self.assertIs(out["allow"], True)  # FreeCAD's property, as a fact beside the count
        self.assertNotIn("on purpose", out["said"] + out["row"])
        self.assertFalse(out["graded"])  # facts only (27 Nov): no ok, no problems

    def test_solids_that_touch_are_not_said_to_be_apart(self):
        out = run_stub(self.BODY + textwrap.dedent("""
            Shape.distToShape = lambda self, o: (0.0, [], [])
            print(json.dumps(s.body_check({"body": "Stem"})["solidsSaid"]))
        """))
        self.assertIn("2 separate solids; at least two touch", out)
        self.assertNotIn("do not touch", out)

    def test_without_a_distance_only_the_count_is_said(self):
        out = run_stub(self.BODY + textwrap.dedent("""
            print(json.dumps(s.body_check({"body": "Stem"})["solidsSaid"]))
        """))
        self.assertEqual(out, "2 separate solids")


class OpenEndsNameNoConstraint(unittest.TestCase):
    """27 Nov (owner): the todo words of open ends are facts only (each end, its ref and the measured distance). They name
    no constraint, so they cannot disagree with the card (26 Nov QA: coincident in the todo, tangent on the card)."""

    def words(self, ends):
        return in_a_process(SETUP + '''
    from agentlink.families import sketch
    print(json.dumps(sketch.open_end_words(%r, [0, 1, 2], 100.0, lambda i, p: 50.0)))
''' % (ends,))

    def test_a_line_and_an_arc(self):
        got = self.words([[2, "line", 1, [10, 20]], [0, "arc", 2, [10, 20.009]]])
        self.assertEqual(got, ["the start of line 2 [2, 1] (10, 20) and the end of arc 0 [0, 2] (10, 20.009) are open ends, 0.009 mm apart"])
        # The arc found first: the same two ends, in the order found.
        got = self.words([[0, "arc", 2, [10, 20]], [2, "line", 1, [10, 20.009]]])
        self.assertIn("the end of arc 0 [0, 2] (10, 20) and the start of line 2 [2, 1] (10, 20.009) are open ends, 0.009 mm apart", got[0])

    def test_two_lines(self):
        got = self.words([[2, "line", 1, [10, 20]], [1, "line", 2, [10, 20.009]]])
        self.assertIn("are open ends, 0.009 mm apart", got[0])
        for w in ("sketch_constrain", "coincident", "tangent", "joins"):
            self.assertNotIn(w, got[0])

    def test_the_card_says_what_joins_a_line_to_an_arc(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            card = json.load(f)["entries"]["sketch_add"]["description"]
        self.assertIn("sketch_constrain tangent on two end points [[line, v], [arc, v]] makes them coincident and smooth.", card)


class PartialProfiles(unittest.TestCase):
    STUB = '''
class Prism:
    def __init__(s, f): s.f = f
    def common(s, other):
        vol, depth = s.f.hits.get(other.tag, (0.0, 0.0))
        class P: Point = V(0, 0, 0)
        class Q: Point = V(0, 0, depth)
        class R:
            Volume = vol
            Vertexes = [P, Q]
        return R()
class Face:
    Area = 20.0
    def __init__(s, hits): s.hits = hits
    def normalAt(s, u, v): return V(0, 0, 1)
    def translated(s, v): return s
    def extrude(s, v): return Prism(s)
class C:
    def __init__(s): s.Length = 0.0
class BB:
    DiagonalLength = 70.0
    Center = C()
class Tagged:
    def __init__(s, tag): s.tag = tag; s.BoundBox = BB
reg, old = Tagged("reg"), Tagged("old")
'''

    def test_half_holes_are_not_both_cut(self):
        got = child(self.STUB + '''
pc.profile_faces = lambda feat: [("the circle r 2.5 at (15, 0)", Face({"reg": (50.0, 5.0)})), ("the circle r 2.5 at (45, 0)", Face({"reg": (50.0, 5.0)}))]
print(json.dumps(pc.profile_results(None, reg, old, 0.01, cut=True)))
''')
        text = got["profiles"]
        self.assertNotIn("both cut", text)
        self.assertEqual(text, "2 profiles: the circle r 2.5 at (15, 0) cut 50% of the volume its area gives over the same depth (50 of 100 mm³); "
                               "the circle r 2.5 at (45, 0) cut 50% of the volume its area gives over the same depth (50 of 100 mm³).")

    def test_a_full_one_beside_a_partial_one_and_the_unmeasured(self):
        got = child(self.STUB + '''
pc.profile_faces = lambda feat: [("a", Face({"reg": (100.0, 5.0)})), ("b", Face({"reg": (25.0, 5.0)}))]
out = [pc.profile_results(None, reg, old, 0.01, cut=True)["profiles"]]
class NoVerts:
    Volume = 40.0
Prism.common = lambda s, other: NoVerts() if other.tag == "reg" else type("Z", (), {"Volume": 0.0})()
out.append(pc.profile_results(None, reg, old, 0.01, cut=True)["profiles"])
print(json.dumps(out))
''')
        self.assertEqual(got[0], "2 profiles: b cut 25% of the volume its area gives over the same depth (25 of 100 mm³); 1 cut in full.")
        self.assertNotIn("cut in full", got[1])
        self.assertNotIn("both cut", got[1])
        self.assertIn("not measured", got[1])


class RepeatStopUsesTheBatchAlias(unittest.TestCase):
    def test_a_renamed_sketch_is_not_the_one_the_earlier_call_used(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import protocol
    class Sk:
        TypeId = "Sketcher::SketchObject"
        def __init__(self, name, label):
            self.Name, self.Label = name, label
    old, new = Sk("Sketch", "CrankSketch"), Sk("Sketch001", "CrankSketch 2")
    class Doc:
        Name = "Crank"
        Objects = [old, new]
        def getObject(self, n):
            return next((o for o in self.Objects if o.Name == n), None)
    doc = Doc()
    sys.modules["FreeCAD"].listDocuments = lambda: {"Crank": doc}
    s = types.SimpleNamespace(doc=doc, by="agent")
    args = {"sketch": "CrankSketch", "length": 5}
    rec = {"name": "pd_pad", "call": protocol.canonical_call(args), "seq": 1, "made": [("object", "Crank", "Sketch", "CrankSketch", ())],
           "doc": "Crank", "sketch": "Sketch", "filled": False, "token": None, "step": None}
    tool = types.SimpleNamespace(changes_for=lambda a: True, changes=True)
    server = types.SimpleNamespace(session=s, tools={"pd_pad": tool}, _ran=[rec], _seq=1, refusal=lambda *a, **k: {"isError": True})
    same = "refusal" in protocol.again_before(server, {"name": "pd_pad", "arguments": args})
    # A sketch_new of this batch got "CrankSketch 2": the name now means that one.
    s.__dict__["_batch_aliases"] = {("Crank", "CrankSketch"): "Sketch001"}
    server._seq = 5
    renamed = "refusal" in protocol.again_before(server, {"name": "pd_pad", "arguments": args})
    print(json.dumps([same, renamed]))
''')
        self.assertEqual(got, [True, False])  # the same sketch is still refused; the renamed one is not


if __name__ == "__main__":
    unittest.main()
