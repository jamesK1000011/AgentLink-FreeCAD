# SPDX-License-Identifier: LGPL-2.1-or-later
# history_diff on a real FreeCAD document: moved, features and recheck beside
# the bodies' numbers, and only what changed. Its comparing is tested on
# stand-ins in test_smart_calls.py. Skipped where FreeCAD cannot be imported.
import json
import os
import unittest

from _fc import HAVE, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class HistoryDiff(unittest.TestCase):
    def setUp(self):
        self.session, self.srv = server()
        call = caller(self.srv)

        def ok(name, args=None):
            err, out = call(name, args)
            self.assertFalse(err, f"{name}: {out}")
            return out

        self.ok = ok

    def test_an_edit_is_named_and_the_check_that_ran_is_stale(self):
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Cube"})
        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "at": [50, 0, 0], "name": "Other"})
        self.ok("body_check", {"body": "Cube"})
        self.ok("body_check", {"body": "Other"})
        self.ok("object_set", {"object": "Cube", "values": {"Length": 20}})
        d = self.ok("history_diff", {})
        self.assertTrue(d["changed"])
        self.assertEqual(list(d["bodies"]), ["Cube"])
        self.assertEqual(d["bodies"]["Cube"]["volume"], {"from": 1000.0, "to": 2000.0})
        self.assertEqual(d["features"], {"edited": {"Cube": {"Length": {"from": 10.0, "to": 20.0}}}})
        self.assertNotIn("moved", d)  # its lowest corner stayed
        self.assertEqual(d["recheck"], [{"tool": "body_check", "body": "Cube", "ranAt": 2}])

    def test_a_move_is_moved_and_nothing_else(self):
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Cube"})
        self.ok("part_transform", {"op": "move", "body": "Cube", "by": [3, 4, 0]})
        d = self.ok("history_diff", {})
        self.assertTrue(d["changed"])
        self.assertEqual(d["bodies"], {})
        self.assertEqual(d["moved"], {"Cube": {"by": [3.0, 4.0, 0.0], "distance": 5.0}})
        self.assertNotIn("recheck", d)  # no check ran before it
        # the Placement is the edit that moved it
        self.assertIn("Placement", d["features"]["edited"]["Cube"])

    def test_nothing_changed_says_only_that(self):
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Cube"})
        self.ok("object_set", {"object": "Cube", "values": {"Length": 10}})
        d = self.ok("history_diff", {})
        self.assertFalse(d["changed"])
        for k in ("moved", "features", "recheck"):
            self.assertNotIn(k, d)

    def test_a_sketchs_dimension_is_named(self):
        try:
            import PartDesign  # noqa: F401
            import Sketcher  # noqa: F401
        except ImportError:
            self.skipTest("no PartDesign or Sketcher here")
        self.ok("pd_body_new", {"name": "Block"})
        self.ok("sketch_new", {"plane": "XY", "name": "Base"})
        self.ok("sketch_add", {"sketch": "Base", "items": [{"kind": "rectangle", "corner": [0, 0], "size": [40, 20], "dims": True}]})
        self.ok("pd_pad", {"sketch": "Base", "length": 10})
        sk = self.session.doc.getObjectsByLabel("Base")[0]
        i = next(k for k, c in enumerate(sk.Constraints) if c.Type in ("DistanceX", "Distance") and abs(c.Value - 40) < 1e-6)
        import FreeCAD

        self.session.doc.openTransaction("edit")
        sk.setDatum(i, FreeCAD.Units.Quantity("50 mm"))
        self.session.doc.commitTransaction()
        self.session.doc.recompute()
        self.session.snapshot("test edit")
        d = self.ok("history_diff", {})
        row = d["features"]["edited"]["Base (Block)"]["constraintValues"][0]
        self.assertEqual((row["index"], row["from"], row["to"]), (i, 40.0, 50.0))
        self.assertEqual(d["bodies"]["Block"]["volume"], {"from": 8000.0, "to": 10000.0})

    def test_a_batch_names_its_record_and_the_record_holds_what_ran(self):
        box = {"tool": "part_primitive", "arguments": {"kind": "box", "size": [5, 5, 5], "name": "A"}}
        b = self.ok("batch", {"calls": [box, {"tool": "session_state", "arguments": {}}]})
        self.assertTrue(b["record"].endswith(".json") and os.sep + "batches" + os.sep in b["record"], b)
        with open(b["record"], encoding="utf-8") as f:
            rec = json.load(f)
        self.assertEqual((rec["calls"], rec["ran"], len(rec["results"])), (2, 2, 2))
        self.assertNotIn("running", rec)
        self.assertEqual(rec["results"][0]["result"]["body"], "A")
        # with to: the short answer names both files
        t = self.ok("batch", {"calls": [{"tool": "session_state", "arguments": {}}], "to": "run.json"})
        self.assertIn("record", t)
        self.assertIn("written", t)


if __name__ == "__main__":
    unittest.main()
