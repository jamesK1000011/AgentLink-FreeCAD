# SPDX-License-Identifier: LGPL-2.1-or-later
# The later families on a real FreeCAD, each answer checked against what the
# shapes must give: exports, point clouds, Surface, BIM, OpenSCAD, Robot,
# gears, Assembly couplings, TechDraw marks and hatching, FEM probes, CAM
# tool sets. A family this build leaves out is skipped.
import json
import os
import unittest

from _pd_base import HAVE, Base


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class MoreFamilies(Base):
    def have(self, tool):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["result"]
        names = {t["name"] for t in r["tools"]}
        if tool not in names:
            self.skipTest(f"{tool} is not in this build")

    def unavailable_skip(self, name, args):
        err, out = self.call(name, args)
        if err and out["error"]["code"] == "unavailable":
            self.skipTest(out["error"]["message"])
        self.assertFalse(err, f"{name}: {out}")
        return out

    def box(self, name, size, at=None):
        args = {"kind": "box", "size": size, "name": name}
        if at:
            args["at"] = at
        return self.ok("part_primitive", args)

    def test_exports(self):
        self.box("Ex plate", [60, 30, 10])
        for ext in ("glb", "gltf", "dae", "ply", "off", "wrl"):
            out = self.ok("export", {"objects": ["Ex plate"], "path": f"ex.{ext}"})
            self.assertTrue(os.path.getsize(out["path"]) > 0, ext)
        g = self.ok("export", {"objects": ["Ex plate"], "path": "ex2.glb", "colors": {"Ex plate": "#3366cc"}})
        self.assertEqual(g["verify"]["size"], [60.0, 30.0, 10.0])
        d = self.ok("export", {"objects": ["Ex plate"], "path": "ex.dxf", "view": "front", "hidden": True})
        self.assertEqual(d["verify"]["size"], [60.0, 10.0])
        s = self.ok("export", {"objects": ["Ex plate"], "path": "ex.svg", "section": 5})
        self.assertEqual(s["verify"]["size"], [60.0, 30.0])
        self.refused("export", {"objects": ["Ex plate"], "path": "ex3.dxf", "section": 50})

    def test_points(self):
        self.have("points_fit")
        self.box("Pt block", [40, 40, 20], [200, 0, 0])
        self.ok("points_sample", {"object": "Pt block", "count": 3000, "noise": 0.01, "name": "Pt cloud"})
        top = self.ok("points_crop", {"points": "Pt cloud", "box": [[200, 0, 19.9], [240, 40, 20.1]], "replace": False, "name": "Pt top"})
        self.assertGreater(top["points"], 100)
        f = self.ok("points_fit", {"points": "Pt top", "shape": "plane", "tolerance": 0.1})
        self.assertGreater(abs(f["normal"][2]), 0.999)
        self.assertEqual(f["verdict"], "fits")
        e = self.ok("points_export", {"points": "Pt top", "path": "top.ply"})
        back = self.ok("points_import", {"path": e["path"], "name": "Pt back"})
        self.assertEqual(back["points"], top["points"])

    def test_points_hardening(self):
        # Fixes of the hardening pass (private records: bimcam-findings.md), on shapes of known size.
        import FreeCAD

        self.have("points_fit")
        self.ok("part_primitive", {"kind": "cylinder", "radius": 10, "height": 40, "at": [600, 0, 0], "name": "Ph cyl"})
        doc = self.session.doc
        s0 = self.ok("points_sample", {"object": "Ph cyl", "count": 6000, "name": "Ph cloud"})
        self.assertEqual(s0["points"], 6000)
        self.assertAlmostEqual(s0["min"][0], 590, delta=0.2)
        # A placed cloud is read where it stands: the kernel carries the Placement already
        # (Points::Feature::onChanged), so 100 mm along X moves the reading 100, not 200.
        cloud = doc.getObjectsByLabel("Ph cloud")[0]
        cloud.Placement = FreeCAD.Placement(FreeCAD.Vector(100, 0, 0), FreeCAD.Rotation())
        doc.recompute()
        moved = self.ok("points_info", {"points": "Ph cloud"})
        self.assertAlmostEqual(moved["min"][0], s0["min"][0] + 100, delta=0.001)
        self.assertAlmostEqual(moved["centre"][0], 700, delta=0.5)
        # The wall alone (the caps cropped off) fits back to the cylinder it came from.
        wall = self.ok("points_crop", {"points": "Ph cloud", "box": [[680, -20, 2], [720, 20, 38]], "replace": False, "name": "Ph wall"})
        self.assertGreater(wall["kept"], 1000)
        self.assertAlmostEqual(wall["min"][0], 690, delta=0.3)
        f = self.ok("points_fit", {"points": "Ph wall", "shape": "cylinder", "tolerance": 0.05, "make": True, "name": "Ph fit"})
        self.assertAlmostEqual(f["radius"], 10, delta=0.02)
        self.assertAlmostEqual(f["diameter"], 20, delta=0.04)
        self.assertGreater(abs(f["axis"][2]), 0.9999)
        self.assertAlmostEqual(f["length"], 36, delta=0.5)
        self.assertAlmostEqual(f["base"][0], 700, delta=0.05)
        self.assertEqual(f["verdict"], "fits")
        self.assertEqual(f["body"], "Ph fit")
        # every format is read back with its own reader: the count holds
        for ext, err in (("ply", 1e-3), ("pcd", 1e-5), ("asc", 1e-5), ("csv", 1e-5)):
            e = self.ok("points_export", {"points": "Ph wall", "path": f"ph.{ext}"})
            self.assertEqual(e["readBack"], e["count"], ext)
            self.assertEqual(e["count"], wall["kept"], ext)
            self.assertLess(e["maxError"], err, ext)
            self.assertNotIn("warning", e)
            back = self.ok("points_import", {"path": e["path"], "name": f"Ph back {ext}"})
            self.assertEqual(back["points"], wall["kept"], ext)
            self.assertAlmostEqual(back["min"][0], wall["min"][0], delta=0.01)
        m = self.ok("points_merge", {"points": ["Ph back ply", "Ph back csv"], "name": "Ph both"})
        self.assertEqual(m["points"], "Ph both")
        self.assertEqual(m["count"], 2 * wall["kept"])
        self.refused("points_crop", {"points": "Ph wall"})
        self.refused("points_crop", {"points": "Ph wall", "outside": True})
        self.refused("points_fit", {"points": "Ph wall", "shape": "cone"})
        self.refused("points_import", {"path": "ph.ply", "scale": 0})
        self.refused("points_export", {"points": "Ph wall", "path": "ph.stl"})
        self.refused("points_merge", {"points": ["Ph wall", "Ph wall"]})

    def test_points_mesh_curve(self):
        self.have("points_mesh")
        self.box("Pm plate", [60, 40, 10], [0, 300, 0])
        self.ok("points_sample", {"object": "Pm plate", "count": 6000, "name": "Pm cloud"})
        self.ok("points_crop", {"points": "Pm cloud", "box": [[0, 300, 9.9], [60, 340, 10.1]], "replace": False, "name": "Pm top"})
        m = self.ok("points_mesh", {"points": "Pm top"})
        self.assertGreater(m["area"], 2400 * 0.85)
        self.assertLess(m["area"], 2400 * 1.02)
        self.ok("part_primitive", {"kind": "cylinder", "radius": 20, "height": 30, "at": [200, 300, 0], "name": "Pm cyl"})
        self.ok("points_sample", {"object": "Pm cyl", "count": 8000, "name": "Pm cc"})
        self.ok("points_crop", {"points": "Pm cc", "box": [[150, 270, 14.8], [250, 330, 15.2]], "replace": False, "name": "Pm ring"})
        c = self.ok("points_fit", {"points": "Pm ring", "shape": "curve", "tolerance": 0.3})
        self.assertTrue(c["closed"])
        self.assertAlmostEqual(c["length"], 2 * 3.14159 * 20, delta=2)

    def test_surface(self):
        self.have("surface_sew")
        self.box("Sf cube", [20, 20, 20], [300, 0, 0])
        out = self.ok("surface_sew", {"faces": [f"Sf cube.Face{i}" for i in range(1, 7)], "solid": True})
        self.assertTrue(out["closed"])
        self.assertAlmostEqual(out["solid"]["volume"], 8000, delta=0.5)

    def test_surface_hardening(self):
        """The hardening pass (16 Nov 2026), from FreeCAD 1.1's Surface sources:
        a 40 x 30 frame of four lines, two of them drawn backwards."""
        self.have("surface_sew")
        y0 = 600
        for name, p, q in (("Sh a", [0, y0, 0], [40, y0, 0]), ("Sh b", [40, y0 + 30, 0], [40, y0, 0]),
                           ("Sh c", [40, y0 + 30, 0], [0, y0 + 30, 0]), ("Sh d", [0, y0, 0], [0, y0 + 30, 0])):
            self.ok("part_wire", {"kind": "line", "from": p, "to": q, "name": name})
        frame = ["Sh a", "Sh b", "Sh c", "Sh d"]
        b = self.ok("surface_boundary", {"edges": frame, "name": "Sh patch"})
        self.assertAlmostEqual(b["area"], 1200, delta=0.01)
        self.assertEqual((b["fill"], b["sides"]), ("stretched", 4))
        # Not going round: refused before FreeCAD is asked.
        err, out = self.call("surface_boundary", {"edges": ["Sh a", "Sh c", "Sh b", "Sh d"]})
        self.assertTrue(err)
        self.assertIn("end to end", str(out))
        self.ok("part_wire", {"kind": "line", "from": [100, y0, 0], "to": [110, y0, 0], "name": "Sh e"})
        err, out = self.call("surface_boundary", {"edges": frame + ["Sh e"]})
        self.assertTrue(err)
        self.assertIn("these are 5", str(out))
        # Through two opposite sides running the same way: the same rectangle (Sh c runs back, which would twist it).
        self.ok("part_wire", {"kind": "line", "from": [0, y0 + 30, 0], "to": [40, y0 + 30, 0], "name": "Sh h"})
        sec = self.ok("surface_sections", {"sections": ["Sh a", "Sh h"], "name": "Sh ruled"})
        self.assertEqual(sec["sections"], 2)
        self.assertAlmostEqual(sec["area"], 1200, delta=0.5)
        # Filled across the four: one closed run. A fifth edge apart from it is a second run.
        f = self.ok("surface_fill", {"edges": frame, "name": "Sh filled"})
        self.assertAlmostEqual(f["area"], 1200, delta=0.01)
        err, out = self.call("surface_fill", {"edges": frame + ["Sh e"]})
        self.assertTrue(err)
        self.assertIn("2 separate runs", str(out))
        err, out = self.call("surface_fill", {"edges": frame[:3]})
        self.assertTrue(err)
        self.assertIn("mm apart", str(out))
        # Run on 10% at each end, both ways: 48 x 36.
        ex = self.ok("surface_extend", {"face": "Sh patch.Face1", "u": 0.1, "v": 0.1, "name": "Sh wider"})
        self.assertAlmostEqual(ex["area"], 48 * 36, delta=1.0)
        err, out = self.call("surface_extend", {"face": "Sh patch.Face1", "u": 20})
        self.assertTrue(err)
        # Cut by a solid over its right half: 20 x 30 left. By a surface: nothing removed, and said.
        self.box("Sh block", [40, 60, 20], [20, y0 - 10, -10])
        cut = self.ok("surface_cut", {"surface": "Sh patch", "by": "Sh block", "name": "Sh half"})
        self.assertAlmostEqual(cut["area"], 600, delta=0.01)
        self.assertNotIn("note", cut)
        # Five of a cube's six faces: a shell, open, so no solid; the reason counts the free edges.
        self.box("Sh cube", [20, 20, 20], [300, y0, 0])
        op = self.ok("surface_sew", {"faces": [f"Sh cube.Face{i}" for i in range(1, 6)], "solid": True, "name": "Sh open"})
        self.assertFalse(op["closed"])
        self.assertIn("not made", op["solid"])
        self.assertIn("4 edge(s)", op["solid"])
        # A blend from the end of one line to the start of another at right angles: one edge, longer than the chord.
        self.ok("part_wire", {"kind": "line", "from": [200, y0, 0], "to": [210, y0, 0], "name": "Sh f"})
        self.ok("part_wire", {"kind": "line", "from": [220, y0 + 10, 0], "to": [220, y0 + 20, 0], "name": "Sh g"})
        bl = self.ok("surface_blend", {"start": {"edge": "Sh f", "at": 1, "continuity": 1}, "end": {"edge": "Sh g", "at": 0, "continuity": 1}, "name": "Sh blend"})
        self.assertEqual((bl["faces"], bl["edges"]), (0, 1))
        self.assertGreater(bl["length"], 14.14)
        self.assertLess(bl["length"], 40)
        err, out = self.call("surface_blend", {"start": {"edge": "Sh f", "size": 0}, "end": {"edge": "Sh g"}})
        self.assertTrue(err)
        self.assertIn("size", str(out))

    def test_bim(self):
        self.have("bim_wall")
        w = self.ok("bim_wall", {"points": [[0, 1000], [5000, 1000]], "width": 200, "height": 3000, "name": "B wall"})
        self.assertAlmostEqual(w["volume_m3"], 3.0, delta=0.01)
        o = self.ok("bim_opening", {"wall": "B wall", "kind": "door", "at": 1000})
        self.assertGreater(o["wallCut_m3"], 0.3)
        self.refused("bim_opening", {"wall": "B wall", "kind": "window", "at": 4800, "width": 1000})
        slab = self.ok("bim_structure", {"kind": "slab", "points": [[0, 0], [5000, 0], [5000, 3000], [0, 3000]], "thickness": 200, "name": "B slab"})
        self.assertAlmostEqual(slab["volume_m3"], 3.0, delta=0.01)
        r = self.ok("bim_rebar", {"structure": "B slab", "along": "x", "spacing": 200})
        self.assertLessEqual(r["spacing"], 200)
        sch = self.ok("bim_schedule", {})
        kinds = {row["kind"] for row in sch["rows"]}
        self.assertTrue({"wall", "slab", "door", "rebar"} <= kinds)

    def test_openscad(self):
        self.have("scad_op")
        # two boxes apart: their hull is the box round both, 40 × 10 × 10
        self.box("Sc a", [10, 10, 10], [500, 0, 0])
        self.box("Sc b", [10, 10, 10], [530, 0, 0])
        h = self.unavailable_skip("scad_op", {"op": "hull", "objects": ["Sc a", "Sc b"]})
        self.assertAlmostEqual(h["volume"], 4000, delta=1)
        self.box("Sc box", [10, 20, 30], [600, 0, 0])
        e = self.ok("scad_export", {"objects": ["Sc box"], "path": "box.csg"})
        with open(e["path"]) as f:
            self.assertIn("cube", f.read())

    def test_robot(self):
        self.have("robot_new")
        self.ok("robot_new", {"model": "puma", "name": "R1"})
        m = self.ok("robot_move", {"robot": "R1", "tcp": {"at": [1000, 200, 800], "ypr": [0, 90, 0]}})
        self.assertTrue(m["reached"])
        self.ok("robot_path", {"name": "R path", "waypoints": [{"at": [1000, 0, 800], "ypr": [0, 90, 0], "speed": 100}, {"at": [1000, 300, 800], "ypr": [0, 90, 0], "speed": 100}]})
        run = self.ok("robot_run", {"robot": "R1", "trajectory": "R path", "samples": 10})
        self.assertEqual(run["verdict"], "reaches all")
        k = self.ok("robot_export", {"robot": "R1", "trajectory": "R path", "path": "r.src"})
        self.assertEqual(k["moves"], 2)

    def test_robot_hardening(self):
        # From FreeCAD's Robot sources: a point the arm cannot reach leaves the
        # axes as they were (robot_run said "reaches all" for any path, since
        # the Tcp property keeps the value asked for); the dress-up's own name
        # for adding an orientation is "AddOrintation"; the edge trajectory's
        # type is Robot::Edge2TracObject; the robot with no kinematics file is
        # FreeCAD's default, not a Puma.
        self.have("robot_new")
        n = self.ok("robot_new", {"model": "puma", "name": "Rh"})
        self.assertIn("default", n["model"])
        # the tool point at the home pose, not [0, 0, 0] until the first move (live finding)
        self.assertGreater(n["tcp"]["at"][0], 1000)
        fwd = self.ok("robot_move", {"robot": "Rh", "axes": [0, -90, 90, 0, 0, 0]})
        for got, want in zip(fwd["tcp"]["at"], [1825, 0, 2400]):
            self.assertAlmostEqual(got, want, delta=0.5)
        far = self.ok("robot_move", {"robot": "Rh", "tcp": {"at": [9000, 0, 0], "ypr": fwd["tcp"]["ypr"]}})
        self.assertFalse(far["reached"])
        self.assertGreater(far["off_mm"], 1000)
        self.ok("robot_path", {"name": "Rh far", "waypoints": [{"at": [9000, 0, 0], "speed": 100}, {"at": [9000, 500, 0], "speed": 100}]})
        run = self.ok("robot_run", {"robot": "Rh", "trajectory": "Rh far", "samples": 5})
        self.assertTrue(run["verdict"].startswith("misses"), run)
        self.ok("robot_path", {"name": "Rh near", "waypoints": [{"at": [1825, 0, 2400], "ypr": fwd["tcp"]["ypr"], "speed": 100}, {"at": [1825, 100, 2400], "ypr": fwd["tcp"]["ypr"], "speed": 100}]})
        self.ok("robot_trajectory", {"op": "dress", "trajectory": "Rh near", "ypr": [10, 0, 0], "name": "Rh turned"})
        add = self.ok("object_get", {"object": "Rh turned", "filter": ["AddType"]})["properties"]["AddType"]["value"]
        self.assertEqual(add, "AddOrintation")
        self.ok("robot_trajectory", {"op": "dress", "trajectory": "Rh near", "move": [0, 0, -50], "ypr": [10, 0, 0], "name": "Rh both"})
        add = self.ok("object_get", {"object": "Rh both", "filter": ["AddType"]})["properties"]["AddType"]["value"]
        self.assertEqual(add, "AddPositionAndOrientation")
        self.refused("robot_trajectory", {"op": "dress", "trajectory": "Rh near", "move": [0, 0, 1], "add": "Sideways"})
        self.box("Rh rail", [200, 10, 10], [1500, 0, 2000])
        e = self.ok("robot_path", {"name": "Rh edge", "edges": ["Rh rail.Edge1"]})
        self.assertGreaterEqual(e["waypoints"], 2)
        err, out = self.call("robot_export", {"robot": "Rh", "trajectory": "Rh near", "path": "rh_full.src", "full": True})
        if err:
            self.assertEqual(out["error"]["code"], "unavailable", out)
        self.refused("robot_move", {"robot": "Rh", "axes": [0, 0, 0, 0, 0, 0], "home": True})

    def test_openscad_round_trip(self):
        # CSG out and in again needs only FreeCAD: a 20 x 30 x 10 box keeps its volume.
        self.have("scad_export")
        self.box("Rt box", [20, 30, 10])
        e = self.ok("scad_export", {"objects": ["Rt box"], "path": "rt_box.csg"})
        err, out = self.call("scad_import", {"path": e["path"]})
        if err and out["error"]["code"] == "unavailable":
            self.skipTest(out["error"]["message"])
        self.assertFalse(err, out)
        self.assertAlmostEqual(max(m.get("volume", 0) for m in out["made"]), 6000, delta=0.01)
        self.refused("scad_import", {"path": "rt_box.stl"})

    def test_openscad_never_searches(self):
        # FreeCAD's own search for OpenSCAD (Finder through AppleScript on a
        # Mac, no time limit) is never run: the plain one stands in its place
        # in every loaded copy of the module, and the reader's own window
        # switch is back as it was after an import.
        self.have("scad_import")
        import sys

        import FreeCAD

        from agentlink.families import openscad

        up = FreeCAD.GuiUp
        self.box("Ns box", [20, 30, 10])
        e = self.ok("scad_export", {"objects": ["Ns box"], "path": "ns_box.csg"})
        err, out = self.call("scad_import", {"path": e["path"]})
        if err and out["error"]["code"] == "unavailable":
            self.skipTest(out["error"]["message"])
        self.assertFalse(err, out)
        self.assertEqual(out["objects"], 1, out)
        self.assertEqual(FreeCAD.GuiUp, up)
        for name in openscad.SEARCHERS:
            m = sys.modules.get(name)
            if m is not None:
                self.assertIs(m.searchforopenscadexe, openscad._search, name)
        self.assertIn("OpenSCADUtils", sys.modules)
        import importCSG

        self.assertEqual(bool(importCSG.gui), bool(up))
        self.assertEqual(importCSG.original_root_objects, [])
        # a file whose hull only the OpenSCAD program can work out: refused before anything is read
        if openscad.exe() is None:
            p = os.path.join(os.path.dirname(e["path"]), "ns_hull.csg")
            with open(p, "w", encoding="utf-8") as f:
                f.write("hull() {\n cube(size = [10, 10, 10], center = false);\n multmatrix([[1, 0, 0, 30], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) {\n  cube(size = [10, 10, 10], center = false);\n }\n}\n")
            before = len(self.session.doc.Objects)
            err, out = self.call("scad_import", {"path": p})
            self.assertTrue(err, out)
            self.assertEqual(out["error"]["code"], "unavailable", out)
            self.assertIn("hull", out["error"]["message"])
            self.assertEqual(len(self.session.doc.Objects), before)

    def test_gear(self):
        self.have("pd_gear")
        self.ok("pd_body_new", {"name": "Gear body"})
        g = self.ok("pd_gear", {"body": "Gear body", "teeth": 20, "module": 2, "thickness": 8, "bore": 8})
        self.assertAlmostEqual(g["pitchDiameter"], 40)
        self.assertAlmostEqual(g["box"][0], 44, delta=0.1)

    def test_fea_probe(self):
        self.have("fea_probe")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        self.box("Fe beam", [100, 20, 10], [0, 500, 0])
        self.ok("fea_setup", {"body": "Fe beam", "material": "PLA", "mesh": 3})
        self.ok("fea_hold", {"faces": {"normal": [-1, 0, 0]}})
        self.ok("fea_load", {"faces": {"normal": [1, 0, 0]}, "force": [0, 0, -20]})
        self.ok("fea_solve", {})
        p = self.ok("fea_probe", {"points": [[50, 510, 10]]})
        # beam theory: 20 N × 50 mm × 5 mm / (20 × 10³ / 12) = 3.0 MPa at the top fibre
        self.assertAlmostEqual(p["points"][0]["vonMisesMPa"], 3.0, delta=0.4)
        # FreeCAD 1.1's post-processing charts, headless.
        h = self.ok("fea_chart", {"kind": "histogram", "bins": 10})
        self.assertTrue(os.path.getsize(h["svg"]) > 500)
        with open(h["csv"]) as f:
            bins = [ln.split(",") for ln in f.read().strip().splitlines()[1:]]
        self.assertEqual(len(bins), 10)
        self.assertEqual(sum(int(b[2]) for b in bins), h["nodes"])
        self.assertLessEqual(h["median"], h["p95"])
        self.assertLessEqual(h["p95"], h["max"])
        ln = self.ok("fea_chart", {"kind": "line", "line": {"from": [0, 510, 10], "to": [100, 510, 10], "samples": 11}})
        self.assertEqual(ln["samples"], 11)
        self.assertTrue(os.path.exists(ln["svg"]))
        t = self.ok("fea_chart", {"kind": "table", "points": [[50, 510, 10], [90, 510, 10]], "field": "displacement"})
        self.assertEqual(len(t["table"]), 3)
        self.assertAlmostEqual(t["table"][1][3], p["points"][0]["vonMisesMPa"], delta=1e-6)
        err, _ = self.call("fea_chart", {"kind": "line"})
        self.assertTrue(err)

    def test_fea_thermal(self):
        self.have("fea_probe")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        self.box("Th bar", [100, 10, 10], [0, 700, 0])
        self.ok("fea_setup", {"body": "Th bar", "material": "PLA", "mesh": 3})
        self.ok("fea_hold", {"faces": {"normal": [-1, 0, 0]}})
        self.ok("fea_load", {"temperature": 50, "alpha": 68e-6})
        free = self.ok("fea_solve", {})
        self.assertAlmostEqual(free["displacementMax"]["mm"], 100 * 68e-6 * 50, delta=0.02)  # L·alpha·dT
        self.ok("fea_hold", {"faces": {"normal": [1, 0, 0]}})
        self.ok("fea_solve", {})
        mid = self.ok("fea_probe", {"points": [[50, 705, 5]]})["points"][0]["vonMisesMPa"]
        self.assertAlmostEqual(mid, 3500 * 68e-6 * 50, delta=1.5)  # E·alpha·dT

    def test_fea_spin(self):
        self.have("fea_probe")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        # a quarter of a spinning PLA disk on symmetry slides: centre (3+nu)/8 rho w2 R2
        self.ok("part_primitive", {"kind": "cylinder", "radius": 100, "height": 5, "name": "Sp disk"})
        self.box("Sp q", [120, 120, 10], [0, 0, -2])
        self.ok("part_boolean", {"op": "common", "body": "Sp disk", "bodies": ["Sp q"]})
        self.ok("fea_setup", {"body": "Sp disk", "material": "PLA", "mesh": 5})
        for n in ([-1, 0, 0], [0, -1, 0], [0, 0, -1]):
            self.ok("fea_hold", {"faces": {"normal": n}, "kind": "slide"})
        self.ok("fea_load", {"spin": {"rpm": 10000}})
        r = self.ok("fea_solve", {})
        w2 = (10000 * 2 * 3.14159265 / 60) ** 2
        rho = 1.24e-9
        self.assertAlmostEqual(r["vonMisesMax"]["MPa"], (3.36 / 8) * rho * w2 * 1e4, delta=0.6)

    def test_techdraw_marks_hatch(self):
        self.have("td_hatch")
        self.box("Td plate", [60, 40, 10], [0, 1000, 0])
        self.ok("part_primitive", {"kind": "cylinder", "radius": 6, "height": 10, "at": [30, 1020, 0], "name": "Td hole"})
        self.ok("part_boolean", {"op": "cut", "body": "Td plate", "bodies": ["Td hole"], "name": "Td holed"})
        self.ok("td_page", {"action": "new", "paper": "A4", "name": "Td sheet"})
        self.ok("td_view", {"page": "Td sheet", "bodies": ["Td holed"], "direction": "top", "name": "Td top"})
        m = self.ok("td_centermarks", {"views": ["Td top"]})
        self.assertEqual(m["views"][0]["circles"], 1)
        top = self.ok("shape_query", {"body": "Td holed", "normal": [0, 0, 1]})["items"][0]["ref"]
        h = self.ok("td_hatch", {"view": "Td top", "faces": [top]})
        self.assertNotIn("warning", h)
        ex = self.ok("td_export", {"page": "Td sheet", "formats": ["svg"], "name": "td"})
        with open(ex["files"]["svg"]["path"]) as f:
            svg = f.read()
        self.assertIn("8 1.5 1.5 1.5", svg)  # the centre marks' chain line

    def test_cam_library(self):
        self.have("cam_library")
        self.box("Cm block", [60, 40, 15], [0, 2000, 0])
        self.ok("cam_job", {"body": "Cm block", "tool": {"diameter": 6}, "name": "Cm job"})
        e = self.ok("cam_library", {"job": "Cm job", "action": "export", "path": "tools.json"})
        with open(e["path"]) as f:
            data = json.load(f)
        self.assertEqual(data["tools"][0]["diameter"], 6.0)



    def test_part_more(self):
        self.box("Pm B", [40, 30, 20], [500, 0, 0])
        self.ok("part_primitive", {"kind": "cylinder", "radius": 5, "height": 40, "at": [520, 15, -10], "name": "Pm C"})
        self.ok("part_boolean", {"op": "cut", "body": "Pm B", "bodies": ["Pm C"]})
        sec = self.ok("part_section", {"body": "Pm B", "plane": {"normal": [0, 0, 1], "at": [0, 0, 10]}, "face": True})
        self.assertAlmostEqual(sec["area_mm2"], 1200 - 78.54, delta=0.1)
        self.ok("part_wire", {"kind": "polygon", "sides": 6, "radius": 10, "name": "Pm hex"})
        band = self.ok("part_offset2d", {"shape": "Pm hex", "distance": 2, "fill": True})
        self.assertAlmostEqual(band["area_mm2"], 120 + 3.14159 * 4, delta=0.1)
        d = self.ok("part_defeature", {"body": "Pm B", "faces": ["Face7"], "name": "Pm plain"})
        self.assertAlmostEqual(d["volume_mm3"], 24000, delta=0.5)
        faces = [f"Pm plain.Face{i}" for i in range(1, 7)]
        sol = self.ok("part_extract", {"refs": faces, "build": "solid", "name": "Pm rebuilt"})
        self.assertEqual(sol["solids"], 1)
        r = self.ok("part_fix", {"body": "Pm rebuilt", "op": "reverse"})
        self.assertLess(r["volume_mm3"], 0)
        self.box("Pm datum box", [10, 10, 20], [600, 0, 0])
        dt = self.ok("part_datum", {"kind": "csys", "to": "Pm datum box.Face6", "at": [5, 0, 0]})
        self.assertEqual(dt["placement"]["at"][2], 20.0)

    def test_mesh_more(self):
        self.have("meshobj_boundary")
        c = self.ok("meshobj_primitive", {"kind": "cylinder", "radius": 5, "height": 20, "at": [0, 900, 0], "name": "Mm cyl"})
        self.assertEqual(c["box"], [10.0, 10.0, 20.0])
        t = self.ok("meshobj_primitive", {"kind": "torus", "radius": 10, "radius2": 2, "at": [50, 900, 0], "name": "Mm torus"})
        self.assertAlmostEqual(t["box"][2], 4.0, delta=0.01)
        self.ok("meshobj_trim", {"mesh": "Mm cyl", "at": [0, 900, 15], "normal": [0, 0, 1]})
        b = self.ok("meshobj_boundary", {"mesh": "Mm cyl"})
        self.assertEqual(b["loops"], 1)
        self.assertAlmostEqual(b["boundaries"][0]["centre"][2], 15.0, delta=0.01)
        m = self.ok("meshobj_merge", {"meshes": ["Mm cyl", "Mm torus"]})
        self.assertEqual(m["components"], 2)

    def test_bim_more(self):
        self.have("bim_preflight")
        self.ok("bim_wall", {"points": [[0, 3000], [5000, 3000]], "height": 3000, "width": 200, "name": "Bm wall"})
        self.ok("bim_structure", {"kind": "slab", "points": [[0, 5000], [3000, 5000], [3000, 7000], [0, 7000]], "thickness": 200, "name": "Bm slab"})
        c = self.unavailable_skip("bim_covering", {"face": "Bm slab.Face6", "tile": [300, 300], "thickness": 10, "joint": 3})
        if "tiles" in c:
            self.assertAlmostEqual(c["volume_m3"], 6.0 * 0.98 * 0.01, delta=0.002)
        lay = self.ok("bim_layers", {"layers": [{"material": "Bm brick", "thickness": 215, "density": 1900}, {"material": "Bm plaster", "thickness": 13, "density": 1200}], "objects": ["Bm wall"]})
        self.assertEqual(lay["total_mm"], 228.0)
        q = self.ok("bim_quantities", {"by": "material"})
        self.assertIn("Layers", q["groups"])
        i = self.ok("bim_ifc", {"objects": ["Bm wall"], "properties": {"Pset_WallCommon.FireRating": "REI60"}})
        self.assertEqual(i["objects"][0]["properties"]["Pset_WallCommon"]["FireRating"], "REI60")
        cut = self.ok("bim_edit", {"op": "cut", "object": "Bm wall", "at": [0, 0, 2500], "normal": [0, 0, 1]})
        self.assertGreater(cut["removed_m3"], 0.2)
        pf = self.ok("bim_preflight", {})
        self.assertFalse(pf["ok"])

    def test_techdraw_cosmetics(self):
        self.have("td_cosmetic")
        self.ok("part_primitive", {"kind": "cylinder", "radius": 10, "height": 60, "at": [0, 0, 1200], "name": "Tc shaft"})
        self.ok("part_transform", {"op": "rotate", "body": "Tc shaft", "axis": [0, 1, 0], "angle": 90, "about": [0, 0, 1200]})
        self.ok("td_page", {"action": "new", "paper": "A4", "name": "Tc page"})
        self.ok("td_view", {"page": "Tc page", "bodies": ["Tc shaft"], "direction": "front", "scale": 2, "at": [110, 150], "name": "Tc front"})
        self.ok("td_view", {"page": "Tc page", "bodies": ["Tc shaft"], "direction": "right", "scale": 2, "at": [220, 150], "name": "Tc end"})
        g = self.ok("td_geometry", {"view": "Tc front", "kind": "lines"})
        lines = [i["ref"] for i in g["items"] if i["kind"] == "line"]
        c = self.ok("td_cosmetic", {"view": "Tc front", "items": [{"kind": "centerline", "edges": lines[:2]}, {"kind": "thread", "edges": lines[:2], "length": 25}]})
        self.assertEqual(c["made"][1]["note"], "M20x2.5")
        self.ok("td_finish", {"view": "Tc front", "on": lines[0], "ra": "0.8", "process": "ground"})
        a = self.ok("td_area", {"view": "Tc end", "face": "Tc shaft.Face2"})
        self.assertAlmostEqual(a["area"], 314.159, delta=0.01)
        out = self.ok("td_export", {"page": "Tc page", "formats": ["svg"], "name": "tc"})
        with open(out["files"]["svg"]["path"]) as f:
            self.assertIn("Ra 0.8", f.read())
        # the page goes, so later tests find one page as before
        page = next(o for o in self.session.doc.Objects if o.Label == "Tc page")
        for v in list(page.Views):
            self.session.doc.removeObject(v.Name)
        self.session.doc.removeObject(page.Name)

    def test_cam_edit(self):
        self.have("cam_edit")
        self.box("Ce block", [40, 30, 10], [0, 1500, 0])
        self.ok("cam_job", {"body": "Ce block", "tool": {"diameter": 6}, "name": "Ce job"})
        self.ok("cam_op", {"job": "Ce job", "kind": "profile", "side": "outside", "name": "Ce outline"})
        self.ok("cam_edit", {"job": "Ce job", "action": "copy", "op": "Ce outline", "name": "Ce rough"})
        st = self.ok("cam_edit", {"job": "Ce job", "action": "stop", "text": "check part", "after": "Ce rough"})
        self.assertIn("M0", st["gcode"])
        off = self.ok("cam_edit", {"job": "Ce job", "action": "active", "op": "Ce rough", "on": False})
        self.assertIn("Ce rough (off)", off["ops"])
        post = self.ok("cam_post", {"job": "Ce job", "path": "ce.nc"})
        with open(post["path"]) as f:
            self.assertIn("M0", f.read())

    def test_sketch_more(self):
        self.have("sketch_merge")
        self.ok("pd_body_new", {"name": "Sm body"})
        self.ok("sketch_new", {"body": "Sm body", "plane": "XY", "name": "Sm s1"})
        r = self.ok("sketch_add", {"sketch": "Sm s1", "items": [{"kind": "arc3", "points": [[0, 0], [10, 10], [20, 0]]}, {"kind": "parabola", "vertex": [0, 40], "focal": 5},
                                                                 {"kind": "bspline", "points": [[0, 80], [20, 90], [40, 80], [60, 95]]}]})
        ov = r["state"]["openVertices"]
        self.assertIn([5.0, 50.0], ov)
        b = self.ok("sketch_bspline", {"sketch": "Sm s1", "geo": 2, "op": "degree", "by": 1})
        self.assertEqual(b["degree"], 4)
        self.ok("sketch_new", {"body": "Sm body", "plane": "XY", "name": "Sm s2"})
        self.ok("sketch_add", {"sketch": "Sm s2", "items": [{"kind": "rectangle", "corner": [100, 0], "size": [20, 10]}]})
        m = self.ok("sketch_merge", {"sketches": ["Sm s1", "Sm s2"]})
        self.assertEqual(m["geometry"], 7)
        self.ok("sketch_attach", {"sketch": "Sm s2", "plane": "XZ", "offset": 5})

    def test_robot_trajectory(self):
        self.have("robot_trajectory")
        self.ok("robot_new", {"name": "Rt robot"})
        self.ok("robot_path", {"waypoints": [{"at": [400, 0, 400], "type": "PTP"}, {"at": [400, 200, 400], "type": "LIN", "speed": 100}], "name": "Rt t1"})
        self.ok("robot_path", {"waypoints": [{"at": [400, 200, 300], "type": "LIN"}, {"at": [400, 0, 300], "type": "LIN", "speed": 100}], "name": "Rt t2"})
        j = self.ok("robot_trajectory", {"op": "join", "trajectories": ["Rt t1", "Rt t2"]})
        self.assertEqual(j["waypoints"], 4)
        d = self.ok("robot_trajectory", {"op": "dress", "trajectory": "Rt t1", "speed": 50, "move": [0, 0, -100], "name": "Rt dressed"})
        r = self.ok("robot_run", {"robot": "Rt robot", "trajectory": "Rt dressed"})
        for ax in r["axes"]:
            self.assertGreaterEqual(ax["from"], -180.0)
            self.assertLessEqual(ax["to"], 180.0)

    def test_fea_parts(self):
        self.have("fea_parts")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        self.box("Fp base", [20, 20, 20], [0, 0, 1800])
        self.box("Fp top", [20, 20, 20], [0, 0, 1820])
        res = {}
        for how in ("tie", "contact"):
            p = self.ok("fea_parts", {"bodies": ["Fp base", "Fp top"], "materials": {"Fp base": "pla", "Fp top": "petg"}, "join": how, "mesh": 5})
            self.assertEqual(len(p["touching"]), 1)
            self.ok("fea_hold", {"faces": {"normal": [0, 0, -1], "z": 1800}})
            for n in ([-1, 0, 0], [0, -1, 0]):
                self.ok("fea_hold", {"faces": {"normal": n}, "kind": "slide"})
            self.ok("fea_load", {"faces": {"normal": [0, 0, 1], "z": 1840}, "pressure": 1})
            r = self.ok("fea_solve", {})
            res[how] = r
            self.assertEqual({x["body"] for x in r["parts"]}, {"Fp base", "Fp top"})
        # in series: 20/E_pla + 20/E_petg under 1 MPa, held both ways nearly alike
        expect = 20 / 3500 + 20 / 2100
        for how, r in res.items():
            self.assertAlmostEqual(r["displacementMax"]["mm"], expect, delta=expect * 0.15, msg=how)

    def test_fea_shell(self):
        self.have("fea_shell")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        self.box("Sh slab", [200, 200, 5], [0, 0, 2400])
        self.ok("part_extract", {"refs": ["Sh slab.Face6"], "name": "Sh plate"})
        D = 3500 * 5 ** 3 / (12 * (1 - 0.36 ** 2))
        for kind, alpha in (("pinned", 0.00406), ("fixed", 0.00126)):
            r = self.ok("fea_shell", {"object": "Sh plate", "thickness": 5, "material": "pla", "holds": [{"edges": "boundary", "kind": kind}], "pressure": 0.001, "mesh": 10})
            want = alpha * 0.001 * 200 ** 4 / D
            self.assertAlmostEqual(r["deflectionMaxMm"], want, delta=want * 0.1, msg=kind)


    def test_ifc_in_place(self):
        self.have("ifc_open")
        self.ok("bim_wall", {"points": [[0, 20000], [5000, 20000]], "height": 2700, "width": 200, "name": "If wall"})
        self.ok("bim_level", {"objects": ["If wall"], "name": "If level"})
        e = self.unavailable_skip("bim_export", {"objects": ["If level"], "path": "if.ifc"})
        self.ok("ifc_open", {"path": e["path"]})
        w = self.ok("ifc_find", {"class": "IfcWall", "name": "If wall"})
        self.assertEqual(w["count"], 1)
        self.ok("ifc_edit", {"ids": [w["elements"][0]["id"]], "properties": {"Pset_WallCommon.FireRating": "REI60"}, "material": "Block",
                             "classification": {"system": "Uniclass", "code": "EF_25_10", "title": "Walls"}})
        s = self.ok("ifc_save", {"path": "if_edited.ifc"})
        d = self.ok("ifc_diff", {"a": e["path"], "b": s["path"]})
        ch = d["changed"][0]["changes"]
        self.assertEqual(ch["Pset_WallCommon.FireRating"][1], "REI60")
        self.assertEqual(ch["material"][1], "Block")


    def test_asm_motion_and_draft_extras(self):
        self.have("asm_motion")
        self.box("Am plate", [100, 100, 5], [0, 3000, 0])
        self.box("Am post", [10, 10, 20], [70, 3045, 5])
        self.box("Am arm", [60, 6, 5], [20, 3047, 5])
        self.ok("asm_new", {"parts": ["Am plate", "Am post", "Am arm"], "name": "Am asm"})
        self.ok("asm_ground", {"assembly": "Am asm", "part": "Am post"})
        self.ok("asm_joint", {"assembly": "Am asm", "kind": "revolute", "name": "Am pivot", "a": {"part": "Am plate", "element": {"kind": "face", "normal": [0, 0, 1]}},
                              "b": {"part": "Am arm", "element": {"kind": "face", "normal": [0, 0, -1]}}, "reverse": False})
        self.ok("asm_motion", {"assembly": "Am asm", "action": "save", "name": "Am swing", "keys": [{"Am pivot": 30}, {"Am pivot": 150}]})
        p = self.ok("asm_motion", {"action": "play", "name": "Am swing", "steps": 4})
        self.assertEqual(p["frames"], 5)
        self.assertEqual(p["verdict"], "clear")
        ex = self.unavailable_skip("asm_export", {"assembly": "Am asm"})
        self.assertGreater(ex["bytes"], 100)
        wp = self.ok("draft_plane", {"face": "Am plate.Face6", "name": "Am top"})
        self.assertEqual(wp["normal"], [0.0, 0.0, 1.0])
        st = self.ok("draft_style", {"action": "set", "name": "Am shop", "values": {"FontSize": 3.5, "Decimals": 1}})
        self.assertEqual(st["values"]["FontSize"], 3.5)


    def test_fea_nonlinear(self):
        self.have("fea_solve")
        import shutil

        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not installed")
        self.box("Fnl bar", [100, 10, 10], [0, 0, 2400])
        self.ok("fea_setup", {"body": "Fnl bar", "material": "pla", "mesh": 3})
        self.ok("fea_hold", {"faces": {"normal": [-1, 0, 0]}})
        # 95 N at the tip: 57 MPa at the root, past PLA's 50 but short of a plastic hinge (~125 N)
        self.ok("fea_load", {"faces": {"normal": [1, 0, 0]}, "force": [0, 0, -95]})
        lin = self.ok("fea_solve", {})
        self.assertTrue(any("nonlinear: true" in w for w in lin["warnings"]))
        r = self.ok("fea_solve", {"nonlinear": True})
        self.assertTrue(r["nonlinear"]["plastic"])
        self.assertGreater(r["nonlinear"]["plasticStrainMax"], 0)
        self.assertFalse(any("linear solve is rough" in w for w in r["warnings"]))

    def test_fea_native_elmer(self):
        self.have("fea_native")
        try:
            import ObjectsFem
        except ImportError:
            self.skipTest("no FEM module")
        if not hasattr(ObjectsFem, "makeSolverElmer"):
            self.skipTest("no Elmer solver object")
        self.box("Fel fin", [60, 20, 10], [0, 0, 2600])
        self.ok("fea_setup", {"body": "Fel fin", "material": "pla", "mesh": 4})
        self.ok("fea_hold", {"faces": {"normal": [-1, 0, 0]}})
        self.ok("fea_load", {"faces": {"normal": [1, 0, 0]}, "force": [0, 0, -200]})
        for bad in ({"solver": "calculix", "equations": ["heat"]},
                    {"solver": "elmer", "equations": ["elasticity"], "temperatures": [{"faces": {"normal": [-1, 0, 0]}, "celsius": 80}]}):
            err, out = self.call("fea_native", bad)
            self.assertTrue(err)
            self.assertEqual(out["error"]["code"], "invalid_input")
        import shutil

        write = bool(shutil.which("gmsh"))
        r = self.ok("fea_native", {"solver": "elmer", "equations": ["elasticity", "heat"], "name": "Fel analysis",
                                   "temperatures": [{"faces": {"normal": [-1, 0, 0]}, "celsius": 80}],
                                   "heat": [{"faces": {"normal": [1, 0, 0]}, "watts": 5}], "write": write})
        self.assertIn("Heatflux", " ".join(r["objects"]))
        self.assertEqual(r["equations"], ["elasticity", "heat"])
        if write:
            sif = open(os.path.join(r["files"], "case.sif")).read()
            self.assertIn("HeatSolver", sif)
            self.assertIn("StressSolver", sif)
            self.assertIn("Heat Conductivity = Real 0.13", sif)
            self.assertIn("Temperature = Real 353.15", sif)
            self.assertTrue(os.path.exists(os.path.join(r["files"], "mesh.unv")))

    def test_notes_and_steps(self):
        self.have("note_add")
        self.box("Nt box", [20, 20, 20], [0, 0, 2800])
        n = self.ok("note_add", {"text": "Is this face the mount?", "body": "Nt box", "faces": {"normal": [0, 0, 1]}})["note"]
        self.assertEqual(n["by"], "agent")
        self.assertAlmostEqual(n["at"][2], 2820, delta=0.01)
        from agentlink.families import notes as nf

        p = nf.add_note(self.session.doc, [1, 2, 3], "Make it 2 mm thicker", "person")
        lst = self.ok("note_list", {})
        self.assertEqual(lst["waiting"], [p["id"]])
        self.ok("note_answer", {"id": p["id"], "text": "Done: 4 mm now"})
        self.ok("note_done", {"id": p["id"]})
        self.assertEqual(len(self.ok("note_list", {"open": True})["notes"]), 1)
        self.ok("note_delete", {"id": n["id"]})
        self.assertEqual(len(self.ok("note_list", {})["notes"]), 1)

        self.ok("pd_body_new", {"name": "St body"})
        self.ok("pd_primitive", {"body": "St body", "kind": "box", "size": {"length": 30, "width": 20, "height": 10}})
        self.ok("pd_primitive", {"body": "St body", "kind": "cylinder", "size": {"radius": 4, "height": 10}, "at": [15, 10, 0], "subtractive": True})
        st = self.ok("steps_list", {"body": "St body"})
        self.assertEqual(st["count"], 2)
        self.assertAlmostEqual(st["steps"][0]["change"], 6000, delta=1)
        self.assertLess(st["steps"][1]["change"], 0)
        r = self.ok("steps_render", {"body": "St body", "inline": False, "width": 240, "height": 180})
        self.assertEqual(len(r["files"]), 2)
        self.assertTrue(os.path.getsize(r["sheet"]) > 0)

    def test_app_prefs(self):
        self.have("pref_set")
        path = "BaseApp/Preferences/Mod/AgentLinkTest"
        r = self.ok("pref_set", {"path": path, "values": {"Flag": True, "Count": 3, "Name": "x"}})
        self.assertEqual(r["set"]["Count"]["type"], "integer")
        got = self.ok("pref_get", {"path": path})["values"]
        self.assertTrue(got["Flag"]["value"])
        self.assertEqual(got["Count"]["value"], 3)
        self.ok("pref_reset", {"path": path, "names": ["Count"]})
        self.assertNotIn("Count", self.ok("pref_get", {"path": path})["values"])
        packs = self.ok("pref_pack", {})["packs"]
        self.assertIn("Studio Dark", packs)
        err, out = self.call("cmd_run", {"name": "Std_ViewFitAll"})
        if err:
            self.assertEqual(out["error"]["code"], "unavailable")

if __name__ == "__main__":
    unittest.main()
