# SPDX-License-Identifier: LGPL-2.1-or-later
# Bicycle runs (21 Nov), FreeCAD 1.1.3, 32 assembly parts (two spoke bodies of
# 32 solids, a frame of about 190 faces): one asm_joint took 134.7 s, 119.2 s
# of it the tool's own overlap scan, which cut every pair of the assembly.
# asm_joint cuts only pairs with a part the solve moved (or a joint's part);
# asm_check keeps its full list, with boxes first, solid by solid and point
# tests. On the data tests' stand-in FreeCAD in a child process.
import os
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)

from test_bicycle_1120 import child  # noqa: E402

# 32 parts: Base (grounded), Lid (moved by the joint), a frame and fork that
# overlap and stay put, a 32-solid spoke body that overlaps the frame and
# stays put, and 27 parts far off. A._shape gives counted box shapes.
BUILD = r'''
    from test_bicycle_runs_1121 import _Shape
    far = [f"Far{i}" for i in range(27)]
    for n in ["Frame", "Fork", "Spokes"] + far:
        fc.a_part(n, (0, 0, 0), (1, 1, 1), name=n)
    asm, jg = assembly("Base", "Lid", "Frame", "Fork", "Spokes", *far)
    shapes = {
        "Base": _Shape([((-500, -500, -500), (-490, -490, -490))]),
        # Lid after the solve: into the frame and three of the spoke body's solids
        "Lid": _Shape([((-300, -1, -1), (-255, 1, 1))]),
        "Frame": _Shape([((-310, -2, -2), (300, 2, 2))]),
        "Fork": _Shape([((290, -1, -1), (320, 1, 1))]),
        "Spokes": _Shape([((-300 + 18 * i, -1, -1), (-290 + 18 * i, 1, 1)) for i in range(32)]),
    }
    for i, n in enumerate(far):
        shapes[n] = _Shape([((1000 + 50 * i, 0, 0), (1010 + 50 * i, 10, 10))])
    A._shape = lambda o: shapes[o.Name]
    fc.state["flags"].update(joint_puts={"Lid": [0, 0, 5]})
    _Shape.cuts[0] = 0
'''


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


class JointOverlaps(unittest.TestCase):

    def test_only_pairs_with_the_moved_part_are_cut(self):
        r, cuts = child(BUILD, '''
            got = run("asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face2"}})
            print(json.dumps([got, _Shape.cuts[0]], default=str))
        ''')
        self.assertEqual(r[0], "ok", r)
        ans = r[1]
        self.assertIn("Lid", ans["moved"])
        pairs = sorted(sorted(h["parts"]) for h in ans["overlaps"])
        self.assertEqual(pairs, [["Frame", "Lid"], ["Lid", "Spokes"]])
        for p in pairs:
            self.assertIn("Lid", p)
        # Lid's box meets the frame and 3 of the 32 spoke solids; Frame/Fork and Frame/Spokes are not cut
        self.assertEqual(cuts, 4)
        self.assertIn("2 pairs of parts that did not move", ans["otherPairs"])
        self.assertIn("asm_check", ans["otherPairs"])

    def test_asm_check_keeps_the_full_list_with_bounded_booleans(self):
        r, cuts = child(BUILD, '''
            fc.put("Lid", [0, 0, 5])
            got = run("asm_check", {})
            print(json.dumps([got, _Shape.cuts[0]], default=str))
        ''')
        self.assertEqual(r[0], "ok", r)
        ans = r[1]
        pairs = sorted(sorted(h["parts"]) for h in ans["overlaps"])
        self.assertEqual(pairs, [["Fork", "Frame"], ["Frame", "Lid"], ["Frame", "Spokes"], ["Lid", "Spokes"]])
        # 32 parts, 496 pairs: only the 4 pairs whose boxes meet; per solid, only solids whose boxes meet
        self.assertEqual(ans["cuts"]["pairs"], 4)
        self.assertEqual(ans["cuts"]["booleans"], cuts)
        self.assertLessEqual(cuts, 1 + 1 + 32 + 3)


class PointTest(unittest.TestCase):

    def test_a_solid_all_inside_is_one_point_test(self):
        got = child(r'''
            from test_bicycle_runs_1121 import _Box, _Shape
            class Named:
                def __init__(self, name):
                    self.Name = self.Label = name
            class Face:
                def __init__(self, lo, hi):
                    self.BoundBox = _Box(lo, hi)
            class Pt:
                def __init__(self, p):
                    self.Point = p
            wall = _Shape([((0, 0, 0), (100, 100, 100))])
            wall.Faces = [Face((0, 0, 0), (0, 100, 100)), Face((100, 0, 0), (100, 100, 100)), Face((0, 0, 0), (100, 0, 100)),
                          Face((0, 100, 0), (100, 100, 100)), Face((0, 0, 0), (100, 100, 0)), Face((0, 0, 100), (100, 100, 100))]
            wall.isInside = lambda p, tol, on: all(0 < c < 100 for c in p)
            pins = _Shape([((40 + 3 * i, 40, 40), (41 + 3 * i, 50, 50)) for i in range(10)])
            for x in pins.Solids:
                x.Vertexes = [Pt((x.BoundBox.XMin, 40, 40))]
            shapes = {"Wall": wall, "Pins": pins}
            A._shape = lambda o: shapes[o.Name]
            st = {}
            _Shape.cuts[0] = 0
            hits, _ = A._overlaps([Named("Wall"), Named("Pins")], 0.0, None, None, st)
            print(json.dumps([[h["volume"] for h in hits], st, _Shape.cuts[0]]))
        ''')
        vols, st, cuts = got
        self.assertEqual(vols, [1000])
        self.assertEqual(st["pointTests"], 10)
        self.assertEqual(st["booleans"], 0)
        self.assertEqual(cuts, 0)


class Cards(unittest.TestCase):

    def test_the_cards_say_it(self):
        import json

        with open(os.path.join(os.path.dirname(TESTS), "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]
        self.assertIn("otherPairs", _cw(e["asm_joint"]))
        self.assertIn("pointTests", _cw(e["asm_check"]))
        self.assertNotIn("cuts every pair", _cw(e["asm_check"]))


if __name__ == "__main__":
    unittest.main()
