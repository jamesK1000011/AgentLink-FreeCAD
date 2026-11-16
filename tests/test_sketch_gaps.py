# SPDX-License-Identifier: LGPL-2.1-or-later
# The Sketcher commands that were window-only: arc slots, chamfers, group
# constraints (FreeCAD 1.2), text, internal geometry and axes alignment.
import math
import unittest

from _pd_base import HAVE, Base


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class SketchGaps(Base):
    def sketch(self, name):
        if not any(o.TypeId == "PartDesign::Body" for o in self.session.doc.Objects):
            self.ok("pd_body_new", {"name": "G body"})
        self.ok("sketch_new", {"plane": "XY", "name": name})

    def test_arc_slot_pads_to_its_area(self):
        self.sketch("G slot")
        self.ok("sketch_add", {"sketch": "G slot", "items": [{"kind": "arc_slot", "center": [0, 0], "radius": 20, "width": 6, "start": 0, "end": 90}]})
        st = self.ok("sketch_state", {"sketch": "G slot", "detail": False})
        self.assertTrue(st.get("readyForFeature", True), st)
        sk = self.session.doc.getObjectsByLabel("G slot")[0]
        import Part

        face = Part.Face(Part.Wire(Part.__sortEdges__(sk.Shape.Edges)))
        want = math.pi / 2 * 20 * 6 + math.pi * 9
        self.assertAlmostEqual(face.Area, want, delta=0.05)

    def test_chamfer_a_corner(self):
        self.sketch("G ch")
        self.ok("sketch_add", {"sketch": "G ch", "items": [{"kind": "polyline", "points": [[0, 0], [20, 0], [20, 10]]}]})
        r = self.ok("sketch_edit", {"sketch": "G ch", "fillet": {"at": [0, 2], "radius": 3, "chamfer": True}})
        self.assertIn("chamfer", r["done"][0])
        sk = self.session.doc.getObjectsByLabel("G ch")[0]
        self.assertEqual(type(sk.Geometry[-1]).__name__, "LineSegment")

    def test_axes_alignment_and_internal_geometry(self):
        self.sketch("G ax")
        self.ok("sketch_add", {"sketch": "G ax", "items": [{"kind": "rectangle", "center": [0, 0], "size": [10, 6]}, {"kind": "ellipse", "center": [30, 0], "major": 10, "minor": 4}]})
        sk = self.session.doc.getObjectsByLabel("G ax")[0]
        n_hv = sum(c.Type in ("Horizontal", "Vertical") for c in sk.Constraints)
        self.assertGreater(n_hv, 0)
        self.ok("sketch_edit", {"sketch": "G ax", "removeAxesAlignment": [0, 1, 2, 3]})
        self.assertLess(sum(c.Type in ("Horizontal", "Vertical") for c in sk.Constraints), n_hv)
        ell = next(i for i, g in enumerate(sk.Geometry) if type(g).__name__ == "Ellipse")
        internal = [i for i in range(len(sk.Geometry)) if i != ell and sk.getConstruction(i)]
        if internal:
            sk.delGeometries(internal)
        self.ok("sketch_edit", {"sketch": "G ax", "exposeInternal": [ell]})

    def test_group_and_text(self):
        self.sketch("G grp")
        self.ok("sketch_add", {"sketch": "G grp", "items": [{"kind": "circle", "center": [0, 0], "radius": 2}, {"kind": "circle", "center": [10, 0], "radius": 2}]})
        err, out = self.call("sketch_edit", {"sketch": "G grp", "group": [0, 1]})
        if err:
            self.assertEqual(out["error"]["code"], "unavailable")
        else:
            self.assertIn("grouped", out["done"][0])
        t = self.ok("sketch_edit", {"sketch": "G grp", "text": {"text": "AL", "at": [0, 10], "height": 5}})
        self.assertIn("text", t["done"][-1])
        sk = self.session.doc.getObjectsByLabel("G grp")[0]
        self.assertGreater(len(sk.Geometry), 4)


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class SketchHardening(Base):
    """What the hardening pass fixed against FreeCAD 1.1's own source."""

    def sketch(self, name):
        if not self.session.doc.getObjectsByLabel("H body"):
            self.ok("pd_body_new", {"name": "H body"})
        self.ok("sketch_new", {"body": "H body", "plane": "XY", "name": name})
        return self.session.doc.getObjectsByLabel(name)[0]

    def test_array_cols_run_along_x_and_rows_along_y(self):
        sk = self.sketch("H arr")
        self.ok("sketch_add", {"sketch": "H arr", "items": [{"kind": "circle", "center": [0, 0], "radius": 1}]})
        r = self.ok("sketch_array", {"sketch": "H arr", "geometry": [0], "rows": 2, "cols": 3, "spacing": [10, 5]})
        self.assertEqual(len(r["new"]), 5, r)
        got = sorted((round(g.Center.x, 3), round(g.Center.y, 3)) for g in sk.Geometry)
        self.assertEqual(got, sorted((10.0 * c, 5.0 * w) for c in range(3) for w in range(2)))
        e = self.refused("sketch_array", {"sketch": "H arr", "geometry": [0], "rows": 2, "cols": 1, "spacing": [10, 0]})
        self.assertIn("spacing", e["message"])

    def test_array_one_column_of_rows(self):
        sk = self.sketch("H arr1")
        self.ok("sketch_add", {"sketch": "H arr1", "items": [{"kind": "circle", "center": [0, 0], "radius": 1}]})
        self.ok("sketch_array", {"sketch": "H arr1", "geometry": [0], "rows": 3, "cols": 1, "spacing": [0, 4]})
        got = sorted((round(g.Center.x, 3), round(g.Center.y, 3)) for g in sk.Geometry)
        self.assertEqual(got, [(0.0, 0.0), (0.0, 4.0), (0.0, 8.0)])

    def test_extend_an_arc_by_mm_and_a_line_to_a_curve(self):
        sk = self.sketch("H ext")
        self.ok("sketch_add", {"sketch": "H ext", "items": [
            {"kind": "arc", "center": [0, 0], "radius": 10, "start": 0, "end": 90},
            {"kind": "line", "from": [30, 0], "to": [40, 0]},
            {"kind": "line", "from": [50, -5], "to": [50, 5]},
        ]})
        # A quarter of a 10 mm circle is 15.708 mm: as much again makes a half.
        self.ok("sketch_extend", {"sketch": "H ext", "geo": 0, "end": 2, "by": 5 * math.pi})
        self.assertAlmostEqual(sk.Geometry[0].length(), 10 * math.pi, delta=1e-3)
        r = self.ok("sketch_extend", {"sketch": "H ext", "geo": 1, "end": 2, "to": 2})
        self.assertAlmostEqual(r["by"], 10.0, places=3)
        self.assertAlmostEqual(sk.Geometry[1].EndPoint.x, 50.0, places=3)
        e = self.refused("sketch_extend", {"sketch": "H ext", "geo": 0, "to": 2})
        self.assertIn("by", e["message"])

    def test_fillet_between_two_curves_by_near_points(self):
        sk = self.sketch("H fil")
        self.ok("sketch_add", {"sketch": "H fil", "items": [{"kind": "line", "from": [0, 0], "to": [20, 0]}, {"kind": "line", "from": [20, 0], "to": [20, 10]}]})
        r = self.ok("sketch_edit", {"sketch": "H fil", "fillet": {"geos": [0, 1], "near": [[15, 0], [20, 5]], "radius": 3}})
        self.assertIn("fillet r3", r["done"][0])
        arcs = [g for g in sk.Geometry if type(g).__name__ == "ArcOfCircle"]
        self.assertEqual(len(arcs), 1)
        self.assertAlmostEqual(arcs[0].Radius, 3.0, places=4)

    def test_point_refs_are_checked(self):
        self.sketch("H ref")
        self.ok("sketch_add", {"sketch": "H ref", "items": [{"kind": "line", "from": [0, 0], "to": [10, 0]}, {"kind": "line", "from": [10, 1], "to": [10, 10]}]})
        e = self.refused("sketch_constrain", {"sketch": "H ref", "constraints": [{"type": "coincident", "refs": [[0, 5], [1, 1]]}]})
        self.assertIn("vertex", e["message"])
        # Vertex 0 is the whole curve, not a point: coincident wants two points.
        e = self.refused("sketch_constrain", {"sketch": "H ref", "constraints": [{"type": "coincident", "refs": [[0, 0], [1, 1]]}]})
        self.assertIn("two points", e["message"])
        e = self.refused("sketch_constrain", {"sketch": "H ref", "constraints": [{"type": "point_on_object", "refs": [[0, 2], -3]}]})
        self.assertIn("outside edges", e["message"])
        ok = self.ok("sketch_constrain", {"sketch": "H ref", "constraints": [{"type": "coincident", "refs": [[0, 2], [1, 1]]}]})
        self.assertEqual(ok["added"], [0])

    def test_outside_edges_get_one_id_each(self):
        self.ok("pd_body_new", {"name": "H box"})
        self.ok("sketch_new", {"body": "H box", "plane": "XY", "name": "H base"})
        self.ok("sketch_add", {"sketch": "H base", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 30]}]})
        self.ok("pd_pad", {"body": "H box", "sketch": "H base", "length": 5})
        self.ok("sketch_new", {"body": "H box", "face": {"at": [0, 0, 5], "normal": [0, 0, 1]}, "name": "H top"})
        # Two edges of the same feature: FreeCAD lists them under one link.
        ext = self.ok("sketch_external", {"sketch": "H top", "edges": [{"type": "line", "near": [0, 15, 5]}, {"type": "line", "near": [0, -15, 5]}]})
        self.assertEqual(ext["ids"], [-3, -4], ext)
        self.ok("sketch_add", {"sketch": "H top", "items": [{"kind": "point", "at": [3, 2]}]})
        c = self.ok("sketch_constrain", {"sketch": "H top", "constraints": [{"type": "point_on_object", "refs": [[0, 1], -4]}]})
        sk = self.session.doc.getObjectsByLabel("H top")[0]
        self.assertAlmostEqual(abs(sk.Geometry[0].Y), 15.0, places=4)
        self.assertEqual(c["state"]["solver"], "solved")
        e = self.refused("sketch_constrain", {"sketch": "H top", "constraints": [{"type": "point_on_object", "refs": [[0, 1], -5]}]})
        self.assertIn("-3 to -4", e["message"])
        # The base sketch is what the pad (the tip) is built from.
        e = self.refused("sketch_external", {"sketch": "H base", "edges": ["Edge1"]})
        self.assertIn("built from", e["message"])

    def test_validate_reads_the_solver_and_repairs(self):
        sk = self.sketch("H val")
        self.ok("sketch_add", {"sketch": "H val", "items": [{"kind": "line", "from": [0, 0], "to": [10, 0]}, {"kind": "line", "from": [10, 0], "to": [10, 10]}]})
        v = self.ok("sketch_validate", {"sketch": "H val"})
        self.assertEqual(v["solver"], "solved", v)
        self.assertEqual(v["found"].get("missingCoincidences"), 1, v)
        f = self.ok("sketch_validate", {"sketch": "H val", "fix": True})
        self.assertIn("missing coincidences added", f["fixed"])
        self.assertEqual(sum(c.Type == "Coincident" for c in sk.Constraints), 1)

    def test_mirrored_sketch_keeps_its_arcs(self):
        self.sketch("H mir")
        self.ok("sketch_add", {"sketch": "H mir", "items": [{"kind": "arc", "center": [10, 0], "radius": 5, "start": 0, "end": 90}]})
        m = self.ok("sketch_mirror", {"sketch": "H mir", "about": "y"})
        g = self.session.doc.getObjectsByLabel(m["sketch"])[0].Geometry[0]
        ends = sorted((round(p.x, 3), round(p.y, 3)) for p in (g.StartPoint, g.EndPoint))
        self.assertEqual(ends, [(-15.0, 0.0), (-10.0, 5.0)])
        mid = g.value((g.FirstParameter + g.LastParameter) / 2)
        self.assertAlmostEqual(mid.x, -10 - 5 * math.cos(math.pi / 4), places=3)
        self.assertAlmostEqual(mid.y, 5 * math.sin(math.pi / 4), places=3)
        self.assertAlmostEqual(g.length(), 2.5 * math.pi, places=3)


if __name__ == "__main__":
    unittest.main()
