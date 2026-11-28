# SPDX-License-Identifier: LGPL-2.1-or-later
# 26 Nov QA (fixes 2, 8, 9): no small model acted on the terse where-fields.
# A feature's answer says where in one sentence (where), a sketch of several
# profiles says what each one did (profiles), and a fillet's or chamfer's
# edges are sorted into outside (convex: they lose material) and inside
# (concave: they gain it), with an edge filter outside: true / false. The
# geometry is proved live; here the words and the logic, on stand-ins.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CHILD = '''
import json, sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.protocol import ToolError
from agentlink.families import pd_common as pc, refs, measure
V = fc.Vec
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + body], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


# An L of two boxes (base x 0..30, z 0..5; upright x 0..5, z 0..40; y 0..10),
# with flat faces as rectangles and the edges along y where they meet.
L_SHAPE = '''
class Plane:
    def __init__(s, k, c, lo, hi):
        s.k, s.c, s.lo, s.hi = k, c, lo, hi          # axis k at c; the other two axes in lo..hi
        s.Surface = s
        s.Edges = []
    def parameter(s, p):
        return (0.0, 0.0)
    def normalAt(s, u, v):
        n = [0.0, 0.0, 0.0]; n[s.k] = 1.0
        return V(*n)
    def distToShape(s, vx):
        p = vx.Point
        d = [0.0, 0.0, 0.0]
        d[s.k] = p[s.k] - s.c
        j = 0
        for i in range(3):
            if i == s.k:
                continue
            q = min(max(p[i], s.lo[j]), s.hi[j]); d[i] = p[i] - q; j += 1
        return (V(*d).Length, None, None)
    def isSame(s, o):
        return s is o
class Edge:
    def __init__(s, x, z):
        s.x, s.z = x, z
        s.FirstParameter, s.LastParameter, s.Length = 0.0, 10.0, 10.0
    def valueAt(s, t):
        return V(s.x, t, s.z)
    def tangentAt(s, t):
        return V(0, 1, 0)
    def isSame(s, o):
        return s is o
class BB:
    DiagonalLength = 51.0
class LSolid:
    BoundBox = BB
    def isInside(s, p, tol, on):
        box = lambda x0, x1, z0, z1: x0 < p.x < x1 and 0 < p.y < 10 and z0 < p.z < z1
        return box(0, 30, 0, 5) or box(0, 5, 0, 40)
base_top = Plane(2, 5.0, (5, 0), (30, 10))      # z 5, x 5..30, y 0..10
base_end = Plane(0, 30.0, (0, 0), (10, 5))      # x 30, y 0..10, z 0..5
up_side = Plane(0, 5.0, (0, 5), (10, 40))       # x 5, y 0..10, z 5..40
up_top = Plane(2, 40.0, (0, 0), (5, 10))        # z 40, x 0..5
outer = Edge(30, 5); inner = Edge(5, 5); top = Edge(5, 40)
base_top.Edges = [outer, inner]; base_end.Edges = [outer]; up_side.Edges = [inner, top]; up_top.Edges = [top]
sh = LSolid()
sh.Faces = [base_top, base_end, up_side, up_top]
sh.Edges = [outer, inner, top]
'''


