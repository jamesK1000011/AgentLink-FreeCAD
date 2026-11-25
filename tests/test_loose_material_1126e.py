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


if __name__ == "__main__":
    unittest.main()
