# SPDX-License-Identifier: LGPL-2.1-or-later
# Blind QA of nine local-model runs (26 Nov), the sketch answers:
#   1. readyForFeature is true only when every wire is closed and no two
#      closed loops cross or touch (a loop inside another is a hole); a wire
#      that branches (three or more edges at a point) is named;
#   2. two loose line ends near a full circle are not paired ("join them"):
#      the words say to use an arc there;
#   3. the sketch_add card and the sketch guide say round ends are arcs;
#   4. (tests/test_bicycle_bind_fuse.py) the tube rule only when tube bores
#      are found.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_hubfix2 import in_a_process  # noqa: E402
from test_qa_sketch_1124 import SETUP  # noqa: E402

# Stand-in sketch geometry: lines and circles with the distance from a point.
GEO = SETUP + '''
    import types, math
    from agentlink.families import sketch
    class P:
        def __init__(self, x, y, z=0):
            self.x, self.y, self.z = x, y, z
    def seg(a, b, p):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        return math.dist(p, (a[0] + t * dx, a[1] + t * dy))
    class LineSegment:
        def __init__(self, a, b):
            self.a, self.b = a, b
            self.StartPoint, self.EndPoint = P(*a), P(*b)
        def d(self, p):
            return seg(self.a, self.b, p)
        def toShape(self):
            return types.SimpleNamespace(distToShape=lambda v: (self.d((v.x, v.y)),))
    class Circle:
        def __init__(self, c, r):
            self.c, self.r = c, r
            self.Center, self.Radius = P(*c), r
        def d(self, p):
            return abs(math.dist(p, self.c) - self.r)
        def toShape(self):
            return types.SimpleNamespace(distToShape=lambda v: (self.d((v.x, v.y)),))
    def dist_of(geo):
        return lambda i, p: geo[i].d(p)
    sketch.Part = types.SimpleNamespace(Vertex=lambda v: v)
    sketch.V = P
'''


class Branches(unittest.TestCase):
    def test_lines_that_end_on_a_circle(self):
        # crank, qwen: two lines end where circle 0 passes, at (157.5, 0)
        got = in_a_process(GEO + '''
    geo = {0: Circle((170, 0), 12.5), 2: LineSegment((157.5, 0), (0, 5)), 4: LineSegment((157.5, 0), (0, -5))}
    ends = [(2, "line", 1, (157.5, 0)), (2, "line", 2, (0, 5)), (4, "line", 1, (157.5, 0)), (4, "line", 2, (0, -5))]
    print(json.dumps(sketch.branch_words(ends, {0: "circle", 2: "line", 4: "line"}, 183.0, dist_of(geo), [0])))
''')
        self.assertEqual(got, ["lines 2 and 4 meet circle 0 at (157.5, 0): a wire branches there; an outline has two edges at each joint, "
                               "so use an arc there, not a full circle (two round ends joined by straight sides are one slot item: slot { from, to, radius, radius2 })"])

    def test_three_ends_at_one_point_and_one_end_on_a_line(self):
        got = in_a_process(GEO + '''
    geo = {0: LineSegment((0, 0), (50, 0)), 1: LineSegment((50, 0), (100, 0)), 6: LineSegment((50, 0), (50, 50)),
           7: LineSegment((0, 50), (100, 50)), 8: LineSegment((20, 50), (20, 80))}
    ends = [(g, "line", pos, (q.x, q.y)) for g, l in geo.items() for pos, q in ((1, l.StartPoint), (2, l.EndPoint))]
    print(json.dumps(sketch.branch_words(ends, {g: "line" for g in geo}, 120.0, dist_of(geo))))
''')
        self.assertEqual(got, ["lines 0, 1 and 6 meet at (50, 0): a wire branches there; an outline has two edges at each joint",
                               "line 6 meets line 7 at (50, 50)", "line 8 meets line 7 at (20, 50)"])

    def test_a_plain_outline_has_no_branch(self):
        got = in_a_process(GEO + '''
    pts = [(0, 0), (100, 0), (100, 50), (0, 50)]
    geo = {i: LineSegment(pts[i], pts[(i + 1) % 4]) for i in range(4)}
    ends = [(g, "line", pos, (q.x, q.y)) for g, l in geo.items() for pos, q in ((1, l.StartPoint), (2, l.EndPoint))]
    print(json.dumps(sketch.branch_words(ends, {g: "line" for g in geo}, 112.0, dist_of(geo))))
''')
        self.assertEqual(got, [])


