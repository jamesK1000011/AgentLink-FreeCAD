# SPDX-License-Identifier: LGPL-2.1-or-later
# Live findings of 18 Nov with Sketcher's Insert Radius dialog (FreeCAD
# 1.1.3, macOS), on stand-ins (no Qt, no FreeCAD):
#  56b: a batch of gui_input and a read (sketch_state, session_state) runs
#       while the dialog is up; a batch with a change is still refused.
#  69:  a key or text with no target goes to the dialog's value field, not
#       to the QDialog itself.
#  70:  after a call run inside the dialog's loop closes it, the loop is
#       woken so it ends; calls wait for the call in hand instead of being
#       answered "a menu or dialog is open"; dialog_answer waits for the
#       dialog's loop and is not answered busy at 10 s.
import io
import json
import os
import queue
import sys
import threading
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


def batch(*tools):
    return call("batch", {"calls": [{"tool": t, "arguments": {}} for t in tools]})


class ReadsBesideGuiInput(unittest.TestCase):
    """56b."""

    def test_reads_let_through_changes_not(self):
        self.assertTrue(gui_link._dialog_call(batch("gui_input", "sketch_state")))
        self.assertTrue(gui_link._dialog_call(batch("gui_input", "session_state", "object_list")))
        self.assertTrue(gui_link._dialog_call(batch("session_state", "gui_input")))
        # Reads alone are no answer to the dialog.
        self.assertFalse(gui_link._dialog_call(batch("sketch_state")))
        # A change beside it stays refused.
        self.assertFalse(gui_link._dialog_call(batch("gui_input", "sketch_constrain")))
        self.assertFalse(gui_link._dialog_call(batch("gui_input", "doc_new")))
        # A nested batch is no read.
        self.assertFalse(gui_link._dialog_call(batch("gui_input", "batch")))

    def test_the_window_checks_each_read(self):
        seen = []

        def read_ok(tool, args):
            seen.append(tool)
            return tool != "insp_read"
        self.assertTrue(gui_link._dialog_call(batch("gui_input", "sketch_state"), read_ok))
        self.assertFalse(gui_link._dialog_call(batch("gui_input", "insp_read"), read_ok))
        self.assertEqual(seen, ["sketch_state", "insp_read"])

    def test_read_ok_on_the_link(self):
        link = gui_link.Link.__new__(gui_link.Link)
        changing = protocol.Tool("sketch_state", "", {}, None, changes=True)
        link.server = types.SimpleNamespace(tools={"sketch_state": protocol.Tool("sketch_state", "", {}, None), "pref_get": changing})
        self.assertTrue(link._read_ok("sketch_state", {}))
        self.assertFalse(link._read_ok("pref_get", {}))  # changes: refused
        self.assertFalse(link._read_ok("object_list", {}))  # not a tool here
        link.server = None
        self.assertFalse(link._read_ok("sketch_state", {}))

    def test_supervisor_lets_it_through(self):
        from agentlink import supervise

        self.assertTrue(supervise._answers_dialog({"tool": "batch", "args": {"calls": [{"tool": "gui_input"}, {"tool": "sketch_state"}]}}))
        self.assertFalse(supervise._answers_dialog({"tool": "batch", "args": {"calls": [{"tool": "gui_input"}, {"tool": "pad"}]}}))

    def test_runs_inside_the_dialog_loop(self):
        """_handle_inbox with a dialog up: the batch of gui_input and a read
        runs; a batch with a change is answered blocked."""
        link = gui_link.Link.__new__(gui_link.Link)
        link.calls, link.front, link.going, link.in_call, link.busy = [], None, False, False, None
        link.session, link._dialog = None, None
        link.inbox = queue.Queue()
        link.server = types.SimpleNamespace(tools={"sketch_state": protocol.Tool("sketch_state", "", {}, None)})
        ran = []
        link._run_one = lambda line, f, conn: ran.append(json.loads(line)["id"])
        dialog = {"class": "SketcherGui::InsertDatum", "title": "Insert Radius", "text": "", "buttons": ["OK", "Cancel"], "widget": object()}
        old = gui_link.modal_info
        gui_link.modal_info = lambda: dialog
        self.addCleanup(setattr, gui_link, "modal_info", old)
        old_wake = gui_link.wake
        gui_link.wake = lambda: None
        self.addCleanup(setattr, gui_link, "wake", old_wake)
        ok = gui_link._Line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "batch", "arguments": {"calls": [{"tool": "gui_input", "arguments": {}}, {"tool": "sketch_state", "arguments": {}}]}}}))
        ok.ticket = {"state": "queued", "t": time.time()}
        no = gui_link._Line(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "batch", "arguments": {"calls": [{"tool": "gui_input", "arguments": {}}, {"tool": "sketch_constrain", "arguments": {}}]}}}))
        no.ticket = {"state": "queued", "t": time.time()}
        f = io.StringIO()
        link.inbox.put((ok, io.StringIO(), None))
        link.inbox.put((no, f, None))
        link._handle_inbox()
        self.assertEqual(ran, [1])
        msg = json.loads(json.loads(f.getvalue())["result"]["content"][0]["text"])["error"]["message"]
        self.assertTrue(msg.startswith("Blocked by a dialog"), msg)


