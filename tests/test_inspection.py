# SPDX-License-Identifier: LGPL-2.1-or-later
# The inspection tools on a real FreeCAD: skipped where it cannot be imported.
import os
import unittest

from _fc import HAVE, add_body, caller, server

try:
    import Inspection  # noqa: F401

    HAVE_I = HAVE
except ImportError:
    HAVE_I = False


@unittest.skipUnless(HAVE_I, "FreeCAD with Inspection is not importable here")
class InspectionTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        add_body(cls.session, "Nominal", Part.makeBox(60, 40, 8))
        add_body(cls.session, "Made", Part.makeBox(60.3, 40, 8.1))

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def test_1_run(self):
        r = self.ok("insp_run", {"actual": "Made", "nominals": ["Nominal"], "search_radius": 1, "tolerance": 0.2, "deflection": 0.5})
        self.assertGreater(r["points"], 0)
        self.assertAlmostEqual(r["max"], 0.3, delta=0.02)
        self.assertEqual(r["verdict"], "fail")
        self.assertTrue(r["worst"])
        self.assertAlmostEqual(r["worst"][0]["distance"], 0.3, delta=0.02)

    def test_2_update_and_export(self):
        r = self.ok("insp_update", {"tolerance": 0.35})
        self.assertEqual(r["verdict"], "pass")
        e = self.ok("insp_export", {})
        self.assertTrue(os.path.isfile(e["files"]["csv"]["path"]))
        self.assertEqual(self.ok("insp_list")["inspections"][0]["verdict"], "pass")

    def test_3_refusals(self):
        err, _ = self.call("insp_run", {"actual": "Made", "nominals": []})
        self.assertTrue(err)
        err, _ = self.call("insp_run", {"actual": "Made", "nominals": ["Nominal"], "search_radius": 0.1, "tolerance": 0.5})
        self.assertTrue(err)

    def test_4_moved_copy_and_update(self):
        # A copy moved 0.5 mm along x against the original: the face ahead
        # reads +0.5 (outside the solid nominal), the one behind -0.5.
        import FreeCAD
        import Part

        add_body(self.session, "Shifted", Part.makeBox(60, 40, 8, FreeCAD.Vector(0.5, 0, 0)))
        r = self.ok("insp_run", {"actual": "Shifted", "nominals": ["Nominal"], "search_radius": 1, "deflection": 0.5, "name": "Shift check"})
        self.assertAlmostEqual(r["max"], 0.5, delta=0.02)
        self.assertAlmostEqual(r["min"], -0.5, delta=0.02)
        self.assertEqual(r["outOfReach"], 0)
        # nothing to change is refused; a tolerance past the radius is refused before anything is set
        err, out = self.call("insp_update", {"inspection": "Shift check"})
        self.assertTrue(err, out)
        err, out = self.call("insp_update", {"inspection": "Shift check", "tolerance": 2})
        self.assertTrue(err, out)
        self.assertNotIn("verdict", self.ok("insp_read", {"inspection": "Shift check"}))
        # an inspection made without Agent Link's tolerance properties takes one
        f = next(o for o in self.session.doc.Objects if o.Label == "Shift check")
        for p in ("ToleranceLow", "ToleranceHigh"):
            f.removeProperty(p)
        r = self.ok("insp_update", {"inspection": "Shift check", "tolerance": 0.6})
        self.assertEqual(r["verdict"], "pass")
        faces = self.ok("insp_faces", {"inspection": "Shift check"})
        self.assertTrue(faces["faces"])


if __name__ == "__main__":
    unittest.main()
