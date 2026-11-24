# SPDX-License-Identifier: LGPL-2.1-or-later
# A refusal says what the refused call left (outcome), and code that calls
# sys.exit is refused without stopping the server. No FreeCAD needed.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import changes  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402

EMPTY = {"type": "object", "properties": {}}


def call(s, name, args=None):
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})["result"]
    return r, json.loads(r["content"][0]["text"])


def server():
    def refuse(a):
        raise ToolError("invalid_state", "not now")

    def made_then_refused(a):
        e = ToolError("invalid_state", "half way")
        e.outcome, e.outcome_left = "cleanup_incomplete", ["Pad"]
        raise e

    def leave(a):
        sys.exit(0)

    def stop(a):
        raise KeyboardInterrupt()

    tools = [
        Tool("read_refuse", "A read that refuses.", EMPTY, refuse),
        Tool("change_refuse", "A change refused before it starts.", EMPTY, refuse, changes=True),
        Tool("change_left", "A change that leaves objects.", EMPTY, made_then_refused, changes=True),
        Tool("exits", "Code that calls sys.exit.", EMPTY, leave, changes=True),
        Tool("interrupts", "Code that raises KeyboardInterrupt.", EMPTY, stop, changes=True),
        Tool("ok", "Fine.", EMPTY, lambda a: {"fine": True}),
    ]
    return Server("t", "0", tools)


class Outcome(unittest.TestCase):
    def test_read_refusal_has_no_outcome(self):
        r, b = call(server(), "read_refuse")
        self.assertTrue(r["isError"])
        self.assertNotIn("status", b["error"])

    def test_change_refused_before_it_starts(self):
        r, b = call(server(), "change_refuse")
        self.assertEqual(b["error"]["status"], "not_started")
        self.assertNotIn("left", b["error"])

    def test_cleanup_incomplete_names_what_stays(self):
        r, b = call(server(), "change_left")
        self.assertEqual(b["error"]["status"], "cleanup_incomplete")
        self.assertEqual(b["error"]["left"], ["Pad"])

    def test_invalid_input_is_not_started(self):
        s = Server("t", "0", [Tool("c", "c", {"type": "object", "properties": {"x": {"type": "number"}}, "additionalProperties": False}, lambda a: {}, changes=True)])
        r, b = call(s, "c", {"y": 1})
        self.assertEqual(b["error"]["code"], "invalid_input")
        self.assertEqual(b["error"]["status"], "not_started")


class Exit(unittest.TestCase):
    def test_sys_exit_is_refused_and_the_server_goes_on(self):
        s = server()
        r, b = call(s, "exits")
        self.assertTrue(r["isError"])
        self.assertEqual(b["error"]["code"], "failed")
        self.assertIn("called exit", b["error"]["message"])
        self.assertEqual(b["error"]["status"], "not_started")
        r, b = call(s, "ok")
        self.assertEqual(b["fine"], True)

    def test_a_read_that_exits_says_nothing_changed(self):
        # Live, 22 Nov: a read that called exit was answered "some objects stay".
        def bye(a):
            raise SystemExit(0)
        s = Server("t", "0", [Tool("r", "r", {"type": "object", "properties": {}}, bye)])
        r, b = call(s, "r")
        self.assertIn("it is a read, so nothing changed", b["error"]["message"])
        self.assertNotIn("objects stay", b["error"]["message"])

    def test_keyboard_interrupt_is_refused(self):
        r, b = call(server(), "interrupts")
        self.assertEqual(b["error"]["code"], "failed")
        self.assertIn("KeyboardInterrupt", b["error"]["message"])


class _Obj:
    def __init__(self, name, label=None):
        self.Name, self.Label = name, label or name


class _Doc:
    def __init__(self, names):
        self.Objects = [_Obj(n) for n in names]


class MarkOutcome(unittest.TestCase):
    def mark(self, ev, removed, doc_names, names0):
        e = RuntimeError("x")
        changes.mark_outcome(e, ev, removed, _Doc(doc_names), set(names0))
        return e

    def test_nothing_touched(self):
        e = self.mark([(changes.RECOMPUTED, "D", "Box", None), (changes.VIEW, "D", "Box", None)], [], ["Box"], ["Box"])
        self.assertEqual(e.outcome, "not_started")

    def test_changed_and_taken_back(self):
        e = self.mark([(changes.CHANGED, "D", "Box", "Length")], [], ["Box"], ["Box"])
        self.assertEqual(e.outcome, "rolled_back")
        e = self.mark([], ["Pad"], ["Box"], ["Box"])
        self.assertEqual(e.outcome, "rolled_back")

    def test_objects_that_stay_are_named(self):
        e = self.mark([(changes.NEW, "D", "Pad", None)], [], ["Box", "Pad"], ["Box"])
        self.assertEqual(e.outcome, "cleanup_incomplete")
        self.assertEqual(e.outcome_left, ["Pad"])

    def test_an_outcome_already_set_is_kept(self):
        e = RuntimeError("x")
        e.outcome = "partial"
        changes.mark_outcome(e, [], [], _Doc([]), set())
        self.assertEqual(e.outcome, "partial")

    def test_sys_exit_takes_an_outcome(self):
        e = SystemExit(0)
        changes.mark_outcome(e, [], [], _Doc([]), set())
        self.assertEqual(e.outcome, "not_started")


if __name__ == "__main__":
    unittest.main()
