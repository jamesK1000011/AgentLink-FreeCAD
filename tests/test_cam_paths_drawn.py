# SPDX-License-Identifier: LGPL-2.1-or-later
# CAM paths seen (round 7): an operation's path drawn in the scene by the
# echo (feeds and rapids as polylines, arcs as chords, drilling cycles), put
# away at the next change; path_seen's `shown` false when the window's own
# drawing holds nothing. Without FreeCAD: stand-ins.
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import annotate, echo  # noqa: E402
from test_echo_round6 import SceneCoin, SceneNode, _cam_family, _Maker  # noqa: E402


def c(name, **p):
    return types.SimpleNamespace(Name=name, Parameters=p)


def op(cmds, label="Profile", **kw):
    return types.SimpleNamespace(Label=label, Path=types.SimpleNamespace(Commands=cmds), **kw)


class Lines(unittest.TestCase):
    def test_feeds_and_rapids(self):
        cmds = [c("G0", X=0.0, Y=0.0, Z=5.0), c("G0", Z=1.0), c("G1", Z=0.0), c("G1", X=10.0), c("G1", Y=10.0), c("G0", Z=5.0)]
        feeds, rapids = echo.path_lines(op(cmds))
        self.assertEqual(rapids[0], [(0.0, 0.0, 5.0), (0.0, 0.0, 1.0)])
        self.assertEqual(feeds, [[(0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]])
        self.assertEqual(rapids[1], [(10.0, 10.0, 0.0), (10.0, 10.0, 5.0)])

    def test_arc_as_chords(self):
        # A half circle, counter-clockwise, radius 10 round (10, 0).
        cmds = [c("G0", X=0.0, Y=0.0, Z=0.0), c("G3", X=20.0, Y=0.0, Z=0.0, I=10.0, J=0.0)]
        feeds, _ = echo.path_lines(op(cmds))
        pts = feeds[0]
        self.assertEqual(pts[-1], (20.0, 0.0, 0.0))
        self.assertGreaterEqual(len(pts), 17)  # pi in steps of pi/16, and the start
        for x, y, _z in pts:
            self.assertAlmostEqual((x - 10.0) ** 2 + y ** 2, 100.0, places=6)
        self.assertTrue(all(y <= 1e-9 for _x, y, _z in pts))  # G3 from (0,0) to (20,0) round (10,0) goes below

    def test_drill_cycle(self):
        cmds = [c("G0", X=0.0, Y=0.0, Z=10.0), c("G98"), c("G81", X=5.0, Y=5.0, Z=-3.0, R=2.0)]
        feeds, rapids = echo.path_lines(op(cmds))
        self.assertEqual(feeds, [[(5.0, 5.0, 2.0), (5.0, 5.0, -3.0)]])
        self.assertEqual(rapids[-1], [(5.0, 5.0, -3.0), (5.0, 5.0, 10.0)])

    def test_cap_and_bad_input(self):
        cmds = [c("G0", X=0.0, Y=0.0, Z=0.0)] + [c("G1", X=float(i)) for i in range(1, 500)]
        feeds, _ = echo.path_lines(op(cmds), cap=50)
        self.assertLessEqual(sum(len(r) for r in feeds), 51)
        self.assertEqual(echo.path_lines(types.SimpleNamespace(Label="x")), ([], []))
        self.assertEqual(echo.path_lines(op([types.SimpleNamespace()])), ([], []))


class Drawn(unittest.TestCase):
    def setUp(self):
        self.scene = SceneNode("root")
        self.had = annotate._SERVICE
        annotate._SERVICE = annotate.Annotations(coin=_Maker(SceneCoin()), scene=lambda: self.scene)

    def tearDown(self):
        annotate._SERVICE = self.had

    def test_drawn_then_cleared(self):
        cmds = [c("G0", X=0.0, Y=0.0, Z=5.0), c("G1", Z=0.0), c("G1", X=10.0), c("G0", Z=5.0)]
        got = echo.cam_scene_paths([op(cmds), op([], label="Empty")])
        self.assertEqual(got, {"Profile": 5, "Empty": 0})
        self.assertEqual(len(self.scene.children), 1)
        root = self.scene.children[0]
        self.assertEqual(len(root.children), 2)  # feeds, rapids
        # Drawn again (a read after a change): the old drawing put away first.
        echo.cam_scene_paths([op(cmds)])
        self.assertEqual(len(self.scene.children), 1)
        self.assertEqual(len(self.scene.children[0].children), 2)
        echo.scene_clear()
        self.assertEqual(self.scene.children, [])

    def test_no_view(self):
        annotate._SERVICE = annotate.Annotations(coin=_Maker(SceneCoin()), scene=lambda: None)
        self.assertEqual(echo.cam_scene_paths([op([c("G0", X=0.0, Y=0.0, Z=0.0), c("G1", X=1.0)])]), {"Profile": 0})

    def test_redraw_never_raises(self):
        self.assertFalse(echo.path_redraw(types.SimpleNamespace(Label="x")))
        calls = []
        vo = types.SimpleNamespace(Visibility=True, DisplayMode="Waypoints", StartIndex=0, ShowCount=0,
                                   PropertiesList=["DisplayMode", "StartIndex", "ShowCount"],
                                   update=lambda: calls.append("update"), show=lambda: calls.append("show"))
        self.assertTrue(echo.path_redraw(types.SimpleNamespace(Label="P", ViewObject=vo)))
        self.assertEqual(calls, ["update", "show"])
        vo.Visibility = False
        self.assertFalse(echo.path_redraw(types.SimpleNamespace(Label="P", ViewObject=vo)))


class Honest(unittest.TestCase):
    def setUp(self):
        self.cam = _cam_family()
        if self.cam is None:
            self.skipTest("cam family not importable here")

    def test_view_why(self):
        w = self.cam.view_why
        self.assertIsNone(w({}))
        self.assertIn("no view provider", w({"vp": None, "vpWhy": "no view provider: x"}))
        good = {"vp": "PathGui::ViewProviderPathPython", "Visibility": True, "modeSwitch": {"whichChild": 0, "children": 1},
                "coordPoints": [120, 40], "lineIndices": [300], "inScene": True,
                "sceneSwitches": [{"depth": 2, "whichChild": -3, "children": 4}, {"depth": 4, "whichChild": 1, "children": 2, "childOnPath": 1}],
                "box": [[0, 0, 0], [1, 1, 1]]}
        self.assertIsNone(w(good))
        self.assertIn("switched off", w({**good, "modeSwitch": {"whichChild": -1, "children": 1}}))
        self.assertIn("0 points", w({**good, "coordPoints": [0, 0]}))
        self.assertIn("0 line indices", w({**good, "lineIndices": [0]}))
        self.assertIn("not in the 3D view", w({**good, "inScene": False}))
        self.assertIn("switch above", w({**good, "sceneSwitches": [{"depth": 4, "whichChild": 0, "childOnPath": 1}]}))
        self.assertIn("empty bounding box", w({**good, "box": None}))
        self.assertIsNone(w({**good, "box": "?"}))

    def test_shown_follows_the_view(self):
        cam = self.cam
        cmds = [c("G0", X=0.0, Y=0.0, Z=5.0), c("G1", X=0.0, Y=0.0, Z=0.0)]
        x = types.SimpleNamespace(Label="Profile", Path=types.SimpleNamespace(Commands=cmds), Visibility=True, Active=True, InListRecursive=[])
        real = cam.path_view
        try:
            cam.path_view = lambda o: {"vp": "PathGui::ViewProviderPathPython", "coordPoints": [0]}
            got = cam.path_seen(x)
            self.assertFalse(got["shown"])
            self.assertIn("0 points", got["shownWhy"])
            cam.path_view = lambda o: {"vp": "PathGui::ViewProviderPathPython", "coordPoints": [12]}
            self.assertTrue(cam.path_seen(x)["shown"])
            x.Visibility = False  # the object's own reason comes first
            self.assertEqual(cam.path_seen(x)["shownWhy"], "Profile is hidden")
        finally:
            cam.path_view = real


if __name__ == "__main__":
    unittest.main()
