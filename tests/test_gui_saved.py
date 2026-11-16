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

    stand_in = types.SimpleNamespace(getDocument=lambda name: gui_doc)
    ns = {"FreeCAD": fc}
    exec(compile(ast.Module([fn], []), str(SRC), "exec"), ns)
    inner = ns["_gui_saved"]

    def call(*args, **kw):
        # The stand-in FreeCADGui only for the call: left in sys.modules it
        # passed for the window in every later test of the run (CI).
        had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = stand_in
        try:
            return inner(*args, **kw)
        finally:
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had

    return call


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


class SavedHeadless(unittest.TestCase):
    """Without a window FreeCAD's touched marks are all there is, and its
    save clears none: what was touched as the file was written is the saved
    state, and only a mark that came after it reads as a change."""

    def setUp(self):
        import os
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from agentlink import store

        self.store = store
        store._AT_SAVE.clear()

    def obj(self, name, touched=False):
        return types.SimpleNamespace(Name=name, State=["Touched"] if touched else ["Up-to-date"])

    def doc(self, *objs, file="a.FCStd"):
        d = types.SimpleNamespace(Name="Doc", FileName=file, Objects=list(objs))
        d.isTouched = lambda: any("Touched" in o.State for o in d.Objects)
        return d

    def test_touched_at_the_save_is_saved(self):
        box, holder = self.obj("Box"), self.obj("Records", touched=True)
        d = self.doc(box, holder)
        self.assertTrue(self.store.is_changed(d))
        self.store.note_saved(d)
        self.assertFalse(self.store.is_changed(d))
        self.assertEqual(self.store.touched_since_save(d), [])
        box.State = ["Touched"]  # a change after the save
        self.assertTrue(self.store.is_changed(d))
        self.assertEqual(self.store.touched_since_save(d), ["Box"])
        self.store.note_saved(d)
        self.assertFalse(self.store.is_changed(d))

    def test_another_file_or_no_save_goes_by_touched(self):
        d = self.doc(self.obj("Box", touched=True))
        self.assertTrue(self.store.is_changed(d))
        self.store.note_saved(d)
        d.FileName = "b.FCStd"  # saved elsewhere since, not from here
        self.assertTrue(self.store.is_changed(d))
        self.assertEqual(self.store.touched_since_save(d), ["Box"])
        self.assertFalse(self.store.is_changed(self.doc(self.obj("Box"))))


if __name__ == "__main__":
    unittest.main()
