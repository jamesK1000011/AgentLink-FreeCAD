# SPDX-License-Identifier: LGPL-2.1-or-later
# Toolpaths with FreeCAD's CAM workbench, on a real FreeCAD: a job, a
# profile, a pocket and the holes, posted as G-code.
import json
import unittest

from _fc import BEFORE_1_1, HAVE, add_body, caller, server

try:
    import Path.Main.Job  # noqa: F401

    CAM = HAVE
except Exception:
    CAM = False


@unittest.skipUnless(CAM, "FreeCAD with the CAM workbench is not importable here")
class Cam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import FreeCAD
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("Cam")
        cls.session.switch(FreeCAD.ActiveDocument)
        block = Part.makeBox(60, 40, 20)
        block = block.cut(Part.makeBox(30, 20, 8, FreeCAD.Vector(15, 10, 12)))
        block = block.cut(Part.makeCylinder(3, 20, FreeCAD.Vector(7, 7, 0)))
        add_body(cls.session, "Plate", block)

    def test_1_job_ops_post(self):
        err, r = self.call("cam_job", {"body": "Plate"})
        self.assertTrue(err)
        self.assertIn("tool", r["error"]["message"])
        err, j = self.call("cam_job", {"body": "Plate", "tool": {"diameter": 6, "feed": 800, "plunge": 250, "rpm": 15000}, "stock": {"margin": 3, "top": 1}})
        self.assertFalse(err, j)
        print("\njob:", json.dumps(j))
        self.assertAlmostEqual(j["stock"]["size"][0], 66, delta=0.01)
        self.assertEqual(j["tool"]["diameter"], 6)
        err, p = self.call("cam_op", {"kind": "profile", "side": "outside"})
        print("profile:", json.dumps(p))
        self.assertFalse(err, p)
        self.assertGreater(p["cutMm"], 2 * (60 + 40))
        # Outside the part by the tool's radius.
        self.assertLess(p["cutBox"]["min"][0], -2.9)
        err, k = self.call("cam_op", {"kind": "pocket", "faces": [{"normal": [0, 0, 1], "near": [30, 20, 12]}]})
        print("pocket:", json.dumps(k))
        self.assertFalse(err, k)
        self.assertAlmostEqual(k["cutZ"][0], 12, delta=0.05)
        err, ls = self.call("cam_list")
        self.assertEqual(len(ls["ops"]), 2)
        self.assertGreater(ls["minutes"], 0)
        err, g = self.call("cam_post", {"post": "grbl"})
        print("post:", json.dumps(g))
        self.assertFalse(err, g)
        with open(g["path"]) as f:
            text = f.read()
        self.assertIn("G21", text)
        self.assertNotIn("warnings", g)
        err, x = self.call("cam_op", {"kind": "pocket", "faces": ["Face1"], "name": "Nothing"})
        self.assertTrue(err)
        # Simulated on the stock: no crash, no gouge; the stock's top 1 mm
        # is left over the part (no face op), and the 6 mm mill leaves the
        # pocket's square corners 8 mm deep under it.
        err, sim = self.call("cam_sim", {"inline": False})
        print("sim:", json.dumps(sim))
        self.assertFalse(err, sim)
        self.assertEqual(sim["verdict"], "clear", sim)
        self.assertNotIn("crashes", sim)
        self.assertNotIn("gouge", sim["part"])
        self.assertGreater(sim["removedMm3"], 30 * 20 * 8 * 0.8)
        left = sim["part"]["left"]
        self.assertAlmostEqual(left["most"], 9.0, delta=0.2)
        at = left["at"]
        self.assertTrue(min(abs(at[0] - 15), abs(at[0] - 45)) < 3 and min(abs(at[1] - 10), abs(at[1] - 30)) < 3, at)
        self.assertGreater(left["share"], 0.6)
        import os

        self.assertGreater(os.path.getsize(sim["picture"]), 1000)

    def test_2_drill_finds_the_hole(self):
        # FreeCAD 1.0's Drilling.Create fails headless. An 8 mm tool is too
        # big for the 6 mm hole, so first the refusal, then a 3 mm tool.
        self.call("cam_tool", {"diameter": 8})
        err, r = self.call("cam_op", {"kind": "drill"})
        self.assertTrue(err)
        self.assertIn("smaller tool", r["error"]["message"], r)
        err, t = self.call("cam_tool", {"diameter": 3})
        self.assertFalse(err, t)
        err, d = self.call("cam_op", {"kind": "drill"})
        print("\ndrill:", json.dumps(d))
        self.assertFalse(err, d)
        self.assertGreater(d["cutMm"], 19)
        self.assertAlmostEqual(d["cutBox"]["min"][0], 7, delta=0.01)
        self.assertAlmostEqual(d["cutBox"]["min"][1], 7, delta=0.01)
        err, g = self.call("cam_post", {"post": "grbl"})
        self.assertFalse(err, g)
        self.assertIn("Drill", g["ops"])
        drill = next(o for o in self.session.doc.Objects if o.Label == "Drill")
        print("drill path:", [(c.Name, dict(c.Parameters)) for c in drill.Path.Commands][:14])
        err, sim = self.call("cam_sim", {"inline": False})
        print("drill sim:", json.dumps({k: sim.get(k) for k in ("ops", "crashes", "findings")}))
        self.assertFalse(err, sim)
        self.assertNotIn("crashes", sim)
        drilled = next(o for o in sim["ops"] if o["op"] == "Drill")
        self.assertGreater(drilled["removedMm3"], 3.14 * 1.5 ** 2 * 15)


