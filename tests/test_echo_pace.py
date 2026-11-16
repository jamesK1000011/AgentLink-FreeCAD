# SPDX-License-Identifier: LGPL-2.1-or-later
# A batch in the window: its first three changing calls and its last are
# shown at the full pace, those between at a short one (EchoBatchDelay) with
# no settle paints — the bench still comes up, the button lights and the
# result is selected. A call on its own keeps the full pace. Without
# FreeCAD: the rule (echo.pace) and the echo against a stand-in FreeCADGui.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import echo  # noqa: E402


class Rule(unittest.TestCase):
    def test_single_call_is_full(self):
        self.assertEqual(echo.pace(None, True, 350, 60), ("full", 350))

    def run_batch(self, kinds, batch_ms=60, last=None):
        """The pace of each call of a batch: kinds is a list of booleans
        (changing or not)."""
        if last is None:
            last = max((i for i, c in enumerate(kinds) if c), default=None)
        b = {"i": 0, "n": len(kinds), "lastChange": last, "echoed": 0}
        out = []
        for i, c in enumerate(kinds):
            b["i"] = i
            out.append(echo.pace(b, c, 350, batch_ms))
        return out

    def test_twenty_changes(self):
        got = self.run_batch([True] * 20)
        self.assertEqual(got[:3], [("full", 350)] * 3)
        self.assertEqual(got[3:19], [("short", 60)] * 16)
        self.assertEqual(got[19], ("full", 350))
        # The pauses: 4 full and 16 short, where 20 full were 7 s.
        self.assertEqual(sum(ms for _m, ms in got), 4 * 350 + 16 * 60)

    def test_three_or_fewer_are_all_full(self):
        self.assertEqual(self.run_batch([True] * 3), [("full", 350)] * 3)

    def test_reads_do_not_count_and_last_change_is_full(self):
        # change, read, change, change, change, change, read, read
        got = self.run_batch([True, False, True, True, True, True, False, False])
        self.assertEqual([m for m, _ in got], ["full", "full", "full", "full", "short", "full", "short", "full"])

    def test_preference(self):
        self.assertEqual(self.run_batch([True] * 6, batch_ms=0)[3:5], [("short", 0)] * 2)
        self.assertEqual(self.run_batch([True] * 6, batch_ms=-1), [("full", 350)] * 6)
        # Never slower than a call on its own, and a broken value is the default.
        self.assertEqual(self.run_batch([True] * 6, batch_ms=900)[3], ("short", 350))
        self.assertEqual(self.run_batch([True] * 6, batch_ms=None)[3], ("short", 60))

    def test_not_counted_twice(self):
        b = {"i": 5, "n": 9, "lastChange": 8, "echoed": 0}
        echo.pace(b, True, 350, 60, count=False)
        self.assertEqual(b["echoed"], 0)


class Tool:
    def __init__(self, name, changes=True):
        self.name, self.changes = name, changes


