# SPDX-License-Identifier: LGPL-2.1-or-later
# Live findings of 18 Nov from a student agent that did the film-hinge
# lesson through gui_input { as: "person" } (FreeCAD 1.1.3, macOS), on
# stand-ins (no Qt, no FreeCAD):
#  80:  an item target finds rows of a list model (columnCount(parent)).
#  82:  a window-point click on an open menu's item runs that item, also
#       when the click closed the menu and ran nothing.
#  85:  a dialog's words and buttons leave out the widgets of a closed
#       popup (an expression editor that FreeCAD keeps hidden).
#  56c, 81: reads that a tool's data declares (frontReads) run beside
#       gui_input; window_snapshot alone runs while a menu is open.
#  84:  a batch run inside the dialog's loop of an earlier, answered batch
#       has its own clock.
#  87:  the watchdog times a nested loop from when a dialog was last in
#       front, not from the call's start.
#  88:  a command recipe activates its add-on's workbench first.
import os
import sys
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import test_gui_input as tg  # noqa: E402
import test_gui_popups as tp  # noqa: E402
from test_gui_link_dialog import call, gui_link  # noqa: E402

from agentlink import gui_input as gi  # noqa: E402
from agentlink import protocol  # noqa: E402


class ListModel:
    """A QAbstractListModel as PySide binds it: rowCount and columnCount
    take the parent index (columnCount() alone raised TypeError live)."""

    def __init__(self, rows):
        self.rows = rows

    def rowCount(self, parent):
        return len(self.rows) if not parent.isValid() else 0

    def columnCount(self, parent):
        return 1

    def index(self, r, c=0, parent=None):
        return tg.Ix(self, r, c)

    def data(self, ix, role=0):
        return self.rows[ix.r] if role == 0 else None


class Root:
    def isValid(self):
        return False


class ListModels(unittest.TestCase):
    """80."""

    setUp = tg.Targets.setUp

    def test_item_in_a_list_model(self):
        self.qt.QtCore.QModelIndex = Root
        self.view.m = ListModel(["Basic_sketch", "Body"])
        w, x, y = self.run.resolve(gi.parse_target({"item": {"text": "Basic_sketch"}}, "t"))
        self.assertIs(w, self.view.vp)
        self.assertEqual(self.run.found_in["matches"], 1)


class Signal:
    def __init__(self):
        self.fns = []

    def connect(self, f):
        self.fns.append(f)

    def disconnect(self, f):
        self.fns.remove(f)

    def emit(self):
        for f in list(self.fns):
            f()


class WatchedAction(tp.Action):
    def __init__(self, text):
        super().__init__(text)
        self.triggered = Signal()

    def trigger(self):
        self.fired += 1
        self.triggered.emit()


class MenuPoint(tp.Base):
    """82."""

    def setUp(self):
        super().setUp()
        self.menu.acts = [WatchedAction(a.text()) for a in self.menu.acts]
        self.menu.actionAt = lambda p: self.menu._at(p.y())

    def test_window_point_on_an_item_runs_it(self):
        # The menu at global (130, 140); the main window at (100, 50).
        self.run.run(self.steps(tp.ARROW, {"click": {"window": [40, 120]}}))
        a = self.answers[0]
        self.assertEqual(a["steps"][1]["hit"]["menu"], "clicked")
        self.assertEqual(self.menu.acts[1].fired, 1)
        self.assertEqual(self.menu.acts[0].fired, 0)

    def test_click_that_closes_the_menu_and_runs_nothing(self):
        def on(ev, real=self.menu.on):
            if ev.t == "MouseButtonRelease":
                self.menu.close()  # closed, nothing run (as seen live)
                return
            real(ev)
        self.menu.on = on
        self.run.run(self.steps(tp.ARROW, {"click": {"window": [40, 120]}}))
        a = self.answers[0]
        self.assertEqual(a["steps"][1]["hit"]["menu"], "item run (the click closed the menu and did not run it)")
        self.assertEqual(self.menu.acts[1].fired, 1)
        # The tool button's menu was not opened again.
        self.assertNotIn("opened (popup", str(a["steps"][1]))
        self.assertIsNone(self.state["popup"])

    def test_click_that_does_not_take_is_picked_once(self):
        self.menu.on = lambda ev, real=self.menu.on: real(ev) if ev.t != "MouseButtonRelease" else None
        self.run.run(self.steps(tp.ARROW, {"click": {"window": [40, 120]}}))
        a = self.answers[0]
        self.assertEqual(a["steps"][1]["hit"]["menu"], "picked with Return (the click did not take)")
        self.assertEqual(self.menu.acts[1].fired, 1)
        self.assertEqual(self.menu.acts[1].triggered.fns, [])  # no watch left


