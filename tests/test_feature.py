# SPDX-License-Identifier: LGPL-2.1-or-later
# The PartDesign feature tools on a real FreeCAD: skipped where it cannot be imported.
import math
import unittest

from _fc import BEFORE_1_1, WHY_1_0
from _pd_base import HAVE, Base


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class FeatureTools(Base):
    def test_1_pad(self):
        self.ok("pd_body_new", {"name": "Block"})
        self.ok("sketch_new", {"plane": "XY", "name": "Base"})
        self.ok("sketch_add", {"sketch": "Base", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]})
        p = self.ok("pd_pad", {"sketch": "Base", "length": 10})
        self.assertAlmostEqual(p["volume"], 8000, delta=0.5)
        self.assertEqual(p["box"], [40, 20, 10])
        self.assertTrue(p["valid"])

    def test_2_pocket_on_a_face_found_by_query(self):
        sk = self.ok("sketch_new", {"face": {"at": [5, 5, 10], "normal": [0, 0, 1]}, "name": "Top"})
        self.assertEqual(sk["frame"]["origin"], [0, 0, 10])
        self.assertEqual(sk["frame"]["xAxis"], [1, 0, 0])
        self.ok("sketch_add", {"sketch": "Top", "items": [{"kind": "circle", "center": [10, 0], "radius": 3}]})
        p = self.ok("pd_pocket", {"sketch": "Top", "extent": "through_all"})
        self.assertAlmostEqual(p["volumeChange"], -math.pi * 9 * 10, delta=0.5)

    def test_3_pocket_that_cuts_nothing_is_refused(self):
        n = len(self.ok("feature_list")["features"])
        self.ok("sketch_new", {"face": {"at": [-5, -5, 10], "normal": [0, 0, 1]}, "name": "Away"})
        self.ok("sketch_add", {"sketch": "Away", "items": [{"kind": "circle", "center": [-10, 0], "radius": 2}]})
        self.refused("pd_pocket", {"sketch": "Away", "length": 5, "reversed": True})
        names = [f["name"] for f in self.ok("feature_list")["features"]]
        self.assertEqual(len(names), n + 1, names)  # the sketch stays, the pocket does not
        self.assertFalse([x for x in names if x.startswith("Pocket") and x != "Pocket"], names)

    def test_4_fillet_by_a_point_near_the_edge(self):
        before = self.ok("feature_list")["volume"]
        f = self.ok("pd_fillet", {"edges": [{"near": [20, 10, 5]}], "radius": 2})
        self.assertAlmostEqual(f["volumeChange"], -(4 - math.pi) * 10, delta=0.2)
        self.assertLess(f["volume"], before)
        self.refused("pd_fillet", {"edges": [{"near": [100, 100, 100]}], "radius": 1})

    def test_5_threaded_hole_and_pattern(self):
        self.ok("sketch_new", {"face": {"at": [0, 0, 10], "normal": [0, 0, 1]}, "name": "Holes"})
        self.ok("sketch_add", {"sketch": "Holes", "items": [{"kind": "circle", "center": [-10, 0], "radius": 2}]})
        h = self.ok("pd_hole", {"sketch": "Holes", "thread": "M5", "depth": "through"})
        self.assertLess(h["volumeChange"], -100)
        self.assertIn("M5", h["thread"])
        p = self.ok("pd_linear_pattern", {"features": ["Pocket"], "direction": "y", "occurrences": 2, "spacing": 6})
        self.assertLess(p["volumeChange"], -50)

    def test_6_edit_suppress_remove(self):
        e = self.ok("feature_edit", {"feature": "Pad", "set": {"Length": 12}})
        self.assertEqual(e["box"][2], 12)
        # Where the release renamed the fillet's edges, they were found again.
        if "refsFound" in e:
            print("\nrefs found again:", e["refsFound"])
        self.refused("feature_edit", {"feature": "Pad", "set": {"Nonsense": 1}})
        listing = self.ok("feature_list")
        pad = next(f for f in listing["features"] if f["name"] == "Pad")
        self.assertEqual(pad["length"], 12)
        err, s = self.call("feature_suppress", {"feature": "Fillet"})
        if err:
            self.assertEqual(s["error"]["code"], "unavailable")
        else:
            self.assertGreater(s["volumeChange"], 0)
            self.ok("feature_suppress", {"feature": "Fillet", "suppressed": False})
        r = self.ok("feature_remove", {"feature": "LinearPattern"})
        self.assertGreater(r["volumeChange"], 0)

    def test_7_shell(self):
        self.ok("pd_body_new", {"name": "Tray"})
        self.ok("sketch_new", {"body": "Tray", "plane": "XY", "name": "TrayBase"})
        self.ok("sketch_add", {"sketch": "TrayBase", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]})
        self.ok("pd_pad", {"body": "Tray", "sketch": "TrayBase", "length": 10})
        t = self.ok("pd_thickness", {"body": "Tray", "faces": [{"at": [0, 0, 10], "normal": [0, 0, 1]}], "thickness": 2})
        self.assertAlmostEqual(t["volume"], 8000 - 36 * 16 * 8, delta=1)

    def test_8_revolution_and_loft(self):
        self.ok("pd_body_new", {"name": "Ring"})
        self.ok("sketch_new", {"body": "Ring", "plane": "XZ", "name": "RingProfile"})
        self.ok("sketch_add", {"sketch": "RingProfile", "items": [{"kind": "rectangle", "corner": [5, 0], "size": [5, 10]}]})
        r = self.ok("pd_revolution", {"body": "Ring", "sketch": "RingProfile", "axis": "V_Axis"})
        self.assertAlmostEqual(r["volume"], math.pi * (100 - 25) * 10, delta=1)

        self.ok("pd_body_new", {"name": "Frustum"})
        self.ok("sketch_new", {"body": "Frustum", "plane": "XY", "name": "Bottom"})
        self.ok("sketch_add", {"sketch": "Bottom", "items": [{"kind": "rectangle", "center": [0, 0], "size": [20, 20]}]})
        d = self.ok("pd_datum_plane", {"body": "Frustum", "on": "XY", "offset": 20, "name": "Up"})
        self.assertEqual(d["origin"], [0, 0, 20])
        self.ok("sketch_new", {"body": "Frustum", "plane": "Up", "name": "TopSec"})
        self.ok("sketch_add", {"sketch": "TopSec", "items": [{"kind": "rectangle", "center": [0, 0], "size": [10, 10]}]})
        lo = self.ok("pd_loft", {"body": "Frustum", "profile": "Bottom", "sections": ["TopSec"], "ruled": True})
        self.assertAlmostEqual(lo["volume"], 20 / 3 * (400 + 100 + 200), delta=1)

    # ---- the hardening pass (16 Nov 2026): what FreeCAD 1.1's own source says ----

    @unittest.skipIf(BEFORE_1_1, WHY_1_0 + " (PartDesign Draft's pull direction)")
    def test_9a_two_sides_and_a_draft_from_a_face(self):
        self.ok("pd_body_new", {"name": "Hard"})
        self.ok("sketch_new", {"body": "Hard", "plane": "XY", "name": "HBase"})
        self.ok("sketch_add", {"sketch": "HBase", "items": [{"kind": "rectangle", "center": [0, 0], "size": [30, 20]}]})
        # two sides without the second length is refused, saying which input
        e = self.refused("pd_pad", {"body": "Hard", "sketch": "HBase", "length": 6, "sides": "two"})
        self.assertIn("length2", e["message"])
        e = self.refused("pd_pad", {"body": "Hard", "sketch": "HBase", "extent": "through_all"})
        self.assertIn("up_to_last", e["message"])
        p = self.ok("pd_pad", {"body": "Hard", "sketch": "HBase", "length": 6, "length2": 4, "sides": "two"})
        self.assertAlmostEqual(p["volume"], 6000, delta=0.5)
        self.assertEqual(p["box"], [30, 20, 10])
        type(self).hard_pad = p["feature"]
        # The neutral plane as a face of the body: it is read before the
        # draft becomes the tip (it used to be read after, and found no solid).
        d = self.ok("pd_draft", {"body": "Hard", "faces": [{"at": [15, 0, 1], "normal": [1, 0, 0]}], "angle": 5,
                                 "neutral": {"at": [10, 5, -4], "normal": [0, 0, -1]}, "pull": "z"})
        self.assertAlmostEqual(abs(d["volumeChange"]), 0.5 * 10 * 10 * math.tan(math.radians(5)) * 20, delta=0.5)
        type(self).hard_draft = d["feature"]
        # the pad's face is the draft's: removing the pad is refused, naming the user
        e = self.refused("feature_remove", {"body": "Hard", "feature": p["feature"]})
        self.assertIn("is used by", e["message"])
        self.assertIn(d["feature"], e["message"])

    @unittest.skipIf(BEFORE_1_1, WHY_1_0 + " (needs test_9a's body)")
    def test_9b_through_all_both_ways(self):
        self.ok("sketch_new", {"body": "Hard", "plane": "XY", "name": "HCut"})
        self.ok("sketch_add", {"sketch": "HCut", "items": [{"kind": "circle", "center": [0, 0], "radius": 2}]})
        err, c = self.call("pd_pocket", {"body": "Hard", "sketch": "HCut", "extent": "through_all", "sides": "two"})
        if err:
            # before 1.1 two sides exist for a length only: said so, nothing kept
            self.assertEqual(c["error"]["code"], "unavailable", c)
            c = self.ok("pd_pocket", {"body": "Hard", "sketch": "HCut", "extent": "through_all", "sides": "symmetric"})
        self.assertAlmostEqual(c["volumeChange"], -math.pi * 4 * 10, delta=0.5)
        type(self).hard_cut = c["feature"]

    @unittest.skipIf(BEFORE_1_1, WHY_1_0 + " (needs test_9a's body)")
    def test_9c_fine_thread_and_holes_at_points(self):
        self.ok("sketch_new", {"body": "Hard", "face": {"at": [10, 5, 6], "normal": [0, 0, 1]}, "name": "HHoles"})
        self.ok("sketch_add", {"sketch": "HHoles", "items": [{"kind": "circle", "center": [10, 5], "radius": 1}, {"kind": "point", "at": [-10, 5]},
                                                             {"kind": "circle", "center": [-10, -5], "radius": 1, "construction": True}]})
        e = self.refused("pd_hole", {"body": "Hard", "sketch": "HHoles", "thread": "M8x7"})
        self.assertIn("M8", e["message"])
        # "M8x1" is FreeCAD's "M8x1.0" (ISO fine)
        h = self.ok("pd_hole", {"body": "Hard", "sketch": "HHoles", "thread": "M8x1", "depth": 3})
        self.assertTrue(h["thread"].startswith("M8x1"), h)
        hole = self.session.doc.getObjectsByLabel(h["feature"])[0]
        # FreeCAD 1.1 drills at sketch points too (the Hole's BaseProfileType); never at construction geometry
        self.assertEqual(h["holes"], 2 if int(getattr(hole, "BaseProfileType", 6)) & 1 else 1)
        self.assertAlmostEqual(h["volumeChange"], -h["holes"] * math.pi * (h["diameter"] / 2) ** 2 * 3, delta=1.0)
        type(self).hard_hole = h["feature"]

    @unittest.skipIf(BEFORE_1_1, WHY_1_0 + " (needs test_9a's draft)")
    def test_9d_revolution_sides_and_the_tip(self):
        e = self.refused("pd_revolution", {"body": "Ring", "sketch": "RingProfile", "sides": "two"})
        self.assertIn("TwoAngles", e["message"])
        listing = self.ok("feature_list", {"body": "Hard"})
        self.assertEqual(listing["tip"], self.hard_hole)
        # a sketch is no tip: the solid feature before it, as the window's Set tip does
        t = self.ok("pd_tip", {"body": "Hard", "feature": "HCut"})
        self.assertEqual(t["tip"], self.hard_draft)
        self.assertEqual(t["afterTip"], [self.hard_cut, self.hard_hole])
        # the body as it was after the draft: the pocket and the holes are left out
        self.assertAlmostEqual(abs(t["volume"] - 6000), 0.5 * 10 * 10 * math.tan(math.radians(5)) * 20, delta=0.5)
        self.refused("pd_tip", {"body": "Hard", "feature": "HBase"})
        back = self.ok("pd_tip", {"body": "Hard", "feature": self.hard_hole})
        self.assertNotIn("afterTip", back)
        self.assertAlmostEqual(back["volume"], listing["volume"], delta=0.01)

    def test_9e_revolve_about_a_construction_line(self):
        # A sketch's construction line is FreeCAD's "Axis0" (its own count),
        # not "Edge1" of the sketch's shape, which is the profile's first edge.
        self.ok("pd_body_new", {"name": "Off"})
        self.ok("sketch_new", {"body": "Off", "plane": "XZ", "name": "OffProfile"})
        self.ok("sketch_add", {"sketch": "OffProfile", "items": [{"kind": "line", "from": [120, 0], "to": [120, 10], "construction": True},
                                                                 {"kind": "rectangle", "corner": [130, 0], "size": [4, 6]}]})
        r = self.ok("pd_revolution", {"body": "Off", "sketch": "OffProfile", "axis": 0})
        self.assertAlmostEqual(r["volume"], math.pi * (14 ** 2 - 10 ** 2) * 6, delta=1)
        self.assertEqual(r["box"], [28, 28, 6])
        e = self.refused("pd_revolution", {"body": "Off", "sketch": "OffProfile", "axis": 99})
        self.assertIn("geometry 99", e["message"])


if __name__ == "__main__":
    unittest.main()