class Where(unittest.TestCase):
    def test_added_and_removed_in_one_sentence(self):
        got = child('''
print(json.dumps({
    "below_above": pc.added_sentence((0, 5, -15, 15, -20, 20), (-30, 30, -15, 15, 0, 5)),
    "in_box": pc.added_sentence((0, 5, -15, 15, 0, 5), (-30, 30, -15, 15, 0, 5)),
    "side": pc.added_sentence((30, 40, -15, 15, 0, 5), (-30, 30, -15, 15, 0, 5)),
    "through": pc.removed_sentence([(2, 1, 10), (2, -1, 0)], (0, 1, 0, 1, 0, 10)),
    "one_end": pc.removed_sentence([(2, 1, 10)], (0, 1, 0, 1, 3, 10)),
    "two_ends": pc.removed_sentence([(2, 1, 10), (0, 1, 30)], (26, 30, 0, 1, 3, 10)),
    "slant": pc.removed_sentence([None], (0, 1, 0, 1, 3, 10)),
    "closed": pc.removed_sentence([], (0, 1, 0, 1, 3, 10)),
    "keys": [pc.side_key((0, 0, 1), (1, 2, 10)), pc.side_key((-1.0, 0, 0), (-3, 2, 1)), pc.side_key((0.7071, 0, 0.7071), (1, 2, 3))],
}))
''')
        self.assertEqual(got["below_above"], "The new material goes 20 mm below the body's bottom (z 0) and 15 mm above its top (z 5).")
        self.assertEqual(got["in_box"], "The new material is inside the body's box before.")
        self.assertEqual(got["side"], "The new material goes 10 mm past the body's +x side (x 30).")
        self.assertEqual(got["through"], "The cut goes all the way through along z.")
        self.assertEqual(got["one_end"], "The cut opens on +z (z 10) and goes 7 mm deep.")
        self.assertEqual(got["two_ends"], "The cut opens on +x (x 30), 4 mm deep, and on +z (z 10), 7 mm deep.")
        self.assertEqual(got["slant"], "The cut opens on a slanted or curved face.")
        self.assertEqual(got["closed"], "The cut is closed inside the body.")
        self.assertEqual(got["keys"], [[2, 1, 10], [0, -1, -3], None])

    def test_profiles_say_what_each_did(self):
        got = child('''
class Prism:
    def __init__(s, f): s.f = f
    def common(s, other):
        vol = s.f.hits.get(other.tag, 0.0)
        class P:
            Point = V(0, 0, 0)
        class Q:
            Point = V(0, 0, vol / 1.0)   # a cut 1 mm^2 wide: its depth is its volume
        class R:
            Volume = vol
            Vertexes = [P, Q]
        return R()
class Face:
    Area = 1.0
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
out = {}
pc.profile_faces = lambda feat: [("the circle r 2.5 at (15, 0)", Face({"reg": 98.2, "old": 98.2})), ("the circle r 2.5 at (45, 0)", Face({}))]
out["pocket"] = pc.profile_results(None, reg, old, 0.01, cut=True)
pc.profile_faces = lambda feat: [("the outline at (0, 0)", Face({"reg": 5.0})), ("the circle r 3 at (5, 0)", Face({"old": 9.0}))]
out["missed"] = pc.profile_results(None, reg, old, 0.01, cut=True)
out["pad"] = pc.profile_results(None, reg, old, 0.01, cut=False)
pc.profile_faces = lambda feat: [("a", Face({"reg": 1.0})), ("b", Face({"reg": 1.0}))]
out["both"] = pc.profile_results(None, reg, old, 0.01, cut=True)
pc.profile_faces = lambda feat: [(str(i), Face({"reg": 1.0})) for i in range(16)]
out["many"] = pc.profile_results(None, reg, old, 0.01, cut=True)
pc.profile_faces = lambda feat: []
out["one"] = pc.profile_results(None, reg, old, 0.01, cut=True)
def boom(feat): raise RuntimeError("no face")
pc.profile_faces = boom
out["error"] = pc.profile_results(None, reg, old, 0.01, cut=True)
print(json.dumps(out))
''')
        self.assertEqual(got["pocket"], {"profiles": "2 profiles: the circle r 2.5 at (45, 0) is off the body; 1 cut in full."})
        self.assertEqual(got["missed"], {"profiles": "2 profiles: the circle r 3 at (5, 0) cut nothing; 1 cut in full."})
        self.assertEqual(got["pad"], {"profiles": "2 profiles: the circle r 3 at (5, 0) adds nothing (inside the body already); 1 added in full."})
        self.assertEqual(got["both"], {"profiles": "2 profiles: both cut in full."})
        self.assertEqual(got["many"], {"profiles": "16 profiles (12 looked at): all 12 cut in full."})
        self.assertEqual(got["one"], {})
        self.assertEqual(got["error"], {})

    def test_profile_faces_only_for_sketch_features(self):
        got = child('''
class Feat:
    TypeId = "PartDesign::Fillet"
class Rev:
    TypeId = "PartDesign::Revolution"
print(json.dumps([pc.profile_faces(Feat()), pc.profile_faces(Rev())]))
''')
        self.assertEqual(got, [[], []])