@unittest.skipUnless(CAM, "FreeCAD with the CAM workbench is not importable here")
class CamHardening(unittest.TestCase):
    """The hardening pass's fixes, each read from FreeCAD 1.1's CAM source (docs/hardening/bimcam-findings.md)."""

    @classmethod
    def setUpClass(cls):
        import FreeCAD
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        FreeCAD.newDocument("CamHardening")
        cls.session.switch(FreeCAD.ActiveDocument)
        block = Part.makeBox(60, 40, 20).cut(Part.makeBox(30, 20, 8, FreeCAD.Vector(15, 10, 12)))
        add_body(cls.session, "HPlate", block)
        err, j = cls.call("cam_job", {"body": "HPlate", "tool": {"diameter": 6, "feed": 800, "plunge": 250, "rpm": 15000}, "stock": {"margin": 3, "top": 1}, "name": "HJob"})
        assert not err, j
        err, p = cls.call("cam_op", {"kind": "profile", "side": "outside", "name": "HOutline"})
        assert not err, p

    def ok(self, name, args=None):
        err, out = self.call(name, args or {})
        self.assertFalse(err, f"{name}: {out}")
        return out

    def refused(self, name, args=None):
        err, out = self.call(name, args or {})
        self.assertTrue(err, f"{name} should refuse: {out}")
        return out["error"]["message"]

    def test_1_post_goes_through_the_job(self):
        # Work offsets reach the G-code only through the job's post-processor object (Processor._buildPostList).
        self.ok("cam_setup", {"fixtures": ["G54", "G55"]})
        g = self.ok("cam_post", {"post": "linuxcnc", "path": "hardening.nc"})
        self.assertEqual(g["via"], "job")
        self.assertEqual(g["fixtures"], ["G54", "G55"])
        self.assertEqual(g["units"], "mm (G21)")
        self.assertEqual(g["tools"][0]["number"], 1)
        with open(g["path"]) as f:
            text = f.read()
        self.assertIn("G55", text)
        self.assertIn("M6 T1", text.replace("  ", " "))
        # the job's own arguments are put back, and nothing is left marked for recompute
        job = next(o for o in self.session.doc.Objects if o.Label == "HJob")
        self.assertNotIn("--no-show-editor", job.PostProcessorArgs)
        self.ok("cam_setup", {"fixtures": ["G54"]})
        self.assertIn("Nothing to set", self.refused("cam_setup", {}))

    def test_2_adaptive_finish_is_profiling(self):
        floor = [{"normal": [0, 0, 1], "near": [30, 20, 12]}]
        err, out = self.call("cam_op", {"kind": "adaptive", "faces": floor, "finish": True, "name": "HFinish"})
        if err:
            # the path itself may not compute on every build; the enumeration must not be the reason
            self.assertNotIn("enumeration", out["error"]["message"])
        else:
            op = next(o for o in self.session.doc.Objects if o.Label == "HFinish")
            self.assertEqual(op.OperationType, "Profiling")
            self.ok("cam_remove", {"op": "HFinish"})
        self.assertIn("side", self.refused("cam_op", {"kind": "profile", "side": "left"}))
        self.assertIn("stepOver", self.refused("cam_op", {"kind": "pocket", "faces": floor, "stepOver": 150}))

    def test_3_tools_keep_their_shape_and_sizes(self):
        t = self.ok("cam_tool_add", {"shape": "bullnose", "diameter": 6, "cornerRadius": 1, "name": "HBull"})
        # FreeCAD 1.0's bullnose bit has no corner radius: the answer says it was skipped.
        self.assertEqual(t.get("skipped"), ["cornerRadius"] if BEFORE_1_1 else None, t)
        v = self.ok("cam_tool_add", {"shape": "v-bit", "diameter": 6, "angle": 60, "cornerRadius": 1, "name": "HVee"})
        self.assertEqual(v.get("skipped"), ["cornerRadius"])
        self.assertEqual(v["tool"]["number"], 3)
        e = self.ok("cam_library", {"action": "export", "path": "hardening-tools.json"})
        shapes = {r["name"]: r["shape"] for r in e["tools"]}
        self.assertEqual(shapes["HBull"], "bullnose")
        self.assertEqual(shapes["HVee"], "v-bit")
        rec = next(r for r in e["tools"] if r["name"] == "HBull")
        self.assertAlmostEqual(rec["cornerRadius"], 1.0, delta=0.001)
        vee = next(r for r in e["tools"] if r["name"] == "HVee")
        self.assertAlmostEqual(vee["angle"], 60.0, delta=0.01)
        self.assertIn("over 0", self.refused("cam_tool_add", {"shape": "endmill", "diameter": 0}))

    def test_4_tags_take_their_count_and_a_stack_is_removed_whole(self):
        self.ok("cam_op", {"kind": "profile", "side": "outside", "name": "HTagged"})
        d = self.ok("cam_dressup", {"op": "HTagged", "kind": "tags", "count": 6, "width": 5, "height": 2})
        # FreeCAD spreads them edge by edge, so the count can be one off; its default is 4
        self.assertGreaterEqual(d["tags"], 5)
        dr = next(o for o in self.session.doc.Objects if o.Label == d["dressup"])
        self.assertAlmostEqual(float(dr.Width), 5, delta=0.001)
        self.assertAlmostEqual(float(dr.Height), 2, delta=0.001)
        self.assertIn("no such property", self.refused("cam_dressup", {"op": "HOutline", "kind": "dogbone", "props": {"NotAProperty": 1}}))
        # A stop runs with the tool of the operation it follows, not the one selected in the
        # window (a stop after the pocket took the drill's controller: a tool change posted for it).
        st = self.ok("cam_edit", {"action": "stop", "optional": True, "after": "HOutline"})
        stop = next(o for o in self.session.doc.Objects if o.Label == st["op"])
        outline = next(o for o in self.session.doc.Objects if o.Label == "HOutline")
        if "ToolController" in stop.PropertiesList:
            self.assertEqual(stop.ToolController.Name, outline.ToolController.Name)
        # Coolant goes on the operation under a dressup (the job lists the dressup, which has
        # no coolant mode: a job of one dressed profile answered ops 0 and stayed dry).
        base = next(o for o in self.session.doc.Objects if o.Label == "HTagged")
        if "CoolantMode" in base.PropertiesList:
            c = self.ok("cam_setup", {"coolant": "flood"})
            self.assertGreaterEqual(c["coolant"]["ops"], 2)
            self.assertEqual(str(base.CoolantMode), "Flood")
            self.ok("cam_setup", {"coolant": "none"})
            self.assertEqual(str(base.CoolantMode), "None")
        r = self.ok("cam_remove", {"op": "HTagged"})
        self.assertEqual(sorted(r["removed"]), sorted([d["dressup"], "HTagged"]))
        self.assertEqual([o.Label for o in self.session.doc.Objects if o.Label in (d["dressup"], "HTagged")], [])
        self.assertIn("HOutline", r["ops"])


if __name__ == "__main__":
    unittest.main()
