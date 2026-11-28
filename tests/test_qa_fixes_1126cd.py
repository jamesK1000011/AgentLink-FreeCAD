# SPDX-License-Identifier: LGPL-2.1-or-later
# Blind QA of local-model runs (26 Nov, series s1126c and s1126d), the fixes
# of round 4, on stand-ins (plain Python, no FreeCAD):
#   1. every sketch tool's state is read after the sketch is built again
#      (state_of recomputes it): openVertices and todo of this call, not the
#      one before;
#   2. a coincident that joined two points far apart, and moved them, is said;
#   3. pd_hole's holes counts only the circles that cut;
#   4. a vertex a curve does not have is refused by name (a circle has no
#      start or end point);
#   5. pd_fillet's card and example lead with { type, axis, outside: true };
#   6. doc_save's refusal names only readings get gives; a feature's own
#      answer counts as a measure;
#   7. no feature options for a sketch that is not ready for a feature;
#   8. one message per point: a gap to close is not also called a branch;
#   9. the repeated-phrase filter of a refusal never leaves a sentence cut;
#  10. a direct call sent in a batch step's form ({ tool, arguments }) is
#      taken from inside arguments, or refused by name;
#  11. two ends a hair apart get the coincident words first; one end near a
#      hole circle gets no round-end words;
#  12. sketch_new's taken name is said, and the later calls of the batch get
#      the new sketch by the name asked;
#  13. the repeat note says "ran before (step N)";
#  14. extent: 5 says where a depth goes; get Body.solids points to body_check;
#  15. a cut in separate pieces says how many and where each one is.
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import nexthint, protocol  # noqa: E402
from agentlink.protocol import ToolError, check_input  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402
from test_qa_sketch_1124 import SETUP  # noqa: E402
from test_qa_sketch_1126 import GEO, STATE  # noqa: E402


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


def entries(name="tools.json"):
    with open(os.path.join(ROOT, "agentlink", "data", name), encoding="utf-8") as f:
        return json.load(f)["entries"]


class StateIsFresh(unittest.TestCase):
    def test_state_of_builds_the_sketch_first(self):
        got = in_a_process(STATE + '''
    geo = {0: LineSegment((0, 0), (10, 0)), 1: LineSegment((10, 0), (10, 10)), 2: LineSegment((10, 10), (0, 0))}
    sk = sketch_of(geo, [lines_wire(geo, [0, 1])], 15.0)
    built = []
    def recompute():
        built.append(1)
        sk.Shape.Wires = [Wire(True, lines_wire(geo, [0, 1, 2]).Edges)]
    sk.recompute = recompute
    sk.Document = types.SimpleNamespace(RecomputesFrozen=False)
    fresh = sketch.state_of(sk)
    sk.Shape.Wires = [lines_wire(geo, [0, 1])]
    sk.Document.RecomputesFrozen = True
    held = sketch.state_of(sk)
    print(json.dumps([len(built), fresh["closedWires"], fresh.get("openVertices"), held["closedWires"], "readyForFeature" in fresh]))
''')
        # built once (not while a batch holds the recompute); the closed loop read at once
        self.assertEqual(got, [1, 1, None, 0, False])


