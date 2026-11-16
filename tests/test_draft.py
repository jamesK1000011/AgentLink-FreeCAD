# SPDX-License-Identifier: LGPL-2.1-or-later
# Lettering and filled surfaces, on a real FreeCAD.
import json
import os
import unittest

from _fc import HAVE, add_body, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Draft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import FreeCAD
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("Letters")
        cls.session.switch(FreeCAD.ActiveDocument)
        add_body(cls.session, "Tag", Part.makeBox(60, 30, 10))
        saddle = Part.makePolygon([FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(20, 0, 5), FreeCAD.Vector(20, 20, 0), FreeCAD.Vector(0, 20, 5), FreeCAD.Vector(0, 0, 0)])
        o = cls.session.doc.addObject("Part::Feature", "Frame")
        o.Shape = saddle
        cls.session.doc.recompute()

    def test_1_fonts(self):
        err, f = self.call("draft_fonts")
        self.assertFalse(err, f)
        print("\nfonts:", f["found"], f["default"])
        self.assertGreater(f["found"], 0)

    def test_2_emboss_and_engrave(self):
        err, e = self.call("draft_text", {"body": "Tag", "text": "AL-7", "size": 8, "depth": 1})
        print("emboss:", json.dumps(e))
        self.assertFalse(err, e)
        self.assertGreater(e["volumeChange"], 5)
        bb = self.session.body("Tag").Shape.BoundBox
        self.assertAlmostEqual(bb.ZMax, 11, delta=1e-3)
        # box is the lettering's real extent: raised 1 mm off the top face (it was the flat outline, z 10 … 10)
        self.assertAlmostEqual(e["box"]["min"][2], 10, delta=0.01)
        self.assertAlmostEqual(e["box"]["max"][2], 11, delta=0.01)
        err, g = self.call("draft_text", {"body": "Tag", "text": "B", "size": 6, "depth": 0.5, "mode": "engrave", "face": {"normal": [0, -1, 0]}})
        self.assertFalse(err, g)
        self.assertLess(g["volumeChange"], -1)
        self.assertAlmostEqual(g["box"]["max"][1] - g["box"]["min"][1], 0.5, delta=0.01)  # cut 0.5 into the front face
        self.assertNotIn("warning", g)
        err, w = self.call("draft_text", {"body": "Tag", "text": "MUCH TOO LONG FOR THIS FACE", "size": 8, "depth": 0.4, "mode": "engrave", "face": {"normal": [1, 0, 0]}})
        self.assertFalse(err, w)
        self.assertIn("warning", w)
        out = os.environ.get("AGENTLINK_RENDERS")
        if out:
            self.call("view_render", {"objects": ["Tag"], "views": ["iso", "front"], "inline": False, "path": os.path.join(out, "lettering.png")})

    def test_3_surface_fill(self):
        err, f = self.call("surface_fill", {"edges": ["Frame"], "thickness": 1, "name": "Saddle"})
        print("surface:", json.dumps(f))
        self.assertFalse(err, f)
        self.assertTrue(f["solid"])
        self.assertGreater(f["area"], 400)

    def test_4_surface_loft_points_thicken(self):
        # A curved panel through three arcs of points: a sheet, then 2 mm thick.
        def arc(y, sag):
            return {"points": [[x, y, sag * (1 - ((x - 20) / 20) ** 2)] for x in (0, 10, 20, 30, 40)]}
        err, p = self.call("surface_loft", {"curves": [arc(0, 4), arc(15, 6), arc(30, 4)], "thickness": 2, "side": "both", "name": "Panel"})
        print("\nloft:", json.dumps(p))
        self.assertFalse(err, p)
        self.assertTrue(p["solid"])
        self.assertAlmostEqual(p["volume"], p["area"] * 2, delta=p["area"] * 2 * 0.05)
        self.assertNotIn("warnings", p)
        # Open and closed curves together are refused.
        err, x = self.call("surface_loft", {"curves": [arc(0, 4), {"points": [[0, 0, 0], [10, 0, 0], [10, 10, 0]], "closed": True}]})
        self.assertTrue(err)
        # Through a grid of points: every point on it; then thickened thin.
        rows = [[[x, y, 0.02 * (x - 15) ** 2 - 0.01 * (y - 10) ** 2] for x in range(0, 31, 5)] for y in range(0, 21, 5)]
        err, g = self.call("surface_points", {"rows": rows, "name": "Fitted"})
        print("points:", json.dumps(g))
        self.assertFalse(err, g)
        self.assertLess(g["farthestPoint"], 0.01)
        self.assertFalse(g["solid"])
        err, t = self.call("surface_thicken", {"surface": "Fitted", "thickness": 0.6})
        print("thicken:", json.dumps(t))
        self.assertFalse(err, t)
        self.assertTrue(t["solid"])
        self.assertTrue(any("two printed lines" in w for w in t["warnings"]), t)
        err, r = self.call("surface_points", {"rows": [[[0, 0, 0], [1, 0, 0]], [[0, 1, 0]]]})
        self.assertTrue(err)


    def test_5_outline_from_svg(self):
        """A logo from an SVG: a 20 x 10 plate with a round hole, a triangle,
        and an open stroke left out. In millimetres (width 100mm, viewBox 100)."""
        import math
        import tempfile

        svg = os.path.join(tempfile.mkdtemp(), "logo.svg")
        with open(svg, "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">'
                    '<path d="M 10 10 L 30 10 L 30 20 L 10 20 Z"/>'
                    '<circle cx="20" cy="15" r="3"/>'
                    '<path d="M 40 10 L 50 10 L 45 20 Z"/>'
                    '<path d="M 60 10 L 70 20" fill="none" stroke="black"/></svg>')
        err, o = self.call("draft_outline", {"path": svg, "mode": "extrude", "depth": 2, "name": "Logo"})
        print("\noutline:", json.dumps(o))
        self.assertFalse(err, o)
        # The circle inside the plate is a hole in it (FaceMakerBullseye).
        want = (200 - math.pi * 9 + 50) * 2
        self.assertAlmostEqual(o["volume"], want, delta=want * 0.01)
        self.assertEqual(o["openCurvesLeftOut"], 1)
        # Raised on the tag's top, scaled to 30 mm wide.
        err, e = self.call("draft_outline", {"path": svg, "body": "Tag", "width": 30, "depth": 0.8})
        print("on the tag:", json.dumps(e))
        self.assertFalse(err, e)
        self.assertEqual(e["mode"], "emboss")
        self.assertAlmostEqual(e["size"][0], 30, delta=0.01)
        self.assertGreater(e["volumeChange"], 0)
        err, x = self.call("draft_outline", {"path": "/nonexistent.svg"})
        self.assertTrue(err)


    def test_6_arrays(self):
        import FreeCAD
        import Part

        from _fc import add_body

        add_body(self.session, "Coin", Part.makeCylinder(5, 2))
        # A 3 x 2 grid 2 mm apart: separate solids, so a batch of bodies.
        err, g = self.call("draft_array", {"body": "Coin", "kind": "grid", "count": [3, 2], "separate": True})
        print("\ngrid:", json.dumps(g))
        self.assertFalse(err, g)
        self.assertEqual(len(g["bodies"]), 6)
        last = next(o for o in self.session.doc.Objects if o.Label == g["bodies"][-1]).Shape.BoundBox
        self.assertAlmostEqual(last.XMin, 2 * 12 - 5, delta=1e-6)
        # Six spokes round the middle, joined into one wheel.
        add_body(self.session, "Spoke", Part.makeBox(20, 2, 2, FreeCAD.Vector(0, -1, 0)))
        err, w = self.call("draft_array", {"body": "Spoke", "kind": "polar", "count": 6})
        print("polar:", json.dumps(w))
        self.assertFalse(err, w)
        self.assertEqual(w["solids"], 1)
        self.assertAlmostEqual(w["size"][0], 40, delta=0.2)
        # Along a path of points, turned with it.
        add_body(self.session, "Bead", Part.makeSphere(1.5))
        err, p = self.call("draft_array", {"body": "Bead", "kind": "path", "count": 5, "path": {"points": [[0, 0, 0], [20, 10, 0], [40, 0, 0]]}, "align": True})
        self.assertFalse(err, p)
        self.assertEqual(p["solids"], 5)
        self.assertIn("note", p)
        err, x = self.call("draft_array", {"body": "Bead", "kind": "spiral"})
        self.assertTrue(err)