class Sides(unittest.TestCase):
    def test_outside_and_inside_edges_of_an_l(self):
        got = child(L_SHAPE + '''
print(json.dumps([measure.edge_side(sh, outer), measure.edge_side(sh, inner), measure.edge_side(sh, top)]))
''')
        self.assertEqual(got, ["outside", "inside", "outside"])

    def test_smooth_or_free_edges_are_not_known(self):
        got = child('''
class Full:
    def isInside(s, q, tol, on): return True
class One:
    Faces = []
    def ancestorsOfType(s, e, t): return [1]
class E:
    pass
print(json.dumps([measure.side_of(V(0, 0, 0), V(1, 0, 0), V(-1, 0, 0), 0.01, Full()), measure.edge_side(One(), E()),
                  measure.side_of(V(0, 0, 0), V(-1, 0, 0), V(0, 0, -1), 0.01, Full())]))
''')
        self.assertEqual(got, [None, None, "outside"])

    def test_edge_words_are_records_with_the_side(self):
        got = child('''
E = lambda p, q: fc.Shape("edge", [V(*p), V(*q)], curve="Line")
sh = fc.Shape("solid", [])
sh.Edges = [E((0, 0, 0), (0, 0, 10)), E((5, 5, 0), (5, 5, 10))]
for e in sh.Edges:
    e.Edges = [e]
plain = pc.edge_words(sh, ["Edge1", "Edge2"])
pc.edge_sides = lambda shape, names: ["outside", "inside"]
print(json.dumps({"plain": plain, "sided": pc.edge_words(sh, ["Edge1", "Edge2"])}))
''')
        self.assertEqual(got["plain"], [{"edge": "Edge1", "kind": "line", "along": "z", "length": 10.0, "mid": [0.0, 0.0, 5.0]},
                                        {"edge": "Edge2", "kind": "line", "along": "z", "length": 10.0, "mid": [5.0, 5.0, 5.0]}])
        self.assertEqual([e.get("side") for e in got["sided"]], ["outside", "inside"])
        self.assertEqual(got["sided"][0], {**got["plain"][0], "side": "outside"})

    def test_the_outside_filter(self):
        got = child('''
E = lambda p, q: fc.Shape("edge", [V(*p), V(*q)], curve="Line")
sh = fc.Shape("solid", [])
sh.Edges = [E((0, 0, 0), (0, 0, 10)), E((5, 5, 0), (5, 5, 10)), E((9, 0, 0), (9, 0, 10))]
for e in sh.Edges:
    e.Edges = [e]
    e.isSame = lambda o, e=e: o is e
measure.edge_side = lambda shape, e: "inside" if e.Vertexes[0].Point.x == 5 else "outside"
def refs_of(q):
    return [d["ref"] for _, _, d in measure.filter_shape(sh, q, "edge")[1]]
def refused(q, kind="edge"):
    try:
        measure.filter_shape(sh, q, kind)
    except ToolError as e:
        return e.message
print(json.dumps({"out": refs_of({"type": "line", "axis": "z", "outside": True}), "in": refs_of({"outside": False}),
                  "all": refs_of({"axis": "z"}), "word": refused({"outside": "yes"}), "face": refused({"outside": True}, "face"),
                  "is_filter": refs.is_filter({"outside": True}, ("near", "face", "all", "kind", "tol"))}))
''')
        self.assertEqual(got["out"], ["Edge1", "Edge3"])
        self.assertEqual(got["in"], ["Edge2"])
        self.assertEqual(got["all"], ["Edge1", "Edge2", "Edge3"])
        self.assertIn("outside: true", got["word"])
        self.assertIn("edges only", got["face"])
        self.assertTrue(got["is_filter"])


class Cards(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            self.e = json.load(f)["entries"]

    def test_fillet_card_sorts_the_sides(self):
        d = self.e["pd_fillet"]["description"]
        self.assertNotIn("both are correct", d)
        self.assertIn('{ type: "line", axis: "z", outside: true }', d)
        self.assertIn("outside: true", self.e["pd_chamfer"]["description"])

    def test_shape_query_takes_outside(self):
        sq = self.e["shape_query"]
        self.assertEqual(sq["inputSchema"]["properties"]["outside"], {"type": "boolean"})
        self.assertIn("outside: true", sq["description"])


if __name__ == "__main__":
    unittest.main()
