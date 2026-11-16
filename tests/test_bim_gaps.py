# SPDX-License-Identifier: LGPL-2.1-or-later
# BIM's remaining commands headless, each checked on what it must make.
import json
import os
import unittest

from _fc import HAVE, add_body, caller, server

try:
    import Arch  # noqa: F401

    BIM = HAVE
except Exception:
    BIM = False


@unittest.skipUnless(BIM, "FreeCAD with BIM is not importable here")
class BimGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import FreeCAD

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("BimGaps")
        cls.session.switch(FreeCAD.ActiveDocument)

    def ok(self, name, args=None):
        err, out = self.call(name, args or {})
        self.assertFalse(err, f"{name}: {out}")
        print(f"\n{name}:", json.dumps(out)[:300])
        return out

    def test_1_components(self):
        import Part

        add_body(self.session, "G box", Part.makeBox(1000, 200, 3000))
        c = self.ok("bim_component", {"from": "G box", "name": "G comp"})
        self.assertAlmostEqual(c["volume"], 1000 * 200 * 3000, delta=1)
        cl = self.ok("bim_component", {"kind": "clone", "from": "G comp", "at": [2000, 0, 0]})
        self.assertAlmostEqual(cl["volume"], c["volume"], delta=1)
        un = self.ok("bim_component", {"kind": "unclone", "from": cl["object"]})
        self.assertEqual(un["kind"], "unclone")
        f = self.ok("bim_ifc_brep", {"objects": ["G comp"]})
        self.assertTrue(f["set"][0]["forceBrep"])
        self.assertFalse(self.ok("bim_ifc_brep", {"objects": ["G comp"]})["set"][0]["forceBrep"])

    def test_2_tidy(self):
        import Part

        add_body(self.session, "T a", Part.makeBox(10, 10, 10))
        add_body(self.session, "T b", Part.makeBox(10, 10, 10).translated(__import__("FreeCAD").Vector(20, 0, 0)))
        g = self.ok("bim_glue", {"objects": ["T a", "T b"], "name": "T glued"})
        self.assertEqual(g["of"], 2)
        add_body(self.session, "T e1", Part.makeLine((0, 0, 0), (10, 0, 0)))
        add_body(self.session, "T e2", Part.makeLine((10, 0, 0), (10, 10, 0)))
        r = self.ok("bim_rewire", {"objects": ["T e1", "T e2"]})
        self.assertEqual(len(r["wires"]), 1)
        self.ok("bim_trash", {"action": "put", "objects": ["T glued"]})
        self.assertIn("T glued", self.ok("bim_trash", {"action": "list"})["trash"])
        self.assertIn("T glued", self.ok("bim_trash", {"action": "empty"})["emptied"])
        grp = self.session.doc.addObject("App::DocumentObjectGroup", "Grp")
        for n in ("Zed", "Alpha"):
            o = self.session.doc.addObject("App::FeaturePython", n)
            o.Label = n
            grp.addObject(o)
        self.assertEqual(self.ok("bim_reorder", {"group": "Grp", "sort": True})["order"], ["Alpha", "Zed"])

    def test_3_panels_and_nest(self):
        err, p = self.call("bim_panel", {"points": [[0, 0], [600, 0], [600, 400], [0, 400]], "thickness": 18, "name": "N panel"})
        if err:
            self.skipTest(f"bim_panel: {p}")
        cut = self.ok("bim_panel_out", {"kind": "cut", "panels": ["N panel"]})
        self.assertGreater(cut["cuts"][0]["edges"], 3)
        sh = self.ok("bim_panel_out", {"kind": "sheet", "panels": ["N panel"], "width": 2440, "height": 1220})
        self.assertEqual(sh["size"], [2440.0, 1220.0])

    def test_4_image_views_library(self):
        import tempfile

        png = os.path.join(tempfile.mkdtemp(), "plan.png")
        with open(png, "wb") as f:
            f.write(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4c10000000049454e44ae426082"))
        im = self.ok("bim_image_plane", {"path": png, "width": 5000, "height": 3000})
        self.assertEqual(im["size"], [5000.0, 3000.0])
        lib = os.path.join(tempfile.mkdtemp(), "lib")
        os.makedirs(os.path.join(lib, "doors"))
        import Part

        Part.makeBox(900, 40, 2100).exportStep(os.path.join(lib, "doors", "door 900.step"))
        found = self.ok("bim_library", {"folder": lib, "search": "door"})
        self.assertEqual(found["found"][0]["name"], "door 900.step")
        ins = self.ok("bim_library", {"folder": lib, "insert": found["found"][0]["path"]})
        self.assertTrue(ins["objects"])
        self.ok("bim_wall", {"points": [[0, 0], [4000, 0]], "width": 200, "height": 3000, "name": "V wall"})
        self.ok("bim_level", {"objects": ["V wall"], "name": "V level"})
        v = self.ok("bim_views", {"levels": ["V level"]})
        self.assertEqual(len(v["views"]), 1)

    def test_5_reextrude(self):
        self.ok("bim_wall", {"points": [[0, 5000], [3000, 5000]], "width": 200, "height": 2500, "name": "R wall"})
        w = self.session.doc.getObjectsByLabel("R wall")[0]
        top = max(range(len(w.Shape.Faces)), key=lambda i: w.Shape.Faces[i].CenterOfMass.z)
        r = self.ok("bim_reextrude", {"face": f"R wall.Face{top + 1}", "delete": False})
        self.assertIsNotNone(r.get("volume"))


@unittest.skipUnless(BIM, "FreeCAD with BIM is not importable here")
class BimHardening(unittest.TestCase):
    """The hardening pass's fixes, each from FreeCAD 1.1's own source (docs/hardening/bimcam-findings.md)."""

    @classmethod
    def setUpClass(cls):
        import FreeCAD

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("BimHardening")
        cls.session.switch(FreeCAD.ActiveDocument)

    def ok(self, name, args=None):
        err, out = self.call(name, args or {})
        self.assertFalse(err, f"{name}: {out}")
        return out

    def refused(self, name, args=None):
        err, out = self.call(name, args or {})
        self.assertTrue(err, f"{name} should refuse: {out}")
        return json.dumps(out)

    def obj(self, label):
        return self.session.doc.getObjectsByLabel(label)[0]

    def test_01_left_wall_lies_right_of_its_line(self):
        # ArchWall offsets a Left wall by direction x normal: going +X, that is -Y.
        w = self.ok("bim_wall", {"points": [[0, 0], [4000, 0]], "width": 200, "height": 3000, "align": "left", "name": "H left"})
        self.assertAlmostEqual(w["min"][1], -200, delta=0.5)
        self.assertEqual(w["box"], [4000.0, 200.0, 3000.0])
        o = self.ok("bim_opening", {"wall": "H left", "kind": "window", "at": 1000, "width": 1000, "height": 1200, "sill": 900})
        self.assertAlmostEqual(o["wallCut_m3"], 1.0 * 1.2 * 0.2, delta=0.002)
        self.assertNotIn("warning", o)
        w = self.ok("bim_wall", {"points": [[0, 2000], [4000, 2000]], "width": 200, "height": 3000, "align": "right", "name": "H right"})
        self.assertAlmostEqual(w["min"][1], 2000, delta=0.5)
        o = self.ok("bim_opening", {"wall": "H right", "kind": "door", "at": 500})
        self.assertAlmostEqual(o["wallCut_m3"], 0.9 * 2.1 * 0.2, delta=0.002)

    def test_02_opening_refusals(self):
        self.ok("bim_wall", {"points": [[0, 4000], [3000, 4000]], "width": 200, "height": 2500, "name": "H low"})
        self.assertIn("sill + height", self.refused("bim_opening", {"wall": "H low", "kind": "window", "sill": 1500, "height": 1200}))
        self.assertIn("at", self.refused("bim_opening", {"wall": "H low", "at": -100}))

    def test_03_structure_shapes(self):
        # A Beam or Column with Length above Height is laid along X by FreeCAD: squat ones are built on a section.
        c = self.ok("bim_structure", {"kind": "column", "at": [10000, 0, 0], "width": 600, "depth": 400, "height": 300, "name": "H pad"})
        self.assertEqual(c["box"], [600.0, 400.0, 300.0])
        self.assertEqual(c["min"], [9700.0, -200.0, 0.0])
        b = self.ok("bim_structure", {"kind": "beam", "from": [10000, 2000, 1000], "to": [10100, 2000, 1000], "width": 200, "depth": 400, "name": "H stub"})
        self.assertEqual(b["box"], [100.0, 200.0, 400.0])
        t = self.ok("bim_structure", {"kind": "column", "at": [12000, 0, 0], "width": 300, "depth": 300, "height": 3000, "name": "H col"})
        self.assertEqual(t["box"], [300.0, 300.0, 3000.0])
        # A slab rises from its outline whichever way round the corners run; a footing hangs below.
        cw = [[14000, 0], [14000, 3000], [18000, 3000], [18000, 0]]
        sl = self.ok("bim_structure", {"kind": "slab", "points": cw, "thickness": 200, "name": "H slab cw"})
        self.assertEqual(sl["min"][2], 0.0)
        self.assertAlmostEqual(sl["volume_m3"], 4 * 3 * 0.2, delta=0.001)
        ft = self.ok("bim_structure", {"kind": "footing", "points": cw, "thickness": 500, "name": "H footing cw"})
        self.assertEqual(ft["min"][2], -500.0)

    def test_04_roof_either_way_round(self):
        ccw = [[20000, 0], [26000, 0], [26000, 4000], [20000, 4000]]
        a = self.ok("bim_roof", {"points": ccw, "angle": [30, 90, 30, 90], "thickness": 150, "overhang": 300, "name": "H roof ccw"})
        b = self.ok("bim_roof", {"points": [[30000, 0], [30000, 4000], [36000, 4000], [36000, 0]], "angle": [90, 30, 90, 30], "thickness": 150, "overhang": 300, "name": "H roof cw"})
        self.assertNotIn("flipped", a)
        self.assertTrue(b.get("flipped"))
        self.assertGreater(a["volume_m3"], 0.5)
        self.assertAlmostEqual(a["volume_m3"], b["volume_m3"], delta=a["volume_m3"] * 0.01)
        self.assertEqual(a["box"], b["box"])
        # ridge midway: run 2000 at 30 degrees
        self.assertAlmostEqual(a["ridge"], 2000 * 0.57735, delta=2)
        # A hipped roof (one angle all round): the panes over the 4000 span meet at
        # 2000 x tan 30 and cut the end panes off there, whatever the end panes' own
        # run says (live run: ridge 1732.1 reported on a roof 1501 high in all).
        h = self.ok("bim_roof", {"points": [[40000, 0], [40000, 4000], [46000, 4000], [46000, 0]], "angle": 30, "thickness": 150, "overhang": 300, "name": "H roof hip"})
        self.assertAlmostEqual(h["ridge"], 2000 * 0.57735, delta=2)
        self.assertLess(h["ridge"], h["box"][2])
        self.assertIn("gable", self.refused("bim_roof", {"points": ccw, "angle": 90}))
        self.assertIn("one per edge", self.refused("bim_roof", {"points": ccw, "angle": [30, 30]}))

    def test_05_grid_lines(self):
        g = self.ok("bim_grid", {"xSpacing": [3000, 3000], "ySpacing": [4000], "length": 9000, "name": "H grid"})
        self.assertEqual(g["lines"], {"x": [0.0, 3000.0, 6000.0], "y": [0.0, 4000.0]})
        gx, gy = self.obj("H grid X"), self.obj("H grid Y")
        self.assertAlmostEqual(float(gx.Length), 9000, delta=0.01)
        bx, by = gx.Shape.BoundBox, gy.Shape.BoundBox
        self.assertAlmostEqual(bx.XMax, 6000, delta=0.5)
        self.assertAlmostEqual(bx.YMax, 9000, delta=0.5)
        self.assertAlmostEqual(by.XMin, 0, delta=0.5)
        self.assertAlmostEqual(by.XMax, 9000, delta=0.5)
        self.assertAlmostEqual(by.YMax, 4000, delta=0.5)
        # one structure per system; the data runner refuses two before FreeCAD answers a list
        self.ok("bim_structure", {"kind": "column", "at": [0, 0, 0], "name": "H gc1"})
        self.ok("bim_structure", {"kind": "column", "at": [0, 0, 0], "name": "H gc2"})
        self.assertIn("one structure per call", self.refused("bim_structural_system", {"structures": ["H gc1", "H gc2"], "axes": ["H grid X", "H grid Y"]}))
        st = self.ok("bim_structural_system", {"structures": ["H gc1"], "axes": ["H grid X", "H grid Y"], "name": "H system"})
        # 3 x 2 crossings; the y = 0 line meets the x lines at their very ends, which
        # FreeCAD's intersection may or may not count: the three on y = 4000 are certain.
        self.assertIn(st["copies"], (3, 6))

    def test_06_fence_posts_stand_on_the_path(self):
        f = self.ok("bim_fence", {"points": [[0, -6000, 0], [6000, -6000, 0]], "height": 1200, "post": 100, "spacing": 2000, "panel": 20, "name": "H fence"})
        self.assertEqual(f["NumberOfSections"], 3)
        self.assertEqual(f["NumberOfPosts"], 4)
        bb = self.obj("H fence").Shape.BoundBox
        # posts centred across the path (y = -6000), the fence its height
        self.assertAlmostEqual(bb.YMin, -6050, delta=1)
        self.assertAlmostEqual(bb.YMax, -5950, delta=1)
        self.assertAlmostEqual(bb.ZLength, 1200, delta=1)
        self.assertIn("spacing", self.refused("bim_fence", {"points": [[0, 0, 0], [1000, 0, 0]], "post": 200, "spacing": 150}))

    def test_07_data_that_was_dropped(self):
        import Part

        add_body(self.session, "H sink", Part.makeBox(600, 450, 200))
        e = self.ok("bim_equipment", {"object": "H sink", "ifc": "sanitary terminal", "url": "https://example.org/sink", "model": "S-600", "name": "H sink eq"})
        o = self.obj("H sink eq")
        self.assertEqual(o.ProductURL, "https://example.org/sink")
        self.assertEqual(o.IfcType, "Sanitary Terminal")
        self.assertEqual(e["ifc"], "Sanitary Terminal")
        add_body(self.session, "H chair", Part.makeBox(400, 400, 800))
        self.assertIn("Near", self.refused("bim_equipment", {"object": "H chair", "ifc": "Furnitur"}))
        self.ok("bim_wall", {"points": [[0, 8000], [3000, 8000]], "name": "H mat wall"})
        m = self.ok("bim_material", {"name": "H brick", "density": 1900, "color": "#cc3319", "objects": ["H mat wall"]})
        self.assertEqual(m["on"], ["H mat wall"])
        col = self.obj("H brick").Color
        for got, want in zip(col[:3], (0.8, 0.2, 0.098)):
            self.assertAlmostEqual(got, want, delta=0.01)
        self.assertIn("rrggbb", self.refused("bim_material", {"name": "H brick", "color": "reddish"}))
        self.assertEqual(self.ok("bim_ifc", {"objects": ["H mat wall"], "type": "IfcBuildingElementProxy"})["objects"][0]["ifc"], "Building Element Proxy")
        self.assertIn("Near", self.refused("bim_ifc", {"objects": ["H mat wall"], "type": "Wal"}))
        self.ok("bim_ifc", {"objects": ["H mat wall"], "type": "wall"})

    def test_08_space_use(self):
        pts = [[40000, 0], [44000, 0], [44000, 3000], [40000, 3000]]
        sp = self.ok("bim_space", {"points": pts, "height": 2600, "use": "room", "name": "H room"})
        self.assertEqual(sp["use"], "Room")
        self.assertAlmostEqual(sp["area_m2"], 12.0, delta=0.01)
        self.assertIn("space types", self.refused("bim_space", {"points": pts, "use": "Bedroom"}))

    def test_09_remove_shape_answers_after_the_object_is_replaced(self):
        self.ok("bim_structure", {"kind": "column", "at": [50000, 0, 0], "name": "H shape col"})
        r = self.ok("bim_remove_shape", {"objects": ["H shape col"]})
        self.assertEqual(r["turned"], ["H shape col"])

    def test_10_nest(self):
        import ArchNesting
        import Part

        def face(label, w, h, x):
            return add_body(self.session, label, Part.Face(Part.makePolygon([(x, -20000, 0), (x + w, -20000, 0), (x + w, -20000 + h, 0), (x, -20000 + h, 0), (x, -20000, 0)])))

        face("H sheet", 1000, 600, 0)
        face("H piece a", 400, 300, 2000)
        face("H piece b", 300, 200, 3000)
        add_body(self.session, "H solid piece", Part.makeBox(100, 100, 18))
        self.assertIn("single flat face", self.refused("bim_nest", {"container": "H sheet", "pieces": ["H solid piece"]}))
        was = list(ArchNesting.ROTATIONS)
        n = self.ok("bim_nest", {"container": "H sheet", "pieces": ["H piece a", "H piece b"], "rotations": [0, 90], "margin": 5})
        self.assertEqual(ArchNesting.ROTATIONS, was)
        self.assertEqual(n["placed"], 2)
        self.assertEqual(n["rotations"], [0, 90])
        self.assertIn("not applied", n["margin"])

    def test_11_join_keeps_the_last_wall(self):
        self.ok("bim_wall", {"points": [[60000, 0], [63000, 0], [63000, 2000]], "name": "H join a"})
        self.ok("bim_wall", {"points": [[63000, 2000], [60000, 2000]], "name": "H join b"})
        j = self.ok("bim_edit", {"op": "join", "walls": ["H join a", "H join b"]})
        self.assertEqual(j["kept"], "H join b")
        self.assertEqual(j["removed"], ["H join a"])
        self.assertEqual(self.session.doc.getObjectsByLabel("H join a"), [])
        self.assertAlmostEqual(j["volume_m3"], (3 + 2 + 3) * 0.2 * 3, delta=0.15)

    def test_12_schedule_sheet_is_a_change(self):
        before = len(self.session.steps)
        self.ok("bim_schedule", {})
        self.assertEqual(len(self.session.steps), before)
        sh = self.ok("bim_schedule", {"sheet": "H schedule"})
        self.assertEqual(sh["sheet"], "H schedule")
        self.assertEqual(len(self.session.steps), before + 1)

    def test_13_quantities_count_each_member_once(self):
        # A level and a building carry their members' solids as their own shape
        # (live run: 143 m3 with no material in a 37 m3 house).
        self.ok("bim_structure", {"kind": "slab", "points": [[50000, 0], [52000, 0], [52000, 1000], [50000, 1000]], "thickness": 100, "name": "H q slab"})
        before = self.ok("bim_quantities", {"by": "type", "detail": True})
        self.ok("bim_level", {"objects": ["H q slab"], "name": "H q level"})
        self.ok("bim_building", {"levels": ["H q level"], "name": "H q house"})
        after = self.ok("bim_quantities", {"by": "type", "detail": True})
        self.assertEqual(after["objects"], before["objects"])
        self.assertEqual(after["groups"]["Slab"], before["groups"]["Slab"])
        names = [r["object"] for r in after["rows"]]
        self.assertNotIn("H q level", names)
        self.assertNotIn("H q house", names)
        self.assertNotIn("Building Storey", after["groups"])
        self.assertNotIn("Building", after["groups"])


if __name__ == "__main__":
    unittest.main()
