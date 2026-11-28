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


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


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
            ex = examples.for_tool(name, facts, how="null")["ready"]
            self.assertEqual(ex.pop("tool"), name)
            # a value to give: one of the input's own type (27 Nov: pd_body_new's name is text)
            props = t["inputSchema"]["properties"]
            ex = {k: (("x" if props[k].get("type") == "string" else 1) if v is None else v) for k, v in ex.items()}
            check_input(t["inputSchema"], ex, name)


class Build(unittest.TestCase):
    def test_from_the_document(self):
        got = examples.for_tool("pd_pad", {"bodyName": "Body", "sketchName": "Sketch001"}, how="null")
        self.assertEqual(got["ready"], {"tool": "pd_pad", "body": "Body", "sketch": "Sketch001", "length": 10})
        self.assertEqual(got["plain"], {"tool": "pd_pad", "body": None, "sketch": None, "length": 10})  # no document: the names are marked, the worked length stays
        self.assertTrue(got["fill"][0].startswith("length: mm"))
        self.assertIn("Change it to yours", got["fill"][0])

    def test_pad_and_pocket_examples_carry_a_length(self):
        # Audit top 10 #1 (24 Nov): the depth is in the call, not only named.
        for name in ("pd_pad", "pd_pocket"):
            got = examples.for_tool(name, {}, how="angle")
            self.assertIsInstance(got["ready"]["length"], (int, float))
            self.assertIsInstance(got["plain"]["length"], (int, float))
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
        self.assertEqual(got["ready"]["radius"], "<radius>")
        self.assertEqual(got["plain"]["radius"], "<radius>")

    def test_open_sketch_first_and_no_facts_left_out(self):
        got = examples.for_tool("sketch_add", {"editSketch": "Sk2", "sketchName": "Sk1"})
        self.assertEqual(got["ready"]["sketch"], "Sk2")
        self.assertIsNone(got["plain"]["sketch"])
        got = examples.for_tool("pd_pad", {})
        self.assertIsNone(got["ready"]["body"])  # what the document does not give stays in the call, marked

    def test_picked_edges_fill_the_edges(self):
        got = examples.for_tool("pd_fillet", {"pickedEdges": ["Edge3"]})
        self.assertEqual(got["ready"]["edges"], ["Edge3"])
        self.assertIsNone(got["plain"]["edges"])
        self.assertFalse(any(w.startswith("edges") for w in got["fill"]))

    def test_off_and_unknown(self):
        self.assertIsNone(examples.for_tool("no_such_tool", {}))
        os.environ["AGENTLINK_EXAMPLES"] = "0"
        self.addCleanup(os.environ.pop, "AGENTLINK_EXAMPLES", None)
        self.assertIsNone(examples.for_tool("pd_pad", {}))


class Placed(unittest.TestCase):
    """Blind QA (24-25 Nov): small models copy the examples. Every sketch
    used center [0, 0], and round ends were full circles. The examples now
    show a round-ended outline, a centred plate and a shape at an edge."""

    def test_sketch_add_example_is_one_flat_shape(self):
        # 27 Nov: one call adds one shape, so the card's example is one centred rectangle, and the card's words
        # give the facts about its inputs, not a part.
        got = examples.for_tool("sketch_add", {"sketchName": "Sketch"}, how="null")
        for k in ("plain", "ready"):
            self.assertEqual({x: v for x, v in got[k].items() if x != "sketch"},
                             {"tool": "sketch_add", "kind": "rectangle", "center": [0, 0], "size": [40, 20]})
        self.assertEqual(got["ready"]["sketch"], "Sketch")
        self.assertEqual([w.split(":")[0] for w in got["fill"]], ["kind", "center", "size"])
        for w in got["fill"]:
            self.assertLess(len(w), 200, w)
        # the recipe for a round-ended outline is in the guide, as four flat calls
        with open(os.path.join(HERE, "..", "agentlink", "families", "sketch.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('return [("Tangent", refs[0][0], refs[0][1], refs[1][0], refs[1][1])]', src)
        self.assertIn('if "corner" in item:', src)

    def test_edge_example_numbers_follow_body_extent(self):
        # A 50 x 40 plate centred on XY, padded 4: world x [-25, 25], y [-20, 20], z [0, 4].
        # face_frame on the +z face: x is world x (the first axis in the face), y = z cross x = world y,
        # origin (0, 0, 4); so bodyExtent is the plate's x and y.
        # (25 Nov: the rule is agentlink/orient.py's face_axes; a +z face is not a standing face.)
        from agentlink import orient

        x, y = orient.face_axes((0, 0, 1))
        self.assertEqual((tuple(x), tuple(y)), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
        ext = {"x": [-25.0, 25.0], "y": [-20.0, 20.0]}
        self.assertEqual([ext["x"][0], ext["y"][0]], [-25.0, -20.0])
        tj = tools_json()
        add, new = _cw(tj["sketch_add"]), _cw(tj["sketch_new"])
        self.assertIn('a plate on XY is centred: { "tool": "sketch_add", "kind": "rectangle", "center": [0, 0], "size": [50, 40] }, padded 4.', add)
        self.assertIn('sketch_new { face: { side: "+z" } } answers bodyExtent { x: [-25.0, 25.0], y: [-20.0, 20.0] }.', add)
        self.assertIn("kind rectangle, corner [-25, -20], size [10, 10]", add)
        self.assertIn("Then pd_pad { length: 6 } makes the block.", add)
        self.assertIn("bodyExtent is { x: [-25.0, 25.0], y: [-20.0, 20.0] }.", new)
        self.assertIn("sketch_add rectangle { corner: [-25, -20], size: [10, 10] } is a block on one corner of the plate.", new)
        self.assertIn("+z", tj["sketch_new"]["inputSchema"]["properties"]["face"]["properties"]["side"]["enum"])
        with open(os.path.join(HERE, "..", "agentlink", "guides", "sketch.md"), encoding="utf-8") as f:
            g = f.read()
        self.assertIn("`bodyExtent { x: [-25.0, 25.0], y: [-20.0, 20.0] }`", g)
        self.assertIn("`rectangle { corner: [-25, -20], size: [10, 10] }`", g)
        self.assertIn("`rectangle { center: [0, 0], size: [50, 40] }`", g)
        for text in (add, new, g):
            self.assertNotIn("[4, 30]", text)  # the old upright example is gone
            self.assertNotIn('sides: "symmetric", length: 40', text)

    def test_the_guide_has_the_link_recipe_once_and_the_card_numbers(self):
        with open(os.path.join(HERE, "..", "agentlink", "guides", "sketch.md"), encoding="utf-8") as f:
            g = f.read()
        self.assertEqual(g.count("arcs at x 0 (radius 10) and x 80 (radius 6)"), 1)
        for call in ("arc { center: [0, 0], radius: 10, start: 90, end: 270 }", "arc { center: [80, 0], radius: 6, start: -90, end: 90 }",
                     "line { from: [0, -10], to: [80, -6] }", "line { from: [80, 6], to: [0, 10] }"):
            self.assertIn(call, g)


if __name__ == "__main__":
    unittest.main()
