# SPDX-License-Identifier: LGPL-2.1-or-later
# The shared health check on a real FreeCAD document (agentlink/health.py):
# what each changing tool's answer says under "health". Skipped where
# FreeCAD cannot be imported; test_health.py covers the wording on stand-ins.
import unittest

from _pd_base import HAVE, Base


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class Health(Base):
    def test_1_a_free_sketch_names_its_freedom(self):
        self.ok("pd_body_new", {"name": "Block"})
        self.ok("sketch_new", {"plane": "XY", "name": "Base"})
        out = self.ok("sketch_add", {"sketch": "Base", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]})
        h = out["health"]
        self.assertTrue(h["ok"], h)
        self.assertIn("Base: ", h["verdict"])
        from _fc import BEFORE_1_1

        dof = self.session.doc.getObjectsByLabel('Base')[0].DoF
        if BEFORE_1_1:
            # FreeCAD 1.0's Sketcher cannot say which geometry is free: the count only.
            self.assertIn(f"{dof} DoF left", h["verdict"])
        else:
            self.assertIn("DoF left on", h["verdict"])
            self.assertIn(f"{dof} DoF left on the start of lines", h["verdict"])
        self.assertNotIn("sketches", h)

    def test_2_the_verdict_follows_the_solver(self):
        self.ok("sketch_new", {"plane": "XZ", "name": "Full"})
        self.ok("sketch_add", {"sketch": "Full", "items": [{"kind": "rectangle", "center": [0, 0], "size": [10, 6], "dims": True}]})
        out = self.ok("sketch_constrain", {"sketch": "Full", "constraints": [{"type": "fix", "refs": [[0, 1]]}]})
        sk = self.session.doc.getObjectsByLabel("Full")[0]
        v = out["health"]["verdict"]
        if sk.DoF == 0:
            self.assertIn("Full: fully constrained", v)
            self.assertNotIn("sketches", out["health"])
        else:
            self.assertIn(f"Full: {sk.DoF} DoF left", v)

    def test_3_a_pad_reads_valid_closed_one_solid(self):
        out = self.ok("pd_pad", {"sketch": "Base", "length": 10})
        h = out["health"]
        self.assertTrue(h["ok"], h)
        self.assertIn("Block: valid, closed, 1 solid", h["verdict"])

    def test_4_overlapping_parts_are_named_with_the_overlap(self):
        out = self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "at": [15, 5, 5], "name": "Clash"})
        h = out["health"]
        self.assertTrue(h["ok"], h)  # yellow: an overlap may be the next boolean's tool
        # Block is 40 x 20 x 10 about the origin: the box overlaps 5 x 5 x 5
        self.assertIn("Clash interferes with Block: 125 mm³ in a box 5 × 5 × 5 mm", h["verdict"])
        self.ok("object_delete", {"objects": ["Clash"]})

    def test_4b_a_sketch_in_a_body_does_not_read_the_body_again(self):
        out = self.ok("sketch_new", {"plane": "YZ", "name": "Later"})
        self.assertNotIn("Block:", out["health"]["verdict"])

    def test_4c_an_inside_out_solid_is_red(self):
        self.ok("part_primitive", {"kind": "box", "size": [4, 4, 4], "at": [200, 0, 0], "name": "Turned"})
        out = self.ok("part_fix", {"body": "Turned", "op": "reverse"})
        self.assertFalse(out["health"]["ok"], out)
        self.assertIn("inside out", out["health"]["verdict"])
        self.ok("object_delete", {"objects": ["Turned"]})

    def test_4d_touching_solids_in_a_compound_are_not_a_self_cut(self):
        self.ok("part_primitive", {"kind": "box", "size": [4, 4, 4], "at": [300, 0, 0], "name": "Left"})
        self.ok("part_primitive", {"kind": "box", "size": [4, 4, 4], "at": [304, 0, 0], "name": "Right"})
        out = self.ok("part_compound", {"bodies": ["Left", "Right"], "name": "Pair"})
        h = out["health"]
        self.assertTrue(h["ok"], h)
        self.assertIn("2 solids", h["verdict"])
        self.assertNotIn("geometry check", h["verdict"])

    def test_5_a_failed_recompute_is_named_with_freecads_reason(self):
        import FreeCAD

        doc = self.session.doc
        box = doc.addObject("Part::Box", "HBox")
        doc.recompute()
        f = doc.addObject("Part::Fillet", "HFillet")
        f.Base = box
        f.Edges = [(1, 50.0, 50.0)]  # a radius the 10 mm box cannot take
        box.Visibility = False if FreeCAD.GuiUp else box.Visibility
        out = self.ok("recompute", {})
        h = out["health"]
        self.assertFalse(h["ok"], h)
        self.assertTrue(any(e["object"] == "HFillet" and e.get("new") for e in h["errors"]), h)
        self.assertIn("failed to recompute: HFillet", h["verdict"])
        # the next call does not call it new
        out = self.ok("recompute", {})
        self.assertIn("still failing from before this call: HFillet", out["health"]["verdict"])
        doc.removeObject("HFillet")
        doc.removeObject("HBox")
        doc.recompute()

    def test_6_reads_carry_no_health(self):
        out = self.ok("sketch_state", {"sketch": "Base"})
        self.assertNotIn("health", out)

    def test_7_a_batch_carries_it_per_call_not_twice(self):
        out = self.ok("batch", {"calls": [{"tool": "sketch_new", "arguments": {"plane": "YZ", "name": "InBatch"}},
                                          {"tool": "sketch_add", "arguments": {"sketch": "InBatch", "items": [{"kind": "circle", "center": [0, 0], "radius": 3}]}}]})
        self.assertNotIn("health", out)
        self.assertIn("InBatch: ", out["results"][1]["result"]["health"]["verdict"])

    def test_8_a_sketch_recomputed_without_news_is_not_read_out_again(self):
        # Base has freedom left (test 1). Recomputed by a call that is not a
        # sketch tool's, reading as before: nothing said of it (live, a
        # spreadsheet's edits repeated the sketches using the sheet).
        sk = self.session.doc.getObjectsByLabel("Base")[0]
        self.assertGreater(sk.DoF, 0)
        sk.touch()
        out = self.ok("recompute", {})
        self.assertNotIn("Base:", (out.get("health") or {}).get("verdict", ""))
        # a sketch tool's own call still reads it out
        out = self.ok("sketch_add", {"sketch": "Base", "items": [{"kind": "circle", "center": [5, 0], "radius": 2}]})
        self.assertIn("Base: ", out["health"]["verdict"])


if __name__ == "__main__":
    unittest.main()
