# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA 1126i fixes (26 Nov): cards read, examples of the right kind, the
fillet face rule, sizes a solve changed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_hubfix2 import in_a_process  # noqa: E402
from test_qa_sketch_1124 import SERVER, SETUP, entries  # noqa: E402


class Fixes(unittest.TestCase):
    def test_cards_under_cards_and_results(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import protocol
    srv = types.SimpleNamespace()
    protocol.note_cards(srv, {"cards": [{"tool": "sketch_add", "description": "x"}]})
    protocol.note_cards(srv, {"results": [{"tools": [{"tool": "pd_pad", "description": "y"}]}]})
    print(json.dumps(sorted(srv._cards_read)))
''')
        self.assertEqual(got, ["pd_pad", "sketch_add"])

    def test_example_of_the_kind_in_the_message(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import protocol
    t = types.SimpleNamespace(name="sketch_add", schema={"properties": {"items": {}, "sketch": {}}})
    print(json.dumps(protocol.example_words(t, "invalid_input", "items[0]: polygon: sides (3 or more), radius.")))
''')
        self.assertNotIn('"arc"', got)

    def test_fillet_face_item_rule(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import refs
    from agentlink.protocol import ToolError
    try:
        refs._by_filter(None, {"face": "Face6", "type": "line"}, "edge", "edges", ())
    except ToolError as e:
        print(json.dumps(e.message))
''')
        self.assertEqual(got, "edges: an item with face takes only kind and tol. Put type, axis and the other filters in a second item, without face.")

    def test_solved_away(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink.families import sketch
    class Circle:
        def __init__(s, r, x, y): s.Radius, s.Center = r, types.SimpleNamespace(x=x, y=y)
    class ArcOfCircle(Circle):
        pass
    class LineSegment:
        pass
    sk = types.SimpleNamespace(Geometry=[LineSegment(), ArcOfCircle(12.5, 60, 0), Circle(6.5, 0, 0)])
    before = sketch.round_sizes(sk)
    sk.Geometry[1] = ArcOfCircle(12.465, 60, 0)
    print(json.dumps(sketch.solved_away(sk, before)))
''')
        self.assertEqual(got, ["arc 1: radius 12.5 → 12.465"])

    def test_card_under_results_card(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import protocol
    srv = types.SimpleNamespace()
    protocol.note_cards(srv, {"results": [{"find": "x", "tools": [], "card": {"tool": "pd_fillet", "description": "z"}}]})
    print(json.dumps(sorted(srv._cards_read)))
''')
        self.assertEqual(got, ["pd_fillet"])

    def test_read_as_once_then_said_before(self):
        got = in_a_process(SERVER + '''
    a = call("probe_make", {"arguments": {"name": "A"}})[1]
    b = call("probe_make", {"arguments": {"name": "B"}})[1]
    print(json.dumps([a.get("readAs"), b.get("readAs"), b.get("saidBefore")]))
''')
        self.assertIn("inside arguments", got[0])
        self.assertIsNone(got[1])
        self.assertIn("readAs", got[2])

    def test_tool_find_empty_fields_are_left_out(self):
        got = in_a_process(SERVER + '''
    r = call("tool_find", {"tool": "", "queries": [], "limit": 0, "group": "", "words": "pad"})
    print(json.dumps([r[0], sorted(r[1])]))
''')
        self.assertFalse(got[0], got)

    def test_sketch_new_both_given_names_what_was_sent(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import sketch
    print(json.dumps([sketch.both_given("-z", {"side": "-z"}), sketch.both_given("XY", {"side": "+z"})]))
''')
        self.assertTrue(got[0].startswith('You sent plane "-z" and face {"side": "-z"}: send one of them. plane "-z" is not a plane: a side goes in face { side: "-z" }.'), got[0])
        self.assertNotIn("is not a plane", got[1])
        self.assertNotIn("Pad.Face3", got[0] + got[1])

    def test_tool_find_says_a_name_is_no_tool(self):
        got = in_a_process(SERVER + '''
    r = call("tool_find", {"tool": ["pd_join", "pd_pad"]})
    print(json.dumps([r[1].get("missing"), "readAs" in r[1]]))
''')
        self.assertEqual(got[0], "No tool is named pd_join. What follows is a word search for it.")

    def test_get_says_which_object_it_read(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import fastpath
    o = types.SimpleNamespace(Name="Body", Label="Part", Shape=object(), PropertiesList=["Label", "Shape"], TypeId="PartDesign::Body", Visibility=False)
    doc = types.SimpleNamespace(Label="D", getObject=lambda n: o if n == "Body" else None, getObjectsByLabel=lambda n: [o] if n == "Part" else [])
    s = types.SimpleNamespace(doc=doc)
    try:
        fastpath.read(types.SimpleNamespace(tools={}), s, "Body.solids")
    except Exception:
        pass
    print(json.dumps(s.__dict__.get("_get_read")))
''')
        self.assertEqual(got, "Body Part (internal name Body), hidden")

    def test_repeat_words_skip_a_placeholder_example(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import protocol, examples
    examples.for_tool = lambda name, a: {"example": {"tool": name, "arguments": {"body": "B", "edges": "<edges>", "radius": "<radius>"}}}
    examples.load = lambda: {"pd_fillet": {}}
    print(json.dumps(protocol._try_next(types.SimpleNamespace(), "pd_fillet", ["input.edges"], 3, "tool_find { tool: \\"pd_fillet\\" }")))
''')
        self.assertNotIn("copy the card's example", got)
        self.assertIn("read the form of edges on the card", got, got)

    def test_get_reads_labels_first_and_refuses_a_clash(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink import fastpath
    from agentlink.protocol import ToolError
    body = types.SimpleNamespace(Name="Body", Label="Pad", TypeId="PartDesign::Body")
    pad = types.SimpleNamespace(Name="Pad", Label="Pad001", TypeId="PartDesign::Pad")
    objs = {"Body": body, "Pad": pad}
    doc = types.SimpleNamespace(Label="D", getObject=lambda n: objs.get(n), getObjectsByLabel=lambda n: [o for o in objs.values() if o.Label == n])
    out = [fastpath._doc_object(doc, "Pad").Name]
    try:
        fastpath._doc_object(doc, "Pad", clash=True)
    except ToolError as e:
        out.append(e.message)
    print(json.dumps(out))
''')
        self.assertEqual(got[0], "Body")
        self.assertEqual(got[1], '"Pad" is the label of Pad (internal name Body) and the internal name of Pad001: give "Body" for the first or "Pad001" for the second.')

    def test_tool_find_listing_says_what_it_did_not_use(self):
        got = in_a_process(SERVER + '''
    r = call("tool_find", {"listing": True, "tool": "pd_pad"})
    print(json.dumps(r[1].get("notUsed")))
''')
        self.assertEqual(got, "listing: true gives the listing only; tool was not used. Send it without listing.")

    def test_cards_say_it(self):
        e = entries()
        self.assertIn("solvedAway: the radii and centres that the solve changed", e["sketch_constrain"]["description"])
        self.assertIn("It has no document input: it saves the current document (doc_switch first).", e["doc_save"]["description"])
        self.assertTrue(e["sketch_constrain"]["answer"]["fields"]["solvedAway"]["when"])


if __name__ == "__main__":
    unittest.main()
