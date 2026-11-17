# SPDX-License-Identifier: LGPL-2.1-or-later
# The CAM path probe (round 7): path_seen's view block — present only with a
# window, never raising, cut short in time. Without FreeCAD: stand-ins.
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from test_echo_round6 import _cam_family  # noqa: E402


def c(name, **p):
    return types.SimpleNamespace(Name=name, Parameters=p)


CMDS = [c("G0", X=0.0, Y=0.0, Z=5.0), c("G1", X=0.0, Y=0.0, Z=0.0), c("G1", X=10.0, Y=0.0, Z=0.0)]


class Raises:
    """An object whose every attribute read fails."""

    def __getattr__(self, k):
        raise RuntimeError(k)


class Probe(unittest.TestCase):
    def setUp(self):
        self.cam = _cam_family()
        if self.cam is None:
            self.skipTest("cam family not importable here")
        self.fc = self.cam.FreeCAD

    def op(self, **kw):
        job = types.SimpleNamespace(Label="Job", PropertiesList=["Operations", "Stock"], Visibility=True)
        base = {"Label": "Profile", "Path": types.SimpleNamespace(Commands=CMDS), "Visibility": True, "Active": True, "InListRecursive": [job]}
        return types.SimpleNamespace(**{**base, **kw})

    def test_no_view_block_headless(self):
        had = getattr(self.fc, "GuiUp", None)
        try:
            self.fc.GuiUp = False
            got = self.cam.path_seen(self.op())
            self.assertNotIn("view", got)
            self.assertTrue(got["shown"])
            self.assertIsNone(self.cam.path_view(self.op()))
        finally:
            if had is None:
                try:
                    del self.fc.GuiUp
                except AttributeError:
                    pass
            else:
                self.fc.GuiUp = had

    def test_never_raises(self):
        for x in (Raises(), types.SimpleNamespace(), None, self.op(Path=None), self.op(InListRecursive=Raises())):
            try:
                got = self.cam.path_seen(x)
            except Exception as e:  # noqa: BLE001
                self.fail(f"path_seen raised {type(e).__name__}: {e}")
            self.assertIn("shown", got)

    def test_window_without_view_provider(self):
        """A window up, but the operation has no view provider (and no pivy
        here): the block says so, and the job's facts come along."""
        had_up = getattr(self.fc, "GuiUp", None)
        had_gui = sys.modules.get("FreeCADGui")
        try:
            self.fc.GuiUp = True
            sys.modules["FreeCADGui"] = types.ModuleType("FreeCADGui")
            stock = types.SimpleNamespace(Label="Stock", ViewObject=types.SimpleNamespace(Visibility=True, Transparency=70))
            clone = types.SimpleNamespace(Label="Clone", ViewObject=types.SimpleNamespace(Visibility=True, Transparency=80))
            ops = types.SimpleNamespace(Group=[], ViewObject=types.SimpleNamespace(Visibility=False))
            job = types.SimpleNamespace(Label="Job", PropertiesList=["Operations", "Stock"], Visibility=True, Operations=ops,
                                        Model=types.SimpleNamespace(Group=[clone], ViewObject=types.SimpleNamespace(Visibility=True)),
                                        Stock=stock, ViewObject=types.SimpleNamespace(Visibility=True))
            op = types.SimpleNamespace(Label="Profile", Path=types.SimpleNamespace(Commands=CMDS), Visibility=True, Active=True,
                                       InListRecursive=[ops, job], ViewObject=None)
            ops.Group.append(op)
            got = self.cam.path_seen(op)
            v = got["view"]
            self.assertIsNone(v["vp"])
            self.assertIn("no view provider", v["vpWhy"])
            self.assertEqual(v["job"]["Operations"], False)
            self.assertTrue(v["job"]["inOperations"])
            self.assertEqual(v["job"]["clones"], [{"name": "Clone", "Visibility": True, "Transparency": 80}])
            self.assertEqual(v["job"]["StockTransparency"], 70)
            # A view provider, but no pivy here: its properties read, no nodes.
            op.ViewObject = types.SimpleNamespace(TypeId="PathGui::ViewProviderPathPython", Proxy=None, Visibility=True,
                                                  LineWidth=3, ShowCount=0, StartIndex=0, DisplayMode="Waypoints",
                                                  PropertiesList=["Visibility", "LineWidth", "ShowCount", "StartIndex", "DisplayMode"],
                                                  isVisible=lambda: True)
            v = self.cam.path_seen(op)["view"]
            self.assertEqual(v["vp"], "PathGui::ViewProviderPathPython")
            self.assertEqual((v["LineWidth"], v["ShowCount"], v["DisplayMode"], v["isVisible"]), (3, 0, "Waypoints", True))
        finally:
            if had_up is None:
                try:
                    del self.fc.GuiUp
                except AttributeError:
                    pass
            else:
                self.fc.GuiUp = had_up
            if had_gui is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had_gui


if __name__ == "__main__":
    unittest.main()
