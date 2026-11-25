# SPDX-License-Identifier: LGPL-2.1-or-later
# A feature's answer says where its material went (24 Nov QA, fix 1): the
# body's bounds beside its size, the added region and the sides of the old
# body it goes past, or the removed region and the faces it opens. The
# geometry itself is proved live; here the words and the plain-number parts.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_hubfix2 import in_a_process  # noqa: E402


class Words(unittest.TestCase):
    def test_words(self):
        got = in_a_process('''
            from agentlink.families import pd_common as pc
            class BB:
                XMin, XMax, YMin, YMax, ZMin, ZMax = -30.0, 30.0, -15.0, 15.0, -20.0, 20.0
            class Reg:
                def __init__(s, bb): s.BoundBox = bb; s.Volume = 5250.0
                def isNull(s): return False
            class Old:
                class BoundBox:
                    XMin, XMax, YMin, YMax, ZMin, ZMax = -30.0, 30.0, -15.0, 15.0, 0.0, 5.0
                    DiagonalLength = 68.0
                Solids = [1]; Faces = [1] * 6
                def isNull(s): return False
                def cut(s, o): raise AssertionError("a pad looks at new less old only")
            class AddBB:
                XMin, XMax, YMin, YMax, ZMin, ZMax = 0.0, 5.0, -15.0, 15.0, -20.0, 20.0
            class New:
                Faces = [1] * 12
                BoundBox = BB
                def isNull(s): return False
                def cut(s, o): return Reg(AddBB)
            class Feat:
                class BaseFeature:
                    Shape = Old()
            class Body:
                Shape = New()
            class First:
                BaseFeature = None
            print(json.dumps({
                "span": pc.span_text(BB),
                "beyond": pc.beyond_sides((0, 5, -15, 15, -20, 20), (-30, 30, -15, 15, 0, 5)),
                "inside": pc.beyond_sides((0, 5, -15, 15, 0, 40), (-30, 30, -15, 15, 0, 40)),
                "top": pc.side_word((0, 0, 1), (1, 2, 10)),
                "bottom": pc.side_word((0, 0, -1.0), (1, 2, -0.0)),
                "slant": pc.side_word((0.7071, 0, 0.7071), (1, 2, 3)),
                "pad": pc.where_went(Feat(), Body(), 5250.0),
                "first": pc.where_went(First(), Body(), 9000.0),
            }))
        ''')
        self.assertEqual(got["span"], "x -30..30, y -15..15, z -20..20")
        self.assertEqual(got["beyond"], ["-z", "+z"])
        self.assertEqual(got["inside"], [])
        self.assertEqual(got["top"], "+z at z 10")
        self.assertEqual(got["bottom"], "-z at z 0")
        self.assertTrue(got["slant"].startswith("normal [0.71, 0, 0.71]"))
        self.assertEqual(got["pad"], {"added": "x 0..5, y -15..15, z -20..20", "beyond": ["-z", "+z"]})
        self.assertEqual(got["first"], {})


if __name__ == "__main__":
    unittest.main()
