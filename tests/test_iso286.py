# SPDX-License-Identifier: LGPL-2.1-or-later
# ISO 286 limits against values from the standard's tables.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import iso286 as I  # noqa: E402


class Iso286(unittest.TestCase):
    def test_limits(self):
        cases = {
            (10, "H7"): (0.015, 0.0), (10, "g6"): (-0.005, -0.014), (25, "h6"): (0.0, -0.013),
            (20, "p6"): (0.035, 0.022), (6, "js6"): (0.004, -0.004), (50, "H8"): (0.039, 0.0),
            (50, "f7"): (-0.025, -0.050), (8, "k6"): (0.010, 0.001), (100, "n6"): (0.045, 0.023),
            (3, "H7"): (0.010, 0.0), (30, "G7"): (0.028, 0.007),
        }
        for (n, code), want in cases.items():
            got = I.limits(n, code)
            self.assertAlmostEqual(got[0], want[0], places=6, msg=f"{n} {code}")
            self.assertAlmostEqual(got[1], want[1], places=6, msg=f"{n} {code}")


    def test_refusals(self):
        for bad in ((10, "Q7"), (10, "H3"), (600, "H7"), (0, "h6")):
            with self.assertRaises(ValueError):
                I.limits(*bad)


class CoreFirst(unittest.TestCase):
    """TechDraw's own Hole/Shaft Fit first where it tables the code; this
    table where it does not, or where the two disagree (and said)."""

    def test_techdraw_when_it_agrees(self):
        up, lo = I.limits(10, "H7")
        self.assertEqual(I.limits_from(10, "H7", core=lambda n, c: (up, lo)), (up, lo, I.TECHDRAW))

    def test_own_where_techdraw_has_none(self):
        up, lo = I.limits(10, "js6")
        self.assertEqual(I.limits_from(10, "js6", core=lambda n, c: None), (up, lo, I.OWN))

    def test_techdraw_only(self):
        self.assertEqual(I.limits_from(10, "D10", core=lambda n, c: (0.098, 0.040)), (0.098, 0.040, I.TECHDRAW))

    def test_disagreement_said(self):
        up, lo, src = I.limits_from(10, "H7", core=lambda n, c: (0.020, 0.0))
        self.assertEqual((up, lo), I.limits(10, "H7"))
        self.assertIn("gave +0.02/0", src)

    def test_neither(self):
        with self.assertRaises(ValueError):
            I.limits_from(10, "Q7", core=lambda n, c: None)

    def test_techdraw_absent_here(self):
        """Without the window TechDraw's tools are not imported at all: their
        import pulls in FreeCADGui, which headless lacks addCommand and
        getMainWindow, and every later call that tries FreeCADGui broke."""
        try:
            import FreeCAD

            up = bool(getattr(FreeCAD, "GuiUp", False))
        except ImportError:
            up = False
        if up:
            self.skipTest("FreeCAD's window is up: TechDraw's tools may be here")
        had = "FreeCADGui" in sys.modules
        self.assertIsNone(I.techdraw_limits(10, "H7"))
        self.assertEqual("FreeCADGui" in sys.modules, had)
        self.assertNotIn("TechDrawTools", sys.modules)


if __name__ == "__main__":
    unittest.main()