class Crossing(unittest.TestCase):
    def test_loops_that_meet(self):
        got = in_a_process(GEO + '''
    at = {(0, 2): (7.5, 6.6), (1, 2): (40, 5)}
    print(json.dumps(sketch.cross_words(["circle 0", "circle 1", "the loop of lines 2, 3, 4 and 5"], lambda i, j: at.get((i, j)))))
''')
        self.assertEqual(got, ["circle 0 meets the loop of lines 2, 3, 4 and 5 at (7.5, 6.6): a pad or pocket uses only loops that do not cross or touch; make one outline",
                               "circle 1 meets the loop of lines 2, 3, 4 and 5 at (40, 5)"])

    def test_loops_apart_or_nested_say_nothing(self):
        got = in_a_process(GEO + '''
    print(json.dumps(sketch.cross_words(["circle 0", "circle 1"], lambda i, j: None)))
''')
        self.assertEqual(got, [])


class RoundEnds(unittest.TestCase):
    def test_ends_near_a_circle_are_not_paired(self):
        # crank, gpt-oss: full circles plus lines that stop 2.4 mm short of circle 0.
        # Before: "the start of line 1 (0, 7.4) is 14.8 mm from the start of line 2 (0, -7.4): ... coincident joins them"
        got = in_a_process(GEO + '''
    geo = {0: Circle((0, 0), 5), 3: Circle((150, 0), 6), 1: LineSegment((0, 7.4), (150, 6)), 2: LineSegment((0, -7.4), (150, -6))}
    ends = [(1, "line", 1, (0, 7.4)), (1, "line", 2, (150, 6)), (2, "line", 1, (0, -7.4)), (2, "line", 2, (150, -6))]
    print(json.dumps(sketch.open_end_words(ends, [0, 1, 2, 3], 161.6, dist_of(geo), [0, 3])))
''')
        self.assertEqual(got, ["line 1 ends at (0, 7.4), 2.4 mm from circle 0: an outline uses an arc there, not a full circle",
                               "line 2 ends at (0, -7.4), 2.4 mm from circle 0: an outline uses an arc there, not a full circle"])

    def test_ends_far_from_a_circle_still_pair(self):
        got = in_a_process(GEO + '''
    geo = {0: Circle((-60, 0), 5), 1: LineSegment((0, 0), (100, 0)), 2: LineSegment((100, 0), (100, 50)),
           3: LineSegment((100, 50), (0, 50)), 4: LineSegment((0, 50), (0, 0.4))}
    ends = [(4, "line", 2, (0, 0.4)), (1, "line", 1, (0, 0))]
    print(json.dumps(sketch.open_end_words(ends, [0, 1, 2, 3, 4], 170.0, dist_of(geo), [0])))
''')
        self.assertEqual(got, ["the end of line 4 (0, 0.4) is 0.4 mm from the start of line 1 (0, 0): sketch_constrain coincident joins them"])


# state_of on a stand-in sketch: its geometry, and its Shape's wires as FreeCAD builds them.
STATE = GEO + '''
    class Vx:
        def __init__(self, p):
            self.Point = P(*p)
        def isSame(self, o):
            return o is self
    class Edge:
        def __init__(self, vs, g=None):
            self.Vertexes, self.g = vs, g
            self.FirstParameter, self.LastParameter = 0.0, 2 * math.pi
        def valueAt(self, t):
            return P(self.g.c[0] + self.g.r * math.cos(t), self.g.c[1] + self.g.r * math.sin(t))
    class Wire:
        def __init__(self, closed, edges, circle=None):
            self.closed, self.Edges, self.circle = closed, edges, circle
            self.Vertexes = list({id(v): v for e in edges for v in e.Vertexes}.values())
        def isClosed(self):
            return self.closed
        def distToShape(self, o):
            a, b = self.circle, o.circle
            d = math.dist(a.c, b.c)
            gap = max(d - a.r - b.r, abs(a.r - b.r) - d, 0.0)
            ux, uy = ((b.c[0] - a.c[0]) / d, (b.c[1] - a.c[1]) / d) if d else (1.0, 0.0)
            p = P(a.c[0] + a.r * ux, a.c[1] + a.r * uy)
            return gap, [(p, p)], None
    def circle_wire(g):
        v = Vx((g.c[0] + g.r, g.c[1]))
        return Wire(True, [Edge([v], g)], g)
    def lines_wire(geo, ids):
        vs = {}
        def vx(p):
            return vs.setdefault((round(p.x, 6), round(p.y, 6)), Vx((p.x, p.y)))
        return Wire(False, [Edge([vx(geo[i].StartPoint), vx(geo[i].EndPoint)]) for i in ids])
    class Same:
        def multVec(self, v):
            return v
    def sketch_of(geo, wires, size):
        sk = types.SimpleNamespace(Label="Sketch", DoF=0, Geometry=[geo[i] for i in range(len(geo))],
                                   getConstruction=lambda i: False, solve=lambda: 0,
                                   Placement=types.SimpleNamespace(inverse=lambda: Same()))
        sk.Shape = types.SimpleNamespace(isNull=lambda: False, Wires=wires, BoundBox=types.SimpleNamespace(DiagonalLength=size))
        return sk
'''


