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


@unittest.skipUnless(HAVE_M, "FreeCAD with Mesh and MeshPart is not importable here")
class MeshHardening(unittest.TestCase):
    """The hardening pass (16 Nov 2026), written from FreeCAD 1.1's source
    (Mesh.cpp, MeshPyImp.cpp, BuildRegularGeoms.py, AppMeshPartPy.cpp)."""

    @classmethod
    def setUpClass(cls):
        import FreeCAD

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("MeshHardening")
        cls.session.switch(FreeCAD.ActiveDocument)
        cls.call("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Cube"})
        cls.call("part_primitive", {"kind": "sphere", "radius": 10, "at": [50, 0, 0], "name": "Globe"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def refused(self, n, a=None):
        err, out = self.call(n, a)
        self.assertTrue(err, f"{n}: {out}")
        return str(out)

    def obj(self, label):
        return next(o for o in self.session.doc.Objects if o.Label == label)

    def test_1_known_counts(self):
        import math

        c = self.ok("meshobj_from_shape", {"body": "Cube"})
        # Two triangles a flat face, points shared: 8 and 12 at any deflection.
        self.assertEqual((c["points"], c["facets"]), (8, 12))
        self.assertTrue(c["solid"])
        self.assertAlmostEqual(c["volume"], 1000, places=3)
        self.assertAlmostEqual(c["area"], 600, places=3)
        full = 4 / 3 * math.pi * 1000
        coarse = self.ok("meshobj_from_shape", {"body": "Globe", "deflection": 0.5, "angle": 30, "name": "Globe coarse"})
        fine = self.ok("meshobj_from_shape", {"body": "Globe", "deflection": 0.01, "angle": 5, "name": "Globe fine"})
        # Inscribed triangles: under the true volume, closer as they shrink.
        self.assertLess(coarse["volume"], fine["volume"])
        self.assertLess(fine["volume"], full)
        self.assertGreater(fine["volume"], full * 0.99)
        self.assertTrue(fine["solid"])
        self.assertIn("deflection", self.refused("meshobj_from_shape", {"body": "Cube", "deflection": 0}))
        self.assertIn("Cube", self.refused("meshobj_from_shape", {"body": "Nope"}))

    def test_2_refine_is_three_not_four(self):
        r = self.ok("meshobj_refine", {"mesh": "Cube mesh", "copy": True, "name": "Cube fine"})
        # a point in the middle of each triangle: three for one (FreeCAD skips a deformed triangle)
        self.assertGreater(r["facets"], 12)
        self.assertLessEqual(r["facets"], 36)
        self.assertAlmostEqual(r["volume"], 1000, places=2)

    def test_3_placed_meshes(self):
        import FreeCAD

        self.ok("meshobj_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Placed"})
        o = self.obj("Placed")
        o.Placement = FreeCAD.Placement(FreeCAD.Vector(100, 0, 0), FreeCAD.Rotation())
        self.session.doc.recompute()
        # It stands at x 100 … 110. A quarter turn about the document's z then 5 up:
        # x -10 … 0, y 100 … 110, z 5 … 15 (the turn was made before the placement: x 90 … 100).
        self.ok("meshobj_transform", {"mesh": "Placed", "rotate": {"axis": [0, 0, 1], "angle": 90}, "move": [0, 0, 5]})
        bb = self.obj("Placed").Mesh.BoundBox
        for got, want in zip((bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), (-10, 0, 100, 110, 5, 15)):
            self.assertAlmostEqual(got, want, places=3)
        self.assertGreater(self.obj("Placed").Mesh.Volume, 0)
        # Mirrored: still facing out.
        m = self.ok("meshobj_transform", {"mesh": "Placed", "mirror": "x", "copy": True, "name": "Placed mirror"})
        self.assertAlmostEqual(m["volume"], 1000, places=2)
        self.assertGreater(self.obj("Placed mirror").Mesh.Volume, 0)
        self.assertAlmostEqual(self.obj("Placed mirror").Mesh.BoundBox.XMax, 10, places=3)
        # Merged where they stand: the cube at the origin and the placed one.
        mg = self.ok("meshobj_merge", {"meshes": ["Cube mesh", "Placed"], "name": "Both"})
        self.assertEqual(mg["components"], 2)
        bb = self.obj("Both").Mesh.BoundBox
        self.assertAlmostEqual(bb.YMax, 110, places=3)
        self.assertAlmostEqual(bb.XMin, -10, places=3)
        self.assertIn("One or more", self.refused("meshobj_transform", {"mesh": "Placed"}))
        self.assertIn("mirror", self.refused("meshobj_transform", {"mesh": "Placed", "mirror": "w"}))

    def test_4_primitives(self):
        t = self.ok("meshobj_primitive", {"kind": "torus", "radius": 10, "radius2": 2, "at": [50, 100, 0], "name": "Ring"})
        c = self.obj("Ring").Mesh.BoundBox.Center
        # FreeCAD's builder stands the ring off the origin by its radius along its axis.
        for got, want in zip((c.x, c.y, c.z), (50, 100, 0)):
            self.assertAlmostEqual(got, want, delta=0.01)
        self.assertAlmostEqual(t["box"][2], 4.0, delta=0.01)
        big = self.ok("meshobj_primitive", {"kind": "cylinder", "radius": 100, "height": 1000, "name": "Mast"})
        self.assertEqual(big["box"], [200.0, 200.0, 1000.0])
        self.assertLess(big["facets"], 20000)  # rings 25 mm apart, not 0.5
        self.assertTrue(big["solid"])
        self.assertEqual(self.ok("meshobj_primitive", {"kind": "box", "name": "Unit"})["facets"], 12)
        self.assertIn("radius", self.refused("meshobj_primitive", {"kind": "sphere", "radius": 0}))

    def test_5_sections_and_segments(self):
        self.ok("meshobj_primitive", {"kind": "box", "size": [10, 10, 10], "at": [0, 20, 0], "name": "Off"})
        # Along [1, -1, 0] the box reaches from -21.21 to -7.07: two slices at
        # thirds of that (they were both at the middle: the reach was read off two corners).
        s = self.ok("meshobj_sections", {"mesh": "Off", "normal": [1, -1, 0], "count": 2})
        ats = [x["at"] for x in s["slices"]]
        self.assertAlmostEqual(ats[0], -16.4992, places=3)
        self.assertAlmostEqual(ats[1], -11.7851, places=3)
        for sl in s["slices"]:  # each a 9.428 x 10 rectangle
            self.assertAlmostEqual(sl["length"], 2 * (9.4281 + 10), delta=0.05)
        self.assertIn("count", self.refused("meshobj_sections", {"mesh": "Off", "count": 0}))
        # Curvature segments: Mesh.getSegmentsByCurvature takes (max, min, tolerance, tolerance, facets);
        # the call passed a name first and always failed.
        fine = self.ok("meshobj_from_shape", {"body": "Cube", "method": "mefisto", "maxLength": 1, "name": "Cube even"})
        self.assertTrue(fine["solid"])
        seg = self.ok("meshobj_segments", {"mesh": "Cube even", "kind": "curvature", "minFacets": 10})
        self.assertGreaterEqual(seg["segments"], 1)
        pl = self.ok("meshobj_segments", {"mesh": "Cube even", "kind": "planar", "keep": True, "top": 2})
        self.assertEqual(pl["segments"], 6)
        self.assertEqual(len(pl["kept"]), 2)
        self.assertAlmostEqual(self.obj(pl["kept"][0]).Mesh.Area, pl["largest"][0]["area"], places=2)  # kept in the order listed

    def test_6_files_and_unwrap(self):
        import os

        e = self.ok("meshobj_export", {"mesh": "Cube mesh", "path": "cube.stl"})
        self.assertEqual(e["format"], "stl")
        self.assertEqual(e["bytes"], 84 + 50 * 12)  # binary STL: an 84-byte head and 50 bytes a triangle
        self.assertTrue(os.path.isfile(e["file"]))
        back = Mesh.Mesh(e["file"])
        self.assertEqual(back.CountFacets, 12)
        self.assertAlmostEqual(back.Volume, 1000, places=2)
        self.assertIn("stl", self.refused("meshobj_export", {"mesh": "Cube mesh", "path": "cube.step"}))
        # A mesh by its name reaches the unwrapping (it was refused as "has no shape").
        err, out = self.call("meshobj_unwrap", {"of": "Cube mesh"})
        self.assertTrue(err)
        self.assertNotIn("has no shape", str(out))
        self.assertTrue("closed mesh" in str(out) or "flatmesh" in str(out), out)
        whole = self.refused("meshobj_unwrap", {"of": "Cube"})
        self.assertTrue("Face" in whole or "flatmesh" in whole, whole)

    def test_7_split_guard_and_trim(self):
        self.assertIn("nothing", self.refused("meshobj_trim", {"mesh": "Cube mesh", "at": [0, 0, -5], "normal": [0, 0, 1], "copy": True}))
        self.assertIn("one piece", self.refused("meshobj_split", {"mesh": "Cube mesh"}))
        sp = self.ok("meshobj_split", {"mesh": "Both"})
        self.assertEqual(len(sp["pieces"]), 2)
        self.assertEqual(sp["facets"], [12, 12])

    def test_8_live_run_findings(self):
        # Trim counts what went, not the triangle count's difference: a cube cut in
        # half has 14 triangles where it had 12 (the reply said removed -2).
        self.ok("meshobj_primitive", {"kind": "box", "size": [10, 10, 10], "at": [200, 0, 0], "name": "L cube"})
        p = self.ok("meshobj_trim", {"mesh": "L cube", "at": [0, 0, 5], "normal": [0, 0, 1], "preview": True})
        self.assertEqual((p["wouldRemove"], p["wouldCut"]), (2, 8))
        t = self.ok("meshobj_trim", {"mesh": "L cube", "at": [0, 0, 5], "normal": [0, 0, 1], "copy": True, "name": "L half"})
        self.assertEqual((t["removed"], t["cut"]), (2, 8))
        self.assertAlmostEqual(t["area"], 300, delta=0.01)
        # A slice through a row of the mesh's own edges is one loop once round
        # (a sphere's equator came back 125.6 long for a 62.8 circle).
        self.ok("part_primitive", {"kind": "sphere", "radius": 10, "at": [250, 0, 0], "name": "L globe"})
        self.ok("meshobj_from_shape", {"body": "L globe", "deflection": 0.01, "angle": 5, "name": "L globe mesh"})
        sl = self.ok("meshobj_sections", {"mesh": "L globe mesh", "normal": [0, 0, 1], "at": [-5, 0, 5]})["slices"]
        for row, want in zip(sl, (54.41, 62.83, 54.41)):
            self.assertEqual(row["loops"], 1)
            self.assertAlmostEqual(row["length"], want, delta=0.3)
        # A line thrown onto the mesh keeps its length where a sample lands on a mesh
        # edge (6 mm over the cube's diagonal came back 16).
        self.ok("part_wire", {"kind": "line", "from": [202, 5, 20], "to": [208, 5, 20], "name": "L stripe"})
        pr = self.ok("meshobj_project", {"mesh": "L cube", "shape": "L stripe", "direction": [0, 0, -1]})
        self.assertAlmostEqual(pr["length"], 6.0, delta=0.01)
        # Smoothing a coarse mesh says how far it pulled it in.
        self.ok("meshobj_from_shape", {"body": "L globe", "deflection": 0.5, "angle": 30, "name": "L globe coarse"})
        sm = self.ok("meshobj_smooth", {"mesh": "L globe coarse", "method": "taubin", "iterations": 5, "copy": True})
        if abs(sm["volumeChange"]) > 0.02 * 4188.79:
            self.assertIn("volume changed", sm["warning"])
        else:
            self.assertNotIn("warning", sm)


if __name__ == "__main__":
    unittest.main()
