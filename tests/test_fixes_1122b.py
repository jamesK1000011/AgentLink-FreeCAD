# SPDX-License-Identifier: LGPL-2.1-or-later
"""22 Nov fixes (owner's items 2 and 3): doc_new first when the document in
front is the person's; a pocket that cut nothing names the side."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import options  # noqa: E402
from agentlink.protocol import ToolError, loose_name, sort_find  # noqa: E402


class Srv:
    tools = {n: None for n in ("pd_pad", "pd_pocket", "pd_fillet", "pd_chamfer", "sketch_add", "sketch_new", "body_check", "tool_find")}


class SortFind(unittest.TestCase):
    def test_names_and_words_in_one_list(self):
        names, qs, _ = sort_find(Srv, {"queries": ["pd_pad", "round an edge", "sketch_add"]})
        self.assertEqual((names, qs), (["pd_pad", "sketch_add"], ["round an edge"]))

    def test_tool_and_queries_in_one_call(self):
        names, qs, _ = sort_find(Srv, {"card": ["pd_pad"], "queries": ["hole"]})
        self.assertEqual((names, qs), (["pd_pad"], ["hole"]))

    def test_loose_names(self):
        for w in ("agentlink_pd_pad", "PD_PAD", "pd-pad", "pd_poket"):
            self.assertIsNotNone(loose_name(Srv, w), w)
        self.assertEqual(loose_name(Srv, "pd_poket"), "pd_pocket")
        self.assertIsNone(loose_name(Srv, "pad sketch"))
        self.assertIsNone(loose_name(Srv, "fillet"))  # a word, not a name
        _, _, read_as = sort_find(Srv, {"queries": ["pd_poket", "x y"]})
        self.assertTrue(any("pd_pocket" in r for r in read_as))

    def test_word_in_tool_is_searched(self):
        names, qs, read_as = sort_find(Srv, {"card": "round edges"})
        self.assertEqual((names, qs), ([], ["round edges"]))
        self.assertTrue(read_as)

    def test_limits_count_searches_and_names_apart(self):
        names, qs, _ = sort_find(Srv, {"queries": ["pd_pad", "pd_pocket", "pd_fillet", "pd_chamfer", "sketch_add", "sketch_new", "body_check", "a", "b"]})
        self.assertEqual((len(names), len(qs)), (7, 2))
        with self.assertRaises(ToolError) as e:
            sort_find(Srv, {"queries": [f"w{i} x" for i in range(7)]})
        self.assertIn("7 searches", e.exception.message if hasattr(e.exception, "message") else str(e.exception))


class TheirsFirst(unittest.TestCase):
    def sess(self, mine):
        doc = types.SimpleNamespace(Name="Doc", Label="Bracket")
        server = types.SimpleNamespace(tools={"doc_new": None})
        return types.SimpleNamespace(doc=doc, agent_docs={"Doc"} if mine else set()), server

    def test_person_doc_gets_doc_new_first(self):
        s, server = self.sess(False)
        o = options.theirs_first(s, server)
        self.assertEqual((o["n"], o["tool"], o["ask"]), (1, "doc_new", [{"arg": "name"}]))
        self.assertIn("Bracket", o["why"])

    def test_agent_doc_gets_none(self):
        s, server = self.sess(True)
        self.assertIsNone(options.theirs_first(s, server))

    def test_no_doc_new_tool(self):
        s, _ = self.sess(False)
        self.assertIsNone(options.theirs_first(s, types.SimpleNamespace(tools={})))


class V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __sub__(self, o):
        return V(self.x - o.x, self.y - o.y, self.z - o.z)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z


if __name__ == "__main__":
    unittest.main()


class Stubbed(unittest.TestCase):
    """The FreeCAD modules as stand-ins, for the plain-Python parts."""

    def setUp(self):
        fc = types.ModuleType("FreeCAD")
        fc.Vector = lambda x=0, y=0, z=0: (x, y, z)
        names = ("FreeCAD", "Part", "Sketcher", "agentlink.geometry", "agentlink.runners", "agentlink.families.picks",
                 "agentlink.families.pd_common", "agentlink.families.sketch")
        self._old = {n: sys.modules.get(n) for n in names}
        sys.modules["FreeCAD"] = fc
        sys.modules["Part"] = types.ModuleType("Part")
        sys.modules["Sketcher"] = types.ModuleType("Sketcher")
        self.addCleanup(self.restore)
        try:
            from agentlink.families import pd_common, sketch
        except ImportError as e:
            self.skipTest(f"needs FreeCAD: {e}")
        self.pc, self.sk = pd_common, sketch

    def restore(self):
        for n, m in self._old.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m

    def test_vec2_refuses_other_forms_with_the_form(self):
        def xy(v):  # the stand-in Vector of whichever test loaded the module first
            return (v.x, v.y) if hasattr(v, "x") else tuple(v[:2])

        self.assertEqual(xy(self.pc.vec2([1, 2], "c")), (1.0, 2.0))
        for given, words in (([1, 2, 0], "[x, y, z]"), ({"x": 1, "y": 2}, "an object")):
            with self.assertRaises(self.pc.ToolError) as e:
                self.pc.vec2(given, "corner")
            self.assertIn(words, e.exception.message)
            self.assertIn('"corner": [10, 0]', e.exception.message)

    def test_constraint_fields_refused_with_the_form(self):
        # 27 Nov: one constraint for each call; the card's schema refuses a field that is not one of its inputs.
        from agentlink import protocol, runners

        schema = runners.entries()["sketch_constrain"]["inputSchema"]
        protocol.check_input(schema, {"type": "fix", "refs": [[1, 2]]}, "sketch_constrain")
        with self.assertRaises(protocol.ToolError) as e:
            protocol.check_input(schema, {"kind": "fix", "point": [1, 0]}, "sketch_constrain")
        m = e.exception.message
        self.assertIn("input.kind, point: not known fields", m)  # 27 Nov: every unknown field in one refusal
        self.assertIn("goes in type", m)
        self.assertIn('"type": "tangent"', m)
        with self.assertRaises(protocol.ToolError):
            protocol.check_input(schema, {"refs": [0]}, "sketch_constrain")


class RectangleWords(Stubbed):
    def test_x_y_width_height_refused_with_the_form(self):
        with self.assertRaises(self.sk.ToolError) as e:
            self.sk.build({"kind": "rectangle", "x": -30, "y": -15, "width": 60, "height": 30})
        m = e.exception.message
        self.assertIn("width, height, x, y: not fields", m)
        self.assertIn('"size": [60, 30]', m)


class PocketDepth(unittest.TestCase):
    def test_depth_is_refused_by_name(self):
        import json

        from agentlink.protocol import ToolError, check_input

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            sc = json.load(f)["entries"]["pd_pocket"]["inputSchema"]
        with self.assertRaises(ToolError) as e:
            check_input(sc, {"depth": 5}, "pd_pocket")
        self.assertIn("input.depth: not a known field", e.exception.message)


class DoesHits(unittest.TestCase):
    def test_by_what_it_does(self):
        from agentlink.protocol import does_hits

        seen = []

        def find(a):
            seen.append(a["words"])
            return {"tools": [{"tool": "sketch_add", "does": "Add geometry to a sketch."}]}

        srv = types.SimpleNamespace(tools={"tool_find": types.SimpleNamespace(fn=find)})
        self.assertEqual(does_hits(srv, "sketch_rectangle"), ["sketch_add (Add geometry to a sketch)"])
        self.assertEqual(seen, ["sketch rectangle"])
        self.assertEqual(does_hits(types.SimpleNamespace(tools={}), "x"), [])


class WrongTypeForm(unittest.TestCase):
    def test_face_as_text_gives_the_form(self):
        import json

        from agentlink.protocol import ToolError, check_input

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            sc = json.load(f)["entries"]["sketch_new"]["inputSchema"]
        with self.assertRaises(ToolError) as e:
            check_input(sc, {"face": "Pad1"}, "sketch_new")
        m = e.exception.message
        self.assertIn("input.face: an object, not text.", m)
        # 22 Nov face selectors: the form names both, side first
        self.assertIn('The form: { side: "+z"', m)
        self.assertIn("{ at: [x,y,z]", m)


class OutlineBesideBody(unittest.TestCase):
    """23 Nov: holes at y +15 beside a plate at y -30..0 got the direction words."""

    def setUp(self):
        try:
            from agentlink.families import pd_common
        except ImportError as e:
            self.skipTest(f"needs FreeCAD: {e}")
        self.pd = pd_common

    def test_beside_names_both_ranges(self):
        w = self.pd.outside_rec((12.5, 47.5, 12.5, 17.5, 5, 5), (0, 60, -30, 0, 0, 40), (0, 0, 1))
        self.assertEqual(w, {"y": {"outline": [12.5, 17.5], "body": [-30.0, 0.0]}})  # facts only (27 Nov): the measured spans, no instruction

    def test_over_the_body_says_nothing(self):
        self.assertEqual(self.pd.outside_rec((12.5, 47.5, -17.5, -12.5, 5, 5), (0, 60, -30, 0, 0, 40), (0, 0, 1)), {})

    def test_the_cut_axis_is_left_out(self):
        # Beside along z only (the cut's own axis): that is the direction words' job.
        self.assertEqual(self.pd.outside_rec((0, 10, 0, 10, 50, 50), (0, 60, 0, 30, 0, 40), (0, 0, 1)), {})
