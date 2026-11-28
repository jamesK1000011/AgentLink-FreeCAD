# SPDX-License-Identifier: LGPL-2.1-or-later
# Answers as records (owner, 28 Nov): health's next and an answer's filled
# are records, not lines.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


class NextRecord(unittest.TestCase):
    def test_a_sketch_in_edit_a_task_panel_and_the_likely_tools(self):
        from agentlink import nexthint

        st = {"window": True, "workbench": "SketcherWorkbench", "sketch": {"name": "Sketch", "dof": 4}, "panel": {"buttons": ["Close"]}}
        got = nexthint.record(st, [{"tool": "sketch_constrain", "why": "4 DoF left"}, "sketch_state"])
        self.assertEqual(got, {"editing": {"sketch": "Sketch", "dof": 4}, "taskPanel": {"buttons": ["Close"]},
                               "likelyNext": [{"tool": "sketch_constrain", "why": "4 DoF left"}, {"tool": "sketch_state"}],
                               "workbench": "SketcherWorkbench"})

    def test_a_dialog_names_no_tool(self):
        from agentlink import nexthint

        got = nexthint.record({"window": True, "dialog": {"title": "Save?", "buttons": ["Yes", "No"]}}, [{"tool": "doc_save", "why": "x"}])
        self.assertEqual(got, {"dialog": {"title": "Save?", "buttons": ["Yes", "No"]}})

    def test_no_window_no_record(self):
        from agentlink import nexthint

        self.assertIsNone(nexthint.record({"window": False}, ["x"]))


class FilledRecord(unittest.TestCase):
    def test_took_writes_a_record(self):
        import types
        from unittest import mock

        for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher"):
            sys.modules.setdefault(n, mock.MagicMock(name=n))

        from agentlink.families import pd_common as pc

        s = types.SimpleNamespace(filled_now=[])
        old = pc._dry
        pc._dry = lambda: False
        try:
            pc.took(s, types.SimpleNamespace(Label="Sketch"), "madeLast")
        finally:
            pc._dry = old
        self.assertEqual(s.filled_now, [{"input": "sketch", "value": "Sketch", "from": "madeLast"}])


if __name__ == "__main__":
    unittest.main()