class Hidden(tg.Widget):
    def __init__(self, *a, shown=True, **k):
        super().__init__(*a, **k)
        self.shown = shown

    def isVisible(self):
        return self.shown and (self.parent is None or self.parent.isVisible())


class DialogWords(unittest.TestCase):
    """85."""

    def test_closed_popup_left_out(self):
        d = Hidden("Insert Length", 0, 0, 300, 120, cls="QDialog")
        ok = Hidden("ok", 0, 90, 60, 20, parent=d, cls="QPushButton")
        old = Hidden("editor", 0, 0, 200, 60, parent=d, cls="QDialog", shown=False)
        old_ok = Hidden("ok2", 0, 0, 60, 20, parent=old, cls="QPushButton")
        live = Hidden("editor2", 0, 0, 200, 60, parent=d, cls="QDialog")
        live_ok = Hidden("ok3", 0, 0, 60, 20, parent=live, cls="QPushButton")
        # Child windows: window() is themselves.
        old.window = lambda: old
        live.window = lambda: live
        for w in (ok, old_ok, live_ok):
            self.assertTrue(w.isVisible() or w is old_ok)
        self.assertTrue(gui_link.shown_in(d, ok))
        self.assertFalse(gui_link.shown_in(d, old_ok))
        self.assertTrue(gui_link.shown_in(d, live_ok))
        empty = Hidden("e", 0, 0, 0, 0, parent=d)
        self.assertFalse(gui_link.shown_in(d, empty))


def batch(*calls):
    return call("batch", {"calls": [{"tool": t, "arguments": a} for t, a in calls]})


class DeclaredReads(unittest.TestCase):
    """56c and 81."""

    def tutor(self):
        return protocol.Tool("tutor", "", {"properties": {"action": {"type": "string", "default": "status"}}}, None, front_reads={"action": ["status", "list"]})

    def test_tool_front_read(self):
        t = self.tutor()
        self.assertTrue(t.front_read({}))  # status by default
        self.assertTrue(t.front_read({"action": "list"}))
        self.assertFalse(t.front_read({"action": "next"}))
        self.assertFalse(protocol.Tool("x", "", {}, None).front_read({}))

    def test_link_lets_declared_reads_through(self):
        link = gui_link.Link.__new__(gui_link.Link)
        link.server = types.SimpleNamespace(tools={"tutor": self.tutor(), "session_state": protocol.Tool("session_state", "", {}, None)})
        line = batch(("gui_input", {}), ("window_snapshot", {}), ("tutor", {"action": "status"}), ("session_state", {}))
        self.assertTrue(gui_link._dialog_call(line, link._read_ok, link._declared_read))
        self.assertFalse(gui_link._dialog_call(batch(("gui_input", {}), ("tutor", {"action": "next"})), link._read_ok, link._declared_read))
        # Without the declaration (an older add-on): refused as before.
        self.assertFalse(gui_link._dialog_call(line, link._read_ok))

    def test_snapshot_alone(self):
        self.assertTrue(gui_link._dialog_call(call("window_snapshot", {})))
        self.assertFalse(gui_link._dialog_call(call("session_state", {})))

    def test_tool_data_field(self):
        from agentlink import tooldata

        doc = {"dataVersion": "1.0.0", "entries": {"tutor": {"group": "tutor", "description": "Run a lesson in the window, step by step.", "inputSchema": {"type": "object", "properties": {}},
                                                               "changes": False, "source": "x", "date": "2026-11-18", "frontReads": {"action": ["status"]}}}}
        self.assertEqual(tooldata.check(doc), [])
        doc["entries"]["tutor"]["frontReads"] = ["status"]
        self.assertTrue(tooldata.check(doc))


