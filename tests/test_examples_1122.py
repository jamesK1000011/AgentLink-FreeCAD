# SPDX-License-Identifier: LGPL-2.1-or-later
"""A ready call on a tool's card (owner, 22 Nov): data/examples.json."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from agentlink import examples  # noqa: E402
from agentlink.protocol import ToolError, check_input  # noqa: E402

DATA = os.path.join(HERE, "..", "agentlink", "data")


def tools_json():
    with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class Data(unittest.TestCase):
    def test_entries_fit_their_schema(self):
        with open(os.path.join(DATA, "examples.schema.json"), encoding="utf-8") as f:
            schema = json.load(f)
        for name, e in examples.load().items():
            check_input(schema, e, name)

    def test_args_are_the_tools_own(self):
        tj = tools_json()
        for name, e in examples.load().items():
            t = tj.get(name)
            if t is None:
                continue  # a tool written in code
            props = t["inputSchema"]["properties"]
            for a in list(e["arguments"]) + [f["arg"] for f in e.get("fill") or ()]:
                self.assertIn(a, props, f"{name}.{a}")

    def test_filled_example_passes_the_schema(self):
        # With the values given, each example is a call its tool takes.
        tj = tools_json()
        facts = {"bodyName": "Body", "sketchName": "Sketch", "pickedEdges": ["Edge1"]}
        for name in examples.load():
            t = tj.get(name)
            if t is None:
                continue
            ex = examples.for_tool(name, facts, how="null")["example"]["arguments"]
            ex = {k: (1 if v is None else v) for k, v in ex.items()}
            check_input(t["inputSchema"], ex, name)


class Build(unittest.TestCase):
    def test_from_the_document(self):
        got = examples.for_tool("pd_pad", {"bodyName": "Body", "sketchName": "Sketch001"}, how="null")
        self.assertEqual(got["example"], {"tool": "pd_pad", "arguments": {"body": "Body", "sketch": "Sketch001", "length": 10}})
        self.assertTrue(got["fill"][0].startswith("length: mm"))
        self.assertIn("Change it to yours", got["fill"][0])

    def test_pad_and_pocket_examples_carry_a_length(self):
        # Audit top 10 #1 (24 Nov): the depth is in the call, not only named.
        for name in ("pd_pad", "pd_pocket"):
            got = examples.for_tool(name, {}, how="angle")
            self.assertIsInstance(got["example"]["arguments"]["length"], (int, float))
            self.assertTrue(tools_json()[name]["inputSchema"]["properties"]["length"].get("description"))

    def test_null_fails_cleanly_and_names_the_field(self):
        schema = tools_json()["pd_fillet"]["inputSchema"]
        with self.assertRaises(ToolError) as e:
            check_input(schema, {"edges": ["Edge1"], "radius": None}, "pd_fillet")
        self.assertIn("radius", str(e.exception.message if hasattr(e.exception, "message") else e.exception))

    def test_angle_value_sent_as_is_is_refused(self):
        schema = tools_json()["pd_fillet"]["inputSchema"]
        with self.assertRaises(ToolError):
            check_input(schema, {"edges": ["Edge1"], "radius": "<radius>"}, "pd_fillet")
        check_input(schema, {"edges": ["Edge1"], "radius": 2}, "pd_fillet")  # a value goes through

    def test_angle_marker(self):
        got = examples.for_tool("pd_fillet", {}, how="angle")
        self.assertEqual(got["example"]["arguments"]["radius"], "<radius>")

    def test_open_sketch_first_and_no_facts_left_out(self):
        got = examples.for_tool("sketch_add", {"editSketch": "Sk2", "sketchName": "Sk1"})
        self.assertEqual(got["example"]["arguments"]["sketch"], "Sk2")
        got = examples.for_tool("pd_pad", {})
        self.assertNotIn("body", got["example"]["arguments"])

    def test_picked_edges_fill_the_edges(self):
        got = examples.for_tool("pd_fillet", {"pickedEdges": ["Edge3"]})
        self.assertEqual(got["example"]["arguments"]["edges"], ["Edge3"])
        self.assertFalse(any(w.startswith("edges") for w in got["fill"]))

    def test_off_and_unknown(self):
        self.assertIsNone(examples.for_tool("no_such_tool", {}))
        os.environ["AGENTLINK_EXAMPLES"] = "0"
        self.addCleanup(os.environ.pop, "AGENTLINK_EXAMPLES", None)
        self.assertIsNone(examples.for_tool("pd_pad", {}))


if __name__ == "__main__":
    unittest.main()