class FarJoins(unittest.TestCase):
    def test_a_join_that_moved_the_shape_is_said_whatever_its_size(self):
        # 27 Nov: no FAR_JOIN limit: a join says what it moved, 40 mm or 0.02 mm.
        got = in_a_process(GEO + '''
    pts = {(0, 2): P(0.9, 20), (3, 1): P(170.7, -12.5)}
    sk = types.SimpleNamespace(Geometry=[types.SimpleNamespace(), None, None, LineSegment((170.7, -12.5), (0, -20))],
                               getPoint=lambda g, p: pts[(g, p)], Shape=types.SimpleNamespace(BoundBox=types.SimpleNamespace(DiagonalLength=200.0)))
    class ArcOfCircle:
        pass
    sk.Geometry[0] = ArcOfCircle()
    joins = sketch.join_points(sk, [("Coincident", 0, 2, 3, 1), ("Distance", 0, 30.0)])
    pts[(0, 2)] = pts[(3, 1)] = P(85, 4)   # the solve joined them half way
    st = sketch.join_move_words({"openEnds": ["close the open wires"]}, sk, joins)
    near = sketch.join_points(sk, [("Coincident", 0, 2, 3, 1)])   # now together
    same = sketch.join_move_words({"openEnds": ["x"]}, sk, near)       # nothing moved: nothing said
    print(json.dumps([len(joins), st["moved"], st["openEnds"], "moved" in same]))
''')
        self.assertEqual(got[0], 1)
        self.assertEqual(got[1], ["coincident joined the end of arc 0 (0.9, 20) and the start of line 3 (170.7, -12.5), 172.882 mm apart: the shape moved"])
        self.assertEqual(got[2:], [["close the open wires"], False])

    def test_the_card_reads_them_before_the_constraints_go_in(self):
        steps = json.dumps(entries()["sketch_constrain"]["steps"])
        self.assertLess(steps.index("join_points(sk, ts)"), steps.index("sk.addConstraint(constraint(t))"))
        self.assertIn("join_move_words(st, sk, joins)", steps)


