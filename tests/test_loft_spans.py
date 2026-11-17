# SPDX-License-Identifier: LGPL-2.1-or-later
# Found rebuilding a scanned pistol shell from 26 closed scan sections (live
# test drive, 16 Nov 2026): a loft of two neighbouring B-spline sections
# failed in OCC, smooth lofts of 5–26 were refused as bulging 16–73%, a
# ruled loft of the same B-splines failed while polygons of 24 points
# worked, and 26 × 24 points went through the conversation inline, twice.
# The numbers behind the fixes, with plain tuples (no FreeCAD), then the
# tools themselves where FreeCAD is importable.
import json
import math
import os
import sys
import tempfile
import unittest

from _fc import HAVE, caller, server

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import loftmath as lm  # noqa: E402
from agentlink import pointfiles as pf  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


def section(x, n=24, a=14.0, b=40.0, start=0, notch=0.0):
    """A closed outline in the plane x = const, from near the top, the
    same way round each time; notch dents one side (a scan's feature)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = 1.0 - (notch if i in (5, 6) else 0.0)
        pts.append([x, a * r * math.sin(t), b * math.cos(t)])
    return pts[start:] + pts[:start]


class Resample(unittest.TestCase):
    def test_square_by_arc_length(self):
        sq = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        out = lm.resample(sq, 8)
        self.assertEqual(len(out), 8)
        for p, q in zip(out, [(0, 0, 0), (5, 0, 0), (10, 0, 0), (10, 5, 0), (10, 10, 0), (5, 10, 0), (0, 10, 0), (0, 5, 0)]):
            self.assertAlmostEqual(lm._d(p, q), 0, places=9)
        # A repeated first point at the end is the same loop.
        self.assertEqual(lm.resample(sq + [sq[0]], 8), out)

    def test_open_keeps_both_ends(self):
        out = lm.resample([(0, 0, 0), (3, 0, 0), (3, 4, 0)], 3, closed=False)
        self.assertEqual(out[0], (0, 0, 0))
        self.assertAlmostEqual(lm._d(out[-1], (3, 4, 0)), 0, places=9)
        self.assertAlmostEqual(lm._d(out[1], (3, 0.5, 0)), 0, places=9)

    def test_best_shift_finds_the_seam_whatever_the_offset(self):
        a = [lm.tup(p) for p in section(0)]
        b = [lm.tup(p) for p in section(7, start=5)]
        self.assertEqual(lm.best_shift(a, b), 24 - 5)
        out, turned = lm.line_up([a, b, [lm.tup(p) for p in section(14, start=20)]])
        self.assertEqual(turned, 2)
        self.assertAlmostEqual(out[1][0][2], 40.0)  # starts at the top again
        self.assertAlmostEqual(out[2][0][2], 40.0)


class Spans(unittest.TestCase):
    def setUp(self):
        self.secs = [[lm.tup(p) for p in section(10 * i)] for i in range(5)]
        self.boxes = [lm.box_of(s) for s in self.secs]
        self.centres = [lm.centroid(s) for s in self.secs]

    def test_no_bulge_inside_each_span(self):
        pts = [p for s in self.secs for p in s]
        self.assertEqual(lm.span_bulges(pts, self.boxes, self.centres, 0.15), [])

    def test_the_bulging_span_is_named(self):
        pts = [p for s in self.secs for p in s]
        pts.append((25.0, 30.0, 0.0))  # between profiles 2 and 3, far out in y
        out = lm.span_bulges(pts, self.boxes, self.centres, 0.15)
        self.assertEqual(out[0]["span"], [2, 3])
        self.assertEqual(out[0]["axis"], "y")
        self.assertAlmostEqual(out[0]["share"], 16.0 / 28.0, places=3)
        self.assertEqual(len(out), 1)

    def test_span_index_ends(self):
        dirs = lm.directions(self.centres)
        self.assertEqual(lm.span_index((-5, 0, 0), self.centres, dirs), 0)
        self.assertEqual(lm.span_index((15, 0, 0), self.centres, dirs), 1)
        self.assertEqual(lm.span_index((99, 0, 0), self.centres, dirs), 3)

    def test_reach_beyond_matches_the_overall_check(self):
        inner, outer = (-30, -5, 0, 30, 5, 10), (-5, -5, 0, 5, 5, 10)
        share, axis = lm.reach_beyond(inner, outer, 0.15)
        self.assertEqual(axis, "x")
        self.assertGreater(share, 0.15)
        self.assertEqual(lm.reach_beyond(outer, outer, 0.15), (0.0, None))

    def test_pieces(self):
        self.assertEqual(lm.pieces(6, {2}), [(0, 2, False), (2, 3, True), (3, 5, False)])
        self.assertEqual(lm.pieces(4, {0, 2}), [(0, 1, True), (1, 2, False), (2, 3, True)])
        self.assertEqual(lm.pieces(3, set()), [(0, 2, False)])


class PointFiles(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="agentlink-pts-")

    def write(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_json_forms(self):
        one = self.write("one.json", json.dumps(section(0)))
        self.assertEqual(len(pf.one_outline(one)), 24)
        many = self.write("many.json", json.dumps([section(10 * i) for i in range(26)]))
        self.assertEqual(len(pf.outlines(many)), 26)
        self.assertEqual(pf.one_outline(many, 3)[0][0], 30.0)
        with self.assertRaises(ToolError) as cm:
            pf.one_outline(many)
        self.assertIn("key", cm.exception.message)
        named = self.write("named.json", json.dumps({"sections": [section(0), section(5)], "note": "scan"}))
        self.assertEqual(len(pf.outlines(named, "sections")), 2)
        byname = self.write("byname.json", json.dumps({"S0": section(0), "S1": section(5)}))
        self.assertEqual([n for n, _ in pf.outlines(byname)], ["S0", "S1"])
        self.assertEqual(pf.one_outline(byname, "S1")[0][0], 5.0)
        with self.assertRaises(ToolError):
            pf.outlines(byname, "S9")
        bad = self.write("bad.json", json.dumps([[1, 2, "x"]]))
        with self.assertRaises(ToolError):
            pf.outlines(bad)

    def test_csv_forms(self):
        plain = self.write("a.csv", "x,y,z\n0,0,0\n1,0,0\n1,1,0\n\n5,0,0\n6,0,0\n6,1,0\n")
        found = pf.outlines(plain)
        self.assertEqual([len(o) for _, o in found], [3, 3])
        named = self.write("b.csv", "name,x,y,z\nS0,0,0,0\nS0,1,0,0\nS1,0,0,5\nS1,1,0,5\nS0,1,1,0\n")
        found = pf.outlines(named)
        self.assertEqual([(n, len(o)) for n, o in found], [("S0", 3), ("S1", 2)])
        self.assertEqual(pf.one_outline(named, "S1")[0], [0.0, 0.0, 5.0])

    def test_missing_file(self):
        with self.assertRaises(ToolError) as cm:
            pf.outlines(os.path.join(self.d, "nope.json"))
        self.assertEqual(cm.exception.code, "not_found")


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class LoftLive(unittest.TestCase):
    def setUp(self):
        self.session, self.srv = server()
        self.call = caller(self.srv)
        self.call("doc_new", {"name": "Spans"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def wires(self, xs, **kw):
        return [self.ok("part_wire", {"kind": "bspline", "closed": True, "points": section(x, **kw), "name": f"W{x}"})["object"] for x in xs]

    def test_two_neighbouring_bspline_profiles_loft(self):
        out = self.ok("part_loft", {"profiles": self.wires([0, 7])})
        self.assertTrue(out["sound"], out)
        self.assertAlmostEqual(out["box"][0], 7, delta=0.05)

    def test_ruled_between_bsplines_is_polygons(self):
        out = self.ok("part_loft", {"profiles": self.wires([0, 7, 14]), "ruled": True})
        self.assertTrue(out["sound"], out)
        self.assertTrue(any("polygon" in r for r in out["route"]), out)

    def test_many_notched_sections_from_a_file(self):
        secs = [section(7 * i, notch=0.25 if i % 2 else 0.0) for i in range(12)]
        with open(os.path.join(self.session.out_dir, "secs.json"), "w") as f:
            json.dump(secs, f)
        out = self.ok("part_loft", {"profiles_file": "secs.json", "smooth": True})
        self.assertTrue(out["sound"], out)
        self.assertIn("strays", out)
        self.assertLess(out["strays"]["maxDistance"], 1.0)

    def test_wire_from_a_points_file_says_its_fit(self):
        with open(os.path.join(self.session.out_dir, "s.csv"), "w") as f:
            f.write("\n".join(",".join(str(v) for v in p) for p in section(0)))
        out = self.ok("part_wire", {"kind": "bspline", "closed": True, "points_file": "s.csv"})
        self.assertTrue(out["closed"])
        self.assertLess(out["fit"]["maxDistance"], 1e-4)

    def test_batch_from_a_file(self):
        calls = [{"tool": "part_primitive", "arguments": {"kind": "box", "size": [5, 5, 5], "name": "F1"}},
                 {"tool": "part_primitive", "arguments": {"kind": "nope"}}]
        with open(os.path.join(self.session.out_dir, "calls.json"), "w") as f:
            json.dump(calls, f)
        out = self.ok("batch", {"file": "calls.json"})
        self.assertEqual(out["stopped"], 1)
        self.assertEqual(out["undone"], 1)
        err, e = self.call("batch", {"file": "~/.ssh/calls.json"})
        self.assertTrue(err)
        err, e = self.call("batch", {"file": "calls.json", "calls": calls})
        self.assertTrue(err)

    def test_batch_file_keeps_its_title(self):
        with open(os.path.join(self.session.out_dir, "titled.json"), "w") as f:
            json.dump({"title": "Two boxes", "calls": [{"tool": "part_primitive", "arguments": {"kind": "box", "size": [5, 5, 5], "name": "T1"}}]}, f)
        out = self.ok("batch", {"file": "titled.json"})
        rec = out.get("record") or out.get("written", {}).get("path")
        with open(rec) as f:
            self.assertEqual(json.load(f).get("title"), "Two boxes")


if __name__ == "__main__":
    unittest.main()
