# SPDX-License-Identifier: LGPL-2.1-or-later
# The hook contract (Agent Link API 1): plain Python, no FreeCAD.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import hooks  # noqa: E402
from agentlink.protocol import Tool, ToolError  # noqa: E402


class Hooks(unittest.TestCase):
    # What other add-ons registered (other tests' servers) is put back.
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()

    def tearDown(self):
        hooks.restore(self.state)

    def test_api_ranges(self):
        self.assertTrue(hooks.api_ok(None))
        self.assertTrue(hooks.api_ok(">=1,<2"))
        self.assertFalse(hooks.api_ok(">=2"))
        self.assertFalse(hooks.api_ok("~1"))

    def test_readers_first_answer_wins_and_failures_pass(self):
        live = hooks.readers("wall")
        hooks.register_reader("wall", lambda s: None)
        hooks.register_reader("wall", lambda s: 1 / 0)
        hooks.register_reader("wall", lambda s: {"least": 1.2})
        live.append(lambda s: {"least": 9})  # an add-on using the old list
        self.assertEqual(hooks.read("wall", "shape"), {"least": 1.2})
        self.assertEqual(len(hooks.readers("wall")), 4)

    def test_services_and_events(self):
        self.assertIsNone(hooks.service("process_of"))
        hooks.provide("process_of", lambda doc, body: "print")
        self.assertEqual(hooks.service("process_of")(None, "B"), "print")
        seen = []
        hooks.on("after_change", lambda s, t: seen.append(t))
        hooks.on("after_change", lambda s, t: 1 / 0)
        hooks.emit("after_change", None, "body_add")
        self.assertEqual(seen, ["body_add"])

    def test_extend_tool(self):
        t = Tool("fea_setup", "x", {"type": "object", "properties": {"body": {"type": "string"}}}, lambda a: {"body": a["body"], "keys": sorted(a)})

        def before(a, s):
            if a.get("printed") and not a.get("body"):
                raise ToolError("invalid_input", "body: which body.")

        def after(a, out, s):
            if a.get("printed"):
                return {**out, "printed": True}

        hooks.extend_tool("fea_setup", {"printed": {"type": "boolean"}}, before, after, "printed: true for a printed part.")
        hooks.apply_extensions([t], session=None)
        self.assertIn("printed", t.schema["properties"])
        self.assertEqual(t.description, "x printed: true for a printed part.")
        out = t.fn({"body": "B", "printed": True})
        # The owner never sees the extension's arguments.
        self.assertEqual(out, {"body": "B", "keys": ["body"], "printed": True})
        self.assertEqual(t.fn({"body": "B"}), {"body": "B", "keys": ["body"]})

    def test_tabs_reviewers_guards_results(self):
        hooks.register_tab("Late", lambda p: None, 90)
        hooks.register_tab("Early", lambda p: None, 10)
        self.assertEqual([x["title"] for x in hooks.TABS], ["Early", "Late"])
        f = hooks.register_reviewer(lambda s, b: {"verdict": "ok"})
        self.assertIs(hooks.REVIEWERS[0], f)
        hooks.guard_setting("Mod/X", "Allow")
        self.assertIn(("Mod/X", "Allow"), hooks.GUARDED)

        class S:
            pass

        s = S()
        self.assertIsNone(hooks.analysis(s, "fea"))
        hooks.remember(s, "fea", {"safety": 2.0})
        self.assertEqual(hooks.analysis(s, "fea"), {"safety": 2.0})


if __name__ == "__main__":
    unittest.main()
