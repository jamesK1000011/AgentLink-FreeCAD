# SPDX-License-Identifier: LGPL-2.1-or-later
# Design E5 co-work items, on stand-ins (no FreeCAD needed):
#  #6 a batch's rollback undoes only the agent's own steps: at the first
#     step on the undo stack that is not the batch's (the person's), it
#     stops, says partial, and the person's step stays.
#  #8 the person's open edit or task panel is not disturbed: a changing
#     call on that body (or that document, when its target is not known)
#     is held (held_person_editing, not_started); reads, other bodies and
#     other documents go on; headless, nothing is held.
import json
import os
import subprocess
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from agentlink import changes, coedit  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


# ---- #6: the undo loop ------------------------------------------------------------------------

class StackDoc:
    """An undo stack by names, the newest first (as FreeCAD's UndoNames)."""

    def __init__(self, names):
        self.UndoNames = list(names)
        self.undid = []

    @property
    def UndoCount(self):
        return len(self.UndoNames)

    def undo(self):
        self.undid.append(self.UndoNames.pop(0))


class UndoOwn(unittest.TestCase):
    def test_all_own_steps_are_undone(self):
        d = StackDoc(["c", "b", "a", "before"])
        self.assertEqual(changes.undo_own(d, 3, ["a", "b", "c"]), (3, None))
        self.assertEqual(d.UndoNames, ["before"])

    def test_stops_at_the_persons_step(self):
        # The agent made a, b, c; the person made Pad between b and c.
        d = StackDoc(["c", "Pad", "b", "a", "before"])
        self.assertEqual(changes.undo_own(d, 3, ["a", "b", "c"]), (1, "Pad"))
        self.assertEqual(d.UndoNames, ["Pad", "b", "a", "before"])

    def test_persons_step_on_top_undoes_nothing(self):
        d = StackDoc(["Sketch", "b", "a"])
        self.assertEqual(changes.undo_own(d, 2, ["a", "b"]), (0, "Sketch"))
        self.assertEqual(d.undid, [])

    def test_names_not_known_undo_as_before(self):
        d = StackDoc(["x", "y", "z"])
        self.assertEqual(changes.undo_own(d, 2, None), (2, None))
        self.assertEqual(changes.undo_own(StackDoc(["x", "y"]), 2, ["y"]), (2, None))

    def test_own_names(self):
        d = StackDoc(["c", "b", "a"])
        self.assertEqual(changes.own_names(d, 2), ["b", "c"])
        self.assertEqual(changes.own_names(d, 0), [])
        self.assertIsNone(changes.own_names(d, 5))


# ---- #6: the real batch on a stand-in FreeCAD (a child process) -------------------------------

def _child(case):
    import tempfile
    from unittest import mock

    class Auto(types.ModuleType):
        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            m = mock.MagicMock(name=f"{self.__name__}.{k}")
            setattr(self, k, m)
            return m

    for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
        sys.modules[n] = Auto(n)
    fc = sys.modules["FreeCAD"]
    fc.GuiUp = False
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-e5-")

    from agentlink.protocol import Tool, ToolError
    from agentlink.tools import Session, build_server

    s = Session(out_dir=tempfile.mkdtemp())

    class Doc:
        Name = Label = "DocE5"
        FileName = ""
        Objects = []

        def __init__(self):
            self.UndoNames = ["earlier"]

        @property
        def UndoCount(self):
            return len(self.UndoNames)

        def undo(self):
            self.UndoNames.pop(0)

        def recompute(self):
            pass

        def openTransaction(self, name=""):
            pass

        def commitTransaction(self):
            pass

        def abortTransaction(self):
            pass

        def isTouched(self):
            return False

    s.doc = Doc()
    srv = build_server(s, lean=False)
    s.server = srv

    def change(a):
        s.doc.UndoNames.insert(0, "probe_change")
        return {"n": a.get("n")}

    def person(a):
        # The person's own step, made while the batch runs (a read for the agent).
        s.doc.UndoNames.insert(0, "Pocket")
        return {}

    def fail(a):
        raise ToolError("invalid_input", "probe: told to fail")

    obj = {"type": "object", "properties": {"n": {}}}
    srv.tools["probe_change"] = Tool("probe_change", "A change.", obj, change, changes=True)
    srv.tools["probe_person"] = Tool("probe_person", "The person acts.", obj, person)
    srv.tools["probe_fail"] = Tool("probe_fail", "A refusal.", obj, fail)
    ch = {"tool": "probe_change", "arguments": {}}
    calls = {
        "interleaved": [ch, {"tool": "probe_person", "arguments": {}}, ch, {"tool": "probe_fail", "arguments": {}}],
        "clean": [ch, ch, {"tool": "probe_fail", "arguments": {}}],
    }[case]
    r = srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "batch", "arguments": {"calls": calls}}})
    return {"body": json.loads(r["result"]["content"][0]["text"]), "stack": s.doc.UndoNames}


