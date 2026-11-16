# SPDX-License-Identifier: LGPL-2.1-or-later
# The Part workbench hardening pass (16 Nov 2026): what was fixed against
# FreeCAD 1.1's own source, each pinned on a real FreeCAD. Primitives' limits
# (PrimitiveFeature.cpp), revolve and shell limits, slices along any normal
# and their material area, attachment modes that exist (Attacher.cpp),
# compound filters' real FilterType names (CompoundTools/CompoundFilter.py),
# BOPTools features made in the session's document, ruled surfaces between
# single edges.
import math
import unittest

from _fc import HAVE, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class PartHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def refused(self, n, a=None):
        err, out = self.call(n, a)
        self.assertTrue(err, f"{n} should refuse: {out}")
        return out["error"]["message"]

    def obj(self, label):
        return self.session.doc.getObjectsByLabel(label)[0]

    def test_1_cone_from_a_point(self):
        # Part::Cone refuses only a radius under 0: the base may be the point.
        r = self.ok("part_primitive", {"kind": "cone", "radius": 0, "radius2": 4, "height": 6, "name": "H cone"})
        self.assertAlmostEqual(r["volume"], math.pi * 16 * 6 / 3, delta=0.05)
        self.assertIn("cylinder", self.refused("part_primitive", {"kind": "cone", "radius": 3, "radius2": 3, "height": 6}))
        self.assertIn("ymin", self.refused("part_primitive", {"kind": "wedge", "wedge": {"xmax": -1}}))

    def test_2_revolve_and_shell_limits(self):
        prof = {"points": [[5, 0, 0], [10, 0, 0], [10, 0, 10], [5, 0, 10]]}
        self.assertIn("angle", self.refused("part_revolve", {"profile": prof, "angle": 0}))
        self.assertIn("angle", self.refused("part_revolve", {"profile": prof, "angle": 400}))
        half = self.ok("part_revolve", {"profile": prof, "angle": 180, "name": "H half ring"})
        self.assertAlmostEqual(half["volume"], math.pi * (100 - 25) * 10 / 2, delta=0.5)
        self.ok("part_primitive", {"kind": "box", "size": [20, 20, 20], "at": [100, 0, 0], "name": "H cup"})
        # At or under twice its tolerance OCC hands the shape back unchanged.
        self.assertIn("thickness", self.refused("part_thickness", {"body": "H cup", "thickness": 0.001, "query": {"normal": "+z"}}))
        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "at": [200, 0, 0], "name": "H pair"})
        two = self.ok("part_transform", {"op": "linear", "body": "H pair", "count": 2, "step": [20, 0, 0], "fuse": False})
        self.assertEqual(two["solids"], 2)
        # Part::Thickness: "Source shape is not single solid."
        self.assertIn("part_compound", self.refused("part_thickness", {"body": "H pair", "thickness": 1, "query": {"normal": "+z"}}))

    def test_3_slices(self):
        self.ok("part_primitive", {"kind": "tube", "radius": 10, "radius2": 6, "height": 20, "at": [300, 0, 0], "name": "H tube"})
        s = self.ok("part_slices", {"body": "H tube", "count": 1})
        self.assertEqual(s["slices"][0]["wires"], 2)
        # The ring, not the two discs added.
        self.assertAlmostEqual(s["slices"][0]["area"], math.pi * (100 - 36), delta=0.05)
        self.ok("part_primitive", {"kind": "box", "size": [10, 20, 30], "name": "H brick"})
        s = self.ok("part_slices", {"body": "H brick", "normal": [1, -1, 0], "count": 1})
        # Along (1, -1, 0) / sqrt 2 the box runs from -20 / sqrt 2 to 10 / sqrt 2.
        self.assertAlmostEqual(s["range"][0], -20 / math.sqrt(2), delta=0.002)
        self.assertAlmostEqual(s["range"][1], 10 / math.sqrt(2), delta=0.002)
        self.assertEqual(s["slices"][0]["wires"], 1)

    def test_4_attach_and_datums(self):
        import Part

        self.ok("part_primitive", {"kind": "box", "size": [20, 20, 10], "at": [0, 100, 0], "name": "H base"})
        self.ok("part_primitive", {"kind": "cylinder", "radius": 2, "height": 5, "name": "H peg"})
        base = self.obj("H base")
        top = next(i for i, f in enumerate(base.Shape.Faces, 1) if abs(f.CenterOfMass.z - 10) < 1e-6)
        r = self.ok("part_attach", {"body": "H peg", "to": f"H base.Face{top}", "offset": [3, 4, 0]})
        self.assertEqual(r["mode"], "FlatFace")
        self.assertAlmostEqual(r["placement"]["at"][2], 10.0, places=4)
        # A vertex takes Translate (ObjectXY reads the whole object's placement).
        r = self.ok("part_attach", {"body": "H peg", "to": "H base.Vertex1"})
        self.assertEqual(r["mode"], "Translate")
        v = base.Shape.Vertexes[0].Point
        self.assertAlmostEqual(r["placement"]["at"][0], v.x, places=4)
        self.assertAlmostEqual(r["placement"]["at"][1], v.y, places=4)
        self.assertIn("FlatFace", self.refused("part_attach", {"body": "H peg", "to": f"H base.Face{top}", "mode": "NoSuchMode"}))
        # A whole object by name: its placement (ObjectXY).
        r = self.ok("part_attach", {"body": "H peg", "to": "H base"})
        self.assertEqual(r["mode"], "ObjectXY")
        self.assertAlmostEqual(r["placement"]["at"][1], 100.0, places=4)

        self.ok("part_primitive", {"kind": "cylinder", "radius": 5, "height": 10, "at": [50, 100, 0], "name": "H drum"})
        drum = self.obj("H drum")
        rim = next(i for i, e in enumerate(drum.Shape.Edges, 1) if isinstance(e.Curve, Part.Circle) and abs(e.CenterOfMass.z - 10) < 1e-6)
        flat = next(i for i, f in enumerate(drum.Shape.Faces, 1) if isinstance(f.Surface, Part.Plane) and abs(f.CenterOfMass.z - 10) < 1e-6)
        line = self.ok("part_datum", {"kind": "line", "to": f"H drum.Edge{rim}", "name": "H axis"})
        self.assertEqual(line["mode"], "AxisOfCurvature")
        pt = self.ok("part_datum", {"kind": "point", "to": f"H drum.Edge{rim}", "name": "H centre"})
        self.assertEqual(pt["mode"], "CenterOfCurvature")
        self.assertAlmostEqual(pt["placement"]["at"][0], 50.0, places=3)
        self.assertAlmostEqual(pt["placement"]["at"][2], 10.0, places=3)
        # "NormalToSurface" is no FreeCAD mode, and FaceNormal takes a face and a vertex.
        before = len(self.session.doc.Objects)
        self.assertIn("FaceNormal", self.refused("part_datum", {"kind": "line", "to": f"H drum.Face{flat}"}))
        self.assertEqual(len(self.session.doc.Objects), before)
        pl = self.ok("part_datum", {"kind": "plane", "to": f"H drum.Face{flat}", "name": "H lid plane"})
        self.assertEqual(pl["mode"], "FlatFace")
        self.assertAlmostEqual(pl["placement"]["at"][2], 10.0, places=3)

    def test_5_compound_filters(self):
        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "at": [0, 300, 0], "name": "F a"})
        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "at": [20, 300, 0], "name": "F b"})
        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "at": [40, 300, 0], "name": "F c"})
        self.ok("part_compound", {"bodies": ["F a", "F b", "F c"], "name": "F comp"})
        self.ok("part_primitive", {"kind": "box", "size": [8, 5, 5], "at": [-4, 300, 0], "name": "F stencil"})
        hit = self.ok("compound_filter", {"compound": "F comp", "keep": "collision-pass", "stencil": "F stencil", "name": "F hit"})
        self.assertEqual(hit["kept"], 1)
        # collision-fail is FreeCAD's collision-pass inverted (no FilterType of that name).
        miss = self.ok("compound_filter", {"compound": "F comp", "keep": "collision-fail", "stencil": "F stencil", "name": "F miss"})
        self.assertEqual(miss["kept"], 2)
        f = self.obj("F miss")
        self.assertEqual((f.FilterType, f.Invert), ("collision-pass", True))
        self.assertEqual(f.Document.Name, self.session.doc.Name)
        # window-distance: pieces by their distance from the stencil, as a percent of the farthest.
        far = self.ok("compound_filter", {"compound": "F comp", "keep": "window-distance", "stencil": "F stencil", "from": 90, "to": 100, "name": "F far"})
        self.assertEqual(far["kept"], 1)
        self.assertEqual(self.obj("F far").FilterType, "window-distance")
        self.assertIn("0 … 2", self.refused("compound_filter", {"compound": "F comp", "items": [3]}))
        self.assertIn("stencil", self.refused("compound_filter", {"compound": "F comp", "keep": "window-distance"}))

    def test_6_bop_features_in_the_sessions_document(self):
        import FreeCAD

        self.ok("part_primitive", {"kind": "box", "size": [40, 30, 20], "at": [0, 400, 0], "name": "S brick"})
        self.ok("part_wire", {"kind": "plane", "length": 80, "width": 80, "at": [-20, 380, 10], "name": "S plane"})
        self.ok("part_wire", {"kind": "plane", "length": 10, "width": 10, "at": [5, 405, 10], "name": "S small"})
        # Another document active: BOPTools' own make* would add there.
        other = FreeCAD.newDocument("HardeningOther")
        try:
            FreeCAD.setActiveDocument(other.Name)
            r = self.ok("part_split", {"mode": "slice", "bodies": ["S brick"], "tools": ["S plane"], "name": "S cut"})
            self.assertEqual(r["pieces"], 2)
            self.assertEqual(len(other.Objects), 0)
            self.assertEqual(self.obj(r["object"]).Document.Name, self.session.doc.Name)
            # A plane that does not pass right through cuts nothing: said.
            r = self.ok("part_split", {"mode": "slice", "bodies": ["S brick"], "tools": ["S small"], "name": "S nocut"})
            self.assertEqual(r["pieces"], 1)
            self.assertIn("Not cut", r["note"])
            self.assertIn("part_extract", self.refused("part_split", {"mode": "slice", "bodies": ["S brick"], "tools": ["S brick.Face1"]}))
        finally:
            FreeCAD.closeDocument(other.Name)
            FreeCAD.setActiveDocument(self.session.doc.Name)

    def test_7_ruled_between_an_edge_and_a_wire(self):
        self.ok("part_primitive", {"kind": "box", "size": [20, 20, 10], "at": [0, 500, 0], "name": "R box"})
        self.ok("part_wire", {"kind": "line", "from": [0, 500, 30], "to": [20, 505, 30], "name": "R line"})
        r = self.ok("part_ruled", {"a": "R line", "b": "R box.Edge1", "name": "R sheet"})
        self.assertEqual(r["faces"], 1)
        o = self.obj("R sheet")
        self.assertEqual(list(o.Curve2[1]), ["Edge1"])
        self.assertIn("Edge3", self.refused("part_ruled", {"a": "R line", "b": "R box.Face1"}))


if __name__ == "__main__":
    unittest.main()
