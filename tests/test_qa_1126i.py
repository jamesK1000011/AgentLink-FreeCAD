# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA 1126i fixes (26 Nov): cards read, examples of the right kind, the
fillet face rule, sizes a solve changed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_hubfix2 import in_a_process  # noqa: E402
from test_qa_sketch_1124 import SETUP, entries  # noqa: E402


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

    def test_cards_say_it(self):
        e = entries()
        self.assertIn("solvedAway: the radii and centres that the solve changed", e["sketch_constrain"]["description"])
        self.assertIn("It has no document input: it saves the current document (doc_switch first).", e["doc_save"]["description"])
        self.assertTrue(e["sketch_constrain"]["answer"]["fields"]["solvedAway"]["when"])


if __name__ == "__main__":
    unittest.main()
