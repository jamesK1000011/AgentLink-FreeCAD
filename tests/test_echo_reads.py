# SPDX-License-Identifier: LGPL-2.1-or-later
# Read-only calls leave FreeCAD's workbench where the person has it: only a
# call that changes the document (its tool's changes flag) or opens a panel
# (an add-on's OPENS) brings its bench up. Without FreeCAD: a stand-in
# FreeCADGui records what the echo asks of it.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import echo  # noqa: E402


class Tool:
    def __init__(self, name, changes):
        self.name, self.changes = name, changes


class Reads(unittest.TestCase):
    def setUp(self):
        self.switched = []
        bench = types.SimpleNamespace(name=lambda: "StartWorkbench")
        status = types.SimpleNamespace(showMessage=lambda *a: None)
        gui = types.ModuleType("FreeCADGui")
        gui.activeWorkbench = lambda: bench
        gui.listWorkbenches = lambda: {"PartDesignWorkbench": 1, "FemWorkbench": 1}
        gui.activateWorkbench = self.switched.append
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: status)
        gui.ActiveDocument = None
        self.had_gui = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        self.saved = {k: getattr(echo, k) for k in ("FreeCAD", "enabled", "caption", "_paint", "_wait", "delay_ms", "flash_command", "_select", "_objects", "OPENS")}
        echo.FreeCAD = types.SimpleNamespace(ActiveDocument=None, Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        echo.enabled = lambda: True
        echo.caption = lambda *a, **k: None
        echo._paint = lambda *a, **k: None
        echo._wait = lambda *a, **k: None
        echo.delay_ms = lambda: 0
        echo.flash_command = lambda *a, **k: None
        echo._select = lambda *a: None
        echo._objects = lambda doc, names: []
        self.echo = echo.Echo(types.SimpleNamespace(doc=None))

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had_gui

    def test_a_change_switches(self):
        self.echo.before(Tool("pd_pad", True), {})
        self.assertEqual(self.switched, ["PartDesignWorkbench"])

    def test_a_read_does_not(self):
        for name in ("fea_results", "pd_list", "sketch_state", "view_render", "measure_distance", "body_check"):
            self.echo.before(Tool(name, False), {})
        self.assertEqual(self.switched, [])

    def test_a_read_that_opens_a_panel_does(self):
        echo.declare(types.SimpleNamespace(OPENS=("fea_results",)))
        self.echo.before(Tool("fea_results", False), {})
        self.assertEqual(self.switched, ["FemWorkbench"])

    def test_rule(self):
        self.assertTrue(echo.switches_bench(Tool("pd_pad", True)))
        self.assertFalse(echo.switches_bench(Tool("pd_pad", False)))
        self.assertFalse(echo.switches_bench(None))


if __name__ == "__main__":
    unittest.main()