class Ready(unittest.TestCase):
    def test_an_open_wire_with_branches_is_not_ready(self):
        # a rectangle cut in two by line 6, its sides split at (50, 0) and (50, 50):
        # no one-edge end, so the old test (closed > 0 and no open end) said ready
        got = in_a_process(STATE + '''
    pts = [((0, 0), (50, 0)), ((50, 0), (100, 0)), ((100, 0), (100, 50)), ((100, 50), (50, 50)), ((50, 50), (0, 50)),
           ((0, 50), (0, 0)), ((50, 0), (50, 50))]
    geo = {i: LineSegment(a, b) for i, (a, b) in enumerate(pts)}
    geo[7] = Circle((200, 25), 10)
    sk = sketch_of(geo, [lines_wire(geo, range(7)), circle_wire(geo[7])], 212.0)
    print(json.dumps(sketch.state_of(sk)))
''')
        self.assertEqual((got["wires"], got["closedWires"]), (2, 1))
        self.assertNotIn("openVertices", got)
        self.assertFalse(got["readyForFeature"])
        self.assertEqual(got["todo"], "lines 0, 1 and 6 meet at (50, 0): a wire branches there; an outline has two edges at each joint; "
                                      "lines 3, 4 and 6 meet at (50, 50)")

    def test_loops_that_cross_are_not_ready(self):
        got = in_a_process(STATE + '''
    geo = {0: Circle((0, 0), 10), 1: Circle((15, 0), 10)}
    sk = sketch_of(geo, [circle_wire(geo[0]), circle_wire(geo[1])], 40.0)
    print(json.dumps(sketch.state_of(sk)))
''')
        self.assertEqual((got["wires"], got["closedWires"]), (2, 2))
        self.assertFalse(got["readyForFeature"])
        self.assertEqual(got["todo"], "circle 0 meets circle 1 at (10, 0): a pad or pocket uses only loops that do not cross or touch; make one outline")

    def test_a_loop_inside_another_and_one_loop_are_ready(self):
        got = in_a_process(STATE + '''
    geo = {0: Circle((0, 0), 20), 1: Circle((0, 0), 5)}
    nested = sketch.state_of(sketch_of(geo, [circle_wire(geo[0]), circle_wire(geo[1])], 57.0))
    one = sketch.state_of(sketch_of({0: geo[0]}, [circle_wire(geo[0])], 57.0))
    none = sketch.state_of(sketch_of({}, [], 0.0))
    print(json.dumps([nested["readyForFeature"], one["readyForFeature"], none["readyForFeature"], none["todo"]]))
''')
        self.assertEqual(got, [True, True, False, "no profile yet: sketch_add"])

    def test_circles_plus_lines_name_the_round_ends(self):
        # crank, gpt-oss and gemma: full circles plus two lines that end on them
        got = in_a_process(STATE + '''
    geo = {0: Circle((0, 0), 10), 1: Circle((60, 0), 6), 2: LineSegment((0, -10), (60, -6)), 3: LineSegment((60, 6), (0, 10))}
    sk = sketch_of(geo, [circle_wire(geo[0]), circle_wire(geo[1]), lines_wire(geo, [2]), lines_wire(geo, [3])], 76.7)
    print(json.dumps(sketch.state_of(sk)))
''')
        self.assertFalse(got["readyForFeature"])
        self.assertNotIn("coincident joins them", got["todo"])
        self.assertEqual(got["todo"], "line 2 meets circle 0 at (0, -10): a wire branches there; an outline has two edges at each joint, "
                                      "so use an arc there, not a full circle (two round ends joined by straight sides are one slot item: slot { from, to, radius, radius2 }); line 2 meets circle 1 at (60, -6); line 3 meets circle 1 at (60, 6); "
                                      "line 3 meets circle 0 at (0, 10)")


class Words(unittest.TestCase):
    def test_the_card_and_the_guide_say_round_ends_are_arcs(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]
        d = e["sketch_add"]["description"]
        self.assertIn("In other outlines, round ends joined by straight sides are arcs, not full circles. A full circle is a closed loop of its own.", d)
        self.assertIn("Two round ends joined by straight tangent sides, equal or not: slot { from, to, radius, radius2 }", d)
        self.assertIn("sketch_constrain tangent on their two end points [[line, v], [arc, v]]", d)
        self.assertIn("It is false for an open wire, a branch, or closed loops that cross or touch.", e["sketch_state"]["description"])
        with open(os.path.join(ROOT, "agentlink", "guides", "sketch.md"), encoding="utf-8") as f:
            g = f.read()
        self.assertIn("`[[2, 1], [0, 2]]`, `[[2, 2], [1, 1]]`, `[[1, 2], [3, 1]]`, `[[3, 2], [0, 1]]`", g)
        # the tangent [p, p] form is the one sketch_constrain makes into an end-to-end tangent
        with open(os.path.join(ROOT, "agentlink", "families", "sketch.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('return [("Tangent", refs[0][0], refs[0][1], refs[1][0], refs[1][1])]', src)


if __name__ == "__main__":
    unittest.main()
