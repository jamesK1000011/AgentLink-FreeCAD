# SPDX-License-Identifier: LGPL-2.1-or-later
# gui_input's dev-only as: "person": a student agent standing in for the
# person beside a tutor agent on the same link. Its steps' window events
# and its own call_done are the person's; every other call stays the
# agent's, before, after and inside it; it closes on an error and once the
# answer is decided while a step's menu still holds the call.
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import gui_events, hooks  # noqa: E402
from agentlink import gui_input as gi  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


class Sess:
    def __init__(self):
        self.tx, self.doc, self.by = 0, object(), hooks.AGENT


def call(s, name, args=None):
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})
    return r["result"].get("isError", False), json.loads(r["result"]["content"][0]["text"])


class Base(unittest.TestCase):
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()

    def tearDown(self):
        hooks.restore(self.state)
        self.assertFalse(hooks._PERSON_AT)


class PersonInput(Base):
    def test_only_at_its_own_depth(self):
        seen = []
        with hooks.acting():
            seen.append(hooks.agent_acting())
            with hooks.person_input() as p:
                seen.append(hooks.agent_acting())
                with hooks.acting():  # the tutor's call taken inside it
                    seen.append(hooks.agent_acting())
                seen.append(hooks.agent_acting())
                p.close()
                seen.append(hooks.agent_acting())
                p.close()  # twice is harmless
            seen.append(hooks.agent_acting())
        self.assertEqual(seen, [True, False, True, False, True, True])
        self.assertFalse(hooks.agent_acting())

    def test_closed_on_an_error(self):
        with hooks.acting():
            with self.assertRaises(RuntimeError):
                with hooks.person_input():
                    raise RuntimeError("boom")
            self.assertTrue(hooks.agent_acting())

    def test_window_events_by_whom(self):
        got = []
        hooks.on("command_used", lambda name, by: got.append(by))
        hooks.on("workbench_activated", lambda name, by: got.append(by))
        with hooks.acting():
            gui_events._emit("command_used", "PartDesign_Pad")
            with hooks.person_input():
                gui_events._emit("command_used", "PartDesign_Pad")
                gui_events._emit("workbench_activated", "SketcherWorkbench")
            gui_events._emit("workbench_activated", "PartDesignWorkbench")
        self.assertEqual(got, ["agent", "person", "person", "agent"])


def two_agents():
    """One server, one session, as the window's link has it: the student's
    tool (gui_input's as: "person", in small) and the tutor's."""
    sess = Sess()
    seen = []

    def student(a):
        if a.get("as") == "person":
            with hooks.person_input():
                try:
                    seen.append(("student", hooks.agent_acting()))
                    if a.get("inner"):
                        call(srv, "tutor")  # a call taken inside its steps
                        seen.append(("student", hooks.agent_acting()))
                    if a.get("boom"):
                        raise RuntimeError("boom")
                finally:
                    sess.done_by = hooks.PERSON
        else:
            seen.append(("student", hooks.agent_acting()))
        return {"as": a.get("as")}

    def tutor(a):
        seen.append(("tutor", hooks.agent_acting()))
        return {}

    obj = {"type": "object", "properties": {"as": {"type": "string", "enum": ["person"]}, "inner": {"type": "boolean"},
                                            "boom": {"type": "boolean"}}}
    srv = Server("t", "0", [Tool("student", "S.", obj, student), Tool("tutor", "T.", {"type": "object", "properties": {}}, tutor)], "")
    srv.session = sess
    return srv, sess, seen


class TwoAgents(Base):
    def setUp(self):
        super().setUp()
        self.done = []
        hooks.on("call_done", lambda s, tool, ok, changed: self.done.append((tool, s.by)))

    def test_attribution_follows_the_call(self):
        srv, sess, seen = two_agents()
        call(srv, "tutor")
        call(srv, "student", {"as": "person"})
        call(srv, "tutor")
        call(srv, "student")  # without as: the agent's
        self.assertEqual(seen, [("tutor", True), ("student", False), ("tutor", True), ("student", True)])
        self.assertEqual(self.done, [("tutor", "agent"), ("student", "person"), ("tutor", "agent"), ("student", "agent")])
        self.assertEqual(sess.by, hooks.AGENT)
        self.assertIsNone(getattr(sess, "done_by", None))

    def test_a_tutor_call_inside_the_students(self):
        srv, sess, seen = two_agents()
        call(srv, "student", {"as": "person", "inner": True})
        self.assertEqual(seen, [("student", False), ("tutor", True), ("student", False)])
        self.assertEqual(self.done, [("tutor", "agent"), ("student", "person")])

    def test_an_error_resets(self):
        srv, sess, seen = two_agents()
        refused, _ = call(srv, "student", {"as": "person", "boom": True})
        self.assertTrue(refused)
        self.assertFalse(hooks.agent_acting())
        call(srv, "tutor")
        self.assertEqual(seen[-1], ("tutor", True))
        self.assertEqual(self.done, [("student", "person"), ("tutor", "agent")])

    def test_inside_a_batch_only_its_own_call_done(self):
        srv, sess, seen = two_agents()

        def batch(a):
            call(srv, "student", {"as": "person"})
            call(srv, "tutor")
            return {}

        srv.tools["batch"] = Tool("batch", "B.", {"type": "object", "properties": {}}, batch)
        call(srv, "batch")
        self.assertEqual(self.done, [("student", "person"), ("tutor", "agent"), ("batch", "agent")])