class Watchdog(unittest.TestCase):
    """87."""

    def test_nested_loop_timed_from_the_dialog(self):
        from agentlink import supervise

        now = time.time()
        hb = {"busy": "gui_input", "busySince": now - 112, "t": now, "loops": 2, "dialog": None, "popup": None}
        self.assertIsNotNone(supervise.nested_hang(hb, now, limit=60))
        hb["frontAt"] = now - 3  # OK was pressed 3 s ago
        self.assertIsNone(supervise.nested_hang(hb, now, limit=60))
        hb["frontAt"] = now - 90  # the loop did not end in 90 s after it
        self.assertIsNotNone(supervise.nested_hang(hb, now, limit=60))

    def test_heartbeat_says_front_at(self):
        link = gui_link.Link.__new__(gui_link.Link)
        link.busy, link.busy_since, link._front_at = "gui_input", 100.0, 150.0
        link.until = link.stuck = None
        self.assertEqual(link._busy_beat().get("frontAt"), 150.0)
        link._front_at = 50.0  # before this call: not said
        self.assertNotIn("frontAt", link._busy_beat())


class BatchClock(unittest.TestCase):
    """84."""

    def test_own_clock_after_an_answered_batch(self):
        from agentlink import batchrec

        self.assertEqual(batchrec.clock_start(None, 500.0), 500.0)
        self.assertEqual(batchrec.clock_start({"t0": 100.0, "answered": False}, 500.0), 100.0)  # a call inside it
        self.assertEqual(batchrec.clock_start({"t0": 100.0, "answered": True}, 500.0), 500.0)  # the client's next call


class FrontDocument(unittest.TestCase):
    """79: the parts of the check that need no window."""

    def test_kinds(self):
        steps = gi.parse_steps([{"click": {"view": [10, 10]}}, {"shot": "a"}, {"drag": {"from": {"window": [1, 2]}, "to": {"window": [3, 4]}}}])
        self.assertEqual(gi.target_kinds(steps), {"view", "window"})
        self.assertTrue(gi.acts(steps))
        self.assertFalse(gi.acts(gi.parse_steps([{"shot": "a"}, {"wait": 10}])))


class CookbookWorkbench(unittest.TestCase):
    """88."""

    def test_scaffold_records_it(self):
        from agentlink import porting

        doc = porting.cookbook_json({"name": "Texturizer", "package": "texturizer", "workbench": "TexturizerWorkbench"}, "texturizer",
                                    [{"tool": "tex_check", "description": "Check the texture.", "command": "Texturizer_Check"}], "2026-11-18")
        self.assertEqual(doc["addon"]["workbench"], "TexturizerWorkbench")

    def test_run_activates_first(self):
        from agentlink import cookbook

        got = []
        orig = (cookbook.load, cookbook.state)
        cookbook.load = lambda name, tools=(), kept=None: ({"addon": {"package": "texturizer", "workbench": "TexturizerWorkbench"},
                                                            "entries": {"check": {"recipe": {"command": "Texturizer_Check"}}}}, "sha", [])
        cookbook.state = lambda name, sha: "approved"
        self.addCleanup(lambda: (setattr(cookbook, "load", orig[0]), setattr(cookbook, "state", orig[1])))
        out = cookbook.run("texturizer", "check", {}, {"command": lambda c, i: got.append(("cmd", c)) or {"ran": c},
                                                        "workbench": lambda wb, c: got.append(("wb", wb)) or f"activated {wb} first"})
        self.assertEqual(got, [("wb", "TexturizerWorkbench"), ("cmd", "Texturizer_Check")])
        self.assertEqual(out["workbench"], "activated TexturizerWorkbench first")

    def test_check_takes_the_field(self):
        from agentlink import cookbook

        def doc(wb):
            return {"cookbookVersion": "1.0.0", "name": "texturizer", "about": "Texturizer commands.", "addon": {"package": "texturizer", "workbench": wb},
                    "entries": {"check": {"description": "Check the texture.", "recipe": {"command": "Texturizer_Check"}}}}
        self.assertFalse([p for p in cookbook.check(doc("TexturizerWorkbench")) if "workbench" in p])
        self.assertTrue([p for p in cookbook.check(doc("bad name")) if "workbench" in p])


if __name__ == "__main__":
    unittest.main()