class HolesCut(unittest.TestCase):
    def test_holes_counts_only_the_circles_that_cut(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import pd_common as pc
    out = {"profiles": "2 profiles: the circle r 2.5 at (45, 0) is off the body; 1 cut in full.", pc.NOT_CUT: 1}
    one = pc.holes_cut(2, out)
    print(json.dumps([one, sorted(out), pc.holes_cut(3, {})]))
''')
        self.assertEqual(got, [1, ["holeSpots", "profiles"], 3])

    def test_the_card(self):
        e = entries()["pd_hole"]
        self.assertIn("holes is the number of holes that removed material", _cw(e))
        self.assertIn("profiles names each circle that cut nothing", _cw(e))
        self.assertIn("holes_cut(spots, out)", json.dumps(e["answer"]))


class Vertices(unittest.TestCase):
    def test_a_circle_has_no_start_point(self):
        got = in_a_process(GEO + '''
    from agentlink.protocol import ToolError
    class ArcOfCircle:
        pass
    class Point:
        pass
    sk = types.SimpleNamespace(Geometry=[Circle((0, 0), 20), LineSegment((0, 0), (10, 0)), ArcOfCircle(), Point()])
    out = []
    for c in ({"type": "coincident", "refs": [[1, 2], [0, 1]]}, {"type": "coincident", "refs": [[1, 3], [2, 3]]},
              {"type": "coincident", "refs": [[3, 2], [2, 1]]}):
        try:
            sketch.make_constraint(sk, c)
            out.append(None)
        except ToolError as e:
            out.append(e.message)
    out.append(sketch.make_constraint(sk, {"type": "coincident", "refs": [[1, 2], [0, 3]]}))
    out.append(sketch.vertex_words(sk, 2, 3))
    print(json.dumps(out))
''')
        self.assertEqual(got[0], "(coincident): circle 0 has no start or end point; use its centre, [0, 3], or the circle itself, 0 "
                                 "(point_on_object, refs [[g, v], 0], puts point v of curve g on the circle). Nothing was added.")
        self.assertEqual(got[1], "(coincident): line 1 has no centre (vertex 3); its points are [1, 1] its start point, [1, 2] its end point. Nothing was added.")
        self.assertEqual(got[2], "(coincident): point 3 has only one vertex: [3, 1]. Nothing was added.")
        self.assertEqual(got[3], [["Coincident", 1, 2, 0, 3]])
        self.assertIsNone(got[4])  # an arc has a centre


class Fillet(unittest.TestCase):
    def test_outside_corners_lead_and_the_plain_form_is_said_once(self):
        d = _cw(entries()["pd_fillet"])
        self.assertIn('{ type: "line", axis: "z", outside: true } is the outside vertical corners.', d)
        self.assertEqual(d.count('{ type: "line", axis: "z" }'), 1)
        self.assertIn("inside corners too", d)
        self.assertEqual(entries("examples.json")["pd_fillet"]["forms"]["edges"], {"type": "line", "axis": "z", "outside": True})


class Box:
    def __init__(self, x0, x1):
        self.x0, self.x1 = x0, x1

    def intersect(self, o):
        return not (self.x1 < o.x0 or o.x1 < self.x0)


class Loop:
    def __init__(self, x0, x1):
        self.BoundBox = Box(x0, x1)

    def isClosed(self):
        return True

    def distToShape(self, o):
        a, b = self.BoundBox, o.BoundBox
        return (max(b.x0 - a.x1, a.x0 - b.x1, 0.0),)


def sk_with(wires, **more):
    shape = types.SimpleNamespace(Wires=wires, BoundBox=types.SimpleNamespace(DiagonalLength=100.0))
    return types.SimpleNamespace(GeometryCount=4, Shape=shape, **more)


class NotReadyOptions(unittest.TestCase):
    def test_the_fact(self):
        self.assertEqual(nexthint._sketch_progress(sk_with([Loop(0, 10), Loop(20, 30)])), "sketch-closed")
        self.assertEqual(nexthint._sketch_progress(sk_with([Loop(0, 10), Loop(10, 30)])), "sketch-not-ready")
        self.assertEqual(nexthint._sketch_progress(sk_with([Loop(0, 10)], ConflictingConstraints=[3])), "sketch-not-ready")
        self.assertEqual(nexthint._sketch_progress(sk_with([Loop(0, 10)], ConflictingConstraints=[])), "sketch-closed")

    def test_no_feature_for_a_sketch_that_is_not_ready(self):
        feats = ("pd_pad", "pd_pocket", "pd_hole", "pd_revolution", "pd_groove")
        for features in ("none", "some"):
            tools = [p["tool"] for p in nexthint.rank({"body": "sketch-not-ready", "features": features})]
            self.assertFalse(set(tools) & set(feats), tools)
            self.assertEqual(tools[:2], ["sketch_state", "sketch_edit"])
        # a sketch in edit, fully constrained, but not ready: no pad either
        tools = [p["tool"] for p in nexthint.rank({"editing": "sketch", "dof": "full", "body": "sketch-not-ready"})]
        self.assertFalse(set(tools) & set(feats), tools)
        self.assertIn("pd_pad", [p["tool"] for p in nexthint.rank({"editing": "sketch", "dof": "full", "body": "sketch-closed"})])


class OnePointOneMessage(unittest.TestCase):
    def test_a_gap_is_not_also_a_branch(self):
        # crank, gpt-oss: the end of line 0 lies on line 3, 0.003 mm from line 3's end
        got = in_a_process(GEO + '''
    geo = {0: LineSegment((0, 0), (10, 0)), 3: LineSegment((10, 10), (10, -0.003))}
    ends = [(0, "line", 1, (0, 0)), (0, "line", 2, (10, 0)), (3, "line", 1, (10, 10)), (3, "line", 2, (10, -0.003))]
    joins = []
    gaps = sketch.open_end_words(ends, [0, 3], 15.0, dist_of(geo), (), joins)
    print(json.dumps([gaps, sketch.branch_words(ends, {0: "line", 3: "line"}, 15.0, dist_of(geo), (), joins),
                      sketch.branch_words(ends, {0: "line", 3: "line"}, 15.0, dist_of(geo), ())]))
''')
        gaps, branches, before = got
        # 27 Nov (owner): facts only. The end of line 0 is on line 3: a branch, said once, by branch_words. The end of
        # line 3 is an open end, said once, with the measured distance to the nearest other open end. No words of one
        # are held back for the other, and no constraint is named.
        self.assertIn("the end of line 3 [3, 2] (10, -0.003) is an open end; the nearest other open end is the end of line 0 [0, 2] (10, 0), 0.003 mm away"
                      "", gaps)
        self.assertFalse([w for w in gaps if w.startswith("the end of line 0")], gaps)
        self.assertEqual(branches, before)
        self.assertTrue(before and "meets line 3" in before[0], before)
        self.assertNotIn("sketch_constrain", " ".join(gaps + branches))


SCHEMA = {"type": "object", "properties": {"card": {"type": "string"}, "words": {"type": "string"}}, "additionalProperties": False}
GET = {"type": "object", "properties": {"what": {"type": "string"}}, "required": ["what"], "additionalProperties": False}


class Wrapped(unittest.TestCase):
    def test_the_step_form_on_a_direct_call(self):
        a = {"tool": "agentlink_tool_find", "arguments": {"card": "pd_pad"}}
        said = check_input(SCHEMA, a, "tool_find")
        self.assertEqual(a, {"card": "pd_pad"})
        self.assertEqual(said, ["inputs taken from inside arguments (a direct call takes them at the top level); ignored tool"])
        a = {"arguments": {"what": "Body.size"}, "rollback": False, "stopOnError": False}
        check_input(GET, a, "get")
        self.assertEqual(a, {"what": "Body.size"})
        a = {"arguments": {"what": "Body.size"}}
        check_input(GET, a, "get")
        self.assertEqual(a, {"what": "Body.size"})

    def test_other_keys_beside_arguments_are_refused_by_name(self):
        for a in ({"what": "Body.size", "arguments": {"what": "Body.area"}}, {"tool": "pd_pad", "arguments": {"what": "x"}}):
            with self.assertRaises(ToolError) as e:
                check_input(GET, dict(a), "get")
            self.assertEqual(e.exception.message, "inputs go at the top level of a direct call: get { what: … }, not inside arguments. "
                                                  "A batch step is { tool, <its inputs> }: the inputs stand beside tool.")

    def test_names_tool(self):
        self.assertTrue(protocol.names_tool("mcp__agentlink__tool_find", "tool_find"))
        self.assertFalse(protocol.names_tool("pd_pad", "tool_find"))


class RoundEndsAndGaps(unittest.TestCase):
    def test_a_hair_gap_beside_a_hole_gets_the_coincident_words(self):
        # crank, gpt-oss: the end of line 1 is 0.001 mm from the end of arc 2, and 6 mm from the pedal hole (circle 8)
        got = in_a_process(GEO + '''
    geo = {8: Circle((170, 0), 6.5), 1: LineSegment((0, 20), (170.707, 12.48)), 2: LineSegment((170.708, 12.48), (170.708, -12.48))}
    ends = [(1, "line", 2, (170.707, 12.48)), (2, "line", 1, (170.708, 12.48))]
    print(json.dumps(sketch.open_end_words(ends, [1, 2, 8], 205.0, dist_of(geo), [8])))
''')
        # 27 Nov (owner): the measured distance, by the same words as any two open ends; the hole decides nothing
        self.assertEqual(got, ["the end of line 1 [1, 2] (170.707, 12.48) and the start of line 2 [2, 1] (170.708, 12.48) are open ends, 0.001 mm apart"
                               ""])

    def test_one_end_near_a_hole_is_not_a_round_end(self):
        got = in_a_process(GEO + '''
    geo = {8: Circle((100, 0), 5), 1: LineSegment((0, 0), (100, 8))}
    ends = [(1, "line", 1, (0, 0)), (1, "line", 2, (100, 8))]
    print(json.dumps(sketch.open_end_words(ends, [1, 8], 110.0, dist_of(geo), [8])))
''')
        self.assertEqual(got, ["the start of line 1 [1, 1] (0, 0) and the end of line 1 [1, 2] (100, 8) are open ends, 100.319 mm apart"
                               ""])
        self.assertNotIn("an outline uses an arc there", got[0])


class TakenName(unittest.TestCase):
    def test_said_and_found_by_the_name_asked_in_the_batch(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import pd_common as pc
    class Sk:
        TypeId = "Sketcher::SketchObject"
        def __init__(self, doc, name, label):
            self.Document, self.Name, self.Label = doc, name, label
    doc = types.SimpleNamespace(Name="D", Objects=[])
    old, new_ = Sk(doc, "Sketch", "Upright"), Sk(doc, "Sketch001", "Upright 2")
    doc.Objects += [old, new_]
    doc.getObject = lambda n: next((o for o in doc.Objects if o.Name == n), None)
    class Ses:
        pass
    s = Ses()
    s.filled_now = []
    s.__dict__["_batch_aliases"] = {}
    pc._dry = lambda: False
    pc.note_made_sketch(s, new_, "Upright")
    inside = pc.sketch_of(doc, "Upright", None, s).Label
    s.__dict__.pop("_batch_aliases")
    after = pc.sketch_of(doc, "Upright", None, s).Label
    print(json.dumps([s.filled_now, inside, after]))
''')
        self.assertEqual(got, [["name=Upright 2 (the name Upright was taken; this sketch is Upright 2)"], "Upright 2", "Upright"])

    def test_the_card_gives_the_name_asked(self):
        self.assertIn({"do": "=note_sketch(sk, a.get('name'))"}, entries()["sketch_new"]["steps"])


