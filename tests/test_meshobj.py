# SPDX-License-Identifier: LGPL-2.1-or-later
# Document meshes: made, evaluated, changed, cut, segmented.
import unittest

from _fc import HAVE, caller, server

try:
    import Mesh  # noqa: F401
    import MeshPart  # noqa: F401

    HAVE_M = HAVE
except ImportError:
    HAVE_M = False


@unittest.skipUnless(HAVE_M, "FreeCAD with Mesh and MeshPart is not importable here")
class MeshObj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        cls.call("part_primitive", {"kind": "box", "size": [40, 30, 20], "name": "Brick"})
        cls.call("part_primitive", {"kind": "sphere", "radius": 12, "at": [40, 15, 20], "name": "Ball"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def test_1_make_and_evaluate(self):
        b = self.ok("meshobj_from_shape", {"body": "Brick", "method": "mefisto", "maxLength": 3})
        self.assertTrue(b["solid"])
        self.ok("meshobj_from_shape", {"body": "Ball", "deflection": 0.05})
        self.assertEqual(self.ok("meshobj_info", {"mesh": "Brick mesh"})["verdict"], "clean")

    def test_2_boolean_and_shape(self):
        d = self.ok("meshobj_boolean", {"a": "Brick mesh", "b": "Ball mesh", "op": "difference"})
        self.assertTrue(d["solid"])
        self.assertIn("Agent Link's boolean", d["how"])
        self.assertAlmostEqual(d["volume"], 24000 - 7238.23 / 4, delta=40)
        t = self.ok("meshobj_trim", {"mesh": "Ball mesh", "at": [40, 15, 20], "normal": [0, 0, 1], "close": True, "copy": True})
        self.assertAlmostEqual(t["volume"], 7195.55 / 2, delta=20)
        # One piece, one flat cap: hemisphere 904.8 + disc 452.4 (it came back
        # with 2 components and three caps' worth of area).
        self.assertEqual(t["components"], 1)
        self.assertAlmostEqual(t["area"], 2 * 3.14159 * 144 + 3.14159 * 144, delta=15)
        info = self.ok("meshobj_info", {"mesh": t["mesh"]})
        self.assertEqual(info["problems"], [], info)
        o = self.ok("meshobj_trim", {"mesh": "Ball mesh", "at": [40, 15, 20], "normal": [0, 0, 1], "copy": True})
        self.assertEqual(o["components"], 1)
        self.assertEqual(self.ok("meshobj_boundary", {"mesh": o["mesh"]})["loops"], 1)
        seg = self.ok("meshobj_segments", {"mesh": "Brick mesh"})
        self.assertEqual(seg["segments"], 6)

    def test_3_read(self):
        c = self.ok("meshobj_curvature", {"mesh": "Ball mesh"})
        self.assertAlmostEqual(c["medianRadius"], 12, delta=0.2)
        s = self.ok("meshobj_sections", {"mesh": "Ball mesh", "count": 1})
        self.assertAlmostEqual(s["slices"][0]["length"], 2 * 3.14159 * 12, delta=1.0)

    def test_4_edit_on_a_copy(self):
        b = self.ok("meshobj_edit", {"action": "begin", "mesh": "Ball mesh"})
        n0 = b["facets"]
        p = self.ok("meshobj_trim", {"mesh": "Ball mesh", "at": [40, 15, 20], "normal": [0, 0, 1], "preview": True})
        self.assertTrue(p["preview"])
        self.assertGreater(p["wouldRemove"], 0)
        self.ok("meshobj_trim", {"mesh": "Ball mesh", "at": [40, 15, 20], "normal": [0, 0, 1]})
        st = self.ok("meshobj_edit", {"action": "state"})
        self.assertEqual(st["editing"][0]["mesh"], "Ball mesh")
        # The original is untouched until use.
        orig = next(o for o in self.session.doc.Objects if o.Label == "Ball mesh")
        self.assertEqual(orig.Mesh.CountFacets, n0)
        u = self.ok("meshobj_edit", {"action": "use", "mesh": "Ball mesh"})
        self.assertLess(u["now"]["facets"], n0)
        self.assertEqual(orig.Mesh.CountFacets, u["now"]["facets"])
        self.assertFalse(any("(editing)" in o.Label for o in self.session.doc.Objects))
        self.ok("meshobj_edit", {"action": "begin", "mesh": "Brick mesh"})
        self.ok("meshobj_edit", {"action": "discard"})
        self.assertEqual(self.ok("meshobj_edit", {})["editing"], [])


    def test_5_repair_never_leaves_it_worse(self):
        # A closed box with a point on an edge: one side's edge a-b split at
        # its middle m on the neighbouring face, closed by a flat triangle
        # (b, a, m). FreeCAD's needle and degenerate fixes delete facets and
        # opened such a mesh (a closed 5,212-triangle cutter came back open);
        # a step that leaves more open or overloaded edges is undone.
        P = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
        quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        tris = []
        for q in quads:
            tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
        # edge 0-1 (the bottom face walks it 1->0, the front face 0->1):
        # split on the bottom at m, closed by the flat (0, m, 1)
        P.append((5, 0, 0))
        m = 8
        tris.remove((0, 2, 1))
        tris += [(0, 2, m), (m, 2, 1), (0, m, 1)]
        mesh = Mesh.Mesh([[P[i] for i in t] for t in tris])
        o = self.session.doc.addObject("Mesh::Feature", "Tee")
        o.Label = "Tee mesh"
        o.Mesh = mesh
        self.session.doc.recompute()
        r = self.ok("meshobj_repair", {"mesh": "Tee mesh", "copy": True})
        before = r.get("before", {}).get("edges") or r.get("edges")
        self.assertLessEqual(r["edges"]["open"], before["open"], r)
        self.assertLessEqual(r["edges"]["overloaded"], before["overloaded"], r)
        if mesh.isSolid():
            self.assertTrue(r["solid"], r)
        # On a mesh made closed and clean, every default step keeps it so.
        b = self.ok("meshobj_repair", {"mesh": "Brick mesh", "copy": True})
        self.assertTrue(b["solid"], b)
        self.assertEqual(b["edges"], {"open": 0, "overloaded": 0})


if __name__ == "__main__":
    unittest.main()