@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class DraftHardening(unittest.TestCase):
    """The hardening pass (16 Nov 2026): Draft's own objects, against the
    wiki's Draft tutorial (two arcs tied by two lines, a frame, a circle, a
    hexagon, a polar array, dimensions). Written from FreeCAD 1.1's source."""

    @classmethod
    def setUpClass(cls):
        import FreeCAD

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("DraftTutorial")
        cls.session.switch(FreeCAD.ActiveDocument)

    def ok(self, name, args=None):
        err, out = self.call(name, args)
        self.assertFalse(err, out)
        return out

    def refused(self, name, args=None):
        err, out = self.call(name, args)
        self.assertTrue(err, out)
        return json.dumps(out)

    def obj(self, label):
        return next(o for o in self.session.doc.Objects if o.Label == label)

    def test_1_shapes(self):
        import math

        a = self.ok("draft_shape", {"kind": "arc", "radius": 30, "start": 60, "end": 120, "name": "Arc30"})
        self.assertAlmostEqual(a["length"], 30 * math.pi / 3, places=3)
        self.assertNotIn("area", a)
        self.ok("draft_shape", {"kind": "arc", "radius": 25, "start": 60, "end": 120, "name": "Arc25"})
        c60, s60 = math.cos(math.radians(60)), math.sin(math.radians(60))
        ln = self.ok("draft_shape", {"kind": "wire", "points": [[30 * c60, 30 * s60, 0], [25 * c60, 25 * s60, 0]], "name": "TieR"})
        self.assertAlmostEqual(ln["length"], 5, places=4)
        self.ok("draft_shape", {"kind": "wire", "points": [[-30 * c60, 30 * s60, 0], [-25 * c60, 25 * s60, 0]], "name": "TieL"})
        r = self.ok("draft_shape", {"kind": "rectangle", "length": 240, "height": 150, "at": [-100, -60, 0], "name": "Frame"})
        self.assertAlmostEqual(r["area"], 36000, places=2)  # Make Face is on as installed
        self.assertAlmostEqual(r["length"], 780, places=3)
        c = self.ok("draft_shape", {"kind": "circle", "radius": 15, "face": False, "name": "Hub"})
        self.assertNotIn("area", c)
        self.assertAlmostEqual(c["length"], 2 * math.pi * 15, places=3)
        h = self.ok("draft_shape", {"kind": "polygon", "sides": 6, "radius": 50, "name": "Hex"})
        self.assertAlmostEqual(h["length"], 300, places=3)
        self.assertAlmostEqual(h["area"], 1.5 * math.sqrt(3) * 2500, places=1)
        e = self.ok("draft_shape", {"kind": "ellipse", "major": 40, "minor": 20, "at": [200, 0, 0], "name": "Oval"})
        self.assertAlmostEqual(e["area"], math.pi * 20 * 10, places=1)
        self.assertEqual(self.obj("Oval").Placement.Base.x, 200)
        # A first point repeated as the last closes the wire (three sides, a face).
        t = self.ok("draft_shape", {"kind": "wire", "points": [[300, 0, 0], [310, 0, 0], [300, 10, 0], [300, 0, 0]], "name": "Tri"})
        self.assertAlmostEqual(t["area"], 50, places=3)
        self.assertIn("sides", self.refused("draft_shape", {"kind": "polygon", "sides": 2, "radius": 5}))
        self.assertIn("radius", self.refused("draft_shape", {"kind": "circle", "radius": 0}))
        self.assertIn("start, end", self.refused("draft_shape", {"kind": "arc", "radius": 5, "start": 10, "end": 370}))

    def test_2_upgrade_array_dimensions(self):
        import math

        up = self.ok("draft_modify", {"op": "upgrade", "objects": ["Arc30", "Arc25", "TieR", "TieL"]})
        wire = (up.get("objects") or [up])[0]
        self.assertAlmostEqual(wire["length"], 55 * math.pi / 3 + 10, places=3)
        arr = self.ok("draft_link_array", {"object": wire["object"], "kind": "polar", "count": 4, "angle": 360, "name": "Ring"})
        self.assertEqual(arr["count"], 4)
        self.assertEqual(arr["of"], wire["object"])
        d = self.ok("draft_dimension", {"kind": "linear", "from": [0, 0, 0], "to": [0, 50 * math.sin(math.radians(60)), 0], "at": [100, 20, 0], "name": "ToHexTop"})
        self.assertAlmostEqual(d["measures"], 43.3013, places=3)
        self.assertEqual(d["unit"], "mm")
        dia = self.ok("draft_dimension", {"kind": "diameter", "object": "Hub", "edge": 1, "at": [20, 20, 0]})
        self.assertAlmostEqual(dia["measures"], 30, places=4)
        ang = self.ok("draft_dimension", {"kind": "angular", "center": [0, 0, 0], "angles": [60, 120], "at": [0, 35, 0]})
        self.assertAlmostEqual(ang["measures"], 60, places=4)  # worked out here: Draft sets Angle only in its window
        self.assertEqual(ang["unit"], "deg")
        follow = self.ok("draft_dimension", {"kind": "linear", "object": "Frame", "vertices": [1, 2]})
        self.assertIn(round(follow["measures"]), (240, 150))
        self.assertIn("Vertex", self.refused("draft_dimension", {"kind": "linear", "object": "Frame", "vertices": [1, 9]}))
        self.assertIn("not a circle", self.refused("draft_dimension", {"kind": "radius", "object": "Frame", "edge": 1}))
        n = len(self.session.doc.Objects)
        self.refused("draft_dimension", {"kind": "radius", "object": "Frame", "edge": 1})
        self.assertEqual(len(self.session.doc.Objects), n)

    def test_3_labels_and_styles(self):
        import FreeCAD

        lb = self.ok("draft_label", {"target": [0, 15, 0], "at": [40, 40, 0], "object": "Hex", "show": "area"})
        # an area reads in the unit FreeCAD's schema picks (cm² for 6495 mm²)
        self.assertTrue(lb["text"] and ("mm" in lb["text"][0] or "cm" in lb["text"][0]), lb)
        self.assertIn("needs object", self.refused("draft_label", {"target": [0, 0, 0], "show": "length"}))
        st = self.ok("draft_style", {"action": "set", "name": "Shop", "values": {"FontSize": 6, "ArrowType": "Tick", "ShowUnit": False, "ExtLines": 45}})
        # As Draft 1.1 stores them: both ends, an arrow's type by its index, floats as floats.
        self.assertEqual(st["values"]["ArrowTypeStart"], 3)
        self.assertEqual(st["values"]["ArrowTypeEnd"], 3)
        self.assertNotIn("ArrowType", st["values"])
        self.assertIsInstance(st["values"]["FontSize"], float)
        import json as js

        from draftutils import utils

        fixed = utils.repair_annotation_style(js.loads(self.session.doc.Meta["Draft_Style_Shop"]))  # raised ValueError on a name
        self.assertEqual(fixed["ArrowTypeStart"], 3)
        self.assertEqual(fixed["FontSize"], 6.0)
        self.assertIn("Tick-2", self.refused("draft_style", {"action": "set", "name": "Shop", "values": {"ArrowType": "Arrowhead"}}))
        ap = self.ok("draft_style", {"action": "apply", "name": "Shop", "objects": ["ToHexTop"]})
        self.assertEqual((ap.get("applied") or []) + (ap.get("recorded") or []), ["ToHexTop"])
        if FreeCAD.GuiUp:
            self.assertEqual(ap["applied"], ["ToHexTop"], ap)
        self.assertIn("Shop", self.refused("draft_style", {"action": "apply", "name": "Nope", "objects": ["ToHexTop"]}))

    def test_4_modify(self):
        import math

        self.ok("draft_shape", {"kind": "wire", "points": [[0, 200, 0], [10, 200, 0]], "name": "J1"})
        self.ok("draft_shape", {"kind": "wire", "points": [[10, 200, 0], [10, 210, 0]], "name": "J2"})
        self.ok("draft_shape", {"kind": "wire", "points": [[50, 200, 0], [60, 200, 0]], "name": "Far"})
        # join_wires answers a list whether or not anything joined: no shared end is a refusal now.
        self.assertIn("share an end", self.refused("draft_modify", {"op": "join", "objects": ["J1", "Far"]}))
        j = self.ok("draft_modify", {"op": "join", "objects": ["J1", "J2"]})
        self.assertAlmostEqual(j["length"], 20, places=4)
        self.assertFalse([o for o in self.session.doc.Objects if o.Label == "J2"])
        # An open Draft wire is closed in place by upgrade: nothing new, and not "nothing to upgrade".
        self.ok("draft_shape", {"kind": "wire", "points": [[0, 300, 0], [10, 300, 0], [10, 310, 0]], "name": "Open"})
        u = self.ok("draft_modify", {"op": "upgrade", "objects": ["Open"]})
        self.assertTrue(self.obj("Open").Closed)
        self.assertEqual(u["object"], "Open")
        # A closed wire split on its closing segment: that segment, and the other two as one open wire.
        sp = self.ok("draft_modify", {"op": "split", "objects": ["Open"], "edge": 3})
        lens = sorted(x["length"] for x in sp["objects"])
        self.assertAlmostEqual(lens[0], math.hypot(10, 10), places=3)
        self.assertAlmostEqual(lens[1], 20, places=3)
        self.assertFalse(self.obj("Open").Closed)
        # A Draft circle offsets to a radius, which Draft takes as a number.
        self.ok("draft_shape", {"kind": "circle", "radius": 10, "at": [0, 400, 0], "face": False, "name": "Ring10"})
        of = self.ok("draft_modify", {"op": "offset", "objects": ["Ring10"], "by": [2, 0, 0], "copy": True})
        self.assertAlmostEqual(of["length"], 2 * math.pi * 12, places=2)
        self.assertAlmostEqual(float(self.obj("Ring10").Radius), 10, places=6)
        self.assertIn("factor", self.refused("draft_modify", {"op": "scale", "objects": ["Ring10"], "factor": 0}))
        self.assertIn("different points", self.refused("draft_modify", {"op": "mirror", "objects": ["Ring10"], "from": [0, 0, 0], "to": [0, 0, 0]}))
        m = self.ok("draft_modify", {"op": "mirror", "objects": ["Ring10"], "from": [0, 0, 0], "to": [1, 0, 0]})
        self.assertAlmostEqual(m["length"], 2 * math.pi * 10, places=2)
        self.assertAlmostEqual(self.obj(m["object"]).Shape.BoundBox.Center.y, -400, places=6)

    def test_5_views_hatch_layers_heal(self):
        import Part

        add_body(self.session, "Block", Part.makeBox(20, 10, 5))
        v = self.ok("draft_2d_view", {"object": "Block", "direction": [0, 0, 1]})
        self.assertAlmostEqual(v["length"], 60, delta=0.01)
        # Cut faces come only from a BIM section plane: on a body the view was silently empty.
        self.assertIn("section plane", self.refused("draft_2d_view", {"object": "Block", "section": True}))
        hz = self.ok("draft_hatch", {"object": "Hex", "pattern": "Diagonal4"})
        self.assertGreater(hz.get("length", 0), 100, hz)
        self.assertIn("Diagonal4", self.refused("draft_hatch", {"object": "Hex", "pattern": "Nope"}))
        self.assertIn("flat face", self.refused("draft_hatch", {"object": "Hub"}))
        a = self.ok("draft_layer", {"name": "Outline", "objects": ["Frame", "Hex"]})
        self.assertEqual(sorted(a["objects"]), ["Frame", "Hex"])
        b = self.ok("draft_layer", {"name": "Inner", "objects": ["Hex"]})
        self.assertEqual(b["objects"], ["Hex"])
        self.assertEqual(self.ok("draft_layer", {"name": "Outline"})["objects"], ["Frame"])
        sk = self.ok("draft_to_sketch", {"objects": ["Frame"], "name": "FrameSketch"})
        self.assertEqual(sk["geometry"], 4)
        back = self.ok("draft_from_sketch", {"objects": ["FrameSketch"]})
        self.assertAlmostEqual(back["length"], 780, places=3)
        # heal { objects } rebuilds the named ones as copies and removes them: the reply reads their labels first.
        self.ok("draft_shape", {"kind": "rectangle", "length": 4, "height": 3, "at": [0, 500, 0], "name": "Old"})
        hl = self.ok("draft_fix", {"action": "heal", "objects": ["Old"]})
        self.assertEqual(hl["healed"], ["Old"])
        self.assertEqual(hl["rebuilt"], 1)

    def test_6_upgrade_says_which_ends_do_not_meet(self):
        # The live model's tie lines, their ends typed to six decimals: 1.1e-7 mm off
        # the outer arc's ends (not joined) and 9.5e-8 mm off the inner arc's (joined).
        self.ok("draft_shape", {"kind": "arc", "radius": 30, "start": 60, "end": 120, "at": [0, 600, 0], "name": "G30"})
        self.ok("draft_shape", {"kind": "arc", "radius": 25, "start": 60, "end": 120, "at": [0, 600, 0], "name": "G25"})
        self.ok("draft_shape", {"kind": "wire", "points": [[15.0, 625.980762, 0], [12.5, 621.650635, 0]], "name": "GR"})
        self.ok("draft_shape", {"kind": "wire", "points": [[-15.0, 625.980762, 0], [-12.5, 621.650635, 0]], "name": "GL"})
        up = self.ok("draft_modify", {"op": "upgrade", "objects": ["G30", "G25", "GR", "GL"]})
        if len(up.get("objects") or []) >= 2:  # one wire where this FreeCAD's tolerance takes the hair in
            self.assertIn("not joined", up["note"])
            self.assertIn("1e-7", up["note"])
        else:
            self.assertNotIn("note", up)


if __name__ == "__main__":
    unittest.main()