PAD = {"type": "object", "properties": {"extent": {"type": "string", "description": "length (default), through_all, up_to_first or up_to_face."},
                                        "length": {"type": "number"}}, "additionalProperties": False}


class SaysTheFix(unittest.TestCase):
    def test_a_depth_in_extent(self):
        with self.assertRaises(ToolError) as e:
            check_input(PAD, {"extent": 5}, "pd_pocket")
        self.assertEqual(e.exception.message, "input.extent: extent takes a word (length, through_all, up_to_first or up_to_face); "
                                              "a depth goes in length: { length: 5 }.")
        a = {"extent": "through_all"}
        check_input(PAD, a, "pd_pocket")  # a word is taken as it was
        self.assertEqual(a, {"extent": "through_all"})

    def test_get_solids_points_to_body_check(self):
        got = in_a_process(SETUP + '''
    from agentlink import fastpath
    from agentlink.protocol import ToolError
    o = types.SimpleNamespace(Name="Body", Label="LidBody", Shape=object(), PropertiesList=["Label", "Shape"], TypeId="PartDesign::Body")
    doc = types.SimpleNamespace(Label="Lid", getObject=lambda n: o if n in ("Body", "LidBody") else None, getObjectsByLabel=lambda n: [o] if n == "LidBody" else [])
    s = types.SimpleNamespace(doc=doc)
    out = []
    for w in ("LidBody.solids", "LidBody.valid"):
        try:
            fastpath.read(types.SimpleNamespace(tools={}), s, w)
        except ToolError as e:
            out.append(e.message)
    print(json.dumps(out))
''')
        self.assertEqual(got[0], 'LidBody.solids: get does not read solids. body_check { body: "LidBody" } gives solids, valid and closed '
                                 '(with volume and box); get gives LidBody.volume, .area and .size.')
        self.assertIn("get does not read valid", got[1])
        self.assertNotIn("object_get", "".join(got))


class Pieces(unittest.TestCase):
    def test_two_separate_cuts_are_said_apart(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import pd_common as pc
    def bb(x0, x1):
        return types.SimpleNamespace(XMin=x0, XMax=x1, YMin=-2.5, YMax=2.5, ZMin=-5, ZMax=0)
    a, b = types.SimpleNamespace(BoundBox=bb(-17.5, -12.5)), types.SimpleNamespace(BoundBox=bb(12.5, 17.5))
    pc._lids = lambda reg, skin, diag: ([], [(2, -1, -5.0)])
    print(json.dumps([pc.pieces_sentence([a, b], None, 60.0), pc.pieces_sentence([a] * 6, None, 60.0)]))
''')
        self.assertEqual(got[0], "2 separate cuts: x -17.5..-12.5, y -2.5..2.5, z -5..0: the cut opens on -z (z -5) and goes 5 mm deep; "
                                 "x 12.5..17.5, y -2.5..2.5, z -5..0: the cut opens on -z (z -5) and goes 5 mm deep.")
        self.assertTrue(got[1].startswith("6 separate cuts: "))
        self.assertTrue(got[1].endswith("; and 2 more."), got[1])


if __name__ == "__main__":
    unittest.main()