class Field(tg.Widget):
    def __init__(self, name, parent, cls, chain):
        super().__init__(name, parent.ox + 10, parent.oy + 30, 120, 24, parent=parent, cls=cls)
        self.chain = chain

    def metaObject(self):
        names = [self.cls] + self.chain

        def meta(i):
            return types.SimpleNamespace(className=lambda: names[i], superClass=lambda: meta(i + 1) if i + 1 < len(names) else None)
        return meta(0)


class KeysToTheDialogsField(tp.Base):
    """69: Sketcher's Insert Radius in front, the window in the background:
    Qt keeps no focus widget, and keys with no target went to the QDialog."""

    def setUp(self):
        super().setUp()
        d = self.dialog
        d.kids = []
        self.label = tg.Widget("label", d.ox + 10, d.oy + 5, 100, 20, parent=d, cls="QLabel")
        self.value = Field("labelEdit", d, "Gui::QuantitySpinBox", ["QAbstractSpinBox", "QWidget"])
        self.name = Field("name", d, "QLineEdit", ["QWidget"])
        self.state["modal"] = d
        d.shown = True

    def keys_went_to(self, *steps):
        self.sent.clear()
        out = self.run.run(self.steps(*steps))
        return out, {n for n, _ev in self.sent}

    def test_first_field_takes_keys_and_text(self):
        out, to = self.keys_went_to({"key": "a", "modifiers": ["ctrl"]}, {"type": "7"})
        self.assertEqual(to, {"labelEdit"})
        self.assertEqual(out["steps"][0]["hit"]["class"], "Gui::QuantitySpinBox")
        self.assertTrue(self.value.focused)

    def test_the_dialogs_own_focus_widget_first(self):
        self.name.focused = True
        _out, to = self.keys_went_to({"type": "r1"})
        self.assertEqual(to, {"name"})

    def test_the_applications_focus_widget_when_inside(self):
        self.state["app"].focusWidget = lambda: self.name
        _out, to = self.keys_went_to({"type": "x"})
        self.assertEqual(to, {"name"})
        # One outside the dialog is not taken.
        self.state["app"].focusWidget = lambda: self.mw
        _out, to = self.keys_went_to({"type": "x"})
        self.assertEqual(to, {"labelEdit"})

    def test_no_field_the_dialog(self):
        self.dialog.kids = []
        _out, to = self.keys_went_to({"key": "Escape"})
        self.assertEqual(to, {"Attachment"})