class InTheWindow(unittest.TestCase):
    """The echo itself, each wait recorded: what the short pace leaves out."""

    def setUp(self):
        self.log = []
        self.switched = []
        self.bench = "StartWorkbench"

        def activate(wb):
            self.switched.append(wb)
            self.bench = wb

        status = types.SimpleNamespace(showMessage=lambda *a: None)
        gui = types.ModuleType("FreeCADGui")
        gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: self.bench)
        gui.listWorkbenches = lambda: {"PartDesignWorkbench": 1, "PartWorkbench": 1}
        gui.activateWorkbench = activate
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: status)
        gui.ActiveDocument = None
        self.had_gui = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        keys = ("FreeCAD", "enabled", "caption", "_paint", "_wait", "delay_ms", "batch_delay_ms", "flash_command", "_select", "_objects")
        self.saved = {k: getattr(echo, k) for k in keys}
        echo.FreeCAD = types.SimpleNamespace(ActiveDocument=None, Console=types.SimpleNamespace(PrintLog=lambda *a: self.log.append(("log", a))))
        echo.enabled = lambda: True
        echo.caption = lambda *a, **k: None
        echo._paint = lambda ms=0: self.log.append(("paint", ms))
        echo._wait = lambda ms: self.log.append(("wait", ms))
        echo.delay_ms = lambda: 350
        echo.batch_delay_ms = lambda: 60
        echo.flash_command = lambda cmd, ms=1300, settle=False: self.log.append(("flash", cmd, settle))
        echo._select = lambda objs: self.log.append(("select",))
        echo._objects = lambda doc, names: []
        self.session = types.SimpleNamespace(doc=None, batch_now=None)
        self.echo = echo.Echo(self.session)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had_gui

    def waits(self):
        return [x for x in self.log if x[0] in ("wait", "paint")]

    def test_single_call_full(self):
        self.echo.before(Tool("pd_pad"), {})
        self.assertEqual(self.waits(), [("paint", 0), ("wait", 350)])
        self.assertIn(("flash", "PartDesign_Pad", True), self.log)
        self.assertEqual(self.echo.mode, "full")

    def test_batch_short_from_the_fourth(self):
        b = self.session.batch_now = {"i": 0, "n": 8, "lastChange": 7, "echoed": 0}
        per_call = []
        for i in range(8):
            b["i"] = i
            del self.log[:]
            self.echo.before(Tool("pd_pad" if i % 2 else "part_boolean"), {})
            per_call.append((self.echo.mode, self.waits(), [x for x in self.log if x[0] in ("flash", "select")]))
        for i in (0, 1, 2, 7):
            self.assertEqual(per_call[i][0], "full", i)
            self.assertEqual(per_call[i][1], [("paint", 0), ("wait", 350)], i)
        for i in (3, 4, 5, 6):
            mode, waits, shown = per_call[i]
            self.assertEqual(mode, "short", i)
            self.assertEqual(waits, [("wait", 60)], i)  # one short pause, no settle paint
            # Still shown: the button lit, the arguments' objects selected.
            self.assertEqual([x[0] for x in shown], ["flash", "select"], i)
        # The bench still comes up for each call that is of another bench.
        self.assertEqual(self.switched, ["PartWorkbench", "PartDesignWorkbench"] * 4)
        self.assertFalse([x for x in self.log if x[0] == "log"])

    def test_no_wait_still_paints_once(self):
        echo.batch_delay_ms = lambda: 0
        self.session.batch_now = {"i": 4, "n": 9, "lastChange": 8, "echoed": 4}
        self.echo.before(Tool("pd_pad"), {})
        self.assertEqual(self.waits(), [("paint", 0)])

    def test_same_as_echo_delay(self):
        echo.batch_delay_ms = lambda: -1
        self.session.batch_now = {"i": 4, "n": 9, "lastChange": 8, "echoed": 4}
        self.echo.before(Tool("pd_pad"), {})
        self.assertEqual(self.waits(), [("paint", 0), ("wait", 350)])

    def test_a_skipped_call_resets_the_pace(self):
        self.session.batch_now = {"i": 4, "n": 9, "lastChange": 8, "echoed": 4}
        self.echo.before(Tool("pd_pad"), {})
        self.assertEqual(self.echo.mode, "short")
        self.session.batch_now = None
        self.echo.before(Tool("session_state", False), {})
        self.assertEqual(self.echo.mode, "full")

    def test_joint_faces_pause_only_at_full_pace(self):
        import inspect

        src = inspect.getsource(echo.Echo._container)
        self.assertIn('if self.mode != "short":', src)
        self.assertNotIn("_wait(delay_ms())", inspect.getsource(echo.Echo), "every pause on the echo path goes through the call's pace")


class LitResult(unittest.TestCase):
    def test_a_newer_selection_is_not_cleared(self):
        cleared = []
        gui = types.ModuleType("FreeCADGui")
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: cleared.append(1), addSelection=lambda o: None)
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        try:
            echo._select([object()])
            mark = echo._selected[0]
            n = len(cleared)
            echo._select([object()])  # the next call's
            self.assertFalse(echo._clear_if(mark))
            self.assertEqual(len(cleared), n + 1)  # only _select's own clear
            self.assertTrue(echo._clear_if(echo._selected[0]))
        finally:
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had


if __name__ == "__main__":
    unittest.main()
