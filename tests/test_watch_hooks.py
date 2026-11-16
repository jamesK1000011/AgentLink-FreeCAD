# SPDX-License-Identifier: LGPL-2.1-or-later
# Hooks for add-ons that follow the person: agent_acting while the agent's
# own call runs, socket-thread tools answered without the GUI thread's work,
# and window events (workbench_activated, command_used) on only while
# watched, joining only their own slots.
import json
import os
import sys
import threading
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import gui_events, hooks  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402


class Sess:
    def __init__(self):
        self.tx, self.doc, self.by = 0, object(), hooks.AGENT


def server(session):
    seen = []

    def look(a):
        seen.append(hooks.agent_acting())
        return {"ok": True}

    def wait(a):
        if a.get("bad"):
            raise ToolError("invalid_input", "bad")
        return {"waited": a.get("s", 0), "acting": hooks.agent_acting(), "thread": threading.current_thread().name}

    s = Server("t", "0", [Tool("look", "Look.", {"type": "object", "properties": {}}, look),
                          Tool("watch", "Watch.", {"type": "object", "properties": {"s": {"type": "number"}, "bad": {"type": "boolean"}},
                                                    "additionalProperties": False}, wait)], "")
    s.session = session
    return s, seen


def call(s, name, args=None, light=False):
    msg = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
    r = (s.handle_light if light else s.handle)(msg)
    return r["result"].get("isError", False), json.loads(r["result"]["content"][0]["text"])


class Base(unittest.TestCase):
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()

    def tearDown(self):
        hooks.restore(self.state)


class Acting(Base):
    def test_during_the_agents_call_only(self):
        sess = Sess()
        s, seen = server(sess)
        self.assertFalse(hooks.agent_acting())
        call(s, "look")
        with hooks.as_person(sess):
            call(s, "look")  # a panel click: the person's
        self.assertEqual(seen, [True, False])
        self.assertFalse(hooks.agent_acting())

    def test_after_a_refusal_too(self):
        sess = Sess()
        s, _ = server(sess)
        s.tools["look"].fn = lambda a: (_ for _ in ()).throw(RuntimeError("boom"))
        refused, _ = call(s, "look")
        self.assertTrue(refused)
        self.assertFalse(hooks.agent_acting())


class ThreadTools(Base):
    def test_light_call_skips_the_windows_work(self):
        sess = Sess()
        s, _ = server(sess)
        done, rider = [], []
        hooks.on("call_done", lambda *a: done.append(a))
        hooks.register_rider("x", lambda tool: rider.append(tool) or "line")
        refused, out = call(s, "watch", {"s": 2}, light=True)
        self.assertFalse(refused)
        self.assertEqual((out["waited"], out["acting"]), (2, False))
        self.assertNotIn("rider", out)
        self.assertEqual((done, rider), ([], []))
        self.assertTrue(call(s, "watch", {"bad": True}, light=True)[0])
        refused, out = call(s, "watch", {"nope": 1}, light=True)
        self.assertIn("not a known field", out["error"]["message"])
        self.assertEqual(call(s, "missing", light=True)[1]["error"]["code"], "not_found")

    def test_register(self):
        hooks.register_thread_tool("watch")
        self.assertIn("watch", hooks.THREAD_TOOLS)
        hooks.THREAD_TOOLS.discard("watch")

    def test_gui_link_answers_them_off_the_inbox(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "agentlink", "gui_link.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("if self._thread_call(line, f):", src)
        self.assertIn("hooks.THREAD_TOOLS", src)
        self.assertEqual(src.count("with self._writes()"), 2)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def disconnect(self, fn):
        self.slots.remove(fn)

    def fire(self, *a):
        for fn in list(self.slots):
            fn(*a)


class Action:
    def __init__(self, name, dead=False):
        self.n, self.dead = name, dead
        self.triggered = Signal()
        self.triggered.connect(lambda *a: None)  # FreeCAD's own slot

    def objectName(self):
        if self.dead:
            raise RuntimeError("deleted")
        return self.n

    def property(self, k):
        return None


class WindowEvents(Base):
    def tearDown(self):
        gui_events._STATE.update(on=False, mw=None, bench=None, acts={})
        super().tearDown()

    def test_command_used_by_whom(self):
        got = []
        hooks.on("command_used", lambda name, by: got.append((name, by)))
        acts = [Action("PartDesign_Pad"), Action(""), Action("Sketcher_CreateRectangle")]
        self.assertEqual(gui_events.join_actions(acts, gui_events._connect), 2)
        self.assertEqual(gui_events.join_actions(acts, gui_events._connect), 0)  # joined once
        acts[0].triggered.fire(False)
        with hooks.acting():
            acts[2].triggered.fire(False)
        self.assertEqual(got, [("PartDesign_Pad", "person"), ("Sketcher_CreateRectangle", "agent")])

    def test_detach_takes_off_only_its_own_slots(self):
        a = Action("Std_Undo")
        gui_events.join_actions([a], gui_events._connect)
        self.assertEqual(len(a.triggered.slots), 2)
        gui_events._STATE.update(on=True, mw=types.SimpleNamespace(workbenchActivated=Signal()))
        gui_events.detach()
        self.assertEqual(len(a.triggered.slots), 1)  # FreeCAD's own stays
        self.assertEqual(gui_events._STATE["acts"], {})

    def test_gone_actions_forgotten(self):
        a, b = Action("A"), Action("B")
        gui_events.join_actions([a, b], gui_events._connect)
        a.dead = True
        gui_events.join_actions([b], gui_events._connect)
        self.assertEqual([n for _a, n, _s in gui_events._STATE["acts"].values()], ["B"])

    def test_no_window_no_events(self):
        self.assertFalse(hooks.watch_window("tutor"))
        hooks.unwatch_window("tutor")
        self.assertFalse(gui_events._STATE["on"])


if __name__ == "__main__":
    unittest.main()
