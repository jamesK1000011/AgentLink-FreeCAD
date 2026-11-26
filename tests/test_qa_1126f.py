# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA 1126e leftovers, fixed in round 7 (26 Nov)."""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_hubfix2 import in_a_process  # noqa: E402


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


class TookFrom(unittest.TestCase):
    """A cut names the features whose own material it took (QA 1126e: holes
    meant for the base cut the upright)."""

    def test_names_by_volume(self):
        got = in_a_process('''
            from agentlink.families import pd_common as pc

            class Pl:
                def multiply(self, other):
                    return other

            class Sh:
                def __init__(self, v):
                    self.v, self.Placement = v, Pl()
                def isNull(self):
                    return False
                def copy(self):
                    return self
                def common(self, other):
                    return type("C", (), {"Volume": min(self.v, other.v) if other.v != 9 else 0})()

            class F:
                def __init__(self, label, kind, v, add="Additive"):
                    self.Label, self.kind, self.AddSubType, self.AddSubShape = label, kind, add, Sh(v)
                def isDerivedFrom(self, t):
                    return self.kind == "addsub"

            pad, pad2, sk, other = F("Pad", "addsub", 150), F("Pad 2", "addsub", 46), F("Sketch", "sketch", 1), F("Pad 3", "addsub", 9)
            pocket = F("Pocket", "addsub", 0, "Subtractive")
            body = type("B", (), {"Group": [sk, pad, pad2, other, pocket], "Placement": Pl()})()
            print(json.dumps(pc.took_from(pocket, body, Sh(196))))
        ''')
        self.assertEqual(got, ["Pad: 150 mm³", "Pad 2: 46 mm³"])


if __name__ == "__main__":
    unittest.main()
