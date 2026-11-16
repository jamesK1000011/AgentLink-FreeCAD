# SPDX-License-Identifier: LGPL-2.1-or-later
# batch { build: "end" } (agentlink/hold.py): which calls are held, what a
# held answer says, and the one build with its health. Plain Python: a
# document stood in by an object with FreeCAD's RecomputesFrozen switch.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import hold as H  # noqa: E402


class Doc:
    """FreeCAD's Document as far as a hold goes: recompute() does nothing
    and answers 0 while RecomputesFrozen (FreeCAD 1.1 source:
    src/App/Document.cpp, Document::recompute)."""

    def __init__(self, frozen=False):
        self.RecomputesFrozen = frozen
        self.built = 0

    def recompute(self):
        if self.RecomputesFrozen:
            return 0
        self.built += 1
        return 4


class NoSwitch:
    def recompute(self):
        return 1


def new(health=None, log=None):
    log = [] if log is None else log

    def mark(doc):
        log.append("mark")
        return {"m": 1}

    def check(m, tools):
        log.append(("check", tools))
        return None if tools is None else health

    return H.Hold(mark, check, lambda doc: log.append("snapshot")), log


class Plan(unittest.TestCase):
    def test_which_calls_are_held(self):
        h, _ = new()
        for t in ("sketch_add", "sketch_constrain", "sketch_edit", "sketch_offset", "object_set"):
            self.assertEqual(h.plan(t, True), "hold", t)
        # A tool that builds for itself or reads geometry: the run is built first.
        for t, changing in (("pd_pad", True), ("sketch_new", True), ("param_set", True), ("sketch_state", False), ("session_state", False), ("body_check", False)):
            self.assertEqual(h.plan(t, changing), "build", t)
        for t in H.NO_BUILD:
            self.assertEqual(h.plan(t, False), "pass", t)
        # A held tool's read-only call is a read like any other.
        self.assertEqual(h.plan("object_set", False), "build")

    def test_an_add_on_declares_its_own(self):
        try:
            H.declare("x_edit", ["state.area"])
            h, _ = new()
            self.assertEqual(h.plan("x_edit", True), "hold")
            self.assertEqual(H.held_answer("x_edit", {"state": {"area": 3, "n": 1}})["state"], {"n": 1})
        finally:
            H.HELD_OK.pop("x_edit", None)

    def test_mode(self):
        self.assertEqual(H.mode(None), ("each", None))
        self.assertEqual(H.mode("each"), ("each", None))
        self.assertEqual(H.mode("end"), ("end", None))
        m, words = H.mode("never")
        self.assertIsNone(m)
        self.assertIn("\"end\"", words)


class HeldAnswer(unittest.TestCase):
    def test_no_stale_reading_is_left_in(self):
        body = {"sketch": "S", "added": [1], "state": {"solver": "solved", "dof": 2, "wires": 1, "closedWires": 1, "openVertices": [[0, 0]], "readyForFeature": False, "todo": "close"},
                "bodyAfter": {"volume": 10}, "health": {"ok": True, "verdict": "S: fully constrained"}}
        out = H.held_answer("sketch_edit", body)
        self.assertEqual(out["state"], {"solver": "solved", "dof": 2})
        self.assertNotIn("bodyAfter", out)
        self.assertEqual(out["build"], "held")
        h = out["health"]
        self.assertEqual(h["build"], "held")
        self.assertTrue(h["verdict"].startswith("build: held"))
        self.assertNotIn("ok", h)
        self.assertIn("bodyAfter", h["leftOut"])
        self.assertIn("state.wires", h["leftOut"])
        self.assertNotIn("fully constrained", h["verdict"])

    def test_nothing_to_leave_out(self):
        out = H.held_answer("object_set", {"object": "Pad", "set": {}})
        self.assertNotIn("leftOut", out["health"])
        self.assertEqual(H.held_answer("object_set", [1]), [1])


class Run(unittest.TestCase):
    def test_one_build_for_the_run(self):
        h, log = new({"ok": True, "verdict": "S: 0 DoF"})
        d = Doc()
        self.assertTrue(h.begin(d))
        self.assertTrue(d.RecomputesFrozen)
        for i, t in enumerate(("sketch_add", "sketch_constrain", "object_set")):
            self.assertEqual(d.recompute(), 0)  # the tool's own recompute, held
            h.note(i + 3, t)
        self.assertEqual(d.built, 0)
        e = h.build("end")
        self.assertFalse(d.RecomputesFrozen)
        self.assertEqual(d.built, 1)
        self.assertEqual({k: e[k] for k in ("when", "held", "calls", "recomputed")}, {"when": "end", "held": 3, "calls": [3, 5], "recomputed": 4})
        self.assertEqual(e["health"], {"ok": True, "verdict": "S: 0 DoF"})
        # The health is read once, after the build, for every held tool.
        self.assertEqual(log, ["mark", ("check", ["sketch_add", "sketch_constrain", "object_set"]), "snapshot"])
        self.assertFalse(h.active)
        self.assertIsNone(h.build("end"))
        self.assertEqual(h.builds, [e])
        self.assertFalse(H.build_failed(e))

    def test_nothing_to_say_is_nothing_red(self):
        h, _ = new(None)
        d = Doc()
        h.begin(d)
        h.note(0, "object_set")
        self.assertEqual(h.build("end")["health"], {"ok": True, "verdict": "nothing red"})

    def test_a_build_that_breaks_something(self):
        h, _ = new({"ok": False, "verdict": "1 object failed", "errors": [{"object": "Pad", "new": True}]})
        d = Doc()
        h.begin(d)
        h.note(0, "sketch_edit")
        self.assertTrue(H.build_failed(h.build("end")))
        self.assertFalse(H.build_failed({"health": {"ok": False, "errors": [{"object": "Old"}]}}))
        self.assertFalse(H.build_failed(None))

    def test_the_persons_own_switch_is_left_alone(self):
        h, log = new()
        d = Doc(frozen=True)
        self.assertFalse(h.begin(d))
        self.assertTrue(d.RecomputesFrozen)
        self.assertIn("already switched off", h.off)
        self.assertEqual(log, [])
        # From then on nothing is held or built first.
        self.assertEqual(h.plan("sketch_add", True), "pass")
        self.assertEqual(h.plan("pd_pad", True), "pass")

    def test_a_freecad_without_the_switch(self):
        h, _ = new()
        self.assertFalse(h.begin(NoSwitch()))
        self.assertIn("no RecomputesFrozen", h.off)

    def test_release_builds_nothing(self):
        h, log = new({"ok": True})
        d = Doc()
        h.begin(d)
        h.note(0, "sketch_add")
        h.release()
        self.assertFalse(d.RecomputesFrozen)
        self.assertEqual(d.built, 0)
        self.assertEqual(log, ["mark", ("check", None)])
        self.assertEqual(h.builds, [])

    def test_a_recompute_that_raises_still_lets_go(self):
        class Bad(Doc):
            def recompute(self):
                raise RuntimeError("boom")

        h, _ = new(None)
        d = Bad()
        h.begin(d)
        h.note(0, "sketch_add")
        e = h.build("end")
        self.assertFalse(d.RecomputesFrozen)
        self.assertIn("boom", e["error"])
        self.assertIs(e["health"]["ok"], False)
        self.assertTrue(H.build_failed(e))


if __name__ == "__main__":
    unittest.main()