def run_case(case):
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "child", case], capture_output=True, text=True, timeout=120, cwd=ROOT)
    if r.returncode != 0:
        raise AssertionError(f"child {case} failed:\n{r.stderr[-4000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


class BatchRollbackKeepsThePersonsStep(unittest.TestCase):
    def test_a_foreign_step_stops_the_rollback(self):
        got = run_case("interleaved")
        body = got["body"]
        self.assertEqual(body["undone"], 1, body)
        self.assertEqual(body["outcome"], "partial")
        self.assertIn("history_restore to the agent checkpoint goes back without your step", body["rollbackNote"])
        self.assertIn("Pocket", body["rollbackNote"])
        self.assertEqual(got["stack"], ["Pocket", "probe_change", "earlier"])

    def test_no_foreign_step_rolls_back_whole(self):
        got = run_case("clean")
        body = got["body"]
        self.assertEqual((body["undone"], body["outcome"]), (2, "rolled_back"), body)
        self.assertNotIn("rollbackNote", body)
        self.assertEqual(got["stack"], ["earlier"])


# ---- #8: the hold -----------------------------------------------------------------------------

class Obj:
    def __init__(self, name, type_id="Part::Feature", parent=None, deps=()):
        self.Name = self.Label = name
        self.TypeId = type_id
        self.parent = parent
        self.OutListRecursive = list(deps)

    def getParentGeoFeatureGroup(self):
        return self.parent


class FDoc:
    def __init__(self, name, objs):
        self.Name = self.Label = name
        self.Objects = objs

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


class GuiDoc:
    def __init__(self, doc, edit=None):
        self.Document = doc
        self.edit = edit

    def getInEdit(self):
        return None if self.edit is None else types.SimpleNamespace(Object=self.edit)


class Control:
    def __init__(self, open_=False, alters=False):
        self.open_, self.alters = open_, alters

    def activeDialog(self):
        return self.open_

    def isAllowedAlterDocument(self):
        return self.alters


def gui(gd, control=None):
    return types.SimpleNamespace(ActiveDocument=gd, editDocument=lambda: gd if gd is not None and gd.getInEdit() is not None else None,
                                 Control=control or Control())


def change_tool(name="sketch_add_line"):
    return Tool(name, "A change.", {"type": "object", "properties": {}}, lambda a: {"ok": True}, changes=True)


class Hold(unittest.TestCase):
    def setUp(self):
        self.body = Obj("Body", "PartDesign::Body")
        self.sketch = Obj("Sketch", "Sketcher::SketchObject", parent=self.body)
        self.pad = Obj("Pad", "PartDesign::Pad", parent=self.body, deps=[self.sketch])
        self.body2 = Obj("Body001", "PartDesign::Body")
        self.sk2 = Obj("Sketch001", "Sketcher::SketchObject", parent=self.body2)
        self.doc = FDoc("Model", [self.body, self.sketch, self.pad, self.body2, self.sk2])
        self.s = types.SimpleNamespace(doc=self.doc)
        self.g = gui(GuiDoc(self.doc, edit=self.sketch), Control(True, False))

    def said(self, args, tool=None, g=None, mine=()):
        return coedit.refusal(tool or change_tool(), args, self.s, gui=g or self.g, mine=set(mine))

    def test_same_body_is_held(self):
        w = self.said({"sketch": "Sketch"})
        self.assertIn("Held: the person is editing Sketch in Body in Model", w)
        self.assertIn("closes the task panel", w)
        self.assertTrue(self.said({"feature": "Pad"}))  # another feature of the same body
        self.assertTrue(self.said({"object": "Body"}))

    def test_other_body_goes_on(self):
        self.assertIsNone(self.said({"sketch": "Sketch001"}))
        self.assertIsNone(self.said({"refs": [{"object": "Body001", "sub": "Face1"}]}))

    def test_unknown_target_holds_only_in_the_same_document(self):
        self.assertTrue(self.said({}))
        self.assertTrue(self.said({"name": "NewThing"}))
        other = types.SimpleNamespace(doc=FDoc("Other", []))
        self.assertIsNone(coedit.refusal(change_tool(), {}, other, gui=self.g, mine=set()))

    def test_reads_and_flows_go_on(self):
        read = Tool("sketch_state", "A read.", {"type": "object", "properties": {}}, lambda a: {})
        self.assertIsNone(self.said({"sketch": "Sketch"}, tool=read))
        for n in ("gui_input", "dialog_answer", "cmd_run", "menu_run", "app_force_restart", "batch", "doc_new"):
            self.assertIsNone(self.said({"sketch": "Sketch"}, tool=change_tool(n)), n)

    def test_the_agents_own_edit_is_not_held(self):
        self.assertIsNone(self.said({"sketch": "Sketch"}, mine={("Model", "Sketch")}))

    def test_a_task_panel_with_no_edit(self):
        g = gui(GuiDoc(self.doc), Control(True, False))
        w = self.said({"sketch": "Sketch001"}, g=g)
        self.assertIn("a task panel is open in Model", w)
        g_ok = gui(GuiDoc(self.doc), Control(True, True))
        self.assertIsNone(self.said({}, g=g_ok))
        self.assertIsNone(self.said({}, g=gui(GuiDoc(self.doc), Control(False))))

    def test_part_objects_built_from_one_another(self):
        box = Obj("Box")
        cut = Obj("Cut", deps=[box])
        lone = Obj("Cyl")
        self.s.doc = FDoc("Model", [box, cut, lone])
        g = gui(GuiDoc(self.s.doc, edit=box), Control(True, True))
        self.assertTrue(self.said({"object": "Cut"}, g=g))
        self.assertIsNone(self.said({"object": "Cyl"}, g=g))

    def test_headless_holds_nothing(self):
        was = coedit._gui
        coedit._gui = lambda: None
        try:
            self.assertIsNone(coedit.refusal(change_tool(), {"sketch": "Sketch"}, self.s))
            self.assertIsNone(coedit.check(change_tool(), {"sketch": "Sketch"}, self.s))
        finally:
            coedit._gui = was

    def test_an_edit_opened_during_an_agent_call_is_the_agents(self):
        g = gui(GuiDoc(self.doc), Control(False))
        before = coedit.edit_key(g)
        g.ActiveDocument.edit = self.sketch  # a cmd_run opened the sketch
        coedit.settle(before, g)
        try:
            self.assertIn(("Model", "Sketch"), coedit._opened)
            self.assertIsNone(coedit.refusal(change_tool(), {"sketch": "Sketch"}, self.s, gui=g))
            g.ActiveDocument.edit = None  # closed: no longer kept
            coedit.settle(None, g)
            self.assertNotIn(("Model", "Sketch"), coedit._opened)
        finally:
            coedit._opened.clear()

    def test_through_the_server(self):
        ran = []
        t = Tool("sketch_add_line", "A change.", {"type": "object", "properties": {"sketch": {"type": "string"}}},
                 lambda a: ran.append(1) or {"ok": True}, changes=True)
        srv = Server("t", "1", [t])
        srv.session = self.s
        was = coedit._gui
        coedit._gui = lambda: self.g
        try:
            r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "sketch_add_line", "arguments": {"sketch": "Sketch"}}})
            err = json.loads(r["result"]["content"][0]["text"])["error"]
            self.assertEqual((err["code"], err["outcome"]), ("held_person_editing", "not_started"))
            self.assertEqual(ran, [])
            r = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "sketch_add_line", "arguments": {"sketch": "Sketch001"}}})
            self.assertFalse(r["result"].get("isError"), r)
            self.assertEqual(ran, [1])
        finally:
            coedit._gui = was
            coedit._opened.clear()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "child":
        print(json.dumps(_child(sys.argv[2]), default=str))
    else:
        unittest.main()
