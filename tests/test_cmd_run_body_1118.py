# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live 101: cmd_run of a Part Design command with no active body makes
the selected sketch's body active, so FreeCAD does not ask in a modal."""
import os
import types
import unittest

import ast  # noqa: E402

# body_for alone, from the source (families/app.py needs FreeCAD to import).
_SRC = os.path.join(os.path.dirname(__file__), "..", "agentlink", "families", "app.py")
with open(_SRC, encoding="utf-8") as _f:
    _tree = ast.parse(_f.read())
_ns = {}
exec(compile(ast.Module([n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "body_for"], []), _SRC, "exec"), _ns)
app = types.SimpleNamespace(body_for=_ns["body_for"])


class View:
    def __init__(self, active=None):
        self.active = active

    def getActiveObject(self, key):
        return self.active

    def setActiveObject(self, key, o):
        self.active = o


def gui_with(view, objs):
    sel = [types.SimpleNamespace(Object=o) for o in objs]
    return types.SimpleNamespace(ActiveDocument=types.SimpleNamespace(ActiveView=view),
                                 Selection=types.SimpleNamespace(getSelectionEx=lambda *_a: sel))


class BodyFor(unittest.TestCase):
    def setUp(self):
        self.body = types.SimpleNamespace(TypeId="PartDesign::Body", Label="Body 2", InList=[])
        self.sketch = types.SimpleNamespace(TypeId="Sketcher::SketchObject", InList=[self.body])

    def test_the_sketchs_body_is_made_active(self):
        v = View()
        self.assertEqual(app.body_for(gui_with(v, [self.sketch]), "PartDesign_Pad"), "Body 2")
        self.assertIs(v.active, self.body)

    def test_an_active_body_is_kept(self):
        other = object()
        v = View(other)
        self.assertIsNone(app.body_for(gui_with(v, [self.sketch]), "PartDesign_Pad"))
        self.assertIs(v.active, other)

    def test_other_commands_and_two_bodies_change_nothing(self):
        v = View()
        self.assertIsNone(app.body_for(gui_with(v, [self.sketch]), "Std_ViewFitAll"))
        b2 = types.SimpleNamespace(TypeId="PartDesign::Body", Label="Body", InList=[])
        s2 = types.SimpleNamespace(TypeId="Sketcher::SketchObject", InList=[b2])
        self.assertIsNone(app.body_for(gui_with(v, [self.sketch, s2]), "PartDesign_Pad"))
        self.assertIsNone(v.active)


if __name__ == "__main__":
    unittest.main()