class RunRelease(Base):
    """gi.Run closes its person_input once the answer is decided: at the end,
    on an error, and before an answer sent from inside a held menu."""

    def run_(self, answer_now=lambda body: False):
        from test_gui_input import Widget, fake_qt

        sent = []
        mw = Widget("main", 100, 50, 1200, 800)
        vp = Widget("viewport", 400, 150, 600, 400, parent=mw, cls="QOpenGLWidget", focus=2)
        state = {"modal": None, "popup": None, "main": mw}
        state["app"] = types.SimpleNamespace(activePopupWidget=lambda: state["popup"], activeModalWidget=lambda: state["modal"],
                                             topLevelWidgets=lambda: [mw], focusWidget=lambda: None)
        qt = fake_qt(sent, state)
        gv = types.SimpleNamespace(viewport=lambda: vp)
        view = types.SimpleNamespace(getPointOnViewport=lambda v: (v[0] * 2, v[1] * 2), getSize=lambda: (1200, 800), graphicsView=lambda: gv)
        gui = types.SimpleNamespace(getMainWindow=lambda: mw, ActiveDocument=types.SimpleNamespace(ActiveView=view))
        return gi.Run(qt, gui, lambda *a: a, lambda: None, list, None, answer_now, "/nonexistent")

    def setUp(self):
        super().setUp()
        gi.HELD.update({"widget": None, "buttons": []})
        self.addCleanup(gi.HELD.update, {"widget": None, "buttons": []})

    def test_answer_echoes_and_closes(self):
        run = self.run_()
        with hooks.acting():
            with hooks.person_input() as p:
                run.person, run.as_ = p, "person"
                out = run.run(gi.parse_steps([{"click": {"view": [5, 5]}}]))
                self.assertTrue(hooks.agent_acting())  # closed before the with ends
        self.assertEqual(out["as"], "person")

    def test_closed_on_a_failing_step(self):
        run = self.run_()
        with hooks.acting():
            with hooks.person_input() as p:
                run.person, run.as_ = p, "person"
                out = run.run(gi.parse_steps([{"click": {"view": [700, 10]}}]))
                self.assertTrue(hooks.agent_acting())
        self.assertIn("error", out["steps"][0])
        self.assertEqual(out["as"], "person")

    def test_closed_before_an_answer_from_inside_a_held_menu(self):
        when = []
        run = self.run_(answer_now=lambda body: when.append((body.get("as"), hooks.agent_acting())) or True)
        with hooks.acting():
            with hooks.person_input() as p:
                run.person, run.as_ = p, "person"
                run.frames = [{"i": 0}]  # a step's nested loop still holds the call
                run._finish()
                self.assertTrue(hooks.agent_acting())
        self.assertEqual(when, [("person", True)])
        self.assertTrue(run.answered)

    def test_without_as_nothing_added(self):
        out = self.run_().run(gi.parse_steps([{"wait": 1}]))
        self.assertNotIn("as", out)


class Declared(unittest.TestCase):
    def test_tool_and_guide(self):
        root = os.path.join(os.path.dirname(__file__), "..", "agentlink")
        with open(os.path.join(root, "families", "dev.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"as": {"type": "string", "enum": ["person"]}', src)
        self.assertIn("hooks.person_input()", src)
        self.assertIn("s.done_by = hooks.PERSON", src)
        with open(os.path.join(root, "guides", "view.md"), encoding="utf-8") as f:
            self.assertIn('`as: "person"`', f.read())


if __name__ == "__main__":
    unittest.main()
