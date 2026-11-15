# SPDX-License-Identifier: LGPL-2.1-or-later
# A save through App's document clears the window's modified mark ("*").
import ast
import pathlib
import types
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1] / "agentlink" / "families" / "doc.py"


def _fn(gui_up, gui_doc):
    tree = ast.parse(SRC.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_gui_saved")
    fc = types.SimpleNamespace(GuiUp=gui_up)
    import sys

    sys.modules["FreeCADGui"] = types.SimpleNamespace(getDocument=lambda name: gui_doc)
    ns = {"FreeCAD": fc}
    exec(compile(ast.Module([fn], []), str(SRC), "exec"), ns)
    return ns["_gui_saved"]


class GuiSaved(unittest.TestCase):
    def doc(self, touched=False):
        return types.SimpleNamespace(Name="Part", isTouched=lambda: touched, purgeTouched=lambda: None)

    def test_mark_cleared_after_a_save(self):
        g = types.SimpleNamespace(Modified=True)
        _fn(True, g)(self.doc())
        self.assertFalse(g.Modified)

    def test_cleared_even_when_freecad_still_says_touched(self):
        g = types.SimpleNamespace(Modified=True)
        _fn(True, g)(self.doc(touched=True))
        self.assertFalse(g.Modified)

    def test_headless_does_nothing(self):
        g = types.SimpleNamespace(Modified=True)
        _fn(False, g)(self.doc())
        self.assertTrue(g.Modified)


if __name__ == "__main__":
    unittest.main()
