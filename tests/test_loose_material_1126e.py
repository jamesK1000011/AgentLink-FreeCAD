# SPDX-License-Identifier: LGPL-2.1-or-later
# Added material that does not touch the body says so (live s1126e, 25 Nov:
# an upright drawn beside a plate made a second solid, health said valid
# because AllowCompound is true by default, and the model went on).
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_hubfix2 import in_a_process  # noqa: E402


class Loose(unittest.TestCase):
    def test_words(self):
        got = in_a_process('''
            from agentlink.families import pd_common as pc
            class S:
                def __init__(s, n): s.Solids = [1] * n
            print(json.dumps({
                "apart": pc.loose_sentence(S(1), S(2)),
                "joined": pc.loose_sentence(S(1), S(1)),
                "cut": pc.loose_sentence(S(2), S(1)),
                "odd": pc.loose_sentence(object(), S(2)),
            }))
        ''')
        self.assertIn("does not touch the body", got["apart"])
        self.assertIn("now 2 pieces", got["apart"])
        self.assertIn("bodyExtent", got["apart"])
        self.assertIsNone(got["joined"])
        self.assertIsNone(got["cut"])
        self.assertIsNone(got["odd"])


class Position(unittest.TestCase):
    """Where added material sits on each axis of the body before it (QA
    1126e: an upright across the middle of a base, not at one end)."""

    def test_words(self):
        base = [0, 60, 0, 30, 0, 5]
        got = in_a_process(f'''
            from agentlink.families import pd_common as pc
            print(json.dumps({{
                "middle": pc.position_sentence([25, 35, 0, 30, 5, 45], {base}),
                "end": pc.position_sentence([0, 10, 0, 30, 0, 40], {base}),
                "plus": pc.position_sentence([50, 60, 10, 20, 0, 5], {base}),
                "past": pc.position_sentence([-10, 70, -5, 35, 5, 9], {base}),
            }}))
        ''')
        self.assertIn("in the middle of x, touching neither end (x 25..35 of 0..60)", got["middle"])
        self.assertIn("across all of y", got["middle"])
        self.assertNotIn(" z", got["middle"])  # z goes past the top: added_sentence says it
        self.assertIn("at the -x end (x 0..10 of 0..60)", got["end"])
        self.assertIn("at the +x end", got["plus"])
        self.assertIn("in the middle of y", got["plus"])
        self.assertIn("across all of z", got["plus"])
        self.assertIsNone(got["past"])


if __name__ == "__main__":
    unittest.main()
