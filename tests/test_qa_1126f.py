# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA 1126e leftovers, fixed in round 7 (26 Nov)."""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class ExampleOfTheRightKind(unittest.TestCase):
    """A refusal about one sketch kind does not show an example of another
    (a rounded_rectangle radius refusal showed an arc)."""

    def tool(self):
        return types.SimpleNamespace(name="sketch_add", schema={"properties": {"items": {}, "sketch": {}}})

    def test_other_kind_gives_no_example(self):
        from agentlink import protocol

        got = protocol.example_words(self.tool(), "invalid_input",
                                     "items[0]: rounded_rectangle.radius: over 0 and under half the short side (27.0 mm).")
        self.assertEqual(got, "")

    def test_same_kind_keeps_the_example(self):
        from agentlink import protocol

        got = protocol.example_words(self.tool(), "invalid_input", "items[0]: arc.radius: over 0.")
        self.assertIn('"kind":"arc"', got)


class SketchNewPlaneOrFace(unittest.TestCase):
    """Neither plane nor face is its own refusal, not "not both"."""

    def rules(self):
        import json

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            text = f.read()
        return json.loads(text), text

    def test_two_refusals(self):
        _, text = self.rules()
        self.assertNotIn("\"when\": \"=('plane' in a) == ('face' in a)\"", text)
        self.assertEqual(text.count("No plane or face was given."), 2)
        self.assertEqual(text.count("\"when\": \"=('plane' in a) and ('face' in a)\""), 2)


class SlotCard(unittest.TestCase):
    def test_card_names_radius2(self):
        import json

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            d = json.load(f)["entries"]["sketch_add"]["description"]
        self.assertIn("slot {from, to (end centres), radius, radius2", d)
        self.assertIn("equal or not (radius2)", d)


class RepeatMasksGivenNames(unittest.TestCase):
    """The same fault on a sketch with a new name is the same refusal."""

    def test_new_name_same_fault(self):
        from agentlink.protocol import Server, Tool, ToolError

        def bad(a):
            raise ToolError("invalid_input", f"The pocket on {a['sketch']} cut nothing: no material of CrankBody lies under the outline of {a['sketch']}.")

        obj = {"type": "object", "properties": {"sketch": {"type": "string"}}}
        srv = Server("t", "0", [Tool("pd_pocket", "p.", obj, bad, changes=True)])

        def call(sk):
            import json

            r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "pd_pocket", "arguments": {"sketch": sk}}})["result"]
            return json.loads(r["content"][0]["text"])["error"]

        call("SpindleHoleRect")
        two = call("SpindleHoleSketch")
        self.assertEqual(two.get("repeat"), 2, two)

    def test_whole_words_only(self):
        from agentlink import protocol

        self.assertEqual(protocol._given_names({"a": "line", "b": [{"c": "x"}, "Up 2"]}), {"line", "Up 2"})


if __name__ == "__main__":
    unittest.main()
