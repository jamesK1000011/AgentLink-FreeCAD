# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA 1126h fixes (26 Nov): names, health words, missing kind."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_hubfix2 import in_a_process  # noqa: E402
from test_qa_sketch_1124 import SETUP  # noqa: E402


class Names(unittest.TestCase):
    """A label wins over an internal name; a clash is refused with both."""

    def test_label_first_and_clash(self):
        got = in_a_process('''
            import types
            from agentlink.families import pd_common as pc
            from agentlink.protocol import ToolError
            base = types.SimpleNamespace(Label="BaseSketch", Name="Sketch")
            new = types.SimpleNamespace(Label="Sketch", Name="Sketch001")
            other = types.SimpleNamespace(Label="Holes", Name="Sketch002")
            out = {}
            try:
                pc.by_ref([base, new], "Sketch")
            except ToolError as e:
                out["clash"] = e.message
            out["label"] = pc.by_ref([base, other], "BaseSketch").Name
            out["name"] = pc.by_ref([base, other], "Sketch002").Label
            out["case"] = pc.by_ref([base, other], "holes").Name
            out["none"] = pc.by_ref([base, other], "Zzz")
            print(json.dumps(out))
        ''')
        self.assertEqual(got["clash"], '"Sketch" is the label of Sketch (internal name Sketch001) and the internal name of BaseSketch: '
                                       'give "Sketch001" for the first or "BaseSketch" for the second.')
        self.assertEqual((got["label"], got["name"], got["case"], got["none"]), ("Sketch", "Holes", "Sketch002", None))


class MissingKind(unittest.TestCase):
    def test_no_kind_names_the_field(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import sketch
    from agentlink.protocol import ToolError
    try:
        sketch.build({"type": "rounded_rectangle", "size": [10, 5]})
    except ToolError as e:
        print(json.dumps(e.message))
''')
        self.assertTrue(got.startswith('the item has no kind (it has type: "rounded_rectangle"; the field is kind). The kinds: line,'), got)


if __name__ == "__main__":
    unittest.main()