class LoopWokenWhenTheDialogCloses(unittest.TestCase):
    """70."""

    def link(self):
        link = gui_link.Link.__new__(gui_link.Link)
        link.calls, link.front, link.going, link.in_call, link.busy = [], None, False, True, "batch"
        link.session, link._dialog = None, None
        link.inbox = queue.Queue()
        link.server = None
        return link

    def patch(self, name, value):
        old = getattr(gui_link, name)
        setattr(gui_link, name, value)
        self.addCleanup(setattr, gui_link, name, old)

    def test_woken_after_a_call_closed_it(self):
        widget = object()
        state = {"dialog": {"class": "QDialog", "title": "Insert Radius", "text": "", "buttons": ["OK"], "widget": widget}}
        woke = []
        self.patch("modal_info", lambda: state["dialog"])
        self.patch("popup_info", lambda: None)
        self.patch("wake", lambda: woke.append(1))
        link = self.link()
        link._run_one = lambda line, f, conn: state.update(dialog=None)  # its gui_input pressed OK
        line = gui_link._Line(call("dialog_answer", {"button": "OK"}))
        line.ticket = {"state": "queued", "t": time.time()}
        link.inbox.put((line, io.StringIO(), None))
        link._handle_inbox()
        self.assertEqual(woke, [1])
        # Still open after the call: not woken.
        state["dialog"] = {"class": "QDialog", "title": "Insert Radius", "text": "", "buttons": ["OK"], "widget": widget}
        link._run_one = lambda line, f, conn: None
        link.inbox.put((line, io.StringIO(), None))
        link._handle_inbox()
        self.assertEqual(woke, [1])

    def test_heartbeat_wakes_a_loop_left_running(self):
        woke = []
        self.patch("wake", lambda: woke.append(1))
        self.patch("popup_info", lambda: None)
        levels = {"n": 2}
        self.patch("loop_level", lambda: levels["n"])
        link = self.link()
        link._wake_ended_loop(None)
        self.assertEqual(woke, [])  # no call answered early
        link.calls.append({"id": 1, "name": "batch", "answered": True})
        link._wake_ended_loop({"title": "Insert Radius"})
        self.assertEqual(woke, [])  # a dialog still up
        link._wake_ended_loop(None)
        self.assertEqual(woke, [1])
        levels["n"] = 1
        link._wake_ended_loop(None)
        self.assertEqual(woke, [1])  # back in the main loop

    def test_calls_wait_for_the_call_ending(self):
        woke = []
        self.patch("wake", lambda: woke.append(1))
        link = self.link()
        link.calls.append({"id": 1, "name": "batch", "answered": True})
        self.assertIsNone(link._stuck())  # waited for, not "a menu or dialog is open"
        self.assertTrue(woke)
        link._ending_since = time.time() - gui_link.ENDING_WAIT - 1
        why = link._stuck()
        self.assertIn("no menu or dialog is open", why)
        # With the dialog still up: said as before.
        link.front = {"kind": "dialog", "title": "Insert Radius", "buttons": ["OK"]}
        self.assertIn("Insert Radius", link._stuck())
        self.assertIsNone(link._ending_since)

    def test_dialog_answer_not_answered_busy_while_only_a_dialog_is_up(self):
        link = self.link()
        link.calls.append({"id": 1, "name": "batch", "answered": True})
        link.front = {"kind": "dialog", "title": "Insert Radius", "buttons": ["OK"]}
        self.patch("FRONT_WAIT", 0.3)
        f = io.StringIO()
        line = gui_link._Line(call("dialog_answer", {"button": "OK"}))
        line.ticket = {"state": "queued", "t": time.time()}
        other = gui_link._Line(call("session_state"))
        other.ticket = {"state": "queued", "t": time.time()}
        g = io.StringIO()
        t0 = time.time()
        th = link._arm_busy(line, f, after=0.05, tick=0.02)
        th2 = link._arm_busy(other, g, after=0.05, tick=0.02)
        th2.join(2)
        self.assertIn("Insert Radius", g.getvalue())  # another call: busy at once
        self.assertEqual(f.getvalue(), "")
        th.join(2)
        self.assertGreaterEqual(time.time() - t0, 0.3)  # waited FRONT_WAIT first
        self.assertIn("busy", f.getvalue())

    def test_wake_without_qt_is_harmless(self):
        gui_link.wake()


if __name__ == "__main__":
    unittest.main()
