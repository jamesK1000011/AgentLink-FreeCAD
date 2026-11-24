# SPDX-License-Identifier: LGPL-2.1-or-later
"""With the static list (the default), the words sent at initialize name
tool_find as the way to a tool, not tool_groups (live, 22 Nov: a local
model saw both ways). Read from the source: tools.py needs FreeCAD."""
import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agentlink", "tools.py")


def _const(name):
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


class StaticWords(unittest.TestCase):
    def test_static_note_names_tool_find(self):
        note = _const("STATIC_NOTE")
        self.assertIn("tool_find { words:", note)
        self.assertIn("tool_find { tool: name }", note)
        self.assertNotIn("tool_groups", note)

    def test_working_words_name_tool_find(self):
        w = _const("WORKING")
        self.assertIn("Start with session_state", w)
        self.assertNotIn("tool_groups { tool: name } gives them again", w)
        # The guide list is made at connect from the guide files (24 Nov), not typed here.
        self.assertIn("The guides here: {guides}. {words}", w)
        self.assertIn("A tool's card (tool_find { tool: name })", w)

    def test_static_is_chosen_by_the_mode(self):
        src = open(SRC, encoding="utf-8").read()
        self.assertIn('note = STATIC_NOTE if static else', src)


if __name__ == "__main__":
    unittest.main()
